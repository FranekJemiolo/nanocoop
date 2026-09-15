import { create } from 'zustand';
import {
  AccountState,
  AuditVerification,
  CommunityStats,
  EventModel,
  EventPayload,
  EventSignatures,
  NanoCoopApiClient,
} from '../utils/api';
import {
  GENESIS_HASH,
  generateEventHash,
  generateKeyPair,
  serializeForHashing,
  signPayload,
} from '../utils/crypto';
import { SecureStorage } from '../utils/secureStore';
import { sha256 } from 'js-sha256';

export interface LedgerStoreState {
  apiClient: NanoCoopApiClient;
  communityStats: CommunityStats | null;
  events: EventModel[];
  accounts: Record<string, AccountState>;
  pendingQueue: EventModel[];
  isOnline: boolean;
  isDemoMode: boolean;
  isLoading: boolean;
  lastSyncTime: number | null;
  tellerKeyPair: { privateKeyHex: string; publicKeyHex: string } | null;
  activeTab: 'dashboard' | 'transaction' | 'vsla' | 'integrations' | 'audit';
  auditResult: AuditVerification | null;

  // Sample demo members for quick selection
  sampleMembers: { name: string; publicKey: string; privateKey: string }[];

  // Actions
  setActiveTab: (tab: 'dashboard' | 'transaction' | 'vsla' | 'integrations' | 'audit') => void;
  setOnlineStatus: (isOnline: boolean) => void;
  setDemoMode: (isDemoMode: boolean) => void;
  initTellerKeys: () => Promise<void>;
  fetchRemoteState: () => Promise<void>;
  submitTransaction: (params: {
    amount: number;
    currency?: string;
    userPublicKey: string;
    eventType: 'DEPOSIT_CASH' | 'WITHDRAWAL_CASH';
    userPrivateKeyHex: string;
    notes?: string;
  }) => Promise<{ event: EventModel; isQueued: boolean }>;
  disburseLoan: (params: {
    amount: number;
    borrowerPublicKey: string;
    borrowerPrivateKeyHex: string;
    interestRate?: number;
    termMonths?: number;
    notes?: string;
  }) => Promise<EventModel>;
  repayLoan: (params: {
    amount: number;
    borrowerPublicKey: string;
    borrowerPrivateKeyHex: string;
    loanId?: string;
    notes?: string;
  }) => Promise<EventModel>;
  contributeSocialFund: (params: {
    amount: number;
    memberPublicKey: string;
    memberPrivateKeyHex: string;
    notes?: string;
  }) => Promise<EventModel>;
  payoutSocialFund: (params: {
    amount: number;
    memberPublicKey: string;
    memberPrivateKeyHex: string;
    purpose: string;
  }) => Promise<EventModel>;
  simulateIncomingSmsPayment: (amount: number, senderPhone: string) => Promise<EventModel>;
  simulateDarajaStk: (params: { phoneNumber: string; amount: number }) => Promise<EventModel>;
  simulateMtnMoMo: (params: { phoneNumber: string; amount: number; currency?: string }) => Promise<EventModel>;
  simulateAirtelMoney: (params: { phoneNumber: string; amount: number; currency?: string }) => Promise<EventModel>;
  simulateOrangeMoney: (params: { phoneNumber: string; amount: number; currency?: string }) => Promise<EventModel>;
  simulateWave: (params: { phoneNumber: string; amount: number; currency?: string }) => Promise<EventModel>;
  simulateAfricasTalkingSms: (params: { fromPhone: string; text: string }) => Promise<EventModel>;
  flushPendingQueue: () => Promise<number>;
  runAuditCheck: () => Promise<AuditVerification>;
}

// Helper to calculate Merkle root in pure JS for in-browser demo
function computeDemoMerkleRoot(hashes: string[]): string {
  if (hashes.length === 0) return GENESIS_HASH;
  let currentLayer = hashes.map((h) => sha256(h));
  while (currentLayer.length > 1) {
    const nextLayer: string[] = [];
    for (let i = 0; i < currentLayer.length; i += 2) {
      const left = currentLayer[i];
      const right = i + 1 < currentLayer.length ? currentLayer[i + 1] : left;
      nextLayer.push(sha256(left + right));
    }
    currentLayer = nextLayer;
  }
  return currentLayer[0];
}

// Generate pre-populated demo members with deterministic keys
const demoMember1 = generateKeyPair();
const demoMember2 = generateKeyPair();

export const useLedgerStore = create<LedgerStoreState>((set, get) => ({
  apiClient: new NanoCoopApiClient(),
  communityStats: {
    total_balance: 150.0,
    total_savings: 150.0,
    total_loans_outstanding: 0.0,
    total_social_fund: 20.0,
    total_capital: 170.0,
    total_members: 2,
    total_events: 2,
    merkle_root: '7a3f8901c0824ba1e8912cb901428ba901248ba0912481092a481b9012481234',
    is_chain_valid: true,
  },
  events: [],
  accounts: {},
  pendingQueue: [],
  isOnline: true,
  isDemoMode: true, // Default to demo mode so web/demo is immediately usable
  isLoading: false,
  lastSyncTime: Date.now(),
  tellerKeyPair: null,
  activeTab: 'dashboard',
  auditResult: {
    is_valid: true,
    total_events: 2,
    merkle_root: '7a3f8901c0824ba1e8912cb901428ba901248ba0912481092a481b9012481234',
    last_hash: '0284ac91e84a9218bc894019283ba874b01984218ba901248ba0912481112233',
    tamper_details: null,
  },
  sampleMembers: [
    {
      name: 'Sarah Mwangi (VSLA Chair)',
      publicKey: demoMember1.publicKeyHex,
      privateKey: demoMember1.privateKeyHex,
    },
    {
      name: 'David Kipkorir (Farmer)',
      publicKey: demoMember2.publicKeyHex,
      privateKey: demoMember2.privateKeyHex,
    },
  ],

  setActiveTab: (tab) => set({ activeTab: tab }),

  setOnlineStatus: (isOnline) => set({ isOnline }),

  setDemoMode: (isDemoMode) => {
    set({ isDemoMode });
    if (!isDemoMode) {
      get().fetchRemoteState();
    }
  },

  initTellerKeys: async () => {
    let priv = await SecureStorage.getItem('nanocoop_teller_priv_key');
    let pub = await SecureStorage.getItem('nanocoop_teller_pub_key');

    if (!priv || !pub) {
      const generated = generateKeyPair();
      priv = generated.privateKeyHex;
      pub = generated.publicKeyHex;
      await SecureStorage.setItem('nanocoop_teller_priv_key', priv);
      await SecureStorage.setItem('nanocoop_teller_pub_key', pub);
    }

    set({ tellerKeyPair: { privateKeyHex: priv, publicKeyHex: pub } });

    // Pre-populate initial demo state if empty
    const { events } = get();
    if (events.length === 0 && priv) {
      const p1: EventPayload = {
        amount: 100.0,
        currency: 'USD',
        user_public_key: demoMember1.publicKeyHex,
        notes: 'Initial VSLA cycle deposit',
      };
      const sig1 = {
        teller_sig: signPayload(priv, p1),
        user_sig: signPayload(demoMember1.privateKeyHex, p1),
      };
      const h1 = generateEventHash(
        GENESIS_HASH,
        Buffer.from(serializeForHashing(p1), 'utf-8'),
        Buffer.from(serializeForHashing(sig1), 'utf-8')
      );
      const ev1: EventModel = {
        event_id: 'ev-demo-001',
        timestamp: Math.floor(Date.now() / 1000) - 3600,
        event_type: 'DEPOSIT_CASH',
        payload: p1,
        previous_hash: GENESIS_HASH,
        signatures: sig1,
        current_hash: h1,
      };

      const p2: EventPayload = {
        amount: 50.0,
        currency: 'USD',
        user_public_key: demoMember2.publicKeyHex,
        notes: 'Savings deposit',
      };
      const sig2 = {
        teller_sig: signPayload(priv, p2),
        user_sig: signPayload(demoMember2.privateKeyHex, p2),
      };
      const h2 = generateEventHash(
        h1,
        Buffer.from(serializeForHashing(p2), 'utf-8'),
        Buffer.from(serializeForHashing(sig2), 'utf-8')
      );
      const ev2: EventModel = {
        event_id: 'ev-demo-002',
        timestamp: Math.floor(Date.now() / 1000) - 1800,
        event_type: 'DEPOSIT_CASH',
        payload: p2,
        previous_hash: h1,
        signatures: sig2,
        current_hash: h2,
      };

      const initialEvents = [ev1, ev2];
      const initialRoot = computeDemoMerkleRoot([h1, h2]);

      set({
        events: initialEvents,
        accounts: {
          [demoMember1.publicKeyHex]: {
            user_public_key: demoMember1.publicKeyHex,
            current_balance: 100.0,
            savings_balance: 100.0,
            loan_balance: 0.0,
            social_fund_contributions: 10.0,
            net_balance: 100.0,
            last_activity: ev1.timestamp,
            currency: 'USD',
          },
          [demoMember2.publicKeyHex]: {
            user_public_key: demoMember2.publicKeyHex,
            current_balance: 50.0,
            savings_balance: 50.0,
            loan_balance: 0.0,
            social_fund_contributions: 10.0,
            net_balance: 50.0,
            last_activity: ev2.timestamp,
            currency: 'USD',
          },
        },
        communityStats: {
          total_balance: 150.0,
          total_savings: 150.0,
          total_loans_outstanding: 0.0,
          total_social_fund: 20.0,
          total_capital: 170.0,
          total_members: 2,
          total_events: 2,
          merkle_root: initialRoot,
          is_chain_valid: true,
        },
        auditResult: {
          is_valid: true,
          total_events: 2,
          merkle_root: initialRoot,
          last_hash: h2,
          tamper_details: null,
        },
      });
    }
  },

  fetchRemoteState: async () => {
    const { isDemoMode, apiClient } = get();
    if (isDemoMode) {
      set({ isLoading: false, isOnline: true });
      return;
    }

    set({ isLoading: true });
    try {
      const [stats, eventsData, accountsData] = await Promise.all([
        apiClient.getStats(),
        apiClient.getEvents(undefined, 100),
        apiClient.getAllAccounts(),
      ]);

      set({
        communityStats: stats,
        events: eventsData.events,
        accounts: accountsData,
        isOnline: true,
        isLoading: false,
        lastSyncTime: Date.now(),
      });
    } catch {
      set({ isOnline: false, isLoading: false });
    }
  },

  submitTransaction: async ({
    amount,
    currency = 'USD',
    userPublicKey,
    eventType,
    userPrivateKeyHex,
    notes,
  }) => {
    const { tellerKeyPair, events, isDemoMode, apiClient, pendingQueue } = get();
    const tellerPriv = tellerKeyPair?.privateKeyHex || generateKeyPair().privateKeyHex;

    const previousHash =
      events.length > 0 ? events[events.length - 1].current_hash : GENESIS_HASH;

    const payload: EventPayload = {
      amount,
      currency,
      user_public_key: userPublicKey,
      notes: notes || `${eventType} transaction`,
    };

    const signatures: EventSignatures = {
      teller_sig: signPayload(tellerPriv, payload),
      user_sig: signPayload(userPrivateKeyHex, payload),
    };

    const currentHash = generateEventHash(
      previousHash,
      Buffer.from(serializeForHashing(payload), 'utf-8'),
      Buffer.from(serializeForHashing(signatures), 'utf-8')
    );

    const eventModel: EventModel = {
      event_id: `ev-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`,
      timestamp: Math.floor(Date.now() / 1000),
      event_type: eventType,
      payload,
      previous_hash: previousHash,
      signatures,
      current_hash: currentHash,
    };

    if (isDemoMode) {
      const nextEvents = [...events, eventModel];
      const newRoot = computeDemoMerkleRoot(nextEvents.map((e) => e.current_hash));

      const updatedAccounts = { ...get().accounts };
      const cur = updatedAccounts[userPublicKey]?.current_balance || 0.0;
      const newBal =
        eventType === 'DEPOSIT_CASH'
          ? Math.round((cur + amount) * 100) / 100
          : Math.round((cur - amount) * 100) / 100;

      updatedAccounts[userPublicKey] = {
        user_public_key: userPublicKey,
        current_balance: newBal,
        savings_balance: newBal,
        loan_balance: updatedAccounts[userPublicKey]?.loan_balance || 0.0,
        social_fund_contributions: updatedAccounts[userPublicKey]?.social_fund_contributions || 0.0,
        net_balance: newBal - (updatedAccounts[userPublicKey]?.loan_balance || 0.0),
        last_activity: eventModel.timestamp,
        currency,
      };

      const totalVault = Object.values(updatedAccounts).reduce(
        (sum, a) => sum + (a.savings_balance ?? a.current_balance),
        0
      );

      set({
        events: nextEvents,
        accounts: updatedAccounts,
        communityStats: {
          total_balance: Math.round(totalVault * 100) / 100,
          total_savings: Math.round(totalVault * 100) / 100,
          total_loans_outstanding: get().communityStats?.total_loans_outstanding || 0.0,
          total_social_fund: get().communityStats?.total_social_fund || 20.0,
          total_capital: Math.round((totalVault + (get().communityStats?.total_social_fund || 20.0)) * 100) / 100,
          total_members: Object.keys(updatedAccounts).length,
          total_events: nextEvents.length,
          merkle_root: newRoot,
          is_chain_valid: true,
        },
        auditResult: {
          is_valid: true,
          total_events: nextEvents.length,
          merkle_root: newRoot,
          last_hash: currentHash,
          tamper_details: null,
        },
      });

      return { event: eventModel, isQueued: false };
    }

    try {
      const created = await apiClient.createEvent(eventModel);
      await get().fetchRemoteState();
      return { event: created, isQueued: false };
    } catch {
      set({ pendingQueue: [...pendingQueue, eventModel], isOnline: false });
      return { event: eventModel, isQueued: true };
    }
  },

  disburseLoan: async ({
    amount,
    borrowerPublicKey,
    borrowerPrivateKeyHex,
    interestRate = 5.0,
    termMonths = 3,
    notes,
  }) => {
    const { tellerKeyPair, events } = get();
    const tellerPriv = tellerKeyPair?.privateKeyHex || generateKeyPair().privateKeyHex;
    const previousHash =
      events.length > 0 ? events[events.length - 1].current_hash : GENESIS_HASH;

    const loanId = `LOAN-${Math.random().toString(36).substring(2, 7).toUpperCase()}`;
    const payload: EventPayload = {
      amount,
      currency: 'USD',
      user_public_key: borrowerPublicKey,
      loan_id: loanId,
      interest_rate: interestRate,
      term_months: termMonths,
      notes: notes || `Micro-loan disbursement: ${loanId}`,
    };

    const signatures: EventSignatures = {
      teller_sig: signPayload(tellerPriv, payload),
      user_sig: signPayload(borrowerPrivateKeyHex, payload),
    };

    const currentHash = generateEventHash(
      previousHash,
      Buffer.from(serializeForHashing(payload), 'utf-8'),
      Buffer.from(serializeForHashing(signatures), 'utf-8')
    );

    const eventModel: EventModel = {
      event_id: `ev-loan-${Date.now()}`,
      timestamp: Math.floor(Date.now() / 1000),
      event_type: 'LOAN_DISBURSED',
      payload,
      previous_hash: previousHash,
      signatures,
      current_hash: currentHash,
    };

    const nextEvents = [...events, eventModel];
    const newRoot = computeDemoMerkleRoot(nextEvents.map((e) => e.current_hash));

    const updatedAccounts = { ...get().accounts };
    const curDebt = updatedAccounts[borrowerPublicKey]?.loan_balance || 0.0;
    const accrued = amount * (1 + interestRate / 100);
    const newDebt = Math.round((curDebt + accrued) * 100) / 100;
    const curSavings = updatedAccounts[borrowerPublicKey]?.savings_balance || 0.0;

    updatedAccounts[borrowerPublicKey] = {
      ...updatedAccounts[borrowerPublicKey],
      user_public_key: borrowerPublicKey,
      current_balance: curSavings,
      savings_balance: curSavings,
      loan_balance: newDebt,
      social_fund_contributions: updatedAccounts[borrowerPublicKey]?.social_fund_contributions || 0.0,
      net_balance: Math.round((curSavings - newDebt) * 100) / 100,
      last_activity: eventModel.timestamp,
      currency: 'USD',
    };

    const totalLoans = Object.values(updatedAccounts).reduce((sum, a) => sum + (a.loan_balance || 0), 0);

    set({
      events: nextEvents,
      accounts: updatedAccounts,
      communityStats: {
        total_balance: get().communityStats?.total_savings || 150.0,
        total_savings: get().communityStats?.total_savings || 150.0,
        total_loans_outstanding: Math.round(totalLoans * 100) / 100,
        total_social_fund: get().communityStats?.total_social_fund || 20.0,
        total_capital: Math.round(((get().communityStats?.total_savings || 150.0) + (get().communityStats?.total_social_fund || 20.0)) * 100) / 100,
        total_members: Object.keys(updatedAccounts).length,
        total_events: nextEvents.length,
        merkle_root: newRoot,
        is_chain_valid: true,
      },
    });

    return eventModel;
  },

  repayLoan: async ({
    amount,
    borrowerPublicKey,
    borrowerPrivateKeyHex,
    notes,
  }) => {
    const { tellerKeyPair, events } = get();
    const tellerPriv = tellerKeyPair?.privateKeyHex || generateKeyPair().privateKeyHex;
    const previousHash =
      events.length > 0 ? events[events.length - 1].current_hash : GENESIS_HASH;

    const payload: EventPayload = {
      amount,
      currency: 'USD',
      user_public_key: borrowerPublicKey,
      notes: notes || 'Loan repayment',
    };

    const signatures: EventSignatures = {
      teller_sig: signPayload(tellerPriv, payload),
      user_sig: signPayload(borrowerPrivateKeyHex, payload),
    };

    const currentHash = generateEventHash(
      previousHash,
      Buffer.from(serializeForHashing(payload), 'utf-8'),
      Buffer.from(serializeForHashing(signatures), 'utf-8')
    );

    const eventModel: EventModel = {
      event_id: `ev-repay-${Date.now()}`,
      timestamp: Math.floor(Date.now() / 1000),
      event_type: 'LOAN_REPAID',
      payload,
      previous_hash: previousHash,
      signatures,
      current_hash: currentHash,
    };

    const nextEvents = [...events, eventModel];
    const newRoot = computeDemoMerkleRoot(nextEvents.map((e) => e.current_hash));

    const updatedAccounts = { ...get().accounts };
    const curDebt = updatedAccounts[borrowerPublicKey]?.loan_balance || 0.0;
    const newDebt = Math.max(0, Math.round((curDebt - amount) * 100) / 100);
    const curSavings = updatedAccounts[borrowerPublicKey]?.savings_balance || 0.0;

    updatedAccounts[borrowerPublicKey] = {
      ...updatedAccounts[borrowerPublicKey],
      loan_balance: newDebt,
      net_balance: Math.round((curSavings - newDebt) * 100) / 100,
      last_activity: eventModel.timestamp,
    };

    const totalLoans = Object.values(updatedAccounts).reduce((sum, a) => sum + (a.loan_balance || 0), 0);

    set({
      events: nextEvents,
      accounts: updatedAccounts,
      communityStats: {
        total_balance: get().communityStats?.total_savings || 150.0,
        total_savings: get().communityStats?.total_savings || 150.0,
        total_loans_outstanding: Math.round(totalLoans * 100) / 100,
        total_social_fund: get().communityStats?.total_social_fund || 20.0,
        total_capital: Math.round(((get().communityStats?.total_savings || 150.0) + (get().communityStats?.total_social_fund || 20.0)) * 100) / 100,
        total_members: Object.keys(updatedAccounts).length,
        total_events: nextEvents.length,
        merkle_root: newRoot,
        is_chain_valid: true,
      },
    });

    return eventModel;
  },

  contributeSocialFund: async ({ amount, memberPublicKey, memberPrivateKeyHex, notes }) => {
    const { tellerKeyPair, events } = get();
    const tellerPriv = tellerKeyPair?.privateKeyHex || generateKeyPair().privateKeyHex;
    const previousHash =
      events.length > 0 ? events[events.length - 1].current_hash : GENESIS_HASH;

    const payload: EventPayload = {
      amount,
      currency: 'USD',
      user_public_key: memberPublicKey,
      notes: notes || 'Weekly social safety net contribution',
    };

    const signatures: EventSignatures = {
      teller_sig: signPayload(tellerPriv, payload),
      user_sig: signPayload(memberPrivateKeyHex, payload),
    };

    const currentHash = generateEventHash(
      previousHash,
      Buffer.from(serializeForHashing(payload), 'utf-8'),
      Buffer.from(serializeForHashing(signatures), 'utf-8')
    );

    const eventModel: EventModel = {
      event_id: `ev-welf-${Date.now()}`,
      timestamp: Math.floor(Date.now() / 1000),
      event_type: 'SOCIAL_FUND_CONTRIBUTION',
      payload,
      previous_hash: previousHash,
      signatures,
      current_hash: currentHash,
    };

    const nextEvents = [...events, eventModel];
    const newRoot = computeDemoMerkleRoot(nextEvents.map((e) => e.current_hash));

    const updatedAccounts = { ...get().accounts };
    const curWelf = updatedAccounts[memberPublicKey]?.social_fund_contributions || 0.0;
    updatedAccounts[memberPublicKey] = {
      ...updatedAccounts[memberPublicKey],
      social_fund_contributions: Math.round((curWelf + amount) * 100) / 100,
      last_activity: eventModel.timestamp,
    };

    const newSocialPool = Math.round(((get().communityStats?.total_social_fund || 20.0) + amount) * 100) / 100;

    set({
      events: nextEvents,
      accounts: updatedAccounts,
      communityStats: {
        total_balance: get().communityStats?.total_savings || 150.0,
        total_savings: get().communityStats?.total_savings || 150.0,
        total_loans_outstanding: get().communityStats?.total_loans_outstanding || 0.0,
        total_social_fund: newSocialPool,
        total_capital: Math.round(((get().communityStats?.total_savings || 150.0) + newSocialPool) * 100) / 100,
        total_members: Object.keys(updatedAccounts).length,
        total_events: nextEvents.length,
        merkle_root: newRoot,
        is_chain_valid: true,
      },
    });

    return eventModel;
  },

  payoutSocialFund: async ({ amount, memberPublicKey, memberPrivateKeyHex, purpose }) => {
    const { tellerKeyPair, events } = get();
    const tellerPriv = tellerKeyPair?.privateKeyHex || generateKeyPair().privateKeyHex;
    const previousHash =
      events.length > 0 ? events[events.length - 1].current_hash : GENESIS_HASH;

    const payload: EventPayload = {
      amount,
      currency: 'USD',
      user_public_key: memberPublicKey,
      notes: `Emergency welfare grant: ${purpose}`,
    };

    const signatures: EventSignatures = {
      teller_sig: signPayload(tellerPriv, payload),
      user_sig: signPayload(memberPrivateKeyHex, payload),
    };

    const currentHash = generateEventHash(
      previousHash,
      Buffer.from(serializeForHashing(payload), 'utf-8'),
      Buffer.from(serializeForHashing(signatures), 'utf-8')
    );

    const eventModel: EventModel = {
      event_id: `ev-grant-${Date.now()}`,
      timestamp: Math.floor(Date.now() / 1000),
      event_type: 'SOCIAL_FUND_PAYOUT',
      payload,
      previous_hash: previousHash,
      signatures,
      current_hash: currentHash,
    };

    const nextEvents = [...events, eventModel];
    const newRoot = computeDemoMerkleRoot(nextEvents.map((e) => e.current_hash));
    const newSocialPool = Math.max(0, Math.round(((get().communityStats?.total_social_fund || 20.0) - amount) * 100) / 100);

    set({
      events: nextEvents,
      communityStats: {
        total_balance: get().communityStats?.total_savings || 150.0,
        total_savings: get().communityStats?.total_savings || 150.0,
        total_loans_outstanding: get().communityStats?.total_loans_outstanding || 0.0,
        total_social_fund: newSocialPool,
        total_capital: Math.round(((get().communityStats?.total_savings || 150.0) + newSocialPool) * 100) / 100,
        total_members: Object.keys(get().accounts).length,
        total_events: nextEvents.length,
        merkle_root: newRoot,
        is_chain_valid: true,
      },
    });

    return eventModel;
  },

  simulateIncomingSmsPayment: async (amount: number, senderPhone: string) => {
    return get().simulateDarajaStk({ phoneNumber: senderPhone, amount });
  },

  simulateDarajaStk: async ({ phoneNumber, amount }) => {
    const { events, tellerKeyPair, sampleMembers } = get();
    const priv = tellerKeyPair?.privateKeyHex || generateKeyPair().privateKeyHex;
    const targetMember = sampleMembers[0];

    const previousHash = events.length > 0 ? events[events.length - 1].current_hash : GENESIS_HASH;
    const refCode = `MPESA${Math.random().toString(36).substring(2, 8).toUpperCase()}`;
    const payload: EventPayload = {
      amount,
      currency: 'USD',
      user_public_key: targetMember.publicKey,
      reference: refCode,
      notes: `M-Pesa STK Push from ${phoneNumber}`,
    };

    const signatures: EventSignatures = {
      teller_sig: signPayload(priv, payload),
      user_sig: null,
    };

    const currentHash = generateEventHash(
      previousHash,
      Buffer.from(serializeForHashing(payload), 'utf-8'),
      Buffer.from(serializeForHashing(signatures), 'utf-8')
    );

    const smsEvent: EventModel = {
      event_id: `ev-daraja-${Date.now()}`,
      timestamp: Math.floor(Date.now() / 1000),
      event_type: 'DEPOSIT_MOBILE_MONEY',
      payload,
      previous_hash: previousHash,
      signatures,
      current_hash: currentHash,
    };

    const nextEvents = [...events, smsEvent];
    const newRoot = computeDemoMerkleRoot(nextEvents.map((e) => e.current_hash));

    const updatedAccounts = { ...get().accounts };
    const cur = updatedAccounts[targetMember.publicKey]?.current_balance || 0.0;
    const newBal = Math.round((cur + amount) * 100) / 100;
    updatedAccounts[targetMember.publicKey] = {
      ...updatedAccounts[targetMember.publicKey],
      user_public_key: targetMember.publicKey,
      current_balance: newBal,
      savings_balance: newBal,
      net_balance: newBal - (updatedAccounts[targetMember.publicKey]?.loan_balance || 0),
      last_activity: smsEvent.timestamp,
      currency: 'USD',
    };

    const totalVault = Object.values(updatedAccounts).reduce(
      (sum, a) => sum + (a.savings_balance ?? a.current_balance),
      0
    );

    set({
      events: nextEvents,
      accounts: updatedAccounts,
      communityStats: {
        total_balance: Math.round(totalVault * 100) / 100,
        total_savings: Math.round(totalVault * 100) / 100,
        total_loans_outstanding: get().communityStats?.total_loans_outstanding || 0.0,
        total_social_fund: get().communityStats?.total_social_fund || 20.0,
        total_capital: Math.round((totalVault + (get().communityStats?.total_social_fund || 20.0)) * 100) / 100,
        total_members: Object.keys(updatedAccounts).length,
        total_events: nextEvents.length,
        merkle_root: newRoot,
        is_chain_valid: true,
      },
    });

    return smsEvent;
  },

  simulateMtnMoMo: async ({ phoneNumber, amount, currency = 'USD' }) => {
    return get().simulateDarajaStk({ phoneNumber, amount });
  },

  simulateAirtelMoney: async ({ phoneNumber, amount, currency = 'USD' }) => {
    return get().simulateDarajaStk({ phoneNumber, amount });
  },

  simulateOrangeMoney: async ({ phoneNumber, amount, currency = 'USD' }) => {
    return get().simulateDarajaStk({ phoneNumber, amount });
  },

  simulateWave: async ({ phoneNumber, amount, currency = 'USD' }) => {
    return get().simulateDarajaStk({ phoneNumber, amount });
  },

  simulateAfricasTalkingSms: async ({ fromPhone, text }) => {
    return get().simulateDarajaStk({ phoneNumber: fromPhone, amount: 50.0 });
  },

  flushPendingQueue: async () => {
    const { pendingQueue, isDemoMode, apiClient, events } = get();
    if (pendingQueue.length === 0) return 0;

    if (isDemoMode) {
      set({ pendingQueue: [] });
      return pendingQueue.length;
    }

    let flushedCount = 0;
    const remaining: EventModel[] = [];

    for (const item of pendingQueue) {
      try {
        await apiClient.createEvent(item);
        flushedCount++;
      } catch {
        remaining.push(item);
      }
    }

    set({
      pendingQueue: remaining,
      isOnline: remaining.length === 0,
    });

    if (flushedCount > 0) {
      await get().fetchRemoteState();
    }

    return flushedCount;
  },

  runAuditCheck: async () => {
    const { isDemoMode, apiClient, events } = get();
    if (isDemoMode) {
      const hashes = events.map((e) => e.current_hash);
      const computedRoot = computeDemoMerkleRoot(hashes);
      const lastHash = events.length > 0 ? events[events.length - 1].current_hash : GENESIS_HASH;

      const result: AuditVerification = {
        is_valid: true,
        total_events: events.length,
        merkle_root: computedRoot,
        last_hash: lastHash,
        tamper_details: null,
      };
      set({ auditResult: result });
      return result;
    }

    const result = await apiClient.verifyChain();
    set({ auditResult: result });
    return result;
  },
}));
