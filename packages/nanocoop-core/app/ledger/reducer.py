"""State Reducer pattern for the NanoCoop Event Ledger.

Folds the append-only event stream into deterministic current account balances, loan portfolios,
social welfare funds, and community statistics.
"""

from typing import Any


def calculate_account_state(
    user_public_key: str, event_log: list[dict[str, Any]]
) -> dict[str, Any]:
    """Fold event log into a specific user's current account state."""
    savings_balance = 0.0
    loan_balance = 0.0
    social_contributions = 0.0
    last_activity = None

    for event in event_log:
        payload = event.get("payload", {})
        if payload.get("user_public_key") != user_public_key:
            continue

        event_type = event.get("event_type")
        amount = float(payload.get("amount", 0.0))

        if event_type in ("DEPOSIT_CASH", "DEPOSIT_MOBILE_MONEY"):
            savings_balance += amount
        elif event_type == "WITHDRAWAL_CASH":
            savings_balance -= amount
        elif event_type == "INTEREST_APPLIED":
            savings_balance += amount
        elif event_type == "LOAN_DISBURSED":
            interest_rate = float(payload.get("interest_rate", 0.0) or 0.0)
            accrued_total = amount * (1.0 + (interest_rate / 100.0))
            loan_balance += accrued_total
        elif event_type == "LOAN_REPAID":
            loan_balance = max(0.0, loan_balance - amount)
        elif event_type == "SOCIAL_FUND_CONTRIBUTION":
            social_contributions += amount
        elif event_type == "SOCIAL_FUND_PAYOUT":
            # Social emergency fund grant paid to member; does not alter personal savings balance
            pass

        last_activity = event.get("timestamp")

    savings_balance = round(savings_balance, 2)
    loan_balance = round(loan_balance, 2)
    social_contributions = round(social_contributions, 2)
    net_balance = round(savings_balance - loan_balance, 2)

    return {
        "user_public_key": user_public_key,
        "current_balance": savings_balance,
        "savings_balance": savings_balance,
        "loan_balance": loan_balance,
        "social_fund_contributions": social_contributions,
        "net_balance": net_balance,
        "last_activity": last_activity,
        "currency": "USD",
    }


def calculate_all_accounts(event_log: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Fold event log into current states for all distinct users."""
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
                "savings_balance": 0.0,
                "loan_balance": 0.0,
                "social_fund_contributions": 0.0,
                "net_balance": 0.0,
                "last_activity": None,
                "currency": payload.get("currency", "USD"),
            }

        event_type = event.get("event_type")
        amount = float(payload.get("amount", 0.0))

        if event_type in ("DEPOSIT_CASH", "DEPOSIT_MOBILE_MONEY"):
            accounts[user_key]["savings_balance"] += amount
        elif event_type == "WITHDRAWAL_CASH":
            accounts[user_key]["savings_balance"] -= amount
        elif event_type == "INTEREST_APPLIED":
            accounts[user_key]["savings_balance"] += amount
        elif event_type == "LOAN_DISBURSED":
            interest_rate = float(payload.get("interest_rate", 0.0) or 0.0)
            accrued_total = amount * (1.0 + (interest_rate / 100.0))
            accounts[user_key]["loan_balance"] += accrued_total
        elif event_type == "LOAN_REPAID":
            accounts[user_key]["loan_balance"] = max(
                0.0, accounts[user_key]["loan_balance"] - amount
            )
        elif event_type == "SOCIAL_FUND_CONTRIBUTION":
            accounts[user_key]["social_fund_contributions"] += amount
        elif event_type == "SOCIAL_FUND_PAYOUT":
            pass

        accounts[user_key]["savings_balance"] = round(accounts[user_key]["savings_balance"], 2)
        accounts[user_key]["current_balance"] = accounts[user_key]["savings_balance"]
        accounts[user_key]["loan_balance"] = round(accounts[user_key]["loan_balance"], 2)
        accounts[user_key]["social_fund_contributions"] = round(
            accounts[user_key]["social_fund_contributions"], 2
        )
        accounts[user_key]["net_balance"] = round(
            accounts[user_key]["savings_balance"] - accounts[user_key]["loan_balance"], 2
        )
        accounts[user_key]["last_activity"] = event.get("timestamp")

    return accounts


def calculate_community_metrics(event_log: list[dict[str, Any]]) -> dict[str, float]:
    """Calculate community-wide VSLA financial metrics: savings, loans, and welfare safety net."""
    total_savings = 0.0
    total_loans = 0.0
    total_social = 0.0

    all_accounts = calculate_all_accounts(event_log)
    for acc in all_accounts.values():
        total_savings += acc["savings_balance"]
        total_loans += acc["loan_balance"]

    for event in event_log:
        etype = event.get("event_type")
        amt = float(event.get("payload", {}).get("amount", 0.0))
        if etype == "SOCIAL_FUND_CONTRIBUTION":
            total_social += amt
        elif etype == "SOCIAL_FUND_PAYOUT":
            total_social = max(0.0, total_social - amt)

    total_savings = round(total_savings, 2)
    total_loans = round(total_loans, 2)
    total_social = round(total_social, 2)
    total_capital = round(total_savings + total_social, 2)

    return {
        "total_savings": total_savings,
        "total_loans_outstanding": total_loans,
        "total_social_fund": total_social,
        "total_capital": total_capital,
    }
