import base64
import hashlib
import hmac
import json
import secrets
import threading
import time
from collections import defaultdict, deque

from .config import settings

_SCRYPT_N = 16384
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_DKLEN = 64
_SCRYPT_MAXMEM = 64 * 1024 * 1024


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_SCRYPT_DKLEN,
        maxmem=_SCRYPT_MAXMEM,
    )
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${salt.hex()}${digest.hex()}"


_DUMMY_HASH = hash_password("timing-equalizer-not-a-real-password")


def verify_password(password: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        scheme, n, r, p, salt_hex, digest_hex = stored.split("$")
        if scheme != "scrypt":
            return False
        digest = hashlib.scrypt(
            password.encode("utf-8"),
            salt=bytes.fromhex(salt_hex),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(bytes.fromhex(digest_hex)),
            maxmem=_SCRYPT_MAXMEM,
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def burn_time(password: str) -> None:
    """Constant-ish work when the account does not exist, to avoid user probing."""
    verify_password(password, _DUMMY_HASH)


def new_token() -> str:
    return secrets.token_urlsafe(32)


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sign(raw: bytes) -> str:
    mac = hmac.new(settings.SESSION_SECRET.encode("utf-8"), raw, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(mac).decode("ascii").rstrip("=")


def sign_payload(data: dict) -> str:
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    body = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    return f"{body}.{_sign(raw)}"


def unsign_payload(value: str | None) -> dict | None:
    if not value or "." not in value:
        return None
    body, signature = value.rsplit(".", 1)
    try:
        padded = body + "=" * (-len(body) % 4)
        raw = base64.urlsafe_b64decode(padded.encode("ascii"))
    except (ValueError, TypeError):
        return None
    if not hmac.compare_digest(_sign(raw), signature):
        return None
    try:
        data = json.loads(raw.decode("utf-8"))
        return data if isinstance(data, dict) else None
    except (ValueError, UnicodeDecodeError):
        return None


_lock = threading.Lock()
_attempts: dict[str, deque] = defaultdict(deque)


def note_attempt(key: str, window_seconds: int = 600) -> None:
    now = time.time()
    with _lock:
        bucket = _attempts[key]
        bucket.append(now)
        while bucket and bucket[0] < now - window_seconds:
            bucket.popleft()


def attempts_count(key: str, window_seconds: int = 600) -> int:
    now = time.time()
    with _lock:
        bucket = _attempts[key]
        while bucket and bucket[0] < now - window_seconds:
            bucket.popleft()
        return len(bucket)


def clear_attempts(key: str) -> None:
    with _lock:
        _attempts.pop(key, None)


def password_problem(password: str) -> str | None:
    if len(password) < 8:
        return "كلمة المرور يجب ألا تقل عن 8 أحرف."
    if len(password) > 128:
        return "كلمة المرور طويلة جداً."
    if not any(ch.isalpha() for ch in password) or not any(ch.isdigit() for ch in password):
        return "استخدم حروفاً وأرقاماً معاً في كلمة المرور."
    return None
