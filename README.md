<div align="center">

# NanoCoop

### Offline-First, Cryptographic Community Banking Engine

[![CI/CD Pipeline](https://github.com/FranekJemiolo/nanocoop/actions/workflows/ci.yml/badge.svg)](https://github.com/FranekJemiolo/nanocoop/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/Python-3.12%2B-brightgreen.svg)](https://www.python.org/)
[![Managed with uv](https://img.shields.io/badge/Managed%20with-uv-purple.svg)](https://github.com/astral-sh/uv)
[![React Native / Expo](https://img.shields.io/badge/Expo-SDK%2051-black.svg)](https://expo.dev/)
[![Live Web Demo](https://img.shields.io/badge/Demo-GitHub%20Pages-success.svg)](https://franekjemiolo.github.io/nanocoop/)

*A zero-trust, offline-capable micro-core banking system featuring an append-only event ledger, Merkle tree cryptographic audit proofs, Ed25519 multi-signature authorization, and an asynchronous SMS bridge for mobile money integration.*

[**Live Web Demo**](https://franekjemiolo.github.io/nanocoop/) • [**Download Android APK**](https://github.com/FranekJemiolo/nanocoop/releases) • [**Architectural Design (DESIGN.md)**](DESIGN.md)

</div>

---

## 🌍 The Problem & Project Vision

Over 1.4 billion unbanked adults rely on informal community financial systems—such as **Village Savings and Loan Associations (VSLAs)**, rural agricultural cooperatives, and rotating credit clubs. 

These local institutions operate in extreme, resource-constrained environments:
- **Zero or Intermittent Connectivity:** No cloud access or high-latency cellular networks where internet may be unavailable for days.
- **Vulnerability to Fraud & Power Failure:** Paper ledgers or standard centralized spreadsheets suffer from tampering, disputes, and sudden data loss on sudden power outages.
- **Telecom Fragmentation:** Mobile money (M-Pesa, MTN Mobile Money, Airtel Money) confirmations arrive via plain SMS text messages rather than direct API webhooks.

**NanoCoop** provides a mathematically verifiable, self-contained micro-core banking system designed to run on a cheap Raspberry Pi or local server, paired with Android phones and low-cost cryptographic NFC cards.

---

## 📱 User Interface & Visual Tour

<div align="center">

### 1. Community Vault Dashboard
*Real-time community vault balance, member accounts, and live tamper-evident event stream.*
<br/>
<img src="docs/screenshots/dashboard.jpg" width="850" alt="NanoCoop Dashboard View" />

<br/><br/>

### 2. Branch Multi-Sig Transaction Flow
*Dual Ed25519 authorization requiring both the Teller's local key (Secure Store) and the Customer's NFC Card.*
<br/>
<img src="docs/screenshots/transaction.jpg" width="850" alt="NanoCoop Transaction Flow" />

<br/><br/>

### 3. Cryptographic Audit & Merkle Proofs
*Hierarchical Merkle tree state proof visualizer and one-click mathematical integrity auditor.*
<br/>
<img src="docs/screenshots/audit.jpg" width="850" alt="NanoCoop Audit View" />

</div>

---

## 🏛️ System Architecture

```mermaid
flowchart TD
    subgraph GSM["Cellular Network (GSM / 2G)"]
        SMS[Mobile Money SMS Receipts\nM-Pesa / MTN MoMo / Airtel]
    end

    subgraph Bridge["Android SMS Gateway (nanocoop-sms-bridge)"]
        Receiver[BroadcastReceiver\nandroid.provider.Telephony.SMS_RECEIVED]
        Parser[Telecom Regex Parser]
        Queue[SQLite Store-and-Forward Queue]
        Worker[Background HTTP Worker\nExponential Backoff & Jitter]
    end

    subgraph Core["Core Ledger Backend (nanocoop-core)"]
        API[FastAPI REST Engine]
        Idempotency[SQLite Idempotency Cache\nStatus: SUCCESS / DROPPED]
        Ledger[EventLedger Engine]
        Merkle[Merkle Tree Calculator]
        DB[(SQLite WAL Mode\nJournal=WAL, Sync=NORMAL)]
        Reducer[State Reducer\nFold Events into Balances]
    end

    subgraph Teller["Teller Client (nanocoop-teller)"]
        UI[React Native / Expo UI\nWeb / iOS / Android]
        SecureStore[Hardware KeyStore / SecureStore\nTeller Private Key]
        NFC[Customer NFC Card / QR Scan\nCustomer Private Key]
        OfflineQueue[Zustand Offline Sync Buffer]
    end

    SMS -->|SMS PDU| Receiver
    Receiver --> Parser
    Parser --> Queue
    Queue --> Worker
    Worker -->|POST /api/v1/sms/webhook| API

    UI -->|Dual Ed25519 Signatures| OfflineQueue
    SecureStore -.->|Sign Payload| UI
    NFC -.->|Sign Payload| UI
    OfflineQueue -->|POST /api/v1/events| API

    API --> Idempotency
    Idempotency -->|If New| Ledger
    Ledger --> Merkle
    Ledger --> DB
    DB --> Reducer
    Reducer -->|Account Balances & Stats| UI
```

---

## 📦 Monorepo Structure

```
nanocoop/
├── .github/
│   └── workflows/
│       └── ci.yml             # Secret scanning, Python coverage >=85%, Expo tests, APK & Web demo deploy
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
├── docs/
│   └── screenshots/            # Verified application captures
├── scripts/                    # Screenshot & build automation scripts
├── package.json                # Root npm workspaces configuration
├── DESIGN.md                   # In-depth architectural & cryptographic specification
└── README.md
```

---

## 🔐 Core Cryptographic Principles

### 1. Deterministic Cross-Language Serialization
Hashes and Ed25519 signatures generated in TypeScript on Android devices match Python on the backend identically by strictly enforcing sorted keys and zero extraneous whitespace:
```python
json_string = json.dumps(payload, sort_keys=True, separators=(',', ':'))
```

### 2. Dual-Signature Consensus
Cash transactions require two non-repudiable Ed25519 signatures:
- **Teller Signature:** Generated locally from `expo-secure-store` / hardware Keystore.
- **Customer Signature:** Read from the customer's cryptographic NFC smartcard or physical QR token.

### 3. Merkle Tree State Proofs
Every transaction hash forms a leaf in a binary Merkle Tree. If any historical record is modified or corrupted in the SQLite database, `verify_chain_integrity()` immediately detects the divergence and flags the tampered block.

### 4. Idempotency Cache Protection
To prevent duplicate SMS receipt submissions from double-crediting accounts, incoming receipts are hashed (`SHA256(code + amount + sender)`) and recorded in a primary-key SQLite cache. Duplicate transmissions are safely categorized as `DROPPED` without touching balances.

---

## 🚀 Quickstart & Local Development

### Prerequisites
- Node.js 20+ and npm
- Python 3.12+ with [**uv**](https://github.com/astral-sh/uv) installed (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Git

### 1. Clone & Install Dependencies
```bash
git clone https://github.com/FranekJemiolo/nanocoop.git
cd nanocoop

# Install Node monorepo workspace dependencies
npm install

# Setup and install Python backend with uv
cd packages/nanocoop-core
uv venv --python 3.12
uv pip install -e ".[dev]"
cd ../..
```

### 2. Run All Tests
```bash
# Run backend tests with code coverage (enforces >=85%)
npm run test:core

# Run SMS bridge tests with hardware mocking
npm run test:sms

# Run Teller client unit tests
npm run test:teller
```

### 3. Start the Core Backend Ledger
```bash
cd packages/nanocoop-core
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
API Documentation will be live at `http://localhost:8000/docs`.

### 4. Start the Teller Application (Web & Mobile)
```bash
cd packages/nanocoop-teller

# Start web demo locally:
npx expo start --web

# Or export static production bundle:
npx expo export -p web
```

---

## 🧪 Comprehensive Test Coverage

| Package | Test Framework | Test Types | Coverage |
| :--- | :--- | :--- | :--- |
| **nanocoop-core** | `pytest` + `pytest-cov` + `uv` | PKI crypto, Tamper detection, Idempotency race-conditions, 3-tier E2E | **93.1%** |
| **nanocoop-sms-bridge**| `jest` + `ts-jest` | Telecom regex parsers, Store-and-forward queue, Exponential backoff | **100%** |
| **nanocoop-teller** | `jest` + `jest-expo` | Deterministic serialization, Ed25519 signing, Offline Zustand queue | **100%** |

---

## 📄 License & Attribution

Distributed under the **MIT License**. Created by [**Franek Jemiolo**](https://github.com/FranekJemiolo).
Open-source software designed for financial inclusion and self-sovereign community banking worldwide.
