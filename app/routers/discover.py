import json

from fastapi import APIRouter, Request

from ..content import INTEREST_FIELDS, QUIZ
from ..db import tx
from ..queries import get_latest_quiz
from ..web import flash, redirect, render, require_user, verify_csrf

router = APIRouter()


@router.get("/discover")
def discover_page(request: Request, retake: int = 0):
    user = require_user(request)
    with tx(user.id) as conn:
        result = get_latest_quiz(conn, user.id)
    return render(
        request,
        "discover.html",
        quiz=QUIZ,
        result=result,
        fields=INTEREST_FIELDS,
        retake=bool(retake),
    )


@router.post("/discover")
async def discover_submit(request: Request):
    user = require_user(request)
    form = await request.form()
    verify_csrf(request, form.get("csrf"))

    answers = {}
    scores = {key: 0 for key in INTEREST_FIELDS}
    for question in QUIZ:
        raw = form.get(question["id"])
        try:
            index = int(raw)
        except (TypeError, ValueError):
            index = -1
        if index < 0 or index >= len(question["options"]):
            return redirect("/discover")
        option = question["options"][index]
        answers[question["id"]] = {"option": index, "label": option["label"]}
        for field, weight in option["weights"].items():
            scores[field] = scores.get(field, 0) + weight

    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    top = [key for key, value in ranked[:2] if value > 0]
    suggested = [INTEREST_FIELDS[key]["label"] for key in top]

    with tx(user.id) as conn:
        conn.execute(
            "insert into future_path.interests_results (user_id, answers, suggested_fields) values (%s, %s, %s)",
            (user.id, json.dumps(answers, ensure_ascii=False), suggested),
        )
    response = redirect("/discover")
    return flash(response, request, "تم حفظ نتيجتك الإرشادية. هذه النتيجة إرشادية وليست تقييماً أكاديمياً معتمداً.")
