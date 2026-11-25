import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_env(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env(BASE_DIR / ".env")


class Settings:
    DATABASE_URL: str = os.environ.get("DATABASE_URL", "")
    SESSION_SECRET: str = os.environ.get("SESSION_SECRET", "")
    APP_BASE_URL: str = os.environ.get("APP_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    COOKIE_SECURE: bool = os.environ.get("COOKIE_SECURE", "false").lower() == "true"
    SESSION_DAYS: int = int(os.environ.get("SESSION_DAYS", "30"))
    DEMO_MODE: bool = os.environ.get("DEMO_MODE", "1") == "1"
    SMTP_HOST: str = os.environ.get("SMTP_HOST", "")
    SMTP_PORT: int = int(os.environ.get("SMTP_PORT", "587") or 587)
    SMTP_USER: str = os.environ.get("SMTP_USER", "")
    SMTP_PASSWORD: str = os.environ.get("SMTP_PASSWORD", "")
    SMTP_FROM: str = os.environ.get("SMTP_FROM", "")
    SMTP_TLS: bool = os.environ.get("SMTP_TLS", "true").lower() == "true"

    @property
    def smtp_ready(self) -> bool:
        return bool(self.SMTP_HOST and self.SMTP_FROM)

    def require(self) -> None:
        if not self.DATABASE_URL:
            raise RuntimeError("DATABASE_URL is missing")
        if not self.SESSION_SECRET or len(self.SESSION_SECRET) < 32:
            raise RuntimeError("SESSION_SECRET must be set to at least 32 characters")


settings = Settings()
if not settings.SESSION_SECRET:
    settings.SESSION_SECRET = secrets.token_hex(32)
