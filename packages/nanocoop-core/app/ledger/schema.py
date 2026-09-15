"""Data schemas and Pydantic validation models for the NanoCoop Event Ledger."""

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field, field_validator


class EventType(str, Enum):
    DEPOSIT_CASH = "DEPOSIT_CASH"
    WITHDRAWAL_CASH = "WITHDRAWAL_CASH"
    DEPOSIT_MOBILE_MONEY = "DEPOSIT_MOBILE_MONEY"
    LOAN_DISBURSED = "LOAN_DISBURSED"
    LOAN_REPAID = "LOAN_REPAID"
    SOCIAL_FUND_CONTRIBUTION = "SOCIAL_FUND_CONTRIBUTION"
    SOCIAL_FUND_PAYOUT = "SOCIAL_FUND_PAYOUT"
    INTEREST_APPLIED = "INTEREST_APPLIED"


class EventPayload(BaseModel):
    amount: float = Field(..., gt=0, description="Positive transaction amount")
    currency: str = Field(default="USD", min_length=3, max_length=5)
    user_public_key: str = Field(..., min_length=32, description="Ed25519 User public key")
    reference: str | None = Field(default=None, description="External reference (e.g. MPESA code, loan ID)")
    notes: str | None = Field(default=None, description="Optional ledger notes")
    loan_id: str | None = Field(default=None, description="Unique identifier for micro-loan contracts")
    interest_rate: float | None = Field(default=None, ge=0.0, description="Interest rate percentage (e.g. 5.0 for 5%)")
    term_months: int | None = Field(default=None, ge=1, description="Loan repayment duration in months")

    model_config = {"extra": "forbid"}


class EventSignatures(BaseModel):
    teller_sig: str = Field(..., min_length=64, description="Cryptographic signature by teller or gateway")
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
    savings_balance: float
    loan_balance: float
    social_fund_contributions: float
    net_balance: float
    last_activity: int | None
    currency: str = "USD"


class CommunityStats(BaseModel):
    total_balance: float
    total_savings: float
    total_loans_outstanding: float
    total_social_fund: float
    total_capital: float
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


class LoanDisbursementRequest(BaseModel):
    borrower_public_key: str = Field(..., min_length=32)
    amount: float = Field(..., gt=0)
    currency: str = Field(default="USD")
    loan_id: str | None = Field(default=None)
    interest_rate: float = Field(default=5.0, ge=0.0)
    term_months: int = Field(default=3, ge=1)
    notes: str | None = Field(default=None)
    teller_sig: str = Field(..., min_length=64)
    borrower_sig: str = Field(..., min_length=64)


class LoanRepaymentRequest(BaseModel):
    borrower_public_key: str = Field(..., min_length=32)
    amount: float = Field(..., gt=0)
    currency: str = Field(default="USD")
    loan_id: str | None = Field(default=None)
    notes: str | None = Field(default=None)
    teller_sig: str = Field(..., min_length=64)
    borrower_sig: str | None = Field(default=None)


class SocialFundContributionRequest(BaseModel):
    member_public_key: str = Field(..., min_length=32)
    amount: float = Field(..., gt=0)
    currency: str = Field(default="USD")
    notes: str | None = Field(default=None)
    teller_sig: str = Field(..., min_length=64)
    member_sig: str | None = Field(default=None)


class SocialFundPayoutRequest(BaseModel):
    member_public_key: str = Field(..., min_length=32)
    amount: float = Field(..., gt=0)
    currency: str = Field(default="USD")
    purpose: str = Field(..., min_length=3)
    teller_sig: str = Field(..., min_length=64)
    member_sig: str = Field(..., min_length=64)
