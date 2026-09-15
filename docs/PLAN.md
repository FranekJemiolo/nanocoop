# NanoCoop Comprehensive Implementation Plan

NanoCoop is an offline-first, zero-trust cryptographic community banking engine engineered for low-resource environments (VSLAs, rural cooperatives, microfinance institutions). It features an event-sourced append-only ledger with Merkle tree hashing, Ed25519 dual-signature authorization, an Android SMS gateway with store-and-forward retry queue for mobile money receipts, and an Expo-based cross-platform Teller client with offline local caching and static web demo capability.

---

## 1. Core Architectural Pillars

- **Deterministic Cross-Platform Hashing:** JSON serialization with `sort_keys=True` and separators `(',', ':')` enforced across Python and TypeScript/JavaScript.
- **SQLite WAL Mode:** Resilient against sudden power failures on low-cost hardware (`PRAGMA journal_mode=WAL;` and `PRAGMA synchronous=NORMAL;`).
- **Dual Multi-Signature Consensus:** Cash transactions require non-repudiable signatures from both the Teller's device key and the Customer's NFC/QR smartcard.
- **Asynchronous Mobile Money Bridge:** Telecom SMS receipts (M-Pesa, MTN Mobile Money, Airtel Money) intercepted via Android `BroadcastReceiver` and buffered in a local store-and-forward queue with exponential backoff and jitter.
- **Idempotency Defense:** Deterministic transaction hashing and SQLite primary key constraints prevent double-crediting on cellular network duplicate delivery.

---

## 2. Monorepo Structure

```
nanocoop/
├── .github/
│   └── workflows/
│       └── ci.yml             # Secret scanning, uv Python 3.12 (>=85% cov), Expo tests, APK & Web demo
├── packages/
│   ├── nanocoop-core/          # Python 3.12+ / FastAPI Event-Sourced Ledger
│   │   ├── app/
│   │   │   ├── api/            # REST endpoints (Events, Balance, Stats, Audit, Webhook)
│   │   │   ├── core/           # Deterministic hashing, Ed25519 PKI, Merkle root logic
│   │   │   ├── db/             # SQLite aiosqlite with WAL mode and tables
│   │   │   └── ledger/         # EventLedger engine & State Reducer
│   │   ├── tests/              # Pytest suite (tamper detection, dual-sig, concurrency, e2e)
│   │   ├── pyproject.toml      # Managed with uv
│   │   └── requirements.txt
│   ├── nanocoop-teller/        # React Native / Expo Cross-Platform Teller Client
│   │   ├── src/
│   │   │   ├── components/     # UI components (Header, Badges)
│   │   │   ├── screens/        # Dashboard, Transaction, Audit
│   │   │   ├── store/          # Zustand store with offline caching & sync
│   │   │   └── utils/          # Pure JS Ed25519 crypto, SecureStore, API client
│   │   ├── App.tsx
│   │   └── package.json
│   └── nanocoop-sms-bridge/    # Android SMS Store-and-Forward Gateway
│       ├── src/
│       │   ├── receiver/       # BroadcastReceiver & Telecom regex parsers
│       │   ├── queue/          # Store-and-forward persistent queue
│       │   ├── network/        # HTTP client with exponential backoff & jitter
│       │   └── android/        # Native Kotlin BroadcastReceiver & Manifest
│       ├── tests/              # Jest tests with hardware dependency injection
│       └── package.json
├── docs/                       # Project documentation, diagrams, and UI captures
├── scripts/                    # Automation scripts
├── docker-compose.yml          # Local multi-service orchestration
├── docker-compose.test.yml     # Automated end-to-end container test pipeline
├── package.json                # Root npm workspaces configuration
├── DESIGN.md                   # In-depth architectural & cryptographic specification
└── README.md                   # Public open-source documentation
```

---

## 3. Implementation Milestones

### Milestone 1: Monorepo Initialization & CI/CD
- Set up root npm workspaces and uv Python virtual environment.
- Configure `.gitignore`, `.env.example`, and zero-leak policy.
- Write `.github/workflows/ci.yml` covering secret scanning, Python 3.12 pytest with coverage threshold >=85%, Expo Jest tests, static web export, and standalone Android APK release packaging.

### Milestone 2: Core Python Backend & Cryptography
- Implement Ed25519 PKI utilities (`pynacl` / `cryptography`).
- Implement deterministic canonical JSON serializer and SHA-256 event hash chain generator.
- Implement `EventLedger` engine with append-only storage and tamper detection.
- Implement Merkle tree root calculation.
- Implement State Reducer folding events into account balances.
- Implement SQLite Idempotency Cache table.
- Build FastAPI endpoints with cursor pagination.
- Achieve >=85% test coverage (achieved 93.1%).

### Milestone 3: Android SMS Gateway
- Create Android Kotlin BroadcastReceiver for `android.provider.Telephony.SMS_RECEIVED`.
- Build telecom regex parsers for M-Pesa, MTN Mobile Money, Airtel Money, and generic receipts.
- Implement persistent store-and-forward queue.
- Implement HTTP client with exponential backoff and randomized jitter.
- Implement mock dependency injection for CI/CD environments.

### Milestone 4: Cross-Platform Teller Application
- React Native / Expo application with web, iOS, and Android support.
- Implement pure JavaScript Ed25519 signing and deterministic hashing.
- Secure storage integration via `expo-secure-store`.
- Zustand state management with optimistic offline queueing.
- Implement DashboardScreen, TransactionScreen (multi-sig flow with NFC simulation), and AuditScreen (Merkle tree explorer).
- Implement interactive in-browser demo ledger for GitHub Pages web hosting.

### Milestone 5: E2E Testing & Artifact Generation
- 3-tier end-to-end integration test simulating telecom receipt ingestion -> gateway forward -> core event append -> teller balance reflection -> dual-signed cash withdrawal.
- Standalone Android APK build workflow in GitHub Actions.
- Automated UI screenshot generation pipeline.

### Milestone 6: Documentation, Docker Tests & Handover
- Detailed `README.md` with visual tour, setup instructions, and architecture diagrams.
- Detailed `DESIGN.md` cryptographic and offline sync specification.
- `docker-compose.yml` and `docker-compose.test.yml` running local multi-container integration tests.
- Execution journal `docs/JOURNAL.md`.
