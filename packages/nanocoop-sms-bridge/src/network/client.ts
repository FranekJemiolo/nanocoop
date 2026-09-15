import { QueuedTransaction } from '../queue/storeAndForward';

export interface HttpClientConfig {
  baseUrl: string;
  initialBackoffMs?: number;
  maxBackoffMs?: number;
  backoffFactor?: number;
  maxRetries?: number;
  timeoutMs?: number;
}

export interface WebhookResponse {
  status: 'SUCCESS' | 'DROPPED';
  message: string;
  event_id?: string;
  transaction_hash: string;
}

export class GatewayHttpClient {
  private baseUrl: string;
  private initialBackoffMs: number;
  private maxBackoffMs: number;
  private backoffFactor: number;
  private maxRetries: number;
  private timeoutMs: number;

  constructor(config: HttpClientConfig) {
    this.baseUrl = config.baseUrl.replace(/\/+$/, '');
    this.initialBackoffMs = config.initialBackoffMs ?? 1000;
    this.maxBackoffMs = config.maxBackoffMs ?? 30000;
    this.backoffFactor = config.backoffFactor ?? 2.0;
    this.maxRetries = config.maxRetries ?? 5;
    this.timeoutMs = config.timeoutMs ?? 5000;
  }

  /**
   * Calculate next exponential backoff timestamp with random jitter to prevent thundering herd.
   */
  public calculateNextBackoff(attempts: number, now: number = Date.now()): number {
    const exponent = Math.min(attempts, 8);
    const baseDelay = this.initialBackoffMs * Math.pow(this.backoffFactor, exponent);
    const jitter = Math.floor(Math.random() * (this.initialBackoffMs * 0.5));
    const delay = Math.min(this.maxBackoffMs, baseDelay + jitter);
    return now + delay;
  }

  public shouldRetry(attempts: number): boolean {
    return attempts < this.maxRetries;
  }

  /**
   * Post queued mobile money receipt to FastAPI backend webhook.
   */
  public async postReceipt(item: QueuedTransaction): Promise<WebhookResponse> {
    const url = `${this.baseUrl}/api/v1/sms/webhook`;
    const body = {
      transaction_code: item.receipt.transactionCode,
      sender_phone: item.receipt.senderPhone,
      amount: item.receipt.amount,
      currency: item.receipt.currency,
      user_public_key: item.userPublicKey,
      timestamp: Math.floor(item.receipt.timestamp / 1000),
      gateway_signature: '00'.repeat(32), // In production, signed by Gateway private key
    };

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
        body: JSON.stringify(body),
        signal: controller.signal,
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`HTTP error ${response.status}: ${errorText}`);
      }

      return (await response.json()) as WebhookResponse;
    } finally {
      clearTimeout(timer);
    }
  }
}
