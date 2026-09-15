import { NanoCoopSmsBridge } from '../src/index';
import { MockSmsReceiver } from '../src/receiver/receiver';
import { StoreAndForwardQueue } from '../src/queue/storeAndForward';
import { GatewayHttpClient } from '../src/network/client';

describe('NanoCoopSmsBridge End-to-End Bridge Flow', () => {
  let receiver: MockSmsReceiver;
  let queue: StoreAndForwardQueue;
  let client: GatewayHttpClient;
  let bridge: NanoCoopSmsBridge;

  const mockUserKey = 'e'.repeat(64);

  beforeEach(() => {
    receiver = new MockSmsReceiver();
    queue = new StoreAndForwardQueue();
    client = new GatewayHttpClient({ baseUrl: 'http://mock-core' });

    bridge = new NanoCoopSmsBridge({
      smsSource: receiver,
      queue,
      httpClient: client,
      phoneToUserMap: {
        '+254712345678': mockUserKey,
      },
    });
  });

  afterEach(() => {
    bridge.stop();
  });

  it('receives mock SMS, parses, queues, and posts to core gateway successfully', async () => {
    // Mock the HTTP client postReceipt
    const postSpy = jest.spyOn(client, 'postReceipt').mockResolvedValue({
      status: 'SUCCESS',
      message: 'Credited',
      event_id: 'ev-123',
      transaction_hash: 'tx-hash-1',
    });

    bridge.start();

    const smsText = 'QA12BC34DE Confirmed. You have received USD 100.00 from John Doe 254712345678';
    await receiver.simulateIncomingSms('+254712345678', smsText);

    expect(postSpy).toHaveBeenCalledTimes(1);
    const postCallArg = postSpy.mock.calls[0][0];
    expect(postCallArg.receipt.transactionCode).toBe('QA12BC34DE');
    expect(postCallArg.receipt.amount).toBe(100.0);
    expect(postCallArg.userPublicKey).toBe(mockUserKey);

    const allQueued = await queue.getAll();
    expect(allQueued.length).toBe(1);
    expect(allQueued[0].status).toBe('COMPLETED');
  });

  it('handles offline core backend by scheduling retry with backoff', async () => {
    // Mock network failure on first attempt
    const postSpy = jest
      .spyOn(client, 'postReceipt')
      .mockRejectedValueOnce(new Error('Connection refused'))
      .mockResolvedValueOnce({
        status: 'SUCCESS',
        message: 'Credited on retry',
        transaction_hash: 'tx-hash-2',
      });

    bridge.start();

    const smsText = 'Confirmed: You received $25 from +254712345678';
    await receiver.simulateIncomingSms('+254712345678', smsText);

    // Initial attempt failed, queued item should be pending with attempt = 1
    const queuedItems = await queue.getAll();
    expect(queuedItems.length).toBe(1);
    expect(queuedItems[0].attempts).toBe(1);
    expect(queuedItems[0].status).toBe('PENDING');

    // Simulate time forward for next attempt
    queuedItems[0].nextAttemptAt = Date.now() - 10;
    await queue.enqueue(queuedItems[0]);

    // Flush retry
    const flushRes = await bridge.flushQueue();
    expect(flushRes.successful).toBe(1);

    const afterRetry = await queue.getAll();
    expect(afterRetry[0].status).toBe('COMPLETED');
  });
});
