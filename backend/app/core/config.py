"""NumberShield configuration module.
Loads settings from environment variables with safe, localhost-first defaults.
"""

import os
from pathlib import Path
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


class Settings(BaseModel):
    app_name: str = "NumberShield"
    version: str = "1.0.0"
    host: str = os.getenv("NUMBERSHIELD_HOST", "127.0.0.1")
    port: int = int(os.getenv("NUMBERSHIELD_PORT", "8765"))
    db_path: Path = Path(os.getenv("NUMBERSHIELD_DB_PATH", str(DATA_DIR / "numbershield.db")))
    key_path: Path = Path(os.getenv("NUMBERSHIELD_KEY_PATH", str(DATA_DIR / ".numbershield_key")))
    searxng_instance: str = os.getenv("SEARXNG_INSTANCE_URL", "").strip()
    request_timeout: float = float(os.getenv("NUMBERSHIELD_REQUEST_TIMEOUT_SECONDS", "10.0"))
    max_response_size: int = int(os.getenv("NUMBERSHIELD_MAX_RESPONSE_SIZE_BYTES", "5242880"))
    polite_delay: float = float(os.getenv("NUMBERSHIELD_POLITE_DELAY_SECONDS", "1.5"))
    log_level: str = os.getenv("LOG_LEVEL", "INFO")


settings = Settings()
