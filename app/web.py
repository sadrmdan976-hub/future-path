import logging
import smtplib
import ssl
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from urllib.parse import quote

from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware

from . import content
from .config import BASE_DIR, settings
from .db import tx
from .security import new_token, sha256_hex, sign_payload, unsign_payload

log = logging.getLogger("futurepath")

SESSION_COOKIE = "fp_session"
CSRF_COOKIE = "fp_csrf"
FLASH_COOKIE = "fp_flash"

templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))
templates.env.filters["ar_date"] = content.fmt_date
templates.env.filters["ar_datetime"] = content.fmt_datetime
templates.env.filters["days_left"] = content.days_left


@dataclass
class SessionUser:
    id: str
    email: str
    full_name: str
    account_type: str
    is_admin: bool
    is_demo: bool
    csrf: str

    @property
    def first_name(self) -> str:
        return (self.full_name or "").split(" ")[0]


class RedirectLogin(Exception):
    def __init__(self, next_path: str):
        self.next_path = next_path


class SessionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/static/"):
            response = await call_next(request)
            _security_headers(response)
            return response

        request.state.user = None
        request.state.csrf = None
        request.state.flashes = []

        flash_data = unsign_payload(request.cookies.get(FLASH_COOKIE))
        if flash_data and isinstance(flash_data.get("items"), list):
            request.state.flashes = [
                f for f in flash_data["items"]
                if isinstance(f, dict) and isinstance(f.get("message"), str)
            ][-4:]

        token = request.cookies.get(SESSION_COOKIE)
        if token:
            try:
                self._load_user(request, token)
            except Exception:
                log.exception("session lookup failed")

        set_csrf_cookie = False
        if request.state.user is not None:
            request.state.csrf = request.state.user.csrf
        else:
            cookie_csrf = request.cookies.get(CSRF_COOKIE)
            if cookie_csrf:
                request.state.csrf = cookie_csrf
            else:
                request.state.csrf = new_token()
                set_csrf_cookie = True

        response = await call_next(request)

        if set_csrf_cookie:
            response.set_cookie(
                CSRF_COOKIE,
                request.state.csrf,
                max_age=60 * 60 * 24,
                httponly=True,
                samesite="lax",
                secure=settings.COOKIE_SECURE,
                path="/",
            )
        if request.cookies.get(FLASH_COOKIE):
            response.delete_cookie(FLASH_COOKIE, path="/")
        _security_headers(response)
        return response

    def _load_user(self, request: Request, token: str) -> None:
        token_digest = sha256_hex(token)
        with tx() as conn:
            row = conn.execute(
                "select * from future_path.fp_get_session(%s)", (token_digest,)
            ).fetchone()
            if not row:
                return
            user_id = row["user_id"]
            conn.execute(
                "select set_config('app.user_id', %s, true)", (str(user_id),)
            )
            user = conn.execute(
                """
                select id, email, full_name, account_type, is_active, is_demo,
                       future_path.fp_is_admin() as is_admin
                from future_path.users where id = %s
                """,
                (user_id,),
            ).fetchone()
            if not user or not user["is_active"]:
                conn.execute("select future_path.fp_delete_session(%s)", (token_digest,))
                return
            stale_before = datetime.now(timezone.utc) - timedelta(hours=1)
            if row["last_seen_at"] < stale_before:
                conn.execute("select future_path.fp_touch_session(%s)", (token_digest,))
            request.state.user = SessionUser(
                id=str(user["id"]),
                email=user["email"],
                full_name=user["full_name"],
                account_type=user["account_type"],
                is_admin=bool(user["is_admin"]),
                is_demo=bool(user["is_demo"]),
                csrf=row["csrf_token"],
            )


def _security_headers(response: Response) -> None:
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; img-src 'self' data:; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src https://fonts.gstatic.com; script-src 'self' 'unsafe-inline'; "
        "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
    )
    if settings.APP_BASE_URL.startswith("https://"):
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=15552000; includeSubDomains"
        )


def ctx(request: Request, **extra) -> dict:
    base = {
        "request": request,
        "user": getattr(request.state, "user", None),
        "csrf": getattr(request.state, "csrf", "") or "",
        "flashes": getattr(request.state, "flashes", []),
        "path": request.url.path,
        "demo_mode": settings.DEMO_MODE,
        "DEMO_NOTICE": content.DEMO_NOTICE,
        "app_base_url": settings.APP_BASE_URL,
        "labels": {
            "OPP_TYPE": content.OPP_TYPE,
            "WORK_MODE": content.WORK_MODE,
            "OPP_STATUS": content.OPP_STATUS,
            "APP_STATUS": content.APP_STATUS,
            "BADGE": content.BADGE_CLASS,
            "SKILL_LEVELS": content.SKILL_LEVELS,
            "PROFICIENCY": content.PROFICIENCY,
            "CATEGORIES": content.CATEGORIES,
            "PATH_LEVEL": content.PATH_LEVEL,
            "STUDY_YEARS": content.STUDY_YEARS,
            "CITIES": content.CITIES,
            "FIELDS": content.FIELDS,
            "UNIVERSITIES": content.UNIVERSITIES,
        },
    }
    base.update(extra)
    return base


def render(request: Request, name: str, status_code: int = 200, **extra):
    return templates.TemplateResponse(
        request=request, name=name, context=ctx(request, **extra), status_code=status_code
    )


def redirect(url: str, status_code: int = 303) -> RedirectResponse:
    return RedirectResponse(url=url, status_code=status_code)


def flash(response: Response, request: Request, message: str, kind: str = "ok") -> Response:
    items = list(getattr(request.state, "flashes", []))
    items.append({"message": message, "kind": kind})
    response.set_cookie(
        FLASH_COOKIE,
        sign_payload({"items": items[-4:]}),
        max_age=180,
        httponly=True,
        samesite="lax",
        secure=settings.COOKIE_SECURE,
        path="/",
    )
    _security_headers(response)
    return response


def current_user(request: Request) -> SessionUser | None:
    return getattr(request.state, "user", None)


def require_user(request: Request) -> SessionUser:
    user = current_user(request)
    if user is None:
        raise RedirectLogin(request.url.path + (("?" + request.url.query) if request.url.query else ""))
    return user


def require_admin(request: Request) -> SessionUser:
    user = require_user(request)
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="admin-only")
    return user


def verify_csrf(request: Request, token: str | None) -> None:
    expected = getattr(request.state, "csrf", None)
    if not expected or not token:
        raise HTTPException(status_code=403, detail="csrf")
    import hmac

    if not hmac.compare_digest(str(token), str(expected)):
        raise HTTPException(status_code=403, detail="csrf")


def login_url(next_path: str = "") -> str:
    if next_path:
        return f"/auth/login?next={quote(next_path)}"
    return "/auth/login"


def safe_next(value: str | None) -> str:
    if value and value.startswith("/") and not value.startswith("//"):
        return value
    return ""


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    return (request.client.host if request.client else "")[:64]


def send_email(to: str, subject: str, body: str) -> bool:
    if not settings.smtp_ready:
        return False
    try:
        message = EmailMessage()
        message["From"] = settings.SMTP_FROM
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)
        context = ssl.create_default_context()
        if settings.SMTP_PORT == 465:
            with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, context=context, timeout=15) as server:
                if settings.SMTP_USER:
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.send_message(message)
        else:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as server:
                if settings.SMTP_TLS:
                    server.starttls(context=context)
                if settings.SMTP_USER:
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.send_message(message)
        return True
    except Exception:
        log.exception("email send failed")
        return False
