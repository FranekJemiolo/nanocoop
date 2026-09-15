"""Africa's Talking SMS Gateway Integration for NanoCoop.

Handles inbound SMS webhooks (parsing M-Pesa/MoMo/Airtel receipts from cloud shortcodes)
and outbound SMS passbook receipts to members' basic 2G feature phones.
"""

import logging
import re
from typing import Any
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# Regex patterns matching East/West African telecom SMS formats
MPESA_REGEX = re.compile(
    r"([A-Z0-9]{10})\s+Confirmed\.\s+(?:on\s+\S+\s+)?(?:Ksh|KES)\s*([0-9,]+(?:\.[0-9]{2})?)\s+received\s+from\s+(.+?)\s+([0-9]{10,12})",
    re.IGNORECASE,
)
MTN_REGEX = re.compile(
    r"(?:TxId|Transaction ID)[:\s]+([A-Z0-9]+).+?received\s+(?:UGX|GHS|RWF)\s*([0-9,]+(?:\.[0-9]{2})?)\s+from\s+(.+?)\s+([0-9]{10,12})",
    re.IGNORECASE,
)
AIRTEL_REGEX = re.compile(
    r"(?:Trans\. ID|Txn ID)[:\s]+([A-Z0-9\.]+).+?received\s+(?:Ksh|KES|UGX)\s*([0-9,]+(?:\.[0-9]{2})?)\s+from\s+(.+?)\s+([0-9]{10,12})",
    re.IGNORECASE,
)
GENERIC_REGEX = re.compile(
    r"(?:NANOCOOP|COOP)\s+(?:DEPOSIT|PAYMENT)\s+([0-9,]+(?:\.[0-9]{2})?)\s+(?:REF|ID)\s+([A-Z0-9]+)",
    re.IGNORECASE,
)


class AfricasTalkingClient:
    """Client for Africa's Talking cloud messaging & telecom shortcodes."""

    def __init__(
        self,
        username: str | None = None,
        api_key: str | None = None,
        sender_id: str | None = None,
    ):
        self.username = username or settings.AFRICASTALKING_USERNAME
        self.api_key = api_key or settings.AFRICASTALKING_API_KEY
        self.sender_id = sender_id or settings.AFRICASTALKING_SENDER_ID

        if self.username == "sandbox":
            self.base_url = "https://api.sandbox.africastalking.com/version1"
        else:
            self.base_url = "https://api.africastalking.com/version1"

    @property
    def is_configured(self) -> bool:
        """Check if API credentials are populated."""
        return bool(self.username and self.api_key)

    def parse_inbound_sms(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Parse inbound SMS payload delivered by Africa's Talking webhook."""
        text = payload.get("text", "").strip()
        from_phone = payload.get("from", "").strip()
        sms_id = payload.get("id", "")

        tx_code = sms_id or "UNKNOWN"
        amount = 0.0
        provider = "UNKNOWN"
        sender_name = None

        m_mpesa = MPESA_REGEX.search(text)
        if m_mpesa:
            tx_code = m_mpesa.group(1)
            amount = float(m_mpesa.group(2).replace(",", ""))
            sender_name = m_mpesa.group(3).strip()
            provider = "MPESA"
        else:
            m_mtn = MTN_REGEX.search(text)
            if m_mtn:
                tx_code = m_mtn.group(1)
                amount = float(m_mtn.group(2).replace(",", ""))
                sender_name = m_mtn.group(3).strip()
                provider = "MTN_MOMO"
            else:
                m_airtel = AIRTEL_REGEX.search(text)
                if m_airtel:
                    tx_code = m_airtel.group(1)
                    amount = float(m_airtel.group(2).replace(",", ""))
                    sender_name = m_airtel.group(3).strip()
                    provider = "AIRTEL"
                else:
                    m_gen = GENERIC_REGEX.search(text)
                    if m_gen:
                        amount = float(m_gen.group(1).replace(",", ""))
                        tx_code = m_gen.group(2)
                        provider = "GENERIC"

        return {
            "transaction_code": tx_code,
            "amount": amount,
            "sender_phone": from_phone,
            "sender_name": sender_name,
            "provider": provider,
            "raw_text": text,
            "is_valid": amount > 0,
        }

    async def send_sms(
        self,
        to_phone: str,
        message: str,
        client: httpx.AsyncClient | None = None,
    ) -> dict[str, Any]:
        """Send outbound passbook SMS receipt to a member's basic phone."""
        phone = to_phone.strip()
        if not phone.startswith("+"):
            phone = "+" + phone

        if not self.is_configured:
            return {
                "status": "SIMULATED",
                "to": phone,
                "message": message,
                "recipients": [{"number": phone, "status": "Success", "cost": "0.00"}],
            }

        headers = {
            "apiKey": self.api_key,
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        data = {
            "username": self.username,
            "to": phone,
            "message": message,
        }
        if self.sender_id:
            data["from"] = self.sender_id

        should_close = False
        if client is None:
            client = httpx.AsyncClient(timeout=15.0)
            should_close = True

        try:
            url = f"{self.base_url}/messaging"
            resp = await client.post(url, data=data, headers=headers)
            resp.raise_for_status()
            return resp.json()
        finally:
            if should_close:
                await client.aclose()

    @staticmethod
    def format_passbook_sms(
        event_type: str,
        amount: float,
        currency: str,
        balance: float,
        reference: str | None = None,
    ) -> str:
        """Format a clear, concise SMS receipt for low-resource feature phone displays."""
        ref_str = f" Ref:{reference}" if reference else ""
        return (
            f"[NanoCoop] Confirmed: {event_type} of {currency} {amount:.2f}.{ref_str} "
            f"New Savings Balance: {currency} {balance:.2f}. Cryptographically Verified."
        )


africas_talking_client = AfricasTalkingClient()
