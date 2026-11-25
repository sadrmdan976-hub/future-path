from fastapi import APIRouter, Request

from ..db import tx
from ..queries import get_completion, get_courses, get_experiences, get_languages, get_latest_quiz, get_profile, get_projects, get_skills
from ..web import render, require_user

router = APIRouter()


@router.get("/dashboard")
def dashboard(request: Request):
    user = require_user(request)
    with tx(user.id) as conn:
        data = get_profile(conn, user.id)
        profile = dict(data["profile"] or {})
        profile["full_name"] = data["user"]["full_name"]
        profile["email"] = data["user"]["email"]
        comp = get_completion(conn, user.id, profile)
        skills = get_skills(conn, user.id)
        languages = get_languages(conn, user.id)
        quiz = get_latest_quiz(conn, user.id)
        applications = conn.execute(
            """
            select a.id, a.status, a.applied_at, o.title, o.city, o.deadline,
                   org.name as org_name
            from future_path.applications a
            left join future_path.opportunities o on o.id = a.opportunity_id
            left join future_path.organizations org on org.id = o.organization_id
            where a.student_id = %s
            order by a.applied_at desc
            limit 4
            """,
            (user.id,),
        ).fetchall()
        suggestions = conn.execute(
            """
            select o.*, org.name as org_name
            from future_path.opportunities o
            join future_path.organizations org on org.id = o.organization_id
            where o.status = 'published'
              and o.deadline >= current_date
              and not exists (
                select 1 from future_path.applications a
                where a.opportunity_id = o.id and a.student_id = %s
              )
            order by o.published_at desc nulls last
            limit 3
            """,
            (user.id,),
        ).fetchall()
        counters = {
            "skills": len(skills),
            "languages": len(languages),
            "courses": len(get_courses(conn, user.id)),
            "projects": len(get_projects(conn, user.id)),
            "experiences": len(get_experiences(conn, user.id)),
            "applications": conn.execute(
                "select count(*) as c from future_path.applications where student_id = %s",
                (user.id,),
            ).fetchone()["c"],
        }
    return render(
        request,
        "dashboard.html",
        profile=profile,
        comp=comp,
        skills=skills,
        quiz=quiz,
        applications=applications,
        suggestions=suggestions,
        counters=counters,
    )
