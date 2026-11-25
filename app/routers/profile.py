from fastapi import APIRouter, Request

from ..content import PROFICIENCY, SKILL_LEVELS, STUDY_YEARS, UNIVERSITIES
from ..db import tx
from ..queries import (
    get_completion,
    get_courses,
    get_experiences,
    get_languages,
    get_profile,
    get_projects,
    get_skills,
)
from ..web import flash, redirect, render, require_user, verify_csrf

router = APIRouter()

MAX_ROWS = {"skills": 20, "languages": 8, "courses": 15, "projects": 12, "experiences": 10}


def _clean(value, limit: int) -> str:
    return (value or "").strip()[:limit]


def _rows(form, keys, limit):
    lists = [form.getlist(key)[:limit] for key in keys]
    count = min(max((len(items) for items in lists), default=0), limit)
    rows = []
    for idx in range(count):
        rows.append(tuple(_clean(items[idx], 700) if idx < len(items) else "" for items in lists))
    return rows


def _load(conn, user_id):
    data = get_profile(conn, user_id)
    profile = dict(data["profile"] or {})
    profile["full_name"] = data["user"]["full_name"]
    profile["email"] = data["user"]["email"]
    profile["is_demo"] = data["user"]["is_demo"]
    return profile


@router.get("/profile")
def profile_page(request: Request):
    user = require_user(request)
    with tx(user.id) as conn:
        profile = _load(conn, user.id)
        comp = get_completion(conn, user.id, profile)
        skills = get_skills(conn, user.id)
        languages = get_languages(conn, user.id)
        courses = get_courses(conn, user.id)
        projects = get_projects(conn, user.id)
        experiences = get_experiences(conn, user.id)
    return render(
        request,
        "profile.html",
        profile=profile,
        comp=comp,
        skills=skills,
        languages=languages,
        courses=courses,
        projects=projects,
        experiences=experiences,
        universities=UNIVERSITIES,
        study_years=STUDY_YEARS,
        skill_levels=SKILL_LEVELS,
        proficiency=PROFICIENCY,
        error=None,
    )


@router.post("/profile")
async def profile_save(request: Request):
    user = require_user(request)
    form = await request.form()
    verify_csrf(request, form.get("csrf"))

    full_name = _clean(form.get("full_name"), 120)
    university = _clean(form.get("university"), 160)
    college = _clean(form.get("college"), 160)
    major = _clean(form.get("major"), 160)
    study_year = _clean(form.get("study_year"), 40)
    city = _clean(form.get("city"), 80)
    bio = _clean(form.get("bio"), 1500)

    def rerender_error(message: str):
        with tx(user.id) as conn:
            return render(
                request,
                "profile.html",
                profile={
                    "full_name": full_name,
                    "university": university,
                    "college": college,
                    "major": major,
                    "study_year": study_year,
                    "city": city,
                    "bio": bio,
                    "email": user.email,
                    "is_demo": user.is_demo,
                },
                comp=get_completion(
                    conn,
                    user.id,
                    {
                        "university": university,
                        "college": college,
                        "major": major,
                        "study_year": study_year,
                        "bio": bio,
                    },
                ),
                skills=[],
                languages=[],
                courses=[],
                projects=[],
                experiences=[],
                universities=UNIVERSITIES,
                study_years=STUDY_YEARS,
                skill_levels=SKILL_LEVELS,
                proficiency=PROFICIENCY,
                error=message,
            )

    if len(full_name) < 2:
        return rerender_error("الاسم الكامل مطلوب (حرفان على الأقل).")

    skills_payload = []
    for idx, (name, level) in enumerate(_rows(form, ("skill_name", "skill_level"), MAX_ROWS["skills"])):
        if len(name) < 2:
            continue
        try:
            level_value = min(max(int(level), 1), 5)
        except (TypeError, ValueError):
            level_value = 3
        skills_payload.append((name[:80], level_value, idx))

    languages_payload = []
    for idx, (name, level) in enumerate(_rows(form, ("language_name", "language_level"), MAX_ROWS["languages"])):
        if len(name) < 2:
            continue
        languages_payload.append((name[:60], level if level in PROFICIENCY else "intermediate", idx))

    courses_payload = []
    for idx, (title, provider, year) in enumerate(_rows(form, ("course_title", "course_provider", "course_year"), MAX_ROWS["courses"])):
        if len(title) < 2:
            continue
        courses_payload.append((title[:160], provider[:120], year[:12], idx))

    projects_payload = []
    for idx, (title, description, link) in enumerate(_rows(form, ("project_title", "project_description", "project_link"), MAX_ROWS["projects"])):
        if len(title) < 2:
            continue
        projects_payload.append((title[:160], description[:700], link[:400] or None, idx))

    experiences_payload = []
    for idx, (title, org, period, description) in enumerate(
        _rows(form, ("exp_title", "exp_organization", "exp_period", "exp_description"), MAX_ROWS["experiences"])
    ):
        if len(title) < 2:
            continue
        experiences_payload.append((title[:160], org[:160], period[:60], description[:700], idx))

    with tx(user.id) as conn:
        conn.execute(
            "update future_path.users set full_name = %s, updated_at = now() where id = %s",
            (full_name, user.id),
        )
        conn.execute(
            """
            insert into future_path.profiles
              (user_id, university, college, major, study_year, city, bio, updated_at)
            values (%s, %s, %s, %s, %s, %s, %s, now())
            on conflict (user_id) do update set
              university = excluded.university, college = excluded.college,
              major = excluded.major, study_year = excluded.study_year,
              city = excluded.city, bio = excluded.bio, updated_at = now()
            """,
            (user.id, university, college, major, study_year, city, bio),
        )
        conn.execute("delete from future_path.skills where user_id = %s", (user.id,))
        if skills_payload:
            conn.execute(
                "insert into future_path.skills (user_id, skill_name, level, sort_order) "
                "select %s, * from unnest(%s::text[], %s::smallint[], %s::int[])",
                (
                    user.id,
                    [row[0] for row in skills_payload],
                    [row[1] for row in skills_payload],
                    [row[2] for row in skills_payload],
                ),
            )
        conn.execute("delete from future_path.languages where user_id = %s", (user.id,))
        if languages_payload:
            conn.execute(
                "insert into future_path.languages (user_id, language, proficiency, sort_order) "
                "select %s, * from unnest(%s::text[], %s::text[], %s::int[])",
                (
                    user.id,
                    [row[0] for row in languages_payload],
                    [row[1] for row in languages_payload],
                    [row[2] for row in languages_payload],
                ),
            )
        conn.execute("delete from future_path.courses where user_id = %s", (user.id,))
        if courses_payload:
            conn.execute(
                "insert into future_path.courses (user_id, title, provider, year, sort_order) "
                "select %s, * from unnest(%s::text[], %s::text[], %s::text[], %s::int[])",
                (
                    user.id,
                    [row[0] for row in courses_payload],
                    [row[1] for row in courses_payload],
                    [row[2] for row in courses_payload],
                    [row[3] for row in courses_payload],
                ),
            )
        conn.execute("delete from future_path.projects where user_id = %s", (user.id,))
        if projects_payload:
            conn.execute(
                "insert into future_path.projects (user_id, title, description, link, sort_order) "
                "select %s, * from unnest(%s::text[], %s::text[], %s::text[], %s::int[])",
                (
                    user.id,
                    [row[0] for row in projects_payload],
                    [row[1] for row in projects_payload],
                    [row[2] for row in projects_payload],
                    [row[3] for row in projects_payload],
                ),
            )
        conn.execute("delete from future_path.experiences where user_id = %s", (user.id,))
        if experiences_payload:
            conn.execute(
                "insert into future_path.experiences (user_id, title, organization, period, description, sort_order) "
                "select %s, * from unnest(%s::text[], %s::text[], %s::text[], %s::text[], %s::int[])",
                (
                    user.id,
                    [row[0] for row in experiences_payload],
                    [row[1] for row in experiences_payload],
                    [row[2] for row in experiences_payload],
                    [row[3] for row in experiences_payload],
                    [row[4] for row in experiences_payload],
                ),
            )
        profile = _load(conn, user.id)
        comp = get_completion(conn, user.id, profile)

    response = redirect("/profile")
    return flash(response, request, f"تم حفظ ملفك المهني. نسبة الاكتمال الآن {comp['score']}%.")


@router.get("/cv")
def cv_page(request: Request, lang: str = "ar"):
    user = require_user(request)
    lang = "en" if lang == "en" else "ar"
    with tx(user.id) as conn:
        profile = _load(conn, user.id)
        skills = get_skills(conn, user.id)
        languages = get_languages(conn, user.id)
        courses = get_courses(conn, user.id)
        projects = get_projects(conn, user.id)
        experiences = get_experiences(conn, user.id)
        comp = get_completion(conn, user.id, profile)
    return render(
        request,
        "cv.html",
        profile=profile,
        skills=skills,
        languages=languages,
        courses=courses,
        projects=projects,
        experiences=experiences,
        comp=comp,
        lang=lang,
    )
