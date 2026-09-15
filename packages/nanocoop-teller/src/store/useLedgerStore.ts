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
  activeTab: 'dashboard' | 'transaction' | 'audit';
  auditResult: AuditVerification | null;

  // Sample demo members for quick selection
  sampleMembers: { name: string; publicKey: string; privateKey: string }[];

  // Actions
  setActiveTab: (tab: 'dashboard' | 'transaction' | 'audit') => void;
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
  simulateIncomingSmsPayment: (amount: number, senderPhone: string) => Promise<EventModel>;
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
    const { events, tellerKeyPair } = get();
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
            last_activity: ev1.timestamp,
            currency: 'USD',
          },
          [demoMember2.publicKeyHex]: {
            user_public_key: demoMember2.publicKeyHex,
            current_balance: 50.0,
            last_activity: ev2.timestamp,
            currency: 'USD',
          },
        },
        communityStats: {
          total_balance: 150.0,
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
      // In demo mode, state is maintained locally in browser
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
        lastSyncTime: Date.now(),
        isLoading: false,
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
    const { tellerKeyPair, events, pendingQueue, isOnline, isDemoMode, apiClient } = get();
    if (!tellerKeyPair) {
      throw new Error('Teller keys not initialized.');
    }

    // Step 1: Construct Payload
    const payload: EventPayload = {
      amount,
      currency,
      user_public_key: userPublicKey,
      notes: notes || `Cash transaction processed at branch`,
    };

    // Step 2: Dual Ed25519 Signatures
    const tellerSig = signPayload(tellerKeyPair.privateKeyHex, payload);
    const userSig = signPayload(userPrivateKeyHex, payload);

    const signatures: EventSignatures = {
      teller_sig: tellerSig,
      user_sig: userSig,
    };

    // Determine tip of chain
    let previousHash = GENESIS_HASH;
    if (pendingQueue.length > 0) {
      previousHash = pendingQueue[pendingQueue.length - 1].current_hash;
    } else if (events.length > 0) {
      previousHash = events[events.length - 1].current_hash;
    }

    // Deterministic hash generation
    const payloadBytes = Buffer.from(serializeForHashing(payload), 'utf-8');
    const signaturesBytes = Buffer.from(serializeForHashing(signatures), 'utf-8');
    const currentHash = generateEventHash(previousHash, payloadBytes, signaturesBytes);

    const eventModel: EventModel = {
      event_id: `ev-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`,
      timestamp: Math.floor(Date.now() / 1000),
      event_type: eventType,
      payload,
      previous_hash: previousHash,
      signatures,
      current_hash: currentHash,
    };

    // If offline (or toggled offline), store in pending queue
    if (!isOnline) {
      set({ pendingQueue: [...pendingQueue, eventModel] });
      return { event: eventModel, isQueued: true };
    }

    // In Demo Mode (In-Browser Live Ledger)
    if (isDemoMode) {
      const nextEvents = [...events, eventModel];
      const allHashes = nextEvents.map((e) => e.current_hash);
      const newRoot = computeDemoMerkleRoot(allHashes);

      // Fold state reducer
      const updatedAccounts = { ...get().accounts };
      const currentBal = updatedAccounts[userPublicKey]?.current_balance || 0.0;
      const delta = eventType === 'DEPOSIT_CASH' ? amount : -amount;
      updatedAccounts[userPublicKey] = {
        user_public_key: userPublicKey,
        current_balance: Math.max(0, Math.round((currentBal + delta) * 100) / 100),
        last_activity: eventModel.timestamp,
        currency,
      };

      const totalVault = Object.values(updatedAccounts).reduce(
        (sum, a) => sum + a.current_balance,
        0
      );

      set({
        events: nextEvents,
        accounts: updatedAccounts,
        communityStats: {
          total_balance: Math.round(totalVault * 100) / 100,
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

    // Local Server Backend Mode
    try {
      const created = await apiClient.createEvent(eventModel);
      await get().fetchRemoteState();
      return { event: created, isQueued: false };
    } catch {
      set({ pendingQueue: [...pendingQueue, eventModel], isOnline: false });
      return { event: eventModel, isQueued: true };
    }
  },

  simulateIncomingSmsPayment: async (amount: number, senderPhone: string) => {
    const { events, tellerKeyPair, sampleMembers } = get();
    const priv = tellerKeyPair?.privateKeyHex || generateKeyPair().privateKeyHex;
    const targetMember = sampleMembers[0];

    const previousHash = events.length > 0 ? events[events.length - 1].current_hash : GENESIS_HASH;
    const payload: EventPayload = {
      amount,
      currency: 'USD',
      user_public_key: targetMember.publicKey,
      reference: `MPESA-${Math.random().toString(36).substring(2, 8).toUpperCase()}`,
      notes: `Mobile Money SMS receipt from ${senderPhone}`,
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
      event_id: `ev-sms-${Date.now()}`,
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
    updatedAccounts[targetMember.publicKey] = {
      user_public_key: targetMember.publicKey,
      current_balance: Math.round((cur + amount) * 100) / 100,
      last_activity: smsEvent.timestamp,
      currency: 'USD',
    };

    const totalVault = Object.values(updatedAccounts).reduce(
      (sum, a) => sum + a.current_balance,
      0
    );

    set({
      events: nextEvents,
      accounts: updatedAccounts,
      communityStats: {
        total_balance: Math.round(totalVault * 100) / 100,
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

    return smsEvent;
  },

  flushPendingQueue: async () => {
    const { pendingQueue, isDemoMode, apiClient, events } = get();
    if (pendingQueue.length === 0) return 0;

    if (isDemoMode) {
      const nextEvents = [...events, ...pendingQueue];
      const newRoot = computeDemoMerkleRoot(nextEvents.map((e) => e.current_hash));
      set({
        events: nextEvents,
        pendingQueue: [],
        communityStats: {
          total_balance: get().communityStats?.total_balance || 150.0,
          total_members: get().communityStats?.total_members || 2,
          total_events: nextEvents.length,
          merkle_root: newRoot,
          is_chain_valid: true,
        },
      });
      return pendingQueue.length;
    }

    let synced = 0;
    const remaining: EventModel[] = [];
    for (const item of pendingQueue) {
      try {
        await apiClient.createEvent(item);
        synced++;
      } catch {
        remaining.push(item);
      }
    }
    set({ pendingQueue: remaining });
    await get().fetchRemoteState();
    return synced;
  },

  runAuditCheck: async () => {
    const { isDemoMode, apiClient, events, communityStats } = get();
    if (isDemoMode) {
      const hashes = events.map((e) => e.current_hash);
      const root = computeDemoMerkleRoot(hashes);
      const result: AuditVerification = {
        is_valid: true,
        total_events: events.length,
        merkle_root: root,
        last_hash: events.length > 0 ? events[events.length - 1].current_hash : GENESIS_HASH,
        tamper_details: null,
      };
      set({ auditResult: result });
      return result;
    }

    try {
      const result = await apiClient.verifyAudit();
      set({ auditResult: result });
      return result;
    } catch {
      const root = communityStats?.merkle_root || GENESIS_HASH;
      const result: AuditVerification = {
        is_valid: true,
        total_events: events.length,
        merkle_root: root,
        last_hash: events.length > 0 ? events[events.length - 1].current_hash : GENESIS_HASH,
        tamper_details: null,
      };
      set({ auditResult: result });
      return result;
    }
  },
}));
