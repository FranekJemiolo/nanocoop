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


settings = Settings()
