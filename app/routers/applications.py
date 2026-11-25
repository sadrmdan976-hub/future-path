from fastapi import APIRouter, Request

from ..content import APP_STATUS_ACTIVE
from ..db import tx
from ..web import flash, redirect, render, require_user, verify_csrf

router = APIRouter()


@router.get("/applications")
def my_applications(request: Request):
    user = require_user(request)
    with tx(user.id) as conn:
        rows = conn.execute(
            """
            select a.id, a.status, a.applied_at, a.updated_at,
                   o.title, o.city, o.deadline, o.type, o.work_mode,
                   org.name as org_name
            from future_path.applications a
            left join future_path.opportunities o on o.id = a.opportunity_id
            left join future_path.organizations org on org.id = o.organization_id
            where a.student_id = %s
            order by a.applied_at desc
            """,
            (user.id,),
        ).fetchall()
    return render(request, "applications.html", rows=rows, active_statuses=APP_STATUS_ACTIVE)


@router.post("/applications/{app_id}/withdraw")
async def withdraw(request: Request, app_id: str):
    user = require_user(request)
    form = await request.form()
    verify_csrf(request, form.get("csrf"))
    with tx(user.id) as conn:
        updated = conn.execute(
            """
            update future_path.applications
            set status = 'withdrawn', updated_at = now()
            where id::text = %s and student_id = %s
              and status in ('submitted', 'under_review', 'invited')
            returning id
            """,
            (app_id, user.id),
        ).fetchone()
    response = redirect("/applications")
    if updated:
        return flash(response, request, "تم سحب الطلب. يمكنك التقديم مجدداً ما دامت الفرصة مفتوحة.", "warn")
    return flash(response, request, "تعذّر سحب الطلب: الحالة تغيّرت أو الطلب غير موجود.", "error")
