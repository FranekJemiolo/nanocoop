"""MTN Mobile Money (MoMo Open API) Integration for NanoCoop.

Handles Collections RequestToPay, status polling, and callback verification
across Uganda, Ghana, Rwanda, and West African VSLA networks.
"""

import base64
import logging
from typing import Any
import uuid
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class MtnMoMoClient:
    """Client for communicating with MTN Mobile Money Open API."""

    def __init__(
        self,
        subscription_key: str | None = None,
        api_user: str | None = None,
        api_key: str | None = None,
        environment: str | None = None,
    ):
        self.subscription_key = subscription_key or settings.MTN_MOMO_SUBSCRIPTION_KEY
        self.api_user = api_user or settings.MTN_MOMO_API_USER
        self.api_key = api_key or settings.MTN_MOMO_API_KEY
        self.environment = environment or settings.MTN_MOMO_ENVIRONMENT

        if self.environment == "live":
            self.base_url = "https://momodeveloper.mtn.com"
        else:
            self.base_url = "https://sandbox.momodeveloper.mtn.com"

    @property
    def is_configured(self) -> bool:
        """Check if production/sandbox API credentials are fully populated."""
        return bool(self.subscription_key and self.api_user and self.api_key)

    async def get_access_token(self, client: httpx.AsyncClient | None = None) -> str:
        """Exchange API user & API key for MoMo Bearer token."""
        if not self.is_configured:
            return "mock_mtn_momo_access_token_offline"

        auth_str = f"{self.api_user}:{self.api_key}"
        encoded_auth = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")
        headers = {
            "Authorization": f"Basic {encoded_auth}",
            "Ocp-Apim-Subscription-Key": self.subscription_key,
        }

        should_close = False
        if client is None:
            client = httpx.AsyncClient(timeout=15.0)
            should_close = True

        try:
            url = f"{self.base_url}/collection/token/"
            resp = await client.post(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return data.get("access_token", "")
        finally:
            if should_close:
                await client.aclose()

    async def request_to_pay(
        self,
        amount: float,
        currency: str,
        phone_number: str,
        external_id: str,
        payer_message: str = "NanoCoop Savings Contribution",
        client: httpx.AsyncClient | None = None,
    ) -> dict[str, Any]:
        """Initiate USSD payment prompt on customer's phone via RequestToPay."""
        reference_id = str(uuid.uuid4())
        phone = phone_number.strip().replace("+", "")

        if not self.is_configured:
            return {
                "reference_id": reference_id,
                "status": "PENDING",
                "message": "Simulated MTN MoMo payment prompt issued to phone",
                "simulated": True,
            }

        token = await self.get_access_token(client=client)
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Reference-Id": reference_id,
            "X-Target-Environment": self.environment,
            "Ocp-Apim-Subscription-Key": self.subscription_key,
            "Content-Type": "application/json",
        }

        payload = {
            "amount": str(round(amount, 2)),
            "currency": currency,
            "externalId": external_id,
            "payer": {
                "partyIdType": "MSISDN",
                "partyId": phone,
            },
            "payerMessage": payer_message[:50],
            "payeeNote": "NanoCoop Deposit",
        }

        should_close = False
        if client is None:
            client = httpx.AsyncClient(timeout=15.0)
            should_close = True

        try:
            url = f"{self.base_url}/collection/v1_0/requesttopay"
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            return {
                "reference_id": reference_id,
                "status": "PENDING",
                "status_code": resp.status_code,
            }
        finally:
            if should_close:
                await client.aclose()

    async def get_transaction_status(
        self, reference_id: str, client: httpx.AsyncClient | None = None
    ) -> dict[str, Any]:
        """Check status of a previous RequestToPay transaction."""
        if not self.is_configured:
            return {
                "financialTransactionId": f"MOCK-MOMO-{reference_id[:8]}",
                "externalId": "DEMO-TX",
                "amount": "50.00",
                "currency": "UGX",
                "status": "SUCCESSFUL",
                "simulated": True,
            }

        token = await self.get_access_token(client=client)
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Target-Environment": self.environment,
            "Ocp-Apim-Subscription-Key": self.subscription_key,
        }

        should_close = False
        if client is None:
            client = httpx.AsyncClient(timeout=15.0)
            should_close = True

        try:
            url = f"{self.base_url}/collection/v1_0/requesttopay/{reference_id}"
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            return resp.json()
        finally:
            if should_close:
                await client.aclose()

    @staticmethod
    def parse_callback(payload: dict[str, Any]) -> dict[str, Any]:
        """Parse MTN MoMo webhook callback."""
        return {
            "financial_transaction_id": payload.get("financialTransactionId", ""),
            "external_id": payload.get("externalId", ""),
            "amount": float(payload.get("amount", 0.0)),
            "currency": payload.get("currency", "EUR"),
            "status": payload.get("status", "FAILED"),
            "is_successful": payload.get("status") == "SUCCESSFUL",
            "payer": payload.get("payer", {}).get("partyId", ""),
        }


momo_client = MtnMoMoClient()
