from fastapi import APIRouter, HTTPException, Request

from ..content import CATEGORIES
from ..db import tx
from ..web import current_user, render

router = APIRouter()


@router.get("/skills")
def skills_page(request: Request, category: str = ""):
    user = current_user(request)
    category = category if category in CATEGORIES else ""
    with tx(user.id if user else None) as conn:
        if category:
            paths = conn.execute(
                "select * from future_path.learning_paths where is_active and category = %s order by title",
                (category,),
            ).fetchall()
        else:
            paths = conn.execute(
                "select * from future_path.learning_paths where is_active order by category, title"
            ).fetchall()
        counts = {
            row["category"]: row["c"]
            for row in conn.execute(
                "select category, count(*) as c from future_path.learning_paths where is_active group by category"
            ).fetchall()
        }
    return render(
        request,
        "skills.html",
        paths=paths,
        counts=counts,
        active_category=category,
        categories=CATEGORIES,
    )


@router.get("/skills/{path_id}")
def skill_detail(request: Request, path_id: str):
    user = current_user(request)
    with tx(user.id if user else None) as conn:
        path = conn.execute(
            "select * from future_path.learning_paths where id::text = %s", (path_id,)
        ).fetchone()
        related = conn.execute(
            """
            select * from future_path.learning_paths
            where is_active and category = %s and id::text <> %s
            order by title limit 3
            """,
            (path["category"], path_id),
        ).fetchall() if path else []
    if not path:
        raise HTTPException(status_code=404)
    return render(request, "skill_detail.html", path=path, related=related, categories=CATEGORIES)
