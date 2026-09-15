"""Orange Money Web Payment / Africa API Integration for NanoCoop.

Handles OAuth2 authentication, Web Payment / USSD prompt initiation, status polling,
and webhook callbacks across Francophone Africa (Senegal, Côte d'Ivoire, Mali, Guinea,
Burkina Faso, Cameroon, DRC, etc.).
"""

import base64
import logging
from typing import Any
import uuid
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class OrangeMoneyClient:
    """Client for interacting with Orange Money Developer API."""

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        merchant_key: str | None = None,
        environment: str | None = None,
    ):
        self.client_id = client_id or settings.ORANGE_CLIENT_ID
        self.client_secret = client_secret or settings.ORANGE_CLIENT_SECRET
        self.merchant_key = merchant_key or settings.ORANGE_MERCHANT_KEY
        self.environment = environment or settings.ORANGE_ENVIRONMENT
        self.base_url = "https://api.orange.com"

    @property
    def is_configured(self) -> bool:
        """Check if Orange Money credentials are populated."""
        return bool(self.client_id and self.client_secret and self.merchant_key)

    async def get_access_token(self, client: httpx.AsyncClient | None = None) -> str:
        """Exchange Basic client credentials for an Orange OAuth Bearer token."""
        if not self.is_configured:
            return "mock_orange_access_token_offline"

        auth_str = f"{self.client_id}:{self.client_secret}"
        encoded_auth = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")
        headers = {
            "Authorization": f"Basic {encoded_auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {"grant_type": "client_credentials"}

        should_close = False
        if client is None:
            client = httpx.AsyncClient(timeout=15.0)
            should_close = True

        try:
            url = f"{self.base_url}/oauth/v3/token"
            resp = await client.post(url, data=data, headers=headers)
            resp.raise_for_status()
            res_data = resp.json()
            return res_data.get("access_token", "")
        finally:
            if should_close:
                await client.aclose()

    async def initiate_payment(
        self,
        order_id: str,
        amount: float,
        currency: str = "XOF",
        return_url: str = "https://nanocoop.org/return",
        cancel_url: str = "https://nanocoop.org/cancel",
        notif_url: str = "https://api.nanocoop.org/api/v1/integrations/orange/callback",
        client: httpx.AsyncClient | None = None,
    ) -> dict[str, Any]:
        """Initiate an Orange Money payment token / payment session."""
        if not self.is_configured:
            pay_token = f"OM_TOKEN_{uuid.uuid4().hex[:12].upper()}"
            return {
                "status": 201,
                "message": "OK",
                "pay_token": pay_token,
                "payment_url": f"https://webpayment.orange.com/pay/{pay_token}",
                "notif_token": f"NT_{uuid.uuid4().hex[:8]}",
                "simulated": True,
            }

        token = await self.get_access_token(client=client)
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        body = {
            "merchant_key": self.merchant_key,
            "currency": currency,
            "order_id": order_id,
            "amount": int(amount),
            "return_url": return_url,
            "cancel_url": cancel_url,
            "notif_url": notif_url,
            "lang": "fr",
            "reference": f"NanoCoop-{order_id[:8]}",
        }

        should_close = False
        if client is None:
            client = httpx.AsyncClient(timeout=15.0)
            should_close = True

        try:
            url = f"{self.base_url}/orange-money-webpay/dev/v1/webpayment"
            resp = await client.post(url, json=body, headers=headers)
            resp.raise_for_status()
            return resp.json()
        finally:
            if should_close:
                await client.aclose()

    async def get_transaction_status(
        self,
        order_id: str,
        amount: float,
        pay_token: str,
        client: httpx.AsyncClient | None = None,
    ) -> dict[str, Any]:
        """Query Orange Money transaction status."""
        if not self.is_configured:
            return {
                "status": "SUCCESS",
                "order_id": order_id,
                "amount": amount,
                "txnid": f"OM-TXN-{uuid.uuid4().hex[:8].upper()}",
                "simulated": True,
            }

        token = await self.get_access_token(client=client)
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        body = {
            "order_id": order_id,
            "amount": int(amount),
            "pay_token": pay_token,
        }

        should_close = False
        if client is None:
            client = httpx.AsyncClient(timeout=15.0)
            should_close = True

        try:
            url = f"{self.base_url}/orange-money-webpay/dev/v1/transactionstatus"
            resp = await client.post(url, json=body, headers=headers)
            resp.raise_for_status()
            return resp.json()
        finally:
            if should_close:
                await client.aclose()

    @staticmethod
    def parse_callback(payload: dict[str, Any]) -> dict[str, Any]:
        """Parse incoming Orange Money webhook callback."""
        raw_status = str(payload.get("status", "")).upper()
        is_successful = raw_status in ("SUCCESS", "SUCCESSFUL", "200")

        return {
            "is_successful": is_successful,
            "transaction_id": str(payload.get("txnid") or payload.get("order_id", "")),
            "order_id": str(payload.get("order_id", "")),
            "amount": float(payload.get("amount", 0.0)),
            "currency": str(payload.get("currency", "XOF")),
            "customer_phone": str(payload.get("customer_id") or payload.get("phone", "")),
            "raw_status": raw_status,
        }


orange_client = OrangeMoneyClient()
