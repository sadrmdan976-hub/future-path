"""Seed FUTURE PATH demo data (idempotent).

Run as the database owner (postgres):
    .venv/Scripts/python.exe scripts/seed_db.py

Passwords are generated here, written only to a private file on the Desktop,
and never printed to the console or stored in the repository.
"""
from __future__ import annotations

import secrets
import string
import sys
from datetime import date
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.config import settings  # noqa: E402
from app.security import hash_password  # noqa: E402
from app.queries import cv_snapshot  # noqa: E402

CREDENTIALS_FILE = Path.home() / "Desktop" / "FUTURE PATH - بيانات الدخول.txt"

DEMO_PASSWORD_CHARS = string.ascii_letters + string.digits


def new_password(length: int = 14) -> str:
    return "Fp-" + "".join(secrets.choice(DEMO_PASSWORD_CHARS) for _ in range(length))


def ensure_user(conn, email: str, full_name: str, *, is_demo: bool, is_admin: bool, password: str) -> str:
    row = conn.execute(
        "select id from future_path.users where lower(email) = lower(%s)", (email,)
    ).fetchone()
    password_hash = hash_password(password)
    if row:
        uid = row["id"]
        conn.execute(
            """update future_path.users
               set password_hash = %s, full_name = %s, account_type = %s,
                   is_demo = %s, is_active = true, updated_at = now()
               where id = %s""",
            (password_hash, full_name, "admin" if is_admin else "student", is_demo, uid),
        )
    else:
        uid = conn.execute(
            """insert into future_path.users (email, password_hash, full_name, account_type, is_demo)
               values (%s, %s, %s, %s, %s) returning id""",
            (email.lower(), password_hash, full_name, "admin" if is_admin else "student", is_demo),
        ).fetchone()["id"]
        conn.execute("insert into future_path.profiles (user_id) values (%s)", (uid,))
    conn.execute("delete from future_path.sessions where user_id = %s", (uid,))
    return str(uid)


def seed_student(conn, uid: str) -> None:
    conn.execute(
        """insert into future_path.profiles
             (user_id, university, college, major, study_year, city, bio)
           values (%s, %s, %s, %s, %s, %s, %s)
           on conflict (user_id) do update set
             university = excluded.university, college = excluded.college,
             major = excluded.major, study_year = excluded.study_year,
             city = excluded.city, bio = excluded.bio, updated_at = now()""",
        (
            uid,
            "جامعة القمة الحديثة",
            "كلية إدارة الأعمال",
            "إدارة الأعمال",
            "السنة الثالثة",
            "طرابلس",
            "طالب في السنة الثالثة إدارة أعمال، مهتم بالتسويق الرقمي وبناء الحملات، "
            "أبحث عن تدريب عملي أطبق فيه ما تعلمته وأطور مهاراتي في تحليل السوق وصناعة المحتوى.",
        ),
    )

    conn.execute("delete from future_path.skills where user_id = %s", (uid,))
    for i, (name, level) in enumerate(
        [("التسويق الرقمي", 4), ("إدارة وسائل التواصل", 3), ("Excel", 3), ("كتابة المحتوى", 2), ("تحليل البيانات", 2)]
    ):
        conn.execute(
            "insert into future_path.skills (user_id, skill_name, level, sort_order) values (%s, %s, %s, %s)",
            (uid, name, level, i),
        )

    conn.execute("delete from future_path.languages where user_id = %s", (uid,))
    for i, (lang, prof) in enumerate([("العربية", "native"), ("الإنجليزية", "intermediate"), ("الفرنسية", "beginner")]):
        conn.execute(
            "insert into future_path.languages (user_id, language, proficiency, sort_order) values (%s, %s, %s, %s)",
            (uid, lang, prof, i),
        )

    conn.execute("delete from future_path.courses where user_id = %s", (uid,))
    for i, (title, provider, year) in enumerate(
        [
            ("أساسيات التسويق الرقمي", "منصة إدراك", "2026"),
            ("Excel للمحللين", "Coursera", "2025"),
        ]
    ):
        conn.execute(
            "insert into future_path.courses (user_id, title, provider, year, sort_order) values (%s, %s, %s, %s, %s)",
            (uid, title, provider, year, i),
        )

    conn.execute("delete from future_path.projects where user_id = %s", (uid,))
    for i, (title, desc) in enumerate(
        [
            ("حملة ترويجية افتراضية لنادي ريادة الأعمال", "خطة حملة على إنستغرام لمدة شهر: تحليل الجمهور، تقويم محتوى، ومؤشرات قياس."),
            ("تحليل استبيان تجربة الطلاب", "تنظيف بيانات 120 استجابة وتحويلها إلى لوحة مؤشرات بسيطة في Excel."),
        ]
    ):
        conn.execute(
            "insert into future_path.projects (user_id, title, description, sort_order) values (%s, %s, %s, %s)",
            (uid, title, desc, i),
        )

    conn.execute("delete from future_path.experiences where user_id = %s", (uid,))
    conn.execute(
        """insert into future_path.experiences (user_id, title, organization, period, description, sort_order)
           values (%s, %s, %s, %s, %s, 0)""",
        (
            uid,
            "عضو فريق تنظيم الفعاليات",
            "كلية إدارة الأعمال — جامعة القمة الحديثة",
            "2025 — 2026",
            "تنسيق التسجيل والتواصل مع المشاركين في ثلاث فعاليات طلابية.",
        ),
    )

    has_quiz = conn.execute(
        "select exists(select 1 from future_path.interests_results where user_id = %s) as ok", (uid,)
    ).fetchone()["ok"]
    if not has_quiz:
        answers = {
            "q1": {"option": 0, "label": "تصميم حملة للترويج لمنتج أو فكرة"},
            "q2": {"option": 1, "label": "من ينظّم الخطة ويوزّع المهام"},
            "q3": {"option": 0, "label": "شركة تقنية أو منصة رقمية"},
            "q4": {"option": 0, "label": "تقديم عرض وإقناع الآخرين بفكرة"},
            "q5": {"option": 0, "label": "التسويق الرقمي والإعلانات"},
        }
        conn.execute(
            """insert into future_path.interests_results (user_id, answers, suggested_fields)
               values (%s, %s, %s)""",
            (uid, Jsonb(answers), ["التسويق الرقمي", "إدارة الأعمال"]),
        )


def ensure_org(conn, name: str, city: str, description: str, contact: str, created_by: str) -> str:
    row = conn.execute(
        "select id from future_path.organizations where name = %s limit 1", (name,)
    ).fetchone()
    if row:
        return str(row["id"])
    return str(
        conn.execute(
            """insert into future_path.organizations
                 (name, description, contact_details, city, verification_status, is_demo, created_by)
               values (%s, %s, %s, %s, 'verified', true, %s) returning id""",
            (name, description, contact, city, created_by),
        ).fetchone()["id"]
    )


def ensure_opportunity(conn, org_id: str, created_by: str, data: dict) -> str:
    row = conn.execute(
        """select id from future_path.opportunities
           where organization_id = %s and title = %s limit 1""",
        (org_id, data["title"]),
    ).fetchone()
    if row:
        return str(row["id"])
    return str(
        conn.execute(
            """insert into future_path.opportunities
                 (organization_id, title, type, field, city, work_mode, description, requirements,
                  tasks, location_details, deadline, status, is_verified, is_demo, published_at, created_by)
               values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'published', true, true, now(), %s)
               returning id""",
            (
                org_id, data["title"], data["type"], data["field"], data["city"], data["work_mode"],
                data["description"], data.get("requirements"), data.get("tasks"),
                data.get("location_details"), data["deadline"], created_by,
            ),
        ).fetchone()["id"]
    )


def ensure_path(conn, title: str, category: str, description: str, url: str, level: str, duration: str, demo: bool) -> None:
    exists = conn.execute(
        "select 1 from future_path.learning_paths where title = %s", (title,)
    ).fetchone()
    if exists:
        return
    conn.execute(
        """insert into future_path.learning_paths
             (title, category, description, resource_url, level, duration, is_active, is_demo)
           values (%s, %s, %s, %s, %s, %s, true, %s)""",
        (title, category, description, url, level, duration, demo),
    )


def main() -> None:
    if not settings.DATABASE_URL:
        raise SystemExit("DATABASE_URL is not set. Create .env first.")

    passwords = {
        "student": new_password(),
        "student2": new_password(),
        "admin": new_password(),
    }

    with psycopg.connect(settings.DATABASE_URL, row_factory=dict_row) as conn:
        with conn.transaction():
            admin_id = ensure_user(
                conn,
                "admin@future-path.app",
                "مسؤول المنصة",
                is_demo=False,
                is_admin=True,
                password=passwords["admin"],
            )
            conn.execute(
                """insert into future_path.admin_roles (user_id, role)
                   values (%s, 'superadmin')
                   on conflict (user_id) do update set role = 'superadmin'""",
                (admin_id,),
            )

            student_id = ensure_user(
                conn,
                "ahmed.demo@example.com",
                "أحمد محمد",
                is_demo=True,
                is_admin=False,
                password=passwords["student"],
            )
            seed_student(conn, student_id)

            student2_id = ensure_user(
                conn,
                "sara.demo@example.com",
                "سارة علي",
                is_demo=True,
                is_admin=False,
                password=passwords["student2"],
            )
            conn.execute(
                """insert into future_path.profiles (user_id, university, college, major, study_year, city, bio)
                   values (%s, %s, %s, %s, %s, %s, %s)
                   on conflict (user_id) do update set
                     university = excluded.university, college = excluded.college,
                     major = excluded.major, study_year = excluded.study_year,
                     city = excluded.city, bio = excluded.bio""",
                (
                    student2_id,
                    "جامعة القمة الحديثة",
                    "كلية تقنية المعلومات",
                    "تقنية المعلومات",
                    "السنة الثانية",
                    "طرابلس",
                    "طالبة تقنية معلومات، أتعلم تطوير الويب وأحب دعم المستخدمين وحل المشكلات.",
                ),
            )

            org1 = ensure_org(
                conn,
                "شركة نبض المتوسط للتقنية",
                "طرابلس",
                "شركة تقنية ناشئة تعمل على منتجات رقمية للشركات الصغيرة. (جهة تجريبية)",
                "hr@nabd-demo.example.com",
                admin_id,
            )
            org2 = ensure_org(
                conn,
                "مركز إبداع للتدريب",
                "طرابلس",
                "مركز تدريب يقدم ورشاً في المحتوى والتسويق والمهارات المهنية. (جهة تجريبية)",
                "training@ibdaa-demo.example.com",
                admin_id,
            )
            org3 = ensure_org(
                conn,
                "منصة تعليم بلا حدود",
                "عن بُعد",
                "منصة تعليم إلكتروني تقدم محتوى تعليمياً بالعربية والإنجليزية. (جهة تجريبية)",
                "team@edu-demo.example.com",
                admin_id,
            )

            opps = [
                (org1, {
                    "title": "متدرب تسويق رقمي",
                    "type": "training",
                    "field": "التسويق الرقمي",
                    "city": "طرابلس",
                    "work_mode": "onsite",
                    "description": "تدريب مدفوع جزئياً لمدة ثلاثة أشهر داخل فريق التسويق في شركة نبض المتوسط.\n"
                                   "ستعمل على حملات إعلانية على إنستغرام وفيسبوك، وتحليل نتائج الحملات، وإعداد تقارير أسبوعية.\n"
                                   "الفرصة مناسبة لطالب أو طالبة في السنة الثانية أو الثالثة من تخصص إدارة الأعمال أو التسويق.",
                    "requirements": "معرفة أساسية بأدوات التسويق الرقمي\nمهارة تواصل جيدة بالعربية\nالإلمام بـ Excel\nالالتزام 20 ساعة أسبوعياً",
                    "tasks": "إعداد محتوى الحملات\nمتابعة أداء الإعلانات\nتحليل جمهور المستهدفين\nتجهيز تقارير أسبوعية",
                    "location_details": "برج المتوسط، الطابق الثالث — طرابلس",
                    "deadline": date(2026, 12, 15),
                }),
                (org3, {
                    "title": "مساعد محتوى باللغة الإنجليزية",
                    "type": "training",
                    "field": "المحتوى والكتابة",
                    "city": "عن بُعد",
                    "work_mode": "remote",
                    "description": "فرصة تدريب عن بُعد لطالب يجيد الكتابة بالإنجليزية.\n"
                                   "ستساعد في تحرير الدروس، وكتابة منشورات قصيرة للمنصات الاجتماعية، ومراجعة نصوص المترجمين.\n"
                                   "ساعات مرنة مع اجتماع أسبوعي واحد.",
                    "requirements": "إنجليزية متوسطة إلى متقدمة\nقدرة على الكتابة الواضحة\nاهتمام بالتعليم\nالتزام 10 ساعات أسبوعياً",
                    "tasks": "تحرير نصوص الدروس\nكتابة منشورات قصيرة\nمراجعة الترجمة\nتنسيق المحتوى للنشر",
                    "location_details": "عن بُعد — اجتماع أسبوعي عبر الإنترنت",
                    "deadline": date(2026, 12, 31),
                }),
                (org2, {
                    "title": "مساعد دعم تقني مبتدئ",
                    "type": "job",
                    "field": "تقنية المعلومات",
                    "city": "طرابلس",
                    "work_mode": "onsite",
                    "description": "وظيفة بدوام جزئي مناسبة للطلاب في مركز إبداع للتدريب.\n"
                                   "ستكون أول نقطة تواصل مع المتدربين لحل مشكلات الدخول والمنصة، مع فرصة تعلم صيانة الأجهزة والشبكات.",
                    "requirements": "معرفة أساسية بالحاسوب والشبكات\nأسلوب تواصل ودود\nالقدرة على العمل ضمن فريق\nالدوام 4 ساعات يومياً",
                    "tasks": "استقبال بلاغات المستخدمين\nحل مشكلات الدخول\nإعداد قاعات التدريب\nتوثيق المشكلات المتكررة",
                    "location_details": "مركز إبداع للتدريب — شارع عمر المختار، طرابلس",
                    "deadline": date(2026, 12, 5),
                }),
            ]
            opp_ids = {data["title"]: ensure_opportunity(conn, org_id, admin_id, data) for org_id, data in opps}

            # One application from the second student so the admin dashboard has data
            # while Ahmed's apply flow remains available for the live demo.
            first_opp = opp_ids["متدرب تسويق رقمي"]
            exists_app = conn.execute(
                "select 1 from future_path.applications where opportunity_id = %s and student_id = %s",
                (first_opp, student2_id),
            ).fetchone()
            if not exists_app:
                profile = conn.execute(
                    "select p.*, u.full_name, u.email from future_path.profiles p join future_path.users u on u.id = p.user_id where p.user_id = %s",
                    (student2_id,),
                ).fetchone()
                conn.execute(
                    """insert into future_path.applications (opportunity_id, student_id, cv_snapshot, status)
                       values (%s, %s, %s, 'under_review')""",
                    (first_opp, student2_id, Jsonb(cv_snapshot(conn, student2_id, profile))),
                )

            paths = [
                ("أساسيات التسويق الرقمي", "digital", "تعرّف على قنوات التسويق الرقمي وكيف تبني حملة بسيطة وتقيس نتائجها.", "https://learndigital.withgoogle.com/digitalgarage", "beginner", "4 أسابيع"),
                ("إدارة منصات التواصل الاجتماعي", "digital", "خطة محتوى شهرية، تقويم نشر، وطريقة التعامل مع التعليقات والرسائل.", "https://www.coursera.org/learn/social-media-management", "beginner", "3 أسابيع"),
                ("Excel من الصفر إلى التقارير", "digital", "المعادلات والجداول المحورية وبناء تقرير واضح من بياناتك.", "https://www.coursera.org/learn/excel-essentials", "beginner", "5 أسابيع"),
                ("مقدمة في قواعد البيانات", "digital", "مفاهيم الجداول والعلاقات واستعلامات SQL الأساسية.", "https://www.edraak.org", "intermediate", "6 أسابيع"),
                ("الإنجليزية للمقابلات الوظيفية", "languages", "عبارات وأسئلة متكررة في المقابلات، وتدريب على الإجابة بثقة.", "https://www.futurelearn.com", "intermediate", "4 أسابيع"),
                ("الكتابة المهنية بالعربية", "communication", "رسائل البريد، التقارير، وصياغة النصوص الواضحة في بيئة العمل.", "https://www.edraak.org", "beginner", "3 أسابيع"),
                ("التحدث أمام الجمهور", "communication", "بناء عرض مقنع والتغلب على التوتر أثناء التقديم.", "https://www.futurelearn.com", "beginner", "2 أسابيع"),
                ("إعداد السيرة الذاتية وخطاب التقديم", "professional", "سيرة مختصرة ومقنعة، وخطاب تقديم مخصص لكل فرصة.", "https://www.coursera.org/learn/writing-a-resume", "beginner", "أسبوعان"),
                ("إدارة الوقت للطلاب", "professional", "تنظيم المهام والدراسة والعمل دون احتراق.", "https://www.edraak.org", "beginner", "أسبوعان"),
                ("من فكرة إلى مشروع صغير", "entrepreneurship", "اختبار الفكرة، دراسة السوق المبسطة، وخطة إطلاق أولى.", "https://www.coursera.org/learn/entrepreneurship", "intermediate", "5 أسابيع"),
            ]
            for title, cat, desc, url, level, duration in paths:
                ensure_path(conn, title, cat, desc, url, level, duration, demo=True)

            ensure_path(
                conn,
                "أساسيات التسجيل الأكاديمي",
                "professional",
                "مسار تعريفي يشرح للطالب الجديد كيفية التسجيل في المقررات ومتابعة الجدول الدراسي.",
                "https://www.qimma.example.edu",
                "beginner",
                "أسبوع واحد",
                demo=False,
            )

    lines = [
        "FUTURE PATH | مستقبلك — بيانات الدخول التجريبية",
        "=" * 50,
        "",
        "ملاحظة: هذه البيانات وهمية لأغراض العرض فقط.",
        "",
        "١) حساب الطالب التجريبي (أحمد محمد)",
        "   البريد: ahmed.demo@example.com",
        f"   كلمة المرور: {passwords['student']}",
        "",
        "٢) حساب مسؤول المنصة (منفصل — لا يُنشأ عبر التسجيل)",
        "   البريد: admin@future-path.app",
        f"   كلمة المرور: {passwords['admin']}",
        "",
        "٣) حساب طالب ثانٍ لاختبار العزل بين الطلاب",
        "   البريد: sara.demo@example.com",
        f"   كلمة المرور: {passwords['student2']}",
        "",
        "استخدم الحساب الأول في العرض الحي، والثالث لإثبات أن أي طالب",
        "لا يستطيع رؤية أو تعديل بيانات طالب آخر.",
        "",
        "لا تشارك هذا الملف علناً. لإعادة تعيين كلمة مرور أي حساب:",
        "سجّل دخول المسؤول ← المستخدمون ← رابط إعادة تعيين.",
    ]
    CREDENTIALS_FILE.parent.mkdir(parents=True, exist_ok=True)
    CREDENTIALS_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("Seed completed.")
    print(f"Credentials written to: {CREDENTIALS_FILE}")
    print("Demo student: ahmed.demo@example.com")
    print("Admin: admin@future-path.app")
    print("Second student: sara.demo@example.com")


if __name__ == "__main__":
    main()
