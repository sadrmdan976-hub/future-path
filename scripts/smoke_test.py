"""End-to-end smoke test against a running local server.

Usage:
    .venv/Scripts/python.exe scripts/smoke_test.py [http://127.0.0.1:8000]

Reads demo passwords from the private Desktop credentials file. Prints only
PASS/FAIL lines — never the credentials themselves.
"""
from __future__ import annotations

import http.cookiejar
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.config import settings  # noqa: E402

BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:8000"
CREDS = Path.home() / "Desktop" / "FUTURE PATH - بيانات الدخول.txt"
CSRF_RE = re.compile(r'name="csrf" value="([^"]+)"')
RESET_RE = re.compile(r'value="(https?://[^"]*/auth/reset/[^"]+)"')
OPP_RE = re.compile(r'href="(/opportunities/[0-9a-f-]{36})"')

results: list[tuple[bool, str]] = []


def check(ok: bool, label: str) -> None:
    results.append((bool(ok), label))
    print(("PASS  " if ok else "FAIL  ") + label)


def read_credentials() -> dict[str, str]:
    text = CREDS.read_text(encoding="utf-8")
    passwords = re.findall(r"كلمة المرور:\s*(\S+)", text)
    if len(passwords) < 3:
        raise SystemExit("Credentials file is missing passwords.")
    return {"student": passwords[0], "admin": passwords[1], "student2": passwords[2]}


class Session:
    def __init__(self) -> None:
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.last_url = ""

    def request(self, method: str, path: str, data: list[tuple[str, str]] | dict | None = None,
                follow: bool = True) -> tuple[int, str]:
        url = path if path.startswith("http") else BASE + path
        body = None
        if data is not None:
            body = urllib.parse.urlencode(data, encoding="utf-8").encode()
        req = urllib.request.Request(url, data=body, method=method)
        if body is not None:
            req.add_header("Content-Type", "application/x-www-form-urlencoded")
        try:
            with self.opener.open(req) as resp:
                self.last_url = resp.geturl()
                return resp.status, resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            self.last_url = exc.geturl()
            return exc.code, exc.read().decode("utf-8", "replace")

    def get(self, path: str) -> tuple[int, str]:
        return self.request("GET", path)

    def post(self, path: str, data: list[tuple[str, str]] | dict) -> tuple[int, str]:
        return self.request("POST", path, data)

    @staticmethod
    def csrf(html: str) -> str:
        match = CSRF_RE.search(html)
        if not match:
            raise AssertionError("csrf token not found")
        return match.group(1)

    def login(self, email: str, password: str) -> bool:
        status, html = self.get("/auth/login")
        status, html = self.post("/auth/login", [
            ("csrf", self.csrf(html)),
            ("email", email),
            ("password", password),
        ])
        return status == 200 and "/dashboard" in self.last_url or "/admin" in self.last_url


def main() -> None:
    creds = read_credentials()

    # ---------- public pages ----------
    anon = Session()
    for path in ["/", "/opportunities", "/skills", "/privacy", "/auth/login", "/auth/register", "/healthz"]:
        status, _ = anon.get(path)
        check(status == 200, f"public {path} -> {status}")

    # ---------- student (Ahmed) read-only ----------
    ahmed = Session()
    check(ahmed.login("ahmed.demo@example.com", creds["student"]), "student login")
    status, dash = ahmed.get("/dashboard")
    check(status == 200 and "أحمد محمد" in dash, "student dashboard shows demo student")
    for path in ["/profile", "/discover", "/cv", "/skills", "/applications", "/opportunities", "/account"]:
        status, _ = ahmed.get(path)
        check(status == 200, f"student page {path} -> {status}")
    status, cv = ahmed.get("/cv?lang=en")
    check(status == 200 and "My CV" in cv, "English CV variant renders")
    status, _ = ahmed.get("/admin")
    check(status == 403, "student blocked from /admin (403)")

    # ---------- second student (Sara) mutations ----------
    sara = Session()
    check(sara.login("sara.demo@example.com", creds["student2"]), "second student login")
    status, profile = sara.get("/profile")
    csrf = sara.csrf(profile)
    status, profile = sara.post("/profile", [
        ("csrf", csrf),
        ("full_name", "سارة علي"),
        ("university", "جامعة القمة الحديثة"),
        ("college", "كلية تقنية المعلومات"),
        ("major", "تقنية المعلومات"),
        ("study_year", "السنة الثانية"),
        ("city", "طرابلس"),
        ("bio", "طالبة تقنية معلومات، أتعلم تطوير الويب وأحب دعم المستخدمين."),
        ("skill_name", "البرمجة"), ("skill_level", "3"),
        ("skill_name", "التصوير"), ("skill_level", "2"),
        ("language_name", "العربية"), ("language_level", "native"),
        ("language_name", "الألمانية"), ("language_level", "beginner"),
        ("course_title", "أساسيات الويب"), ("course_provider", "منصة إدراك"), ("course_year", "2026"),
        ("project_title", "صفحة تعريفية شخصية"), ("project_description", "صفحة HTML/CSS بسيطة."), ("project_link", ""),
        ("exp_title", "متطوعة دعم فني"), ("exp_organization", "مركز إدراك"), ("exp_period", "2025"), ("exp_description", "مساعدة المتدربين على الدخول للمنصة."),
    ])
    check(status == 200 and "تم حفظ ملفك المهني" in profile, "profile save (Arabic) succeeds")
    check("التصوير" in profile and "الألمانية" in profile, "new skill and language persisted")

    # ---------- apply / duplicate / withdraw ----------
    status, listing = sara.get("/opportunities")
    ids = list(dict.fromkeys(OPP_RE.findall(listing)))
    target = None
    for opp_id in ids:
        status, detail = sara.get(opp_id)
        if "مساعد محتوى باللغة الإنجليزية" in detail:
            target = opp_id
            break
    check(target is not None, "target opportunity found")
    if target:
        status, detail = sara.get(target)
        status, applications = sara.post(f"{target}/apply", [("csrf", sara.csrf(detail))])
        check(status == 200 and "مساعد محتوى باللغة الإنجليزية" in applications, "application submitted")
        status, detail = sara.get(target)
        status, detail = sara.post(f"{target}/apply", [("csrf", sara.csrf(detail))])
        check("قدّمت على هذه الفرصة مسبقاً" in detail, "duplicate application blocked")
        status, applications = sara.get("/applications")
        withdraw_re = re.compile(r'action="(/applications/[0-9a-f-]{36}/withdraw)"')
        ids_withdraw = withdraw_re.findall(applications)
        applied = [i for i in ids_withdraw]
        check(bool(applied), "withdraw action available")
        if applied:
            status, applications = sara.post(applied[0], [("csrf", sara.csrf(applications))])
            check("انسحب الطالب" in applications, "application withdrawn")

    # ---------- isolation ----------
    status, ahmed_apps = ahmed.get("/applications")
    check("سارة" not in ahmed_apps and "مساعد محتوى" not in ahmed_apps, "student cannot see other student's applications")

    # ---------- admin ----------
    admin = Session()
    check(admin.login("admin@future-path.app", creds["admin"]), "admin login")
    for path in ["/admin", "/admin/opportunities", "/admin/opportunities/new", "/admin/organizations",
                 "/admin/applications", "/admin/reports", "/admin/users", "/admin/paths"]:
        status, _ = admin.get(path)
        check(status == 200, f"admin page {path} -> {status}")
    status, users = admin.get("/admin/users")
    check("sara.demo@example.com" in users, "admin sees users list")
    status, apps = admin.get("/admin/applications")
    check("سارة علي" in apps, "admin sees student applications")

    # ---------- admin create → publish → close ----------
    status, form = admin.get("/admin/opportunities/new")
    org_match = re.search(r'<option value="([0-9a-f-]{36})"', form)
    check(org_match is not None, "opportunity form lists organizations")
    created_id = None
    if org_match:
        status, _ = admin.post("/admin/opportunities", [
            ("csrf", admin.csrf(form)),
            ("organization_id", org_match.group(1)),
            ("title", "فرصة اختبار النشر التلقائي"),
            ("type", "training"),
            ("field", "تقنية المعلومات"),
            ("city", "طرابلس"),
            ("work_mode", "onsite"),
            ("description", "فرصة مؤقتة تُنشأ بواسطة اختبار القبول للتحقق من دورة النشر، وسيتم حذفها بعد الاختبار."),
            ("requirements", "لا متطلبات"),
            ("tasks", "مهمة تجريبية"),
            ("location_details", "مقر تجريبي"),
            ("deadline", "2026-12-28"),
            ("action", "review"),
        ])
        with psycopg.connect(settings.DATABASE_URL, row_factory=dict_row) as conn:
            row = conn.execute(
                "select id from future_path.opportunities where title = %s", ("فرصة اختبار النشر التلقائي",)
            ).fetchone()
            created_id = str(row["id"]) if row else None
        check(created_id is not None, "admin created opportunity (pending review)")
        if created_id:
            status, _ = admin.post(f"/admin/opportunities/{created_id}/action", [
                ("csrf", admin.csrf(admin.get("/admin/opportunities")[1])),
                ("action", "publish"),
            ])
            status, public = anon.get("/opportunities")
            check("فرصة اختبار النشر التلقائي" in public, "published opportunity visible to public")
            admin.post(f"/admin/opportunities/{created_id}/action", [
                ("csrf", admin.csrf(admin.get("/admin/opportunities")[1])),
                ("action", "close"),
            ])
            status, public = anon.get("/opportunities")
            check("فرصة اختبار النشر التلقائي" not in public, "closed opportunity hidden from public")

    # ---------- admin reset link → set same password → login ----------
    sara_id_match = None
    for row in users.split("<tr"):
        if "sara.demo@example.com" in row:
            sara_id_match = re.search(r'action="/admin/users/([0-9a-f-]{36})/reset-link"', row)
            break
    check(sara_id_match is not None, "reset-link action available")
    if sara_id_match:
        status, link_page = admin.post(f"/admin/users/{sara_id_match.group(1)}/reset-link",
                                       [("csrf", admin.csrf(users))])
        reset_match = RESET_RE.search(link_page)
        check(status == 200 and reset_match is not None, "admin generated one-time reset link")
        if reset_match:
            fresh = Session()
            status, reset_form = fresh.get(reset_match.group(1))
            status, final = fresh.post(reset_match.group(1), [
                ("csrf", fresh.csrf(reset_form)),
                ("password", creds["student2"]),
                ("confirm", creds["student2"]),
            ])
            check(status == 200 and "تم تعيين كلمة المرور" in final, "password reset link works once")
            relogin = Session()
            check(relogin.login("sara.demo@example.com", creds["student2"]), "login with reset password")

    # ---------- logout ----------
    status, page = ahmed.get("/dashboard")
    status, final = ahmed.post("/auth/logout", [("csrf", ahmed.csrf(page))])
    status, page = ahmed.get("/dashboard")
    check("/auth/login" in ahmed.last_url, "logout ends the session")

    # ---------- cleanup ----------
    with psycopg.connect(settings.DATABASE_URL) as conn:
        conn.execute("delete from future_path.opportunities where title = %s", ("فرصة اختبار النشر التلقائي",))
        conn.commit()

    failed = [label for ok, label in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    if failed:
        print("FAILED: " + "; ".join(failed))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
