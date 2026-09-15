"""Data schemas and Pydantic validation models for the NanoCoop Event Ledger."""

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field, field_validator


class EventType(str, Enum):
    DEPOSIT_CASH = "DEPOSIT_CASH"
    WITHDRAWAL_CASH = "WITHDRAWAL_CASH"
    DEPOSIT_MOBILE_MONEY = "DEPOSIT_MOBILE_MONEY"
    INTEREST_APPLIED = "INTEREST_APPLIED"


class EventPayload(BaseModel):
    amount: float = Field(..., gt=0, description="Positive transaction amount")
    currency: str = Field(default="USD", min_length=3, max_length=5)
    user_public_key: str = Field(..., min_length=32, description="Ed25519 User public key")
    reference: str | None = Field(default=None, description="External reference (e.g. MPESA code)")
    notes: str | None = Field(default=None, description="Optional ledger notes")

    model_config = {"extra": "forbid"}


class EventSignatures(BaseModel):
    teller_sig: str = Field(..., min_length=64, description="Cryptographic signature by teller")
    user_sig: str | None = Field(
        default=None, description="Cryptographic signature by user via NFC/QR"
    )

    model_config = {"extra": "forbid"}


class EventModel(BaseModel):
    event_id: str = Field(..., description="UUID v4 identifier")
    timestamp: int = Field(..., description="Unix timestamp (seconds)")
    event_type: EventType
    payload: EventPayload
    previous_hash: str = Field(..., description="SHA-256 hash of previous event")
    signatures: EventSignatures
    current_hash: str = Field(..., description="SHA-256 hash of this event")

    @field_validator("event_id")
    @classmethod
    def validate_event_id(cls, v: str) -> str:
        if not v or len(v.strip()) < 8:
            raise ValueError("Invalid event_id")
        return v.strip()


class AccountState(BaseModel):
    user_public_key: str
    current_balance: float
    last_activity: int | None
    currency: str = "USD"


class CommunityStats(BaseModel):
    total_balance: float
    total_members: int
    total_events: int
    merkle_root: str
    is_chain_valid: bool


class AuditVerification(BaseModel):
    is_valid: bool
    total_events: int
    merkle_root: str
    last_hash: str
    tamper_details: str | None = None


class PaginatedEvents(BaseModel):
    events: list[EventModel]
    next_cursor: int | None
    has_more: bool
    total_count: int


class MobileMoneyWebhookPayload(BaseModel):
    transaction_code: str = Field(..., min_length=4, description="Unique telecom receipt ID")
    sender_phone: str = Field(..., min_length=5)
    amount: float = Field(..., gt=0)
    currency: str = Field(default="USD")
    user_public_key: str = Field(..., min_length=32)
    timestamp: int = Field(..., description="Receipt timestamp")
    gateway_signature: str = Field(..., min_length=64)
