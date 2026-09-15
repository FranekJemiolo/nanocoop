# NanoCoop Field Deployment & Production Hardware Guide

This guide provides step-by-step instructions for deploying NanoCoop in low-resource rural environments, Village Savings and Loan Associations (VSLAs), and local agricultural cooperatives.

---

## 1. Hardware Architecture for Rural Cooperatives

A self-contained, zero-trust NanoCoop branch node requires minimal, low-cost hardware:

```
┌─────────────────────────────────────────────────────────┐
│              NanoCoop Branch Infrastructure             │
├──────────────────────────┬──────────────────────────────┤
│ 1. Core Server Node      │ Raspberry Pi 4 (2GB RAM) or  │
│                          │ refurbished mini-PC ($35-60) │
├──────────────────────────┼──────────────────────────────┤
│ 2. SMS Gateway Bridge    │ Budget Android phone (2G/3G/ │
│                          │ 4G SIM with M-Pesa/MoMo line)│
├──────────────────────────┼──────────────────────────────┤
│ 3. Teller Device         │ Android smartphone or tablet │
│                          │ running NanoCoop Teller App  │
├──────────────────────────┼──────────────────────────────┤
│ 4. Member Smartcards     │ NTAG215 / NTAG216 NFC tags   │
│                          │ ($0.15/ea) or printed QR     │
└──────────────────────────┴──────────────────────────────┘
```

---

## 2. Core Server Setup (Raspberry Pi / Linux)

### 2.1 OS & Dependencies Installation
Install Raspberry Pi OS Lite (64-bit) or Ubuntu Server:
```bash
# Update base system
sudo apt-get update && sudo apt-get install -y git curl python3 python3-pip

# Install uv (instant Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env

# Clone repository
git clone https://github.com/FranekJemiolo/nanocoop.git /opt/nanocoop
cd /opt/nanocoop/packages/nanocoop-core

# Setup virtual environment and dependencies
uv venv --python 3.12
uv pip install -e .
```

### 2.2 Systemd Service Configuration
Create `/etc/systemd/system/nanocoop-core.service`:
```ini
[Unit]
Description=NanoCoop Cryptographic Core Ledger Engine
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/opt/nanocoop/packages/nanocoop-core
ExecStart=/opt/nanocoop/packages/nanocoop-core/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
Environment=NANOCOOP_DB_PATH=/var/lib/nanocoop/nanocoop.db
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

Enable and start the service:
```bash
sudo mkdir -p /var/lib/nanocoop && sudo chown -R pi:pi /var/lib/nanocoop
sudo systemctl daemon-reload
sudo systemctl enable nanocoop-core
sudo systemctl start nanocoop-core
sudo systemctl status nanocoop-core
```

---

## 3. Power Failure Resilience & SQLite WAL Backups

Rural areas frequently suffer sudden electrical blackouts. NanoCoop uses **SQLite Write-Ahead Logging (WAL)**:
- Writes are appended to a `.wal` journal without overwriting database pages.
- Reads never block writes; writes never block reads.
- Crash consistency is guaranteed even if power cuts mid-transaction.

### Daily Automated Backup Script
Create `/etc/cron.daily/nanocoop-backup`:
```bash
#!/usr/bin/env bash
BACKUP_DIR="/var/backups/nanocoop"
mkdir -p "$BACKUP_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Use SQLite online backup API to copy clean snapshot safely
sqlite3 /var/lib/nanocoop/nanocoop.db ".backup '$BACKUP_DIR/nanocoop_$TIMESTAMP.db'"

# Retain last 30 daily backups
find "$BACKUP_DIR" -type f -name "nanocoop_*.db" -mtime +30 -delete
```
```bash
sudo chmod +x /etc/cron.daily/nanocoop-backup
```

---

## 4. Android SMS Gateway Setup (nanocoop-sms-bridge)

The SMS Bridge phone intercepts mobile money receipts sent by telecom operators (Safaricom M-Pesa, MTN Mobile Money, Airtel Money).

### 4.1 APK Installation & Permissions
1. Download the release APK from GitHub Actions artifacts or repository releases.
2. Sideload onto the Android phone via USB or browser.
3. Grant required permissions:
   - `RECEIVE_SMS`: To catch broadcasted telecom receipts.
   - `READ_SMS`: To process existing message store.
   - `INTERNET`: To communicate with the Core Server.

### 4.2 Disable Android Battery Doze (Crucial)
Android aggressively puts background apps to sleep. To guarantee zero missed receipts:
1. Navigate to **Settings > Apps > NanoCoop Gateway**.
2. Tap **Battery > Battery Usage**.
3. Select **Unrestricted** (or **Disable Battery Optimization**).
4. Enable **Autostart** if using Xiaomi, Transsion (Tecno/Infinix), or Samsung devices.

---

## 5. Member Provisioning & NFC/QR Smartcards

### 5.1 Member Enrollment
Run the CLI on the server node to create a member:
```bash
cd /opt/nanocoop/packages/nanocoop-core
uv run nanocoop create-member --name "Esther Mutua"
```
Output:
```
==================================================
      New Cooperative Member Credentials Generated 
==================================================
Member Name:  Esther Mutua
Public Key:   606b821402e2f8784a43be91b1ecd1d4ef7ceb951cdddb4e0d6062007648cd87
Private Key:  a4d9201948ba9820fbc8921e9021481b9487c8a912803b984019283ba874b019
==================================================
```

### 5.2 Provisioning NFC Smartcards
1. Use an Android NFC writing tool (e.g., *NFC Tools* app).
2. Write the 64-character hex private key as a protected text record to an NTAG215 card.
3. The member taps this card against the Teller's smartphone during weekly cooperative meetings to authorize cash withdrawals, micro-loan acceptances, and welfare requests.

### 5.3 Paper QR Passbooks (Zero-Smartphone Alternative)
For members who prefer paper or cannot afford an NFC card:
- Print a QR code encoding the member's private key onto a physical paper passbook.
- When authorizing a transaction, the Teller scans the member's QR code using the camera on the Teller app.

---

## 6. Live Telecom Credentials Setup

To connect live mobile money APIs, create `/opt/nanocoop/.env`:

```bash
# Safaricom Daraja M-Pesa (Kenya)
MPESA_ENVIRONMENT=production
MPESA_CONSUMER_KEY=your_live_consumer_key
MPESA_CONSUMER_SECRET=your_live_consumer_secret
MPESA_PASSKEY=your_live_lipa_na_mpesa_passkey
MPESA_SHORTCODE=your_paybill_or_till_number
MPESA_CALLBACK_URL=https://api.yourcoop.org/api/v1/integrations/mpesa/stk-callback

# MTN Mobile Money Open API (Uganda, Ghana, Rwanda)
MTN_MOMO_ENVIRONMENT=live
MTN_MOMO_SUBSCRIPTION_KEY=your_subscription_key
MTN_MOMO_API_USER=your_uuid_v4_user
MTN_MOMO_API_KEY=your_live_api_key

# Africa's Talking Cloud SMS (Sub-Saharan Africa)
AFRICASTALKING_USERNAME=your_username
AFRICASTALKING_API_KEY=your_live_api_key
AFRICASTALKING_SENDER_ID=NANOCOOP
```

Restart the Core Service:
```bash
sudo systemctl restart nanocoop-core
```
Check integration readiness:
```bash
curl -s http://localhost:8000/api/v1/integrations/status | jq .
```
All configured gateways will report `"configured": true`!
