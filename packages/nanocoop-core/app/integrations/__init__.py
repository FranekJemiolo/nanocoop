"""Telecom and Mobile Money integrations package for NanoCoop."""

from app.integrations.daraja import DarajaClient, daraja_client
from app.integrations.mtn_momo import MtnMoMoClient, momo_client
from app.integrations.africas_talking import AfricasTalkingClient, africas_talking_client
from app.integrations.airtel_money import AirtelMoneyClient, airtel_client
from app.integrations.orange_money import OrangeMoneyClient, orange_client
from app.integrations.wave import WaveClient, wave_client

__all__ = [
    "DarajaClient",
    "daraja_client",
    "MtnMoMoClient",
    "momo_client",
    "AfricasTalkingClient",
    "africas_talking_client",
    "AirtelMoneyClient",
    "airtel_client",
    "OrangeMoneyClient",
    "orange_client",
    "WaveClient",
    "wave_client",
]
