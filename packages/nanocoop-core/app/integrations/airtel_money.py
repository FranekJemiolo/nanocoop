"""Airtel Money Developer API Integration for NanoCoop.

Handles OAuth2 authentication, Collections (USSD Push prompt), transaction status inquiry,
and webhook callbacks across 14 African countries (Kenya, Uganda, Tanzania, Rwanda,
Nigeria, Zambia, Malawi, DRC, etc.).
"""

import logging
from typing import Any
import uuid
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class AirtelMoneyClient:
    """Client for interacting with Airtel Africa Open API."""

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        country: str | None = None,
        currency: str | None = None,
        environment: str | None = None,
    ):
        self.client_id = client_id or settings.AIRTEL_CLIENT_ID
        self.client_secret = client_secret or settings.AIRTEL_CLIENT_SECRET
        self.country = country or settings.AIRTEL_COUNTRY
        self.currency = currency or settings.AIRTEL_CURRENCY
        self.environment = environment or settings.AIRTEL_ENVIRONMENT

        if self.environment == "production":
            self.base_url = "https://openapi.airtel.africa"
        else:
            self.base_url = "https://openapiuat.airtel.africa"

    @property
    def is_configured(self) -> bool:
        """Check if production or sandbox Airtel credentials are configured."""
        return bool(self.client_id and self.client_secret)

    async def get_access_token(self, client: httpx.AsyncClient | None = None) -> str:
        """Retrieve OAuth2 Bearer token from Airtel Africa API."""
        if not self.is_configured:
            return "mock_airtel_access_token_offline"

        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "client_credentials",
        }
        headers = {"Content-Type": "application/json"}

        should_close = False
        if client is None:
            client = httpx.AsyncClient(timeout=15.0)
            should_close = True

        try:
            url = f"{self.base_url}/auth/oauth2/token"
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return data.get("access_token", "")
        finally:
            if should_close:
                await client.aclose()

    async def request_to_pay(
        self,
        phone_number: str,
        amount: float,
        reference: str,
        transaction_id: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> dict[str, Any]:
        """Trigger an Airtel Money USSD push authorization prompt on subscriber handset."""
        phone = phone_number.strip().replace("+", "")
        if phone.startswith("0"):
            phone = phone[1:]

        tx_id = transaction_id or str(uuid.uuid4())

        if not self.is_configured:
            return {
                "data": {
                    "transaction": {
                        "id": tx_id,
                        "status": "TIP",  # Transaction In Progress
                    }
                },
                "status": {
                    "code": "200",
                    "message": "Payment prompt sent to member phone",
                    "result_code": "ESB00001",
                    "success": True,
                },
                "simulated": True,
            }

        token = await self.get_access_token(client=client)
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Country": self.country,
            "X-Currency": self.currency,
            "Content-Type": "application/json",
        }

        body = {
            "reference": reference[:32],
            "subscriber": {
                "country": self.country,
                "currency": self.currency,
                "msisdn": phone,
            },
            "transaction": {
                "amount": amount,
                "country": self.country,
                "currency": self.currency,
                "id": tx_id,
            },
        }

        should_close = False
        if client is None:
            client = httpx.AsyncClient(timeout=15.0)
            should_close = True

        try:
            url = f"{self.base_url}/merchant/v1/payments/"
            resp = await client.post(url, json=body, headers=headers)
            resp.raise_for_status()
            return resp.json()
        finally:
            if should_close:
                await client.aclose()

    async def get_payment_status(
        self,
        transaction_id: str,
        client: httpx.AsyncClient | None = None,
    ) -> dict[str, Any]:
        """Query the status of an Airtel Money transaction."""
        if not self.is_configured:
            return {
                "data": {
                    "transaction": {
                        "id": transaction_id,
                        "status": "TS",  # Transaction Success
                        "airtel_money_id": f"AIRTEL-{uuid.uuid4().hex[:8].upper()}",
                    }
                },
                "status": {"code": "200", "success": True},
                "simulated": True,
            }

        token = await self.get_access_token(client=client)
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Country": self.country,
            "X-Currency": self.currency,
        }

        should_close = False
        if client is None:
            client = httpx.AsyncClient(timeout=15.0)
            should_close = True

        try:
            url = f"{self.base_url}/standard/v1/payments/{transaction_id}"
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            return resp.json()
        finally:
            if should_close:
                await client.aclose()

    @staticmethod
    def parse_callback(payload: dict[str, Any]) -> dict[str, Any]:
        """Parse Airtel Africa payment webhook notification."""
        transaction = payload.get("transaction", {})
        status_code = transaction.get("status", "").upper()
        # TS = Transaction Success, TF = Transaction Failed, TIP = In Progress
        is_successful = status_code == "TS"

        return {
            "is_successful": is_successful,
            "transaction_id": transaction.get("id") or transaction.get("airtel_money_id", ""),
            "amount": float(transaction.get("amount", 0.0)),
            "currency": transaction.get("currency", "KES"),
            "subscriber_phone": payload.get("subscriber", {}).get("msisdn", ""),
            "raw_status": status_code,
            "message": transaction.get("message", ""),
        }


airtel_client = AirtelMoneyClient()
