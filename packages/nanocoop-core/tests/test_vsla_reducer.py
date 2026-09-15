"""Tests for VSLA domain logic and state reducer."""

import pytest
from app.ledger.reducer import (
    calculate_account_state,
    calculate_all_accounts,
    calculate_community_metrics,
)


def test_calculate_account_state_vsla_lifecycle():
    user_key = "test_user_key_32_characters_long_123"
    other_key = "other_user_key_32_characters_long_456"

    event_log = [
        # 1. Deposit cash to savings
        {
            "event_type": "DEPOSIT_CASH",
            "timestamp": 1000,
            "payload": {"user_public_key": user_key, "amount": 100.0, "currency": "USD"},
        },
        # Event for another user (should be ignored by calculate_account_state)
        {
            "event_type": "DEPOSIT_CASH",
            "timestamp": 1005,
            "payload": {"user_public_key": other_key, "amount": 250.0, "currency": "USD"},
        },
        # 2. Deposit mobile money
        {
            "event_type": "DEPOSIT_MOBILE_MONEY",
            "timestamp": 1010,
            "payload": {"user_public_key": user_key, "amount": 50.0, "currency": "USD"},
        },
        # 3. Cash withdrawal
        {
            "event_type": "WITHDRAWAL_CASH",
            "timestamp": 1020,
            "payload": {"user_public_key": user_key, "amount": 20.0, "currency": "USD"},
        },
        # 4. Interest dividend applied
        {
            "event_type": "INTEREST_APPLIED",
            "timestamp": 1030,
            "payload": {"user_public_key": user_key, "amount": 5.0, "currency": "USD"},
        },
        # 5. Loan disbursed with 10% interest
        {
            "event_type": "LOAN_DISBURSED",
            "timestamp": 1040,
            "payload": {
                "user_public_key": user_key,
                "amount": 200.0,
                "interest_rate": 10.0,
                "loan_id": "L1",
            },
        },
        # 6. Loan repaid partially ($110)
        {
            "event_type": "LOAN_REPAID",
            "timestamp": 1050,
            "payload": {"user_public_key": user_key, "amount": 110.0, "loan_id": "L1"},
        },
        # 7. Social fund contribution ($10)
        {
            "event_type": "SOCIAL_FUND_CONTRIBUTION",
            "timestamp": 1060,
            "payload": {"user_public_key": user_key, "amount": 10.0},
        },
        # 8. Social fund payout grant received
        {
            "event_type": "SOCIAL_FUND_PAYOUT",
            "timestamp": 1070,
            "payload": {"user_public_key": user_key, "amount": 50.0, "notes": "Emergency relief"},
        },
    ]

    state = calculate_account_state(user_key, event_log)

    # savings = 100 + 50 - 20 + 5 = 135.0
    assert state["savings_balance"] == 135.0
    assert state["current_balance"] == 135.0
    # loan = 200 * 1.10 = 220, minus 110 = 110.0
    assert state["loan_balance"] == 110.0
    # social fund contribution = 10.0
    assert state["social_fund_contributions"] == 10.0
    # net balance = 135 - 110 = 25.0
    assert state["net_balance"] == 25.0
    assert state["last_activity"] == 1070


def test_calculate_all_accounts_and_community_metrics():
    u1 = "user_1_public_key_32_chars_long_00"
    u2 = "user_2_public_key_32_chars_long_00"

    event_log = [
        # Event with missing user_public_key to test edge case branch
        {"event_type": "DEPOSIT_CASH", "timestamp": 50, "payload": {}},
        # U1 operations
        {
            "event_type": "DEPOSIT_CASH",
            "timestamp": 100,
            "payload": {"user_public_key": u1, "amount": 300.0},
        },
        {
            "event_type": "WITHDRAWAL_CASH",
            "timestamp": 110,
            "payload": {"user_public_key": u1, "amount": 50.0},
        },
        {
            "event_type": "INTEREST_APPLIED",
            "timestamp": 120,
            "payload": {"user_public_key": u1, "amount": 10.0},
        },
        {
            "event_type": "LOAN_DISBURSED",
            "timestamp": 130,
            "payload": {"user_public_key": u1, "amount": 100.0, "interest_rate": 5.0},
        },
        {
            "event_type": "LOAN_REPAID",
            "timestamp": 140,
            "payload": {"user_public_key": u1, "amount": 50.0},
        },
        {
            "event_type": "SOCIAL_FUND_CONTRIBUTION",
            "timestamp": 150,
            "payload": {"user_public_key": u1, "amount": 15.0},
        },
        {
            "event_type": "SOCIAL_FUND_PAYOUT",
            "timestamp": 160,
            "payload": {"user_public_key": u1, "amount": 10.0},
        },
        # U2 operations
        {
            "event_type": "DEPOSIT_MOBILE_MONEY",
            "timestamp": 200,
            "payload": {"user_public_key": u2, "amount": 500.0},
        },
        {
            "event_type": "SOCIAL_FUND_CONTRIBUTION",
            "timestamp": 210,
            "payload": {"user_public_key": u2, "amount": 25.0},
        },
    ]

    accounts = calculate_all_accounts(event_log)
    assert u1 in accounts
    assert u2 in accounts
    assert accounts[u1]["savings_balance"] == 260.0
    assert accounts[u1]["loan_balance"] == 55.0  # 100*1.05 - 50 = 55.0
    assert accounts[u1]["social_fund_contributions"] == 15.0
    assert accounts[u1]["net_balance"] == 205.0

    assert accounts[u2]["savings_balance"] == 500.0
    assert accounts[u2]["loan_balance"] == 0.0
    assert accounts[u2]["social_fund_contributions"] == 25.0

    metrics = calculate_community_metrics(event_log)
    assert metrics["total_savings"] == 760.0  # 260 + 500
    assert metrics["total_loans_outstanding"] == 55.0
    assert metrics["total_social_fund"] == 30.0  # (15 + 25) - 10 = 30.0
    assert metrics["total_capital"] == 790.0  # 760 + 30
