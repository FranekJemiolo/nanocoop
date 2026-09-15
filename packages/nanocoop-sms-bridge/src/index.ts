import { TelecomSmsParser, ParsedSmsReceipt } from './receiver/parser';
import { ISmsSource, MockSmsReceiver } from './receiver/receiver';
import { IQueueStorage, QueuedTransaction, StoreAndForwardQueue } from './queue/storeAndForward';
import { GatewayHttpClient, WebhookResponse } from './network/client';

export interface BridgeOptions {
  smsSource?: ISmsSource;
  queue?: IQueueStorage;
  httpClient?: GatewayHttpClient;
  coreBaseUrl?: string;
  phoneToUserMap?: Record<string, string>;
}

export class NanoCoopSmsBridge {
  public readonly smsSource: ISmsSource;
  public readonly queue: IQueueStorage;
  public readonly httpClient: GatewayHttpClient;
  private phoneToUserMap: Map<string, string>;
  private isRunning: boolean = false;
  private syncTimer: NodeJS.Timeout | null = null;

  constructor(options: BridgeOptions = {}) {
    this.smsSource = options.smsSource ?? new MockSmsReceiver();
    this.queue = options.queue ?? new StoreAndForwardQueue();
    this.httpClient =
      options.httpClient ??
      new GatewayHttpClient({
        baseUrl: options.coreBaseUrl ?? 'http://localhost:8000',
      });

    this.phoneToUserMap = new Map(Object.entries(options.phoneToUserMap ?? {}));

    // Register SMS handler
    this.smsSource.registerHandler(this.handleIncomingSms.bind(this));
  }

  public registerMemberPhone(phone: string, userPublicKey: string): void {
    const formatted = phone.startsWith('+') ? phone : `+${phone}`;
    this.phoneToUserMap.set(formatted, userPublicKey);
  }

  public start(): void {
    if (this.isRunning) return;
    this.isRunning = true;
    this.smsSource.startListening();
    this.scheduleSyncLoop(2000);
  }

  public stop(): void {
    this.isRunning = false;
    this.smsSource.stopListening();
    if (this.syncTimer) {
      clearTimeout(this.syncTimer);
      this.syncTimer = null;
    }
  }

  /**
   * Handler invoked whenever an SMS is received from cellular provider.
   */
  public async handleIncomingSms(
    sender: string,
    message: string,
    timestamp: number = Date.now()
  ): Promise<QueuedTransaction | null> {
    const receipt = TelecomSmsParser.parse(message, timestamp);
    if (!receipt) {
      return null;
    }

    // Determine target cooperative member from sender phone or receipt phone
    const targetUser =
      this.phoneToUserMap.get(receipt.senderPhone) ||
      this.phoneToUserMap.get(sender.startsWith('+') ? sender : `+${sender}`) ||
      '0'.repeat(64); // Fallback to cooperative general suspense account

    const queuedItem: QueuedTransaction = {
      id: `q_${receipt.transactionCode}_${Date.now()}`,
      receipt,
      userPublicKey: targetUser,
      attempts: 0,
      nextAttemptAt: Date.now(),
      status: 'PENDING',
      createdAt: Date.now(),
    };

    await this.queue.enqueue(queuedItem);
    // Trigger immediate queue processing attempt
    await this.flushQueue();
    return queuedItem;
  }

  /**
   * Process all pending items currently scheduled for attempt.
   */
  public async flushQueue(): Promise<{ processed: number; successful: number; failed: number }> {
    const now = Date.now();
    const batch = await this.queue.getPendingBatch(now, 10);

    let successful = 0;
    let failed = 0;

    for (const item of batch) {
      try {
        const res: WebhookResponse = await this.httpClient.postReceipt(item);
        if (res.status === 'SUCCESS' || res.status === 'DROPPED') {
          await this.queue.markSuccess(item.id);
          successful++;
        }
      } catch (err: any) {
        failed++;
        const nextAttempts = item.attempts + 1;
        if (this.httpClient.shouldRetry(nextAttempts)) {
          const nextAttemptAt = this.httpClient.calculateNextBackoff(nextAttempts, Date.now());
          await this.queue.markRetry(item.id, nextAttemptAt, err?.message || 'Network error');
        } else {
          await this.queue.markFailed(item.id, `Max retries exceeded: ${err?.message}`);
        }
      }
    }

    return { processed: batch.length, successful, failed };
  }

  private scheduleSyncLoop(intervalMs: number): void {
    if (!this.isRunning) return;
    this.syncTimer = setTimeout(async () => {
      try {
        await this.flushQueue();
      } catch {
        // Ignore loop transient errors
      } finally {
        if (this.isRunning) {
          this.scheduleSyncLoop(intervalMs);
        }
      }
    }, intervalMs);
  }
}

export * from './receiver/parser';
export * from './receiver/receiver';
export * from './queue/storeAndForward';
export * from './network/client';
