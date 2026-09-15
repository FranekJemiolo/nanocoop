"""State Reducer pattern for the NanoCoop Event Ledger.

Folds the append-only event stream into deterministic current account balances and community statistics.
"""

from typing import Any


def calculate_account_state(
    user_public_key: str, event_log: list[dict[str, Any]]
) -> dict[str, Any]:
    """Fold event log into a specific user's current account state."""
    balance = 0.0
    last_activity = None

    for event in event_log:
        payload = event.get("payload", {})
        if payload.get("user_public_key") != user_public_key:
            continue

        event_type = event.get("event_type")
        amount = float(payload.get("amount", 0.0))

        if event_type in ("DEPOSIT_CASH", "DEPOSIT_MOBILE_MONEY"):
            balance += amount
        elif event_type == "WITHDRAWAL_CASH":
            balance -= amount
        elif event_type == "INTEREST_APPLIED":
            balance += amount

        last_activity = event.get("timestamp")

    return {
        "user_public_key": user_public_key,
        "current_balance": round(balance, 2),
        "last_activity": last_activity,
        "currency": "USD",
    }


def calculate_all_accounts(event_log: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Fold event log into current balances for all distinct users."""
    accounts: dict[str, dict[str, Any]] = {}

    for event in event_log:
        payload = event.get("payload", {})
        user_key = payload.get("user_public_key")
        if not user_key:
            continue

        if user_key not in accounts:
            accounts[user_key] = {
                "user_public_key": user_key,
                "current_balance": 0.0,
                "last_activity": None,
                "currency": payload.get("currency", "USD"),
            }

        event_type = event.get("event_type")
        amount = float(payload.get("amount", 0.0))

        if event_type in ("DEPOSIT_CASH", "DEPOSIT_MOBILE_MONEY"):
            accounts[user_key]["current_balance"] += amount
        elif event_type == "WITHDRAWAL_CASH":
            accounts[user_key]["current_balance"] -= amount
        elif event_type == "INTEREST_APPLIED":
            accounts[user_key]["current_balance"] += amount

        accounts[user_key]["current_balance"] = round(accounts[user_key]["current_balance"], 2)
        accounts[user_key]["last_activity"] = event.get("timestamp")

    return accounts
