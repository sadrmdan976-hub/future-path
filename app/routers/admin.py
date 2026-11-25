import uuid
from datetime import date

from fastapi import APIRouter, HTTPException, Request

from ..config import settings
from ..content import APP_STATUS, CATEGORIES, CITIES, FIELDS, OPP_STATUS, OPP_TYPE, PATH_LEVEL, WORK_MODE
from ..db import tx
from ..security import new_token, sha256_hex
from ..web import flash, redirect, render, require_admin, verify_csrf

router = APIRouter(prefix="/admin")


def _as_uuid(value: str) -> str | None:
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        return None


def _text(form, key: str, limit: int) -> str:
    return (form.get(key) or "").strip()[:limit]


def _parse_date(value: str):
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def _opp_values(form) -> tuple[dict, str | None]:
    values = {
        "organization_id": _as_uuid(form.get("organization_id")),
        "title": _text(form, "title", 180),
        "type": form.get("type") if form.get("type") in OPP_TYPE else "training",
        "field": form.get("field") if form.get("field") in FIELDS else "",
        "city": _text(form, "city", 80),
        "work_mode": form.get("work_mode") if form.get("work_mode") in WORK_MODE else "onsite",
        "description": _text(form, "description", 4000),
        "requirements": _text(form, "requirements", 2000),
        "tasks": _text(form, "tasks", 2000),
        "location_details": _text(form, "location_details", 200),
        "deadline": _parse_date(form.get("deadline")),
    }
    if not values["organization_id"]:
        return values, "اختر الجهة."
    if len(values["title"]) < 3:
        return values, "عنوان الفرصة مطلوب (3 أحرف على الأقل)."
    if not values["field"]:
        return values, "اختر المجال."
    if not values["city"]:
        return values, "أدخل المدينة."
    if len(values["description"]) < 20:
        return values, "الوصف مطلوب (20 حرفاً على الأقل)."
    if not values["deadline"]:
        return values, "أدخل آخر موعد تقديم صحيح."
    return values, None


@router.get("")
def dashboard(request: Request):
    user = require_admin(request)
    with tx(user.id) as conn:
        counts = conn.execute(
            """
            select
              (select count(*) from future_path.opportunities where status = 'published') as published,
              (select count(*) from future_path.opportunities where status = 'pending_review') as pending,
              (select count(*) from future_path.applications) as applications,
              (select count(*) from future_path.applications where status = 'accepted') as accepted,
              (select count(*) from future_path.reports where status = 'open') as open_reports,
              (select count(*) from future_path.users where account_type = 'student') as students,
              (select count(*) from future_path.organizations where verification_status = 'pending') as orgs_pending
            """
        ).fetchone()
        recent_apps = conn.execute(
            """
            select a.id, a.status, a.applied_at, u.full_name as student_name,
                   o.title as opp_title
            from future_path.applications a
            join future_path.users u on u.id = a.student_id
            left join future_path.opportunities o on o.id = a.opportunity_id
            order by a.applied_at desc limit 8
            """
        ).fetchall()
        recent_reports = conn.execute(
            """
            select r.id, r.reason, r.status, r.created_at, o.title as opp_title
            from future_path.reports r
            left join future_path.opportunities o on o.id = r.opportunity_id
            order by r.created_at desc limit 5
            """
        ).fetchall()
    return render(
        request,
        "admin/dashboard.html",
        counts=counts,
        recent_apps=recent_apps,
        recent_reports=recent_reports,
    )


@router.get("/opportunities")
def opportunities_list(request: Request, status: str = "", q: str = ""):
    user = require_admin(request)
    status = status if status in OPP_STATUS else ""
    q = (q or "").strip()[:100]
    where = []
    params = {}
    if status:
        where.append("o.status = %(status)s")
        params["status"] = status
    if q:
        where.append("(o.title ILIKE %(q)s OR org.name ILIKE %(q)s)")
        params["q"] = f"%{q}%"
    where_sql = ("where " + " and ".join(where)) if where else ""
    with tx(user.id) as conn:
        rows = conn.execute(
            f"""
            select o.*, org.name as org_name, org.verification_status as org_status,
                   (select count(*) from future_path.applications a where a.opportunity_id = o.id) as apps_count
            from future_path.opportunities o
            join future_path.organizations org on org.id = o.organization_id
            {where_sql}
            order by o.updated_at desc
            limit 300
            """,
            params,
        ).fetchall()
    return render(
        request,
        "admin/opportunities.html",
        rows=rows,
        f_status=status,
        q=q,
        statuses=OPP_STATUS,
    )


def _orgs_for_select(conn):
    return conn.execute(
        "select id, name, verification_status from future_path.organizations order by name"
    ).fetchall()


@router.get("/opportunities/new")
def opportunity_new(request: Request):
    user = require_admin(request)
    with tx(user.id) as conn:
        orgs = _orgs_for_select(conn)
    return render(
        request,
        "admin/opportunity_form.html",
        mode="new",
        opp=None,
        values={"deadline": (date.today().replace(month=min(date.today().month + 1, 12))).isoformat()},
        orgs=orgs,
        error=None,
    )


@router.post("/opportunities")
async def opportunity_create(request: Request):
    user = require_admin(request)
    form = await request.form()
    verify_csrf(request, form.get("csrf"))
    values, error = _opp_values(form)
    action = form.get("action") or "draft"

    with tx(user.id) as conn:
        orgs = _orgs_for_select(conn)
        if error:
            return render(
                request,
                "admin/opportunity_form.html",
                mode="new",
                opp=None,
                values=values,
                orgs=orgs,
                error=error,
                status_code=400,
            )
        status = "pending_review" if action == "review" else "draft"
        row = conn.execute(
            """
            insert into future_path.opportunities
              (organization_id, title, type, field, city, work_mode, description,
               requirements, tasks, location_details, deadline, status, created_by)
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            returning id
            """,
            (
                values["organization_id"],
                values["title"],
                values["type"],
                values["field"],
                values["city"],
                values["work_mode"],
                values["description"],
                values["requirements"] or None,
                values["tasks"] or None,
                values["location_details"] or None,
                values["deadline"],
                status,
                user.id,
            ),
        ).fetchone()
    response = redirect("/admin/opportunities")
    return flash(response, request, "تم إنشاء الفرصة كمسودة. راجعها ثم انشرها ووثّقها.")


@router.get("/opportunities/{opp_id}/edit")
def opportunity_edit(request: Request, opp_id: str):
    user = require_admin(request)
    with tx(user.id) as conn:
        opp = conn.execute(
            "select * from future_path.opportunities where id::text = %s", (opp_id,)
        ).fetchone()
        orgs = _orgs_for_select(conn)
    if not opp:
        raise HTTPException(status_code=404)
    values = dict(opp)
    values["deadline"] = opp["deadline"].isoformat()
    return render(
        request,
        "admin/opportunity_form.html",
        mode="edit",
        opp=opp,
        values=values,
        orgs=orgs,
        error=None,
    )


@router.post("/opportunities/{opp_id}")
async def opportunity_update(request: Request, opp_id: str):
    user = require_admin(request)
    form = await request.form()
    verify_csrf(request, form.get("csrf"))
    values, error = _opp_values(form)
    action = form.get("action") or "save"

    with tx(user.id) as conn:
        opp = conn.execute(
            "select * from future_path.opportunities where id::text = %s", (opp_id,)
        ).fetchone()
        if not opp:
            raise HTTPException(status_code=404)
        orgs = _orgs_for_select(conn)
        if error:
            return render(
                request,
                "admin/opportunity_form.html",
                mode="edit",
                opp=opp,
                values=values,
                orgs=orgs,
                error=error,
                status_code=400,
            )
        next_status = opp["status"]
        if action == "review":
            next_status = "pending_review"
        conn.execute(
            """
            update future_path.opportunities set
              organization_id = %s, title = %s, type = %s, field = %s, city = %s,
              work_mode = %s, description = %s, requirements = %s, tasks = %s,
              location_details = %s, deadline = %s, status = %s, updated_at = now()
            where id = %s
            """,
            (
                values["organization_id"],
                values["title"],
                values["type"],
                values["field"],
                values["city"],
                values["work_mode"],
                values["description"],
                values["requirements"] or None,
                values["tasks"] or None,
                values["location_details"] or None,
                values["deadline"],
                next_status,
                opp["id"],
            ),
        )
    response = redirect("/admin/opportunities")
    return flash(response, request, "تم تحديث الفرصة.")


@router.post("/opportunities/{opp_id}/action")
async def opportunity_action(request: Request, opp_id: str):
    user = require_admin(request)
    form = await request.form()
    verify_csrf(request, form.get("csrf"))
    action = form.get("action") or ""

    with tx(user.id) as conn:
        opp = conn.execute(
            """
            select o.*, org.verification_status as org_status
            from future_path.opportunities o
            join future_path.organizations org on org.id = o.organization_id
            where o.id::text = %s
            """,
            (opp_id,),
        ).fetchone()
        if not opp:
            raise HTTPException(status_code=404)

        if action == "publish":
            if opp["org_status"] != "verified":
                response = redirect("/admin/opportunities")
                return flash(response, request, "لا يمكن النشر قبل توثيق الجهة المرتبطة بالفرصة.", "error")
            if opp["deadline"] < date.today():
                response = redirect("/admin/opportunities")
                return flash(response, request, "لا يمكن نشر فرصة انتهى موعدها. عدّل آخر موعد أولاً.", "error")
            conn.execute(
                """
                update future_path.opportunities
                set status = 'published', is_verified = true,
                    published_at = coalesce(published_at, now()), updated_at = now()
                where id = %s
                """,
                (opp["id"],),
            )
            message = "تم توثيق الفرصة ونشرها، وأصبحت ظاهرة للطلاب."
        elif action == "suspend":
            conn.execute(
                "update future_path.opportunities set status = 'suspended', updated_at = now() where id = %s",
                (opp["id"],),
            )
            message = "تم إيقاف الفرصة للمراجعة وإخفاؤها من الطلاب."
        elif action == "close":
            conn.execute(
                "update future_path.opportunities set status = 'closed', updated_at = now() where id = %s",
                (opp["id"],),
            )
            message = "تم إغلاق الفرصة."
        elif action == "review":
            conn.execute(
                """
                update future_path.opportunities
                set status = 'pending_review', is_verified = false, updated_at = now()
                where id = %s
                """,
                (opp["id"],),
            )
            message = "أُعيدت الفرصة إلى قائمة المراجعة."
        elif action == "draft":
            conn.execute(
                "update future_path.opportunities set status = 'draft', updated_at = now() where id = %s",
                (opp["id"],),
            )
            message = "أُعيدت الفرصة إلى المسودة."
        else:
            raise HTTPException(status_code=400)

    response = redirect("/admin/opportunities")
    return flash(response, request, message)


@router.get("/organizations")
def organizations_list(request: Request):
    user = require_admin(request)
    with tx(user.id) as conn:
        rows = conn.execute(
            """
            select org.*,
                   (select count(*) from future_path.opportunities o where o.organization_id = org.id) as opps_count
            from future_path.organizations org
            order by org.created_at desc
            limit 200
            """
        ).fetchall()
    return render(request, "admin/organizations.html", rows=rows)


@router.post("/organizations")
async def organization_create(request: Request):
    user = require_admin(request)
    form = await request.form()
    verify_csrf(request, form.get("csrf"))
    name = _text(form, "name", 160)
    if len(name) < 2:
        response = redirect("/admin/organizations")
        return flash(response, request, "اسم الجهة مطلوب.", "error")
    verification = form.get("verification_status")
    if verification not in ("pending", "verified", "rejected"):
        verification = "pending"
    with tx(user.id) as conn:
        conn.execute(
            """
            insert into future_path.organizations
              (name, description, contact_details, city, verification_status, is_demo, created_by)
            values (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                name,
                _text(form, "description", 1200) or None,
                _text(form, "contact_details", 400) or None,
                _text(form, "city", 80) or None,
                verification,
                form.get("is_demo") == "on",
                user.id,
            ),
        )
    response = redirect("/admin/organizations")
    return flash(response, request, "تمت إضافة الجهة.")


@router.get("/organizations/{org_id}/edit")
def organization_edit(request: Request, org_id: str):
    user = require_admin(request)
    with tx(user.id) as conn:
        org = conn.execute(
            "select * from future_path.organizations where id::text = %s", (org_id,)
        ).fetchone()
    if not org:
        raise HTTPException(status_code=404)
    return render(request, "admin/organization_form.html", org=org, error=None)


@router.post("/organizations/{org_id}")
async def organization_update(request: Request, org_id: str):
    user = require_admin(request)
    form = await request.form()
    verify_csrf(request, form.get("csrf"))
    name = _text(form, "name", 160)
    verification = form.get("verification_status")
    if verification not in ("pending", "verified", "rejected"):
        verification = "pending"
    if len(name) < 2:
        with tx(user.id) as conn:
            org = conn.execute(
                "select * from future_path.organizations where id::text = %s", (org_id,)
            ).fetchone()
        if not org:
            raise HTTPException(status_code=404)
        return render(
            request,
            "admin/organization_form.html",
            org=org,
            error="اسم الجهة مطلوب.",
            status_code=400,
        )
    with tx(user.id) as conn:
        updated = conn.execute(
            """
            update future_path.organizations
            set name = %s, description = %s, contact_details = %s, city = %s,
                verification_status = %s
            where id::text = %s returning id
            """,
            (
                name,
                _text(form, "description", 1200) or None,
                _text(form, "contact_details", 400) or None,
                _text(form, "city", 80) or None,
                verification,
                org_id,
            ),
        ).fetchone()
    if not updated:
        raise HTTPException(status_code=404)
    response = redirect("/admin/organizations")
    return flash(response, request, "تم تحديث بيانات الجهة.")


@router.get("/applications")
def applications_list(request: Request, status: str = ""):
    user = require_admin(request)
    status = status if status in APP_STATUS else ""
    where_sql = "where a.status = %(status)s" if status else ""
    with tx(user.id) as conn:
        rows = conn.execute(
            f"""
            select a.id, a.status, a.applied_at, u.full_name as student_name,
                   u.email as student_email, o.title as opp_title, org.name as org_name
            from future_path.applications a
            join future_path.users u on u.id = a.student_id
            left join future_path.opportunities o on o.id = a.opportunity_id
            left join future_path.organizations org on org.id = o.organization_id
            {where_sql}
            order by a.applied_at desc
            limit 300
            """,
            {"status": status} if status else None,
        ).fetchall()
    return render(request, "admin/applications.html", rows=rows, f_status=status, statuses=APP_STATUS)


@router.get("/applications/{app_id}")
def application_detail(request: Request, app_id: str):
    user = require_admin(request)
    with tx(user.id) as conn:
        row = conn.execute(
            """
            select a.*, u.full_name as student_name, u.email as student_email,
                   o.title as opp_title, o.deadline, o.city,
                   org.name as org_name
            from future_path.applications a
            join future_path.users u on u.id = a.student_id
            left join future_path.opportunities o on o.id = a.opportunity_id
            left join future_path.organizations org on org.id = o.organization_id
            where a.id::text = %s
            """,
            (app_id,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404)
    return render(request, "admin/application_detail.html", row=row, snapshot=row["cv_snapshot"] or {}, statuses=APP_STATUS)


@router.post("/applications/{app_id}/status")
async def application_status(request: Request, app_id: str):
    user = require_admin(request)
    form = await request.form()
    verify_csrf(request, form.get("csrf"))
    status = form.get("status")
    if status not in APP_STATUS:
        raise HTTPException(status_code=400)
    with tx(user.id) as conn:
        updated = conn.execute(
            "update future_path.applications set status = %s, updated_at = now() where id::text = %s returning id",
            (status, app_id),
        ).fetchone()
    back = form.get("back") or ""
    if not back.startswith("/admin"):
        back = "/admin/applications"
    response = redirect(back)
    if not updated:
        return flash(response, request, "الطلب غير موجود.", "error")
    return flash(response, request, f"تم تحديث حالة الطلب إلى: {APP_STATUS[status]}.")


@router.get("/reports")
def reports_list(request: Request, status: str = "open"):
    user = require_admin(request)
    status = status if status in ("open", "resolved", "dismissed", "all") else "open"
    where_sql = "" if status == "all" else "where r.status = %(status)s"
    with tx(user.id) as conn:
        rows = conn.execute(
            f"""
            select r.*, o.title as opp_title, o.status as opp_status,
                   u.full_name as reporter_name
            from future_path.reports r
            left join future_path.opportunities o on o.id = r.opportunity_id
            left join future_path.users u on u.id = r.reporter_id
            {where_sql}
            order by r.created_at desc limit 200
            """,
            {"status": status} if status != "all" else None,
        ).fetchall()
    return render(request, "admin/reports.html", rows=rows, f_status=status)


@router.post("/reports/{report_id}/status")
async def report_status(request: Request, report_id: str):
    user = require_admin(request)
    form = await request.form()
    verify_csrf(request, form.get("csrf"))
    status = form.get("status")
    if status not in ("open", "resolved", "dismissed"):
        raise HTTPException(status_code=400)
    with tx(user.id) as conn:
        conn.execute(
            "update future_path.reports set status = %s, resolved_at = case when %s = 'open' then null else now() end where id::text = %s",
            (status, status, report_id),
        )
    response = redirect("/admin/reports")
    return flash(response, request, "تم تحديث حالة البلاغ.")


@router.get("/users")
def users_list(request: Request, q: str = ""):
    user = require_admin(request)
    q = (q or "").strip()[:100]
    where_sql = "where (u.full_name ILIKE %(q)s or u.email ILIKE %(q)s)" if q else ""
    with tx(user.id) as conn:
        rows = conn.execute(
            f"""
            select u.id, u.full_name, u.email, u.account_type, u.is_active, u.is_demo,
                   u.created_at, p.university, p.major,
                   (ar.user_id is not null) as is_admin,
                   (select count(*) from future_path.applications a where a.student_id = u.id) as apps_count
            from future_path.users u
            left join future_path.profiles p on p.user_id = u.id
            left join future_path.admin_roles ar on ar.user_id = u.id
            {where_sql}
            order by u.created_at desc
            limit 300
            """,
            {"q": f"%{q}%"} if q else None,
        ).fetchall()
    return render(request, "admin/users.html", rows=rows, q=q)


@router.post("/users/{user_id}/active")
async def user_toggle_active(request: Request, user_id: str):
    user = require_admin(request)
    form = await request.form()
    verify_csrf(request, form.get("csrf"))
    target = _as_uuid(user_id)
    if not target or target == user.id:
        response = redirect("/admin/users")
        return flash(response, request, "لا يمكن تغيير حالة حسابك الحالي.", "error")
    active = form.get("active") == "1"
    with tx(user.id) as conn:
        conn.execute("select future_path.fp_admin_set_active(%s, %s)", (target, active))
    response = redirect("/admin/users")
    return flash(response, request, "تم تفعيل الحساب." if active else "تم إيقاف الحساب وإلغاء جلساته.")


@router.post("/users/{user_id}/reset-link")
async def user_reset_link(request: Request, user_id: str):
    user = require_admin(request)
    form = await request.form()
    verify_csrf(request, form.get("csrf"))
    target = _as_uuid(user_id)
    if not target:
        raise HTTPException(status_code=404)
    token = new_token()
    with tx(user.id) as conn:
        target_user = conn.execute(
            "select id, full_name, email from future_path.users where id = %s", (target,)
        ).fetchone()
        if not target_user:
            raise HTTPException(status_code=404)
        conn.execute(
            "select future_path.fp_admin_create_reset(%s, %s, now() + interval '1 hour')",
            (target, sha256_hex(token)),
        )
    reset_url = f"{settings.APP_BASE_URL}/auth/reset/{token}"
    return render(
        request,
        "admin/reset_link.html",
        target_user=target_user,
        reset_url=reset_url,
    )


@router.get("/paths")
def paths_list(request: Request):
    user = require_admin(request)
    with tx(user.id) as conn:
        rows = conn.execute(
            "select * from future_path.learning_paths order by category, title"
        ).fetchall()
    return render(request, "admin/paths.html", rows=rows, categories=CATEGORIES, levels=PATH_LEVEL)


def _path_values(form) -> tuple[dict, str | None]:
    values = {
        "title": _text(form, "title", 160),
        "category": form.get("category") if form.get("category") in CATEGORIES else "",
        "description": _text(form, "description", 1200),
        "resource_url": _text(form, "resource_url", 400),
        "level": form.get("level") if form.get("level") in PATH_LEVEL else "beginner",
        "duration": _text(form, "duration", 60),
    }
    if len(values["title"]) < 3:
        return values, "عنوان المسار مطلوب."
    if not values["category"]:
        return values, "اختر الفئة."
    if len(values["description"]) < 20:
        return values, "الوصف مطلوب (20 حرفاً على الأقل)."
    if not (values["resource_url"].startswith("http://") or values["resource_url"].startswith("https://")):
        return values, "رابط المورد يجب أن يبدأ بـ http:// أو https://."
    return values, None


@router.post("/paths")
async def path_create(request: Request):
    user = require_admin(request)
    form = await request.form()
    verify_csrf(request, form.get("csrf"))
    values, error = _path_values(form)
    if error:
        response = redirect("/admin/paths")
        return flash(response, request, error, "error")
    with tx(user.id) as conn:
        conn.execute(
            """
            insert into future_path.learning_paths
              (title, category, description, resource_url, level, duration, is_active, is_demo)
            values (%s, %s, %s, %s, %s, %s, true, %s)
            """,
            (
                values["title"],
                values["category"],
                values["description"],
                values["resource_url"],
                values["level"],
                values["duration"] or None,
                form.get("is_demo") == "on",
            ),
        )
    response = redirect("/admin/paths")
    return flash(response, request, "تمت إضافة المسار.")


@router.get("/paths/{path_id}/edit")
def path_edit(request: Request, path_id: str):
    user = require_admin(request)
    with tx(user.id) as conn:
        path = conn.execute(
            "select * from future_path.learning_paths where id::text = %s", (path_id,)
        ).fetchone()
    if not path:
        raise HTTPException(status_code=404)
    return render(request, "admin/path_form.html", path=path, categories=CATEGORIES, levels=PATH_LEVEL, error=None)


@router.post("/paths/{path_id}")
async def path_update(request: Request, path_id: str):
    user = require_admin(request)
    form = await request.form()
    verify_csrf(request, form.get("csrf"))
    values, error = _path_values(form)
    if error:
        with tx(user.id) as conn:
            path = conn.execute(
                "select * from future_path.learning_paths where id::text = %s", (path_id,)
            ).fetchone()
        if not path:
            raise HTTPException(status_code=404)
        merged = dict(path)
        merged.update(values)
        return render(
            request,
            "admin/path_form.html",
            path=merged,
            categories=CATEGORIES,
            levels=PATH_LEVEL,
            error=error,
            status_code=400,
        )
    with tx(user.id) as conn:
        updated = conn.execute(
            """
            update future_path.learning_paths
            set title = %s, category = %s, description = %s, resource_url = %s,
                level = %s, duration = %s
            where id::text = %s returning id
            """,
            (
                values["title"],
                values["category"],
                values["description"],
                values["resource_url"],
                values["level"],
                values["duration"] or None,
                path_id,
            ),
        ).fetchone()
    if not updated:
        raise HTTPException(status_code=404)
    response = redirect("/admin/paths")
    return flash(response, request, "تم تحديث المسار.")


@router.post("/paths/{path_id}/toggle")
async def path_toggle(request: Request, path_id: str):
    user = require_admin(request)
    form = await request.form()
    verify_csrf(request, form.get("csrf"))
    with tx(user.id) as conn:
        conn.execute(
            "update future_path.learning_paths set is_active = not is_active where id::text = %s",
            (path_id,),
        )
    response = redirect("/admin/paths")
    return flash(response, request, "تم تغيير حالة ظهور المسار.")
