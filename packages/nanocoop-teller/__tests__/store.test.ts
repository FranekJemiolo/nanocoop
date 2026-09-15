import { useLedgerStore } from '../src/store/useLedgerStore';
import { generateKeyPair } from '../src/utils/crypto';

describe('useLedgerStore Offline Multi-Sig Flow', () => {
  beforeEach(async () => {
    // Reset Zustand store state
    useLedgerStore.setState({
      events: [],
      pendingQueue: [],
      isOnline: false, // Start in offline mode to test offline queueing
      isDemoMode: false,
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

  it('handles VSLA loan disbursement and repayment in demo mode', async () => {
    useLedgerStore.setState({
      isDemoMode: true,
      events: [],
      accounts: {},
      tellerKeyPair: generateKeyPair(),
    });

    const borrower = generateKeyPair();
    const store = useLedgerStore.getState();

    // 1. Disburse loan
    const loanEv = await store.disburseLoan({
      amount: 200.0,
      borrowerPublicKey: borrower.publicKeyHex,
      borrowerPrivateKeyHex: borrower.privateKeyHex,
      interestRate: 10.0,
      termMonths: 3,
    });
    expect(loanEv.event_type).toBe('LOAN_DISBURSED');
    expect(useLedgerStore.getState().accounts[borrower.publicKeyHex].loan_balance).toBe(220.0);

    // 2. Repay loan
    const repayEv = await store.repayLoan({
      amount: 120.0,
      borrowerPublicKey: borrower.publicKeyHex,
      borrowerPrivateKeyHex: borrower.privateKeyHex,
    });
    expect(repayEv.event_type).toBe('LOAN_REPAID');
    expect(useLedgerStore.getState().accounts[borrower.publicKeyHex].loan_balance).toBe(100.0);

    // 3. Social fund contribution
    const welfEv = await store.contributeSocialFund({
      amount: 15.0,
      memberPublicKey: borrower.publicKeyHex,
      memberPrivateKeyHex: borrower.privateKeyHex,
    });
    expect(welfEv.event_type).toBe('SOCIAL_FUND_CONTRIBUTION');
    expect(useLedgerStore.getState().communityStats?.total_social_fund).toBe(35.0); // 20 initial + 15
  });
});
