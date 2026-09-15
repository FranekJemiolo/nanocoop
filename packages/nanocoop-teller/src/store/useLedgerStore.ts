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
  hexToBytes,
  serializeForHashing,
  signPayload,
} from '../utils/crypto';
import { SecureStorage } from '../utils/secureStore';

export interface LedgerStoreState {
  apiClient: NanoCoopApiClient;
  communityStats: CommunityStats | null;
  events: EventModel[];
  accounts: Record<string, AccountState>;
  pendingQueue: EventModel[];
  isOnline: boolean;
  isLoading: boolean;
  lastSyncTime: number | null;
  tellerKeyPair: { privateKeyHex: string; publicKeyHex: string } | null;
  activeTab: 'dashboard' | 'transaction' | 'audit';
  auditResult: AuditVerification | null;

  // Actions
  setActiveTab: (tab: 'dashboard' | 'transaction' | 'audit') => void;
  setOnlineStatus: (isOnline: boolean) => void;
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
  flushPendingQueue: () => Promise<number>;
  runAuditCheck: () => Promise<AuditVerification>;
}

export const useLedgerStore = create<LedgerStoreState>((set, get) => ({
  apiClient: new NanoCoopApiClient(),
  communityStats: null,
  events: [],
  accounts: {},
  pendingQueue: [],
  isOnline: true,
  isLoading: false,
  lastSyncTime: null,
  tellerKeyPair: null,
  activeTab: 'dashboard',
  auditResult: null,

  setActiveTab: (tab) => set({ activeTab: tab }),

  setOnlineStatus: (isOnline) => set({ isOnline }),

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
  },

  fetchRemoteState: async () => {
    set({ isLoading: true });
    const { apiClient } = get();

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

      // Save local cache in SecureStorage
      await SecureStorage.setItem('cached_stats', JSON.stringify(stats));
      await SecureStorage.setItem('cached_events', JSON.stringify(eventsData.events));
    } catch (err) {
      // Offline fallback: load cached state
      const cachedStats = await SecureStorage.getItem('cached_stats');
      const cachedEvents = await SecureStorage.getItem('cached_events');

      set({
        isOnline: false,
        isLoading: false,
        communityStats: cachedStats ? JSON.parse(cachedStats) : null,
        events: cachedEvents ? JSON.parse(cachedEvents) : [],
      });
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
    const { tellerKeyPair, events, pendingQueue, isOnline, apiClient } = get();
    if (!tellerKeyPair) {
      throw new Error('Teller keys not initialized. Please configure teller keypair.');
    }

    // Step 1: Construct Payload
    const payload: EventPayload = {
      amount,
      currency,
      user_public_key: userPublicKey,
      notes: notes || `Cash transaction processed at branch`,
    };

    // Step 2: Teller Dual Sign with Teller Private Key
    const tellerSig = signPayload(tellerKeyPair.privateKeyHex, payload);

    // Step 3: User Sign with Customer Key (via simulated NFC / QR)
    const userSig = signPayload(userPrivateKeyHex, payload);

    const signatures: EventSignatures = {
      teller_sig: tellerSig,
      user_sig: userSig,
    };

    // Determine tip of chain (including any pending local events)
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
      event_id: `ev-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`,
      timestamp: Math.floor(Date.now() / 1000),
      event_type: eventType,
      payload,
      previous_hash: previousHash,
      signatures,
      current_hash: currentHash,
    };

    if (isOnline) {
      try {
        const created = await apiClient.createEvent(eventModel);
        // Refresh state
        await get().fetchRemoteState();
        return { event: created, isQueued: false };
      } catch (networkErr) {
        // Fallback to offline store-and-forward queue
        set({
          pendingQueue: [...pendingQueue, eventModel],
          isOnline: false,
        });
        return { event: eventModel, isQueued: true };
      }
    } else {
      // Offline mode: store in local pending queue
      set({ pendingQueue: [...pendingQueue, eventModel] });
      return { event: eventModel, isQueued: true };
    }
  },

  flushPendingQueue: async () => {
    const { pendingQueue, apiClient } = get();
    if (pendingQueue.length === 0) return 0;

    let syncedCount = 0;
    const remainingQueue: EventModel[] = [];

    for (const pendingEvent of pendingQueue) {
      try {
        await apiClient.createEvent(pendingEvent);
        syncedCount++;
      } catch (err) {
        remainingQueue.push(pendingEvent);
      }
    }

    set({ pendingQueue: remainingQueue });
    await get().fetchRemoteState();
    return syncedCount;
  },

  runAuditCheck: async () => {
    const { apiClient } = get();
    const result = await apiClient.verifyAudit();
    set({ auditResult: result });
    return result;
  },
}));
