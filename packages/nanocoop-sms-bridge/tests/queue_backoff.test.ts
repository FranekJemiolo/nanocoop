import { StoreAndForwardQueue, QueuedTransaction } from '../src/queue/storeAndForward';
import { GatewayHttpClient } from '../src/network/client';

describe('StoreAndForwardQueue & Exponential Backoff', () => {
  it('stores, queries, and completes queued transactions', async () => {
    const queue = new StoreAndForwardQueue();
    const item: QueuedTransaction = {
      id: 'tx_1',
      receipt: {
        transactionCode: 'MOCK1',
        amount: 50,
        currency: 'USD',
        senderPhone: '+254711000000',
        timestamp: 1000,
        provider: 'MPESA',
        rawMessage: 'MOCK1 Confirmed',
      },
      userPublicKey: 'a'.repeat(64),
      attempts: 0,
      nextAttemptAt: 1000,
      status: 'PENDING',
      createdAt: 1000,
    };

    await queue.enqueue(item);
    const pending = await queue.getPendingBatch(1500, 10);
    expect(pending.length).toBe(1);
    expect(pending[0].id).toBe('tx_1');

    await queue.markSuccess('tx_1');
    const afterSuccess = await queue.getPendingBatch(1500, 10);
    expect(afterSuccess.length).toBe(0);

    const all = await queue.getAll();
    expect(all[0].status).toBe('COMPLETED');
  });

  it('calculates exponential backoff intervals with jitter', () => {
    const client = new GatewayHttpClient({
      baseUrl: 'http://localhost:8000',
      initialBackoffMs: 1000,
      maxBackoffMs: 10000,
      backoffFactor: 2.0,
    });

    const now = 1000000;
    const backoff1 = client.calculateNextBackoff(0, now);
    // attempt 0: delay between 1000 and 1500
    expect(backoff1).toBeGreaterThanOrEqual(now + 1000);
    expect(backoff1).toBeLessThanOrEqual(now + 1500);

    const backoff2 = client.calculateNextBackoff(1, now);
    // attempt 1: delay between 2000 and 2500
    expect(backoff2).toBeGreaterThanOrEqual(now + 2000);
    expect(backoff2).toBeLessThanOrEqual(now + 2500);

    const backoffMax = client.calculateNextBackoff(10, now);
    // capped at maxBackoffMs
    expect(backoffMax).toBeLessThanOrEqual(now + 10000);
  });
});
