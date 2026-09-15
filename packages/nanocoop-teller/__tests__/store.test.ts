import { useLedgerStore } from '../src/store/useLedgerStore';
import { generateKeyPair } from '../src/utils/crypto';

describe('useLedgerStore Offline Multi-Sig Flow', () => {
  beforeEach(async () => {
    // Reset Zustand store state
    useLedgerStore.setState({
      events: [],
      pendingQueue: [],
      isOnline: false, // Start in offline mode to test offline queueing
      communityStats: null,
      tellerKeyPair: generateKeyPair(),
    });
  });

  it('queues signed transactions locally when offline', async () => {
    const userPair = generateKeyPair();
    const store = useLedgerStore.getState();

    const result = await store.submitTransaction({
      amount: 45.0,
      currency: 'USD',
      userPublicKey: userPair.publicKeyHex,
      eventType: 'DEPOSIT_CASH',
      userPrivateKeyHex: userPair.privateKeyHex,
      notes: 'Offline VSLA contribution',
    });

    expect(result.isQueued).toBe(true);
    expect(result.event.signatures.teller_sig).toBeDefined();
    expect(result.event.signatures.user_sig).toBeDefined();

    const updatedState = useLedgerStore.getState();
    expect(updatedState.pendingQueue.length).toBe(1);
    expect(updatedState.pendingQueue[0].event_id).toBe(result.event.event_id);
  });
});
