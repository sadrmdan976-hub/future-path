import re

import psycopg
from fastapi import APIRouter, Request

from ..config import settings
from ..content import UNIVERSITIES
from ..db import tx
from ..security import (
    attempts_count,
    burn_time,
    clear_attempts,
    hash_password,
    new_token,
    note_attempt,
    password_problem,
    sha256_hex,
    verify_password,
)
from ..web import (
    CSRF_COOKIE,
    SESSION_COOKIE,
    client_ip,
    current_user,
    flash,
    redirect,
    render,
    require_user,
    safe_next,
    send_email,
    verify_csrf,
)

router = APIRouter(prefix="/auth")
account_router = APIRouter()

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")


def _start_session(conn, user_id, request) -> tuple[str, str]:
    token = new_token()
    csrf = new_token()
    expires = conn.execute("select now() + interval '30 days' as at").fetchone()["at"]
    conn.execute(
        "select future_path.fp_create_session(%s, %s, %s, %s, %s, %s)",
        (
            user_id,
            sha256_hex(token),
            csrf,
            expires,
            request.headers.get("user-agent", ""),
            client_ip(request),
        ),
    )
    return token, csrf


def _set_session_cookie(response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.SESSION_DAYS * 86400,
        httponly=True,
        samesite="lax",
        secure=settings.COOKIE_SECURE,
        path="/",
    )


@router.get("/login")
def login_form(request: Request, next: str = ""):
    if current_user(request):
        return redirect("/dashboard")
    return render(request, "auth/login.html", next=safe_next(next), error=None, email="")


@router.post("/login")
async def login_submit(request: Request):
    form = await request.form()
    verify_csrf(request, form.get("csrf"))
    email = (form.get("email") or "").strip().lower()
    password = form.get("password") or ""
    next_path = safe_next(form.get("next"))

    ip = client_ip(request)
    if attempts_count(f"login-ip:{ip}") >= 10 or attempts_count(f"login-email:{email}") >= 8:
        return render(
            request,
            "auth/login.html",
            next=next_path,
            email=email,
            error="محاولات كثيرة خلال وقت قصير. انتظر عشر دقائق ثم أعد المحاولة.",
            status_code=429,
        )

    with tx() as conn:
        row = conn.execute(
            "select * from future_path.fp_login_lookup(%s)", (email,)
        ).fetchone()
        if not row:
            burn_time(password)
            note_attempt(f"login-ip:{ip}")
            note_attempt(f"login-email:{email}")
            return render(
                request,
                "auth/login.html",
                next=next_path,
                email=email,
                error="البريد الإلكتروني أو كلمة المرور غير صحيحة.",
                status_code=401,
            )
        if not verify_password(password, row["password_hash"]):
            note_attempt(f"login-ip:{ip}")
            note_attempt(f"login-email:{email}")
            return render(
                request,
                "auth/login.html",
                next=next_path,
                email=email,
                error="البريد الإلكتروني أو كلمة المرور غير صحيحة.",
                status_code=401,
            )
        if not row["is_active"]:
            return render(
                request,
                "auth/login.html",
                next=next_path,
                email=email,
                error="هذا الحساب موقوف حالياً. تواصل مع إدارة المنصة.",
                status_code=403,
            )
        clear_attempts(f"login-ip:{ip}")
        clear_attempts(f"login-email:{email}")
        token, _ = _start_session(conn, row["id"], request)
        conn.execute(
            "select set_config('app.user_id', %s, true)", (str(row["id"]),)
        )
        is_admin = conn.execute(
            "select future_path.fp_is_admin() as ok"
        ).fetchone()["ok"]

    target = next_path or ("/admin" if is_admin else "/dashboard")
    response = redirect(target)
    _set_session_cookie(response, token)
    return flash(response, request, f"أهلاً بك، {row['full_name']}.")


@router.get("/register")
def register_form(request: Request):
    if current_user(request):
        return redirect("/dashboard")
    return render(
        request,
        "auth/register.html",
        error=None,
        form={"full_name": "", "email": ""},
        universities=UNIVERSITIES,
    )


@router.post("/register")
async def register_submit(request: Request):
    form = await request.form()
    verify_csrf(request, form.get("csrf"))
    full_name = (form.get("full_name") or "").strip()
    email = (form.get("email") or "").strip().lower()
    password = form.get("password") or ""
    confirm = form.get("confirm") or ""
    accepted = form.get("terms") == "on"

    def fail(message: str, code: int = 400):
        return render(
            request,
            "auth/register.html",
            error=message,
            form={"full_name": full_name, "email": email},
            universities=UNIVERSITIES,
            status_code=code,
        )

    ip = client_ip(request)
    if attempts_count(f"reg:{ip}") >= 6:
        return fail("تم إنشاء محاولات كثيرة من هذا الجهاز. انتظر قليلاً ثم أعد المحاولة.", 429)
    if len(full_name) < 2 or len(full_name) > 120:
        return fail("أدخل الاسم الكامل (حرفان على الأقل).")
    if not EMAIL_RE.match(email):
        return fail("أدخل بريداً إلكترونياً صحيحاً.")
    problem = password_problem(password)
    if problem:
        return fail(problem)
    if password != confirm:
        return fail("كلمتا المرور غير متطابقتين.")
    if not accepted:
        return fail("يجب الموافقة على سياسة الخصوصية وشروط الاستخدام التجريبية.")

    password_hash = hash_password(password)
    with tx() as conn:
        try:
            user_id = conn.execute(
                "select future_path.fp_create_user(%s, %s, %s) as id",
                (email, password_hash, full_name),
            ).fetchone()["id"]
        except psycopg.errors.UniqueViolation:
            note_attempt(f"reg:{ip}")
            return fail("هذا البريد مسجل مسبقاً. جرّب تسجيل الدخول.", 409)
        token, _ = _start_session(conn, user_id, request)

    response = redirect("/dashboard")
    _set_session_cookie(response, token)
    return flash(response, request, "تم إنشاء حسابك بنجاح. أكمل ملفك المهني لتزيد فرصك.")


@router.post("/logout")
async def logout(request: Request):
    form = await request.form()
    verify_csrf(request, form.get("csrf"))
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        with tx() as conn:
            conn.execute("select future_path.fp_delete_session(%s)", (sha256_hex(token),))
    response = redirect("/")
    response.delete_cookie(SESSION_COOKIE, path="/")
    return flash(response, request, "تم تسجيل الخروج بنجاح.")


@router.get("/forgot")
def forgot_form(request: Request):
    return render(request, "auth/forgot.html", sent=False)


@router.post("/forgot")
async def forgot_submit(request: Request):
    form = await request.form()
    verify_csrf(request, form.get("csrf"))
    email = (form.get("email") or "").strip().lower()
    ip = client_ip(request)
    if attempts_count(f"forgot:{ip}") >= 5:
        return render(request, "auth/forgot.html", sent=True, throttled=True)

    note_attempt(f"forgot:{ip}")
    reset_token = new_token()
    delivered = False
    if EMAIL_RE.match(email):
        with tx() as conn:
            exists = conn.execute(
                "select future_path.fp_request_reset(%s, %s, now() + interval '1 hour') as ok",
                (email, sha256_hex(reset_token)),
            ).fetchone()["ok"]
        if exists and settings.smtp_ready:
            link = f"{settings.APP_BASE_URL}/auth/reset/{reset_token}"
            delivered = send_email(
                email,
                "استعادة كلمة المرور — FUTURE PATH",
                "مرحباً،\n\nلإعادة تعيين كلمة المرور افتح الرابط التالي خلال ساعة:\n"
                f"{link}\n\nإذا لم تطلب ذلك تجاهل الرسالة.\n",
            )
    return render(request, "auth/forgot.html", sent=True, delivered=delivered, smtp_ready=settings.smtp_ready)


@router.get("/reset/{token}")
def reset_form(request: Request, token: str):
    return render(request, "auth/reset.html", token=token, error=None)


@router.post("/reset/{token}")
async def reset_submit(request: Request, token: str):
    form = await request.form()
    verify_csrf(request, form.get("csrf"))
    password = form.get("password") or ""
    confirm = form.get("confirm") or ""
    problem = password_problem(password)
    if problem:
        return render(request, "auth/reset.html", token=token, error=problem, status_code=400)
    if password != confirm:
        return render(request, "auth/reset.html", token=token, error="كلمتا المرور غير متطابقتين.", status_code=400)

    new_hash = hash_password(password)
    with tx() as conn:
        user_id = conn.execute(
            "select future_path.fp_consume_reset(%s) as user_id", (sha256_hex(token),)
        ).fetchone()["user_id"]
        if not user_id:
            return render(
                request,
                "auth/reset.html",
                token=token,
                error="الرابط غير صالح أو انتهت صلاحيته. اطلب رابطاً جديداً.",
                status_code=400,
            )
        conn.execute("select future_path.fp_set_password(%s, %s)", (user_id, new_hash))
    response = redirect("/auth/login")
    return flash(response, request, "تم تعيين كلمة المرور. سجّل الدخول بكلمة المرور الجديدة.", "ok")


@account_router.get("/account")
def account_page(request: Request):
    user = require_user(request)
    return render(request, "auth/account.html", error=None)


@account_router.post("/account/password")
async def account_change_password(request: Request):
    user = require_user(request)
    form = await request.form()
    verify_csrf(request, form.get("csrf"))
    current = form.get("current") or ""
    new_password = form.get("password") or ""
    confirm = form.get("confirm") or ""
    if new_password != confirm:
        return render(request, "auth/account.html", error="كلمتا المرور الجديدتان غير متطابقتين.", status_code=400)
    problem = password_problem(new_password)
    if problem:
        return render(request, "auth/account.html", error=problem, status_code=400)

    with tx(user.id) as conn:
        row = conn.execute(
            "select * from future_path.fp_login_lookup(%s)", (user.email,)
        ).fetchone()
        if not row or not verify_password(current, row["password_hash"]):
            return render(request, "auth/account.html", error="كلمة المرور الحالية غير صحيحة.", status_code=400)
        conn.execute(
            "select future_path.fp_set_password(%s, %s)", (user.id, hash_password(new_password))
        )
    response = redirect("/auth/login")
    response.delete_cookie(SESSION_COOKIE, path="/")
    return flash(response, request, "تم تحديث كلمة المرور وتسجيل الخروج من كل الأجهزة. سجّل الدخول من جديد.")
