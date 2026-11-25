from .content import completion


def get_profile(conn, user_id) -> dict:
    user = conn.execute(
        "select id, email, full_name, is_demo from future_path.users where id = %s",
        (user_id,),
    ).fetchone()
    profile = conn.execute(
        "select * from future_path.profiles where user_id = %s", (user_id,)
    ).fetchone()
    return {"user": user, "profile": profile or {}}


def get_skills(conn, user_id) -> list:
    return conn.execute(
        "select * from future_path.skills where user_id = %s order by sort_order, skill_name",
        (user_id,),
    ).fetchall()


def get_languages(conn, user_id) -> list:
    return conn.execute(
        "select * from future_path.languages where user_id = %s order by sort_order, language",
        (user_id,),
    ).fetchall()


def get_courses(conn, user_id) -> list:
    return conn.execute(
        "select * from future_path.courses where user_id = %s order by sort_order, title",
        (user_id,),
    ).fetchall()


def get_projects(conn, user_id) -> list:
    return conn.execute(
        "select * from future_path.projects where user_id = %s order by sort_order, title",
        (user_id,),
    ).fetchall()


def get_experiences(conn, user_id) -> list:
    return conn.execute(
        "select * from future_path.experiences where user_id = %s order by sort_order, title",
        (user_id,),
    ).fetchall()


def get_latest_quiz(conn, user_id):
    return conn.execute(
        "select * from future_path.interests_results where user_id = %s order by created_at desc limit 1",
        (user_id,),
    ).fetchone()


def get_completion(conn, user_id, profile) -> dict:
    counters = conn.execute(
        """
        select
          (select count(*) from future_path.skills where user_id = %(uid)s) as skills,
          (select count(*) from future_path.languages where user_id = %(uid)s) as languages,
          (select count(*) from future_path.courses where user_id = %(uid)s)
          + (select count(*) from future_path.projects where user_id = %(uid)s)
          + (select count(*) from future_path.experiences where user_id = %(uid)s) as extras,
          (select exists(select 1 from future_path.interests_results where user_id = %(uid)s)) as quiz
        """,
        {"uid": user_id},
    ).fetchone()
    return completion(
        profile,
        counters["skills"] or 0,
        counters["languages"] or 0,
        counters["extras"] or 0,
        bool(counters["quiz"]),
    )


def cv_snapshot(conn, user_id, profile: dict) -> dict:
    return {
        "user_id": str(user_id),
        "full_name": profile.get("full_name"),
        "email": profile.get("email"),
        "university": profile.get("university"),
        "college": profile.get("college"),
        "major": profile.get("major"),
        "study_year": profile.get("study_year"),
        "city": profile.get("city"),
        "bio": profile.get("bio"),
        "skills": [
            {"name": row["skill_name"], "level": row["level"]}
            for row in get_skills(conn, user_id)
        ],
        "languages": [
            {"language": row["language"], "proficiency": row["proficiency"]}
            for row in get_languages(conn, user_id)
        ],
        "courses": [
            {"title": row["title"], "provider": row["provider"], "year": row["year"]}
            for row in get_courses(conn, user_id)
        ],
        "projects": [
            {"title": row["title"], "description": row["description"], "link": row["link"]}
            for row in get_projects(conn, user_id)
        ],
        "experiences": [
            {
                "title": row["title"],
                "organization": row["organization"],
                "period": row["period"],
                "description": row["description"],
            }
            for row in get_experiences(conn, user_id)
        ],
    }
