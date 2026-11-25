from fastapi import APIRouter, Request

from ..content import HOW_IT_WORKS, SERVICES
from ..db import tx
from ..web import current_user, render

router = APIRouter()


@router.get("/")
def home(request: Request):
    user = current_user(request)
    with tx(user.id if user else None) as conn:
        stats = conn.execute(
            """
            select
              (select count(*) from future_path.opportunities where status = 'published') as opportunities,
              (select count(*) from future_path.organizations where verification_status = 'verified') as organizations,
              (select count(*) from future_path.learning_paths where is_active) as paths
            """
        ).fetchone()
        opportunities = conn.execute(
            """
            select o.*, org.name as org_name, org.verification_status as org_status
            from future_path.opportunities o
            join future_path.organizations org on org.id = o.organization_id
            where o.status = 'published'
            order by o.published_at desc nulls last
            limit 3
            """
        ).fetchall()
        paths = conn.execute(
            """
            select * from future_path.learning_paths
            where is_active order by category, title limit 4
            """
        ).fetchall()
    return render(
        request,
        "home.html",
        stats=stats,
        opportunities=opportunities,
        paths=paths,
        services=SERVICES,
        steps=HOW_IT_WORKS,
    )


@router.get("/privacy")
def privacy(request: Request):
    return render(request, "privacy.html")
