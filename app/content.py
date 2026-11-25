from datetime import date, datetime

AR_MONTHS = [
    "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
    "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر",
]

DEMO_NOTICE = "بيانات تجريبية لأغراض العرض فقط"

OPP_TYPE = {"training": "تدريب", "job": "وظيفة"}

WORK_MODE = {"onsite": "في المقر", "remote": "عن بُعد", "hybrid": "هجين"}

OPP_STATUS = {
    "draft": "مسودة",
    "pending_review": "قيد المراجعة",
    "published": "منشورة وموثقة",
    "suspended": "موقوفة للمراجعة",
    "closed": "منتهية",
}

APP_STATUS = {
    "submitted": "تم الاستلام",
    "under_review": "قيد المراجعة",
    "invited": "تمت دعوة الطالب",
    "accepted": "مقبول",
    "rejected": "مرفوض",
    "withdrawn": "انسحب الطالب",
}

APP_STATUS_ACTIVE = ("submitted", "under_review", "invited")

BADGE_CLASS = {
    "draft": "badge-neutral",
    "pending_review": "badge-warn",
    "published": "badge-ok",
    "suspended": "badge-danger",
    "closed": "badge-neutral",
    "submitted": "badge-info",
    "under_review": "badge-warn",
    "invited": "badge-accent",
    "accepted": "badge-ok",
    "rejected": "badge-danger",
    "withdrawn": "badge-neutral",
    "pending": "badge-warn",
    "verified": "badge-ok",
    "rejected_org": "badge-danger",
    "open": "badge-warn",
    "resolved": "badge-ok",
    "dismissed": "badge-neutral",
}

SKILL_LEVELS = {1: "مبتدئ", 2: "أساسي", 3: "متوسط", 4: "متقدم", 5: "خبير"}

PROFICIENCY = {
    "beginner": "مبتدئ",
    "intermediate": "متوسط",
    "advanced": "متقدم",
    "native": "لغة أم",
}

CATEGORIES = {
    "digital": "المهارات الرقمية",
    "languages": "اللغات",
    "communication": "التواصل",
    "professional": "المهارات المهنية",
    "entrepreneurship": "ريادة الأعمال",
}

PATH_LEVEL = {"beginner": "مبتدئ", "intermediate": "متوسط", "advanced": "متقدم"}

STUDY_YEARS = ["السنة الأولى", "السنة الثانية", "السنة الثالثة", "السنة الرابعة", "السنة الخامسة", "خريج"]

CITIES = ["طرابلس", "بنغازي", "مصراتة", "الزاوية", "سبها", "البيضاء", "عن بُعد"]

FIELDS = [
    "التسويق الرقمي",
    "تقنية المعلومات",
    "المحتوى والكتابة",
    "إدارة الأعمال",
    "التصميم",
    "المالية والمحاسبة",
    "خدمة العملاء والدعم",
    "التعليم والتدريب",
]

UNIVERSITIES = [
    "جامعة القمة الحديثة",
    "جامعة طرابلس",
    "جامعة بنغازي",
    "جامعة مصراتة",
    "جامعة الزاوية",
    "أخرى",
]

INTEREST_FIELDS = {
    "marketing": {
        "label": "التسويق الرقمي",
        "blurb": "بناء الحملات، تحليل الجمهور، وإدارة المنصات الاجتماعية والإعلانات المدفوعة.",
    },
    "tech": {
        "label": "تقنية المعلومات",
        "blurb": "البرمجة، قواعد البيانات، الدعم التقني، وحل المشكلات التقنية اليومية.",
    },
    "content": {
        "label": "المحتوى والكتابة",
        "blurb": "صياغة النصوص، كتابة المحتوى التسويقي، والتحرير بالعربية والإنجليزية.",
    },
    "business": {
        "label": "إدارة الأعمال",
        "blurb": "تنظيم العمل، إدارة المشاريع، التخطيط، والقيادة والتنسيق بين الفرق.",
    },
    "design": {
        "label": "التصميم",
        "blurb": "تصميم الواجهات والمواد البصرية وتحسين تجربة المستخدم.",
    },
    "finance": {
        "label": "المالية والمحاسبة",
        "blurb": "الأرقام والتحليل المالي وإعداد التقارير والمتابعة المحاسبية.",
    },
    "support": {
        "label": "خدمة العملاء والدعم",
        "blurb": "التواصل مع العملاء، حل الشكاوى، وبناء تجربة خدمة مريحة.",
    },
    "education": {
        "label": "التعليم والتدريب",
        "blurb": "شرح المفاهيم، تصميم التدريب، ومساعدة الآخرين على التعلم.",
    },
}

QUIZ = [
    {
        "id": "q1",
        "text": "أي نشاط تستمتع به أكثر في يومك؟",
        "options": [
            {"label": "تصميم حملة للترويج لمنتج أو فكرة", "weights": {"marketing": 3, "content": 1}},
            {"label": "حل مشكلة تقنية أو تجربة برنامج جديد", "weights": {"tech": 3, "support": 1}},
            {"label": "كتابة نص أو صياغة محتوى جذاب", "weights": {"content": 3, "marketing": 1}},
            {"label": "تنظيم أرقام وتحليل بيانات وميزانيات", "weights": {"finance": 2, "business": 2}},
        ],
    },
    {
        "id": "q2",
        "text": "عند العمل داخل فريق، ما دورك الطبيعي؟",
        "options": [
            {"label": "مصدر الأفكار الإبداعية", "weights": {"marketing": 2, "design": 2}},
            {"label": "من ينظّم الخطة ويوزّع المهام", "weights": {"business": 3}},
            {"label": "من يشرح ويقنع ويتواصل مع الآخرين", "weights": {"support": 2, "education": 1, "marketing": 1}},
            {"label": "من يبني الحل تقنياً", "weights": {"tech": 3}},
        ],
    },
    {
        "id": "q3",
        "text": "أي بيئة عمل تجذبك أكثر؟",
        "options": [
            {"label": "شركة تقنية أو منصة رقمية", "weights": {"tech": 2, "marketing": 1}},
            {"label": "مؤسسة تعليمية أو مركز تدريب", "weights": {"education": 3}},
            {"label": "وكالة تسويق أو استوديو تصميم", "weights": {"design": 2, "content": 2, "marketing": 1}},
            {"label": "بنك أو شركة مالية", "weights": {"finance": 3}},
        ],
    },
    {
        "id": "q4",
        "text": "أي مهمة تنجزها بسهولة وبدون مجهود كبير؟",
        "options": [
            {"label": "تقديم عرض وإقناع الآخرين بفكرة", "weights": {"business": 1, "marketing": 1, "education": 1}},
            {"label": "تشخيص عطل وإصلاحه خطوة بخطوة", "weights": {"tech": 2, "support": 2}},
            {"label": "كتابة مقال أو منشور واضح ومؤثر", "weights": {"content": 3}},
            {"label": "تنسيق واجهة أو تصميم بصري مرتب", "weights": {"design": 3}},
        ],
    },
    {
        "id": "q5",
        "text": "ما المهارة التي تريد تطويرها أولاً؟",
        "options": [
            {"label": "التسويق الرقمي والإعلانات", "weights": {"marketing": 3}},
            {"label": "البرمجة وقواعد البيانات", "weights": {"tech": 3}},
            {"label": "اللغة الإنجليزية والكتابة", "weights": {"content": 2, "education": 1}},
            {"label": "القيادة وإدارة المشاريع", "weights": {"business": 2, "finance": 1}},
        ],
    },
]

HOW_IT_WORKS = [
    ("أنشئ حسابك", "سجّل ببريدك الجامعي وأكمل بياناتك الأساسية في دقيقة."),
    ("اكتشف اتجاهك", "أجب عن أسئلة قصيرة لتحصل على مجالات إرشادية تناسبك."),
    ("طوّر مهاراتك", "اختر مساراً عملياً وابدأ التعلم بخطوات واضحة."),
    ("قدّم على الفرص", "تصفح الفرص الموثقة وقدّم بسيرتك المحفوظة في المنصة."),
]

SERVICES = [
    ("ملف مهني موحد", "بياناتك الأكاديمية ومهاراتك ولغاتك في مكان واحد جاهز للتقديم.", "profile"),
    ("اكتشف نفسك", "اختبار قصير يرسم لك مجالات مهنية إرشادية غير معتمدة.", "compass"),
    ("مسارات مهارات", "مسارات منظمة في المهارات الرقمية واللغات والتواصل وريادة الأعمال.", "path"),
    ("سيرة ذاتية جاهزة", "تجميع تلقائي لبياناتك مع معاينة وطباعة أو حفظ PDF.", "doc"),
    ("فرص موثقة", "تدريب ووظائف مراجعها فريق المنصة قبل النشر مع تاريخ نشر واضح.", "briefcase"),
    ("متابعة الطلبات", "اعرف حالة كل طلب خطوة بخطوة من التقديم حتى الرد.", "bell"),
]


def fmt_date(value) -> str:
    if value is None:
        return "—"
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return f"{value.day} {AR_MONTHS[value.month - 1]} {value.year}"
    return str(value)


def fmt_datetime(value) -> str:
    if isinstance(value, datetime):
        return f"{fmt_date(value)} — {value.strftime('%H:%M')}"
    return fmt_date(value)


def days_left(deadline) -> int | None:
    if deadline is None:
        return None
    if isinstance(deadline, datetime):
        deadline = deadline.date()
    return (deadline - date.today()).days


def completion(profile: dict, skills: int, languages: int, extras: int, quiz_done: bool) -> dict:
    checks = []
    p = profile or {}
    basic = all(p.get(k) for k in ("university", "college", "major", "study_year"))
    checks.append(("البيانات الأكاديمية", basic, "أكمل الجامعة والكلية والتخصص والسنة", 30))
    checks.append(("النبذة الشخصية", bool((p.get("bio") or "").strip()), "اكتب نبذة قصيرة عنك وعن أهدافك", 12))
    checks.append(("المهارات", skills >= 2, "أضف مهارتين على الأقل", 18))
    checks.append(("اللغات", languages >= 1, "أضف لغة واحدة على الأقل", 10))
    checks.append(("الدورات والمشاريع والخبرات", extras >= 1, "أضف دورة أو مشروعاً أو خبرة", 10))
    checks.append(("اكتشف نفسك", quiz_done, "أكمل اختبار اكتشف نفسك", 10))
    checks.append(("السيرة الذاتية", basic and bool((p.get("bio") or "").strip()), "تجهيز السيرة يتطلب البيانات الأساسية والنبذة", 10))
    score = sum(weight for _, ok, _, weight in checks if ok)
    tips = [tip for _, ok, tip, _ in checks if not ok]
    return {"score": min(score, 100), "checks": checks, "tips": tips}
