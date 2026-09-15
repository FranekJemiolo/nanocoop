"""Application configuration management for NanoCoop Core."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load local .env if present
env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)


class Settings:
    PORT: int = int(os.getenv("NANOCOOP_PORT", "8000"))
    HOST: str = os.getenv("NANOCOOP_HOST", "0.0.0.0")
    DB_PATH: str = os.getenv("NANOCOOP_DB_PATH", "nanocoop.db")
    DEBUG: bool = os.getenv("NANOCOOP_DEBUG", "false").lower() in ("true", "1")
    TELLER_PUBLIC_KEY: str = os.getenv("TELLER_PUBLIC_KEY", "")

    # Safaricom Daraja M-Pesa
    MPESA_ENVIRONMENT: str = os.getenv("MPESA_ENVIRONMENT", "sandbox")
    MPESA_CONSUMER_KEY: str = os.getenv("MPESA_CONSUMER_KEY", "")
    MPESA_CONSUMER_SECRET: str = os.getenv("MPESA_CONSUMER_SECRET", "")
    MPESA_PASSKEY: str = os.getenv("MPESA_PASSKEY", "")
    MPESA_SHORTCODE: str = os.getenv("MPESA_SHORTCODE", "174379")
    MPESA_CALLBACK_URL: str = os.getenv(
        "MPESA_CALLBACK_URL", "https://api.nanocoop.org/api/v1/integrations/mpesa/stk-callback"
    )

    # MTN Mobile Money Open API
    MTN_MOMO_ENVIRONMENT: str = os.getenv("MTN_MOMO_ENVIRONMENT", "sandbox")
    MTN_MOMO_SUBSCRIPTION_KEY: str = os.getenv("MTN_MOMO_SUBSCRIPTION_KEY", "")
    MTN_MOMO_API_USER: str = os.getenv("MTN_MOMO_API_USER", "")
    MTN_MOMO_API_KEY: str = os.getenv("MTN_MOMO_API_KEY", "")

    # Africa's Talking SMS Gateway
    AFRICASTALKING_USERNAME: str = os.getenv("AFRICASTALKING_USERNAME", "sandbox")
    AFRICASTALKING_API_KEY: str = os.getenv("AFRICASTALKING_API_KEY", "")
    AFRICASTALKING_SENDER_ID: str = os.getenv("AFRICASTALKING_SENDER_ID", "")

    # Airtel Money Africa
    AIRTEL_CLIENT_ID: str = os.getenv("AIRTEL_CLIENT_ID", "")
    AIRTEL_CLIENT_SECRET: str = os.getenv("AIRTEL_CLIENT_SECRET", "")
    AIRTEL_COUNTRY: str = os.getenv("AIRTEL_COUNTRY", "KE")
    AIRTEL_CURRENCY: str = os.getenv("AIRTEL_CURRENCY", "KES")
    AIRTEL_ENVIRONMENT: str = os.getenv("AIRTEL_ENVIRONMENT", "staging")

    # Orange Money Africa
    ORANGE_CLIENT_ID: str = os.getenv("ORANGE_CLIENT_ID", "")
    ORANGE_CLIENT_SECRET: str = os.getenv("ORANGE_CLIENT_SECRET", "")
    ORANGE_MERCHANT_KEY: str = os.getenv("ORANGE_MERCHANT_KEY", "")
    ORANGE_ENVIRONMENT: str = os.getenv("ORANGE_ENVIRONMENT", "sandbox")

    # Wave Mobile Money
    WAVE_API_KEY: str = os.getenv("WAVE_API_KEY", "")
    WAVE_WEBHOOK_SECRET: str = os.getenv("WAVE_WEBHOOK_SECRET", "")
    WAVE_ENVIRONMENT: str = os.getenv("WAVE_ENVIRONMENT", "sandbox")

    # Automated Integration Server Signer Key (for signing validated webhook transactions)
    GATEWAY_PRIVATE_KEY: str = os.getenv("GATEWAY_PRIVATE_KEY", "")


settings = Settings()
