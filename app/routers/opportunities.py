from datetime import date

import psycopg
from fastapi import APIRouter, HTTPException, Request
from psycopg.types.json import Json

from ..content import CITIES, FIELDS, WORK_MODE
from ..db import tx
from ..queries import cv_snapshot, get_profile
from ..web import current_user, flash, redirect, render, require_user, verify_csrf

router = APIRouter()

PAGE_SIZE = 9
REPORT_REASONS = [
    "معلومات مضللة",
    "طلب دفع أو رسوم",
    "الوظيفة غير موجودة",
    "محتوى غير لائق",
    "أخرى",
]


@router.get("/opportunities")
def opportunities_list(
    request: Request,
    q: str = "",
    type: str = "",
    field: str = "",
    city: str = "",
    work_mode: str = "",
    sort: str = "newest",
    page: int = 1,
):
    user = current_user(request)
    q = (q or "").strip()[:100]
    type = type if type in ("training", "job") else ""
    field = field if field in FIELDS else ""
    city = city if city in CITIES else ""
    work_mode = work_mode if work_mode in WORK_MODE else ""
    sort = "deadline" if sort == "deadline" else "newest"
    page = max(1, min(page, 500))

    where = ["o.status = 'published'"]
    params = {}
    if q:
        where.append("(o.title ILIKE %(q)s OR org.name ILIKE %(q)s OR o.description ILIKE %(q)s)")
        params["q"] = f"%{q}%"
    if type:
        where.append("o.type = %(type)s")
        params["type"] = type
    if field:
        where.append("o.field = %(field)s")
        params["field"] = field
    if city:
        where.append("o.city = %(city)s")
        params["city"] = city
    if work_mode:
        where.append("o.work_mode = %(work_mode)s")
        params["work_mode"] = work_mode
    where_sql = " and ".join(where)
    order_sql = "o.deadline asc, o.published_at desc" if sort == "deadline" else "o.published_at desc nulls last"

    with tx(user.id if user else None) as conn:
        total = conn.execute(
            f"""
            select count(*) as c from future_path.opportunities o
            join future_path.organizations org on org.id = o.organization_id
            where {where_sql}
            """,
            params,
        ).fetchone()["c"]
        rows = conn.execute(
            f"""
            select o.*, org.name as org_name
            from future_path.opportunities o
            join future_path.organizations org on org.id = o.organization_id
            where {where_sql}
            order by {order_sql}
            limit %(limit)s offset %(offset)s
            """,
            {**params, "limit": PAGE_SIZE, "offset": (page - 1) * PAGE_SIZE},
        ).fetchall()
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    return render(
        request,
        "opportunities.html",
        rows=rows,
        total=total,
        page=page,
        pages=pages,
        q=q,
        f_type=type,
        f_field=field,
        f_city=city,
        f_work_mode=work_mode,
        f_sort=sort,
    )


@router.get("/opportunities/{opp_id}")
def opportunity_detail(request: Request, opp_id: str):
    user = current_user(request)
    with tx(user.id if user else None) as conn:
        opp = conn.execute(
            """
            select o.*, org.name as org_name, org.description as org_description,
                   org.contact_details as org_contact, org.city as org_city,
                   org.verification_status as org_status
            from future_path.opportunities o
            join future_path.organizations org on org.id = o.organization_id
            where o.id::text = %s
            """,
            (opp_id,),
        ).fetchone()
        my_app = None
        if opp and user:
            my_app = conn.execute(
                "select * from future_path.applications where opportunity_id = %s and student_id = %s",
                (opp["id"], user.id),
            ).fetchone()
    if not opp:
        raise HTTPException(status_code=404)
    closed_for_apply = opp["status"] != "published" or opp["deadline"] < date.today()
    return render(
        request,
        "opportunity_detail.html",
        opp=opp,
        my_app=my_app,
        closed_for_apply=closed_for_apply,
        reasons=REPORT_REASONS,
    )


@router.post("/opportunities/{opp_id}/apply")
async def opportunity_apply(request: Request, opp_id: str):
    user = require_user(request)
    form = await request.form()
    verify_csrf(request, form.get("csrf"))
    if user.is_admin:
        response = redirect(f"/opportunities/{opp_id}")
        return flash(response, request, "حساب المسؤول لا يقدّم طلبات. استخدم حساب طالب للتجربة.", "warn")

    with tx(user.id) as conn:
        opp = conn.execute(
            "select * from future_path.opportunities where id::text = %s", (opp_id,)
        ).fetchone()
        if not opp or opp["status"] != "published" or opp["deadline"] < date.today():
            response = redirect(f"/opportunities/{opp_id}")
            return flash(response, request, "لا يمكن التقديم: الفرصة غير منشورة أو انتهى موعدها.", "error")
        data = get_profile(conn, user.id)
        profile = dict(data["profile"] or {})
        profile["full_name"] = data["user"]["full_name"]
        profile["email"] = data["user"]["email"]
        snapshot = cv_snapshot(conn, user.id, profile)
        try:
            conn.execute(
                """
                insert into future_path.applications (opportunity_id, student_id, cv_snapshot)
                values (%s, %s, %s)
                """,
                (opp["id"], user.id, Json(snapshot)),
            )
        except psycopg.errors.UniqueViolation:
            response = redirect(f"/opportunities/{opp_id}")
            return flash(response, request, "قدّمت على هذه الفرصة مسبقاً.", "warn")
        except psycopg.errors.InsufficientPrivilege:
            response = redirect(f"/opportunities/{opp_id}")
            return flash(response, request, "تعذّر التقديم. تأكد أن الحساب طالب وأن الفرصة ما زالت مفتوحة.", "error")

    response = redirect("/applications")
    return flash(response, request, "تم استلام طلبك بنجاح. يمكنك متابعة حالته من صفحة طلباتي.")


@router.post("/opportunities/{opp_id}/report")
async def opportunity_report(request: Request, opp_id: str):
    user = require_user(request)
    form = await request.form()
    verify_csrf(request, form.get("csrf"))
    reason = (form.get("reason") or "").strip()
    details = (form.get("details") or "").strip()[:1000]
    if reason not in REPORT_REASONS:
        reason = "أخرى"
    with tx(user.id) as conn:
        opp = conn.execute(
            "select id from future_path.opportunities where id::text = %s", (opp_id,)
        ).fetchone()
        if opp:
            conn.execute(
                """
                insert into future_path.reports (opportunity_id, reporter_id, reason, details)
                values (%s, %s, %s, %s)
                """,
                (opp["id"], user.id, reason, details),
            )
    response = redirect(f"/opportunities/{opp_id}")
    return flash(response, request, "تم إرسال البلاغ إلى إدارة المنصة للمراجعة. شكراً لك.")
