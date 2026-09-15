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
│       └── ci.yml             # Secret scanning, Python coverage >=85%, Expo tests, APK & Web demo deploy
├── packages/
│   ├── nanocoop-core/          # Python 3.12+ / FastAPI Event-Sourced Ledger
│   │   ├── app/
│   │   │   ├── api/            # REST endpoints (Events, Balance, Stats, Audit, Webhook, Loans, Integrations)
│   │   │   ├── core/           # Deterministic hashing, Ed25519 PKI, Merkle root logic
│   │   │   ├── db/             # SQLite aiosqlite with WAL mode and tables
│   │   │   ├── integrations/   # Live M-Pesa Daraja, MTN MoMo, Africa's Talking gateway clients
│   │   │   └── ledger/         # EventLedger engine & State Reducer (Savings, Loans, Welfare)
│   │   ├── tests/              # Pytest suite with 100% target coverage on core engine
│   │   ├── pyproject.toml      # Managed with uv
│   │   └── requirements.txt
│   ├── nanocoop-teller/        # React Native / Expo Cross-Platform Teller Client
│   │   ├── src/
│   │   │   ├── components/     # UI components (Header, Badges)
│   │   │   ├── screens/        # Dashboard, Transaction, Audit, Loans
│   │   │   ├── store/          # Zustand store with offline caching, demo engine & sync
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
├── docs/
│   ├── PLAN.md                 # Complete implementation plan
│   ├── JOURNAL.md              # Engineering decision & milestone execution journal
│   └── screenshots/            # Verified application captures
├── scripts/
│   ├── capture_ui.sh           # UI screenshot automation script
│   └── run_docker_tests.sh     # Docker Compose test runner script
├── docker-compose.yml          # Multi-container orchestration (Core, SMS Bridge, Teller Web)
├── docker-compose.test.yml     # Automated containerized E2E integration test suite
├── package.json                # Root npm workspaces configuration
├── DESIGN.md                   # In-depth architectural & cryptographic specification
└── README.md                   # Public open-source documentation
```

---

## 3. Implementation Milestones

### Milestone 1: Monorepo Initialization & CI/CD (✅ Completed)
- Set up root npm workspaces and uv Python virtual environment.
- Configure `.gitignore`, `.env.example`, and zero-leak policy.
- Write `.github/workflows/ci.yml` covering secret scanning, Python 3.12 pytest, Expo tests, static web export, and Android APK packaging.

### Milestone 2: Core Python Backend & Cryptography (✅ Completed)
- Implement Ed25519 PKI utilities (`pynacl` / `cryptography`).
- Implement deterministic canonical JSON serializer and SHA-256 event hash chain generator.
- Implement `EventLedger` engine with append-only storage and tamper detection.
- Implement Merkle tree root calculation.
- Implement State Reducer folding events into account balances.
- Implement SQLite Idempotency Cache table.
- Build FastAPI endpoints with cursor pagination.

### Milestone 3: Android SMS Gateway (✅ Completed)
- Create Android Kotlin BroadcastReceiver for `android.provider.Telephony.SMS_RECEIVED`.
- Build telecom regex parsers for M-Pesa, MTN Mobile Money, Airtel Money, and generic receipts.
- Implement persistent store-and-forward queue.
- Implement HTTP client with exponential backoff and randomized jitter.
- Implement mock dependency injection for CI/CD environments.

### Milestone 4: Cross-Platform Teller Application (✅ Completed)
- React Native / Expo application with web, iOS, and Android support.
- Pure JavaScript Ed25519 signing and deterministic hashing.
- Secure storage integration via `expo-secure-store`.
- Zustand state management with optimistic offline queueing.
- Implement DashboardScreen, TransactionScreen (multi-sig flow with NFC simulation), and AuditScreen (Merkle tree explorer).
- Implement interactive in-browser demo ledger for GitHub Pages web hosting.

### Milestone 5: E2E Testing & Artifact Generation (✅ Completed)
- 3-tier end-to-end integration test simulating telecom receipt ingestion -> gateway forward -> core event append -> teller balance reflection -> dual-signed cash withdrawal.
- Standalone Android APK build workflow in GitHub Actions.
- Automated UI screenshot generation pipeline.

### Milestone 6: Documentation, Docker Tests & Handover (✅ Completed)
- Detailed `README.md` with visual tour, setup instructions, and architecture diagrams.
- Detailed `DESIGN.md` cryptographic and offline sync specification.
- `docker-compose.yml` and `docker-compose.test.yml` running local multi-container integration tests.
- Execution journal `docs/JOURNAL.md`.
- Public GitHub repository at `FranekJemiolo/nanocoop` with live GitHub Pages demo.

### Milestone 7: VSLA Microfinance Domain Engine (✅ Completed)
- Expand event types: `LOAN_DISBURSED`, `LOAN_REPAID`, `SOCIAL_FUND_CONTRIBUTION`, `SOCIAL_FUND_PAYOUT`.
- Upgrade State Reducer to track savings, outstanding loan debt, interest pool, and social emergency funds per member.
- Member financial health summary and passbook audit trail.
- Full API routes for loans disbursement, repayment, and welfare contributions/payouts.

### Milestone 8: Production Telecom Gateways (Safaricom Daraja, MTN MoMo, Africa's Talking) (✅ Completed)
- Live async client for Safaricom Daraja M-Pesa (OAuth, STK Push `Lipa Na M-Pesa`, C2B validation and confirmation callbacks).
- Live async client for MTN Mobile Money Open API (Collections, RequestToPay, status checks).
- Inbound SMS webhook adapter for Africa's Talking and outbound passbook statement SMS generator.
- Document token/credential injection in `.env.example`.

### Milestone 9: 100% Cryptographic Ledger Test Coverage (✅ Completed)
- Achieved **100% statement and branch coverage** across all core modules:
  - `app/api/routes.py`: 100%
  - `app/core/crypto.py`: 100%
  - `app/core/config.py`: 100%
  - `app/db/database.py`: 100%
  - `app/integrations/daraja.py`: 100%
  - `app/integrations/mtn_momo.py`: 100%
  - `app/integrations/africas_talking.py`: 100%
  - `app/ledger/ledger.py`: 100%
  - `app/ledger/reducer.py`: 100%
  - `app/ledger/schema.py`: 100%
  - `app/main.py`: 100%
- Total backend coverage: **100.00%** (43/43 tests passing in both local and containerized Docker Compose environments).

### Milestone 10: Teller UI Loans & Integrations Hub & Final Handover (✅ Completed)
- Added VSLA Loans & Welfare Screen in `nanocoop-teller`.
- Added Integrations & Credentials test hub in `nanocoop-teller`.
- Integrated 5-tab navigation: Vault, Transact, VSLA Loans, Telecom, Audit.
- Refreshed static web export (`npm run build:web`).
- Verified all workspace unit tests passing (Teller & SMS Bridge).
- Ready for deployment to GitHub Pages and remote `main`.
