import { ParsedSmsReceipt } from '../receiver/parser';

export type QueueItemStatus = 'PENDING' | 'IN_FLIGHT' | 'COMPLETED' | 'FAILED';

export interface QueuedTransaction {
  id: string;
  receipt: ParsedSmsReceipt;
  userPublicKey: string;
  attempts: number;
  nextAttemptAt: number;
  status: QueueItemStatus;
  createdAt: number;
  lastError?: string;
}

export interface IQueueStorage {
  enqueue(item: QueuedTransaction): Promise<void>;
  peekPending(now: number): Promise<QueuedTransaction | null>;
  getPendingBatch(now: number, limit: number): Promise<QueuedTransaction[]>;
  markSuccess(id: string): Promise<void>;
  markRetry(id: string, nextAttemptAt: number, error: string): Promise<void>;
  markFailed(id: string, error: string): Promise<void>;
  getAll(): Promise<QueuedTransaction[]>;
  clear(): Promise<void>;
}

/**
 * In-memory / Durable store-and-forward queue implementation for offline resilience.
 * Stores receipts when Python FastAPI backend is unreachable and handles retry scheduling.
 */
export class StoreAndForwardQueue implements IQueueStorage {
  private items: Map<string, QueuedTransaction> = new Map();

  public async enqueue(item: QueuedTransaction): Promise<void> {
    this.items.set(item.id, { ...item });
  }

  public async peekPending(now: number): Promise<QueuedTransaction | null> {
    for (const item of this.items.values()) {
      if ((item.status === 'PENDING' || item.status === 'IN_FLIGHT') && item.nextAttemptAt <= now) {
        return { ...item };
      }
    }
    return null;
  }

  public async getPendingBatch(now: number, limit: number = 10): Promise<QueuedTransaction[]> {
    const pending: QueuedTransaction[] = [];
    for (const item of this.items.values()) {
      if (item.status === 'PENDING' && item.nextAttemptAt <= now) {
        pending.push({ ...item });
        if (pending.length >= limit) break;
      }
    }
    return pending;
  }

  public async markSuccess(id: string): Promise<void> {
    const item = this.items.get(id);
    if (item) {
      item.status = 'COMPLETED';
      this.items.set(id, item);
    }
  }

  public async markRetry(id: string, nextAttemptAt: number, error: string): Promise<void> {
    const item = this.items.get(id);
    if (item) {
      item.attempts += 1;
      item.nextAttemptAt = nextAttemptAt;
      item.status = 'PENDING';
      item.lastError = error;
      this.items.set(id, item);
    }
  }

  public async markFailed(id: string, error: string): Promise<void> {
    const item = this.items.get(id);
    if (item) {
      item.status = 'FAILED';
      item.lastError = error;
      this.items.set(id, item);
    }
  }

  public async getAll(): Promise<QueuedTransaction[]> {
    return Array.from(this.items.values());
  }

  public async clear(): Promise<void> {
    this.items.clear();
  }
}
