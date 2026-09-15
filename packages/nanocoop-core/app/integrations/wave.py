"""Wave Mobile Money Integration for NanoCoop.

Handles Wave Checkout sessions and HMAC-SHA256 authenticated webhook verification
across Senegal, Côte d'Ivoire, Mali, Burkina Faso, and Gambia.
"""

import hashlib
import hmac
import logging
import time
from typing import Any
import uuid
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class WaveClient:
    """Client for interacting with Wave Mobile Money API."""

    def __init__(
        self,
        api_key: str | None = None,
        webhook_secret: str | None = None,
        environment: str | None = None,
    ):
        self.api_key = api_key or settings.WAVE_API_KEY
        self.webhook_secret = webhook_secret or settings.WAVE_WEBHOOK_SECRET
        self.environment = environment or settings.WAVE_ENVIRONMENT
        self.base_url = "https://api.wave.com"

    @property
    def is_configured(self) -> bool:
        """Check if Wave API key is configured."""
        return bool(self.api_key)

    async def create_checkout_session(
        self,
        amount: float,
        currency: str = "XOF",
        client_reference: str = "COOP-DEPOSIT",
        restrict_payer_mobile: str | None = None,
        success_url: str = "https://nanocoop.org/success",
        error_url: str = "https://nanocoop.org/error",
        client: httpx.AsyncClient | None = None,
    ) -> dict[str, Any]:
        """Create a Wave checkout session for member deposit."""
        if not self.is_configured:
            session_id = f"cos_{uuid.uuid4().hex[:16]}"
            return {
                "id": session_id,
                "amount": str(int(amount)),
                "currency": currency,
                "checkout_status": "processing",
                "client_reference": client_reference,
                "wave_launch_url": f"https://pay.wave.com/c/{session_id}",
                "simulated": True,
            }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body: dict[str, Any] = {
            "amount": str(int(amount)),
            "currency": currency,
            "error_url": error_url,
            "success_url": success_url,
            "client_reference": client_reference[:32],
        }
        if restrict_payer_mobile:
            body["restrict_payer_mobile"] = restrict_payer_mobile

        should_close = False
        if client is None:
            client = httpx.AsyncClient(timeout=15.0)
            should_close = True

        try:
            url = f"{self.base_url}/v1/checkout/sessions"
            resp = await client.post(url, json=body, headers=headers)
            resp.raise_for_status()
            return resp.json()
        finally:
            if should_close:
                await client.aclose()

    def verify_webhook_signature(
        self,
        raw_body: bytes,
        signature_header: str,
        tolerance_seconds: int = 300,
    ) -> bool:
        """Verify HMAC-SHA256 signature from Wave-Signature header."""
        if not self.webhook_secret:
            return True  # Permissive in offline/unconfigured mock mode

        # Header format: t=1614588902,v1=66b44781745...
        parts = dict(pair.split("=", 1) for pair in signature_header.split(",") if "=" in pair)
        timestamp_str = parts.get("t")
        expected_sig = parts.get("v1")

        if not timestamp_str or not expected_sig:
            return False

        # Tolerance check
        try:
            ts = int(timestamp_str)
            if abs(time.time() - ts) > tolerance_seconds:
                return False
        except ValueError:
            return False

        # Compute HMAC
        signed_payload = f"{timestamp_str}.".encode("utf-8") + raw_body
        computed_sig = hmac.new(
            self.webhook_secret.encode("utf-8"), signed_payload, hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(computed_sig, expected_sig)

    @staticmethod
    def parse_webhook(payload: dict[str, Any]) -> dict[str, Any]:
        """Parse Wave webhook event payload."""
        event_type = payload.get("type", "")
        data = payload.get("data", {})

        is_successful = event_type == "checkout.session.completed"
        return {
            "is_successful": is_successful,
            "event_type": event_type,
            "session_id": data.get("id", ""),
            "transaction_id": data.get("transaction_id") or data.get("id", ""),
            "amount": float(data.get("amount", 0.0)),
            "currency": data.get("currency", "XOF"),
            "client_reference": data.get("client_reference", ""),
            "payer_mobile": data.get("customer", {}).get("mobile", ""),
        }


wave_client = WaveClient()
