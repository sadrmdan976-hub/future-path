# FUTURE PATH | مستقبلك

منصة ويب عربية (RTL) تربط طلاب جامعة القمة الحديثة بفرص التدريب والوظائف، مع ملف مهني وسيرة ذاتية وطلبات وتوثيق إداري للفرص.

**الرابط العام:** يُضاف بعد النشر: `https://<service>.onrender.com`

## المحتوى

- `app/` — تطبيق FastAPI + قوالب Jinja2 + CSS/JS (بدون أي إطار واجهة خارجي).
- `db/schema.sql` — مخطط PostgreSQL كامل: الجداول، القيود، RLS، والدور المقيّد `future_path_app`.
- `db/reset.sql` — إسقاط المخطط محلياً فقط عند الحاجة.
- `scripts/seed_db.py` — بذر بيانات العرض (حسابات وفرص وجهات تجريبية). يكتب بيانات الدخول في ملف على سطح المكتب، ولا يضعها في المستودع.
- `scripts/smoke_test.py` — فحص قبول شامل (47 فحصاً) يعمل ضد أي عنوان: `python scripts/smoke_test.py https://...`
- `scripts/screenshots.py` — لقطات تلقائية عبر Chrome (محلياً).

## التشغيل المحلي

المتطلبات: Python 3.12+، PostgreSQL 16.

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

1. أنشئ قاعدة بيانات فارغة، ثم نفّذ المخطط بحساب المالك:

```bash
psql -U postgres -d future_path -f db/schema.sql
```

2. أنشئ ملف `.env` (غير مرفوع للمستودع):

```ini
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@127.0.0.1:5432/future_path
SESSION_SECRET=ضع-سلسلة-عشوائية-بطول-64-حرفاً-على-الأقل
APP_BASE_URL=http://127.0.0.1:8000
COOKIE_SECURE=false
DEMO_MODE=1
```

3. ابذر بيانات العرض (ينشئ الحسابات ويكتب بيانات الدخول في
   `%USERPROFILE%\Desktop\FUTURE PATH - بيانات الدخول.txt`):

```bash
python scripts/seed_db.py
```

4. شغّل الخادم:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## متغيرات البيئة

| المتغير | الوظيفة |
| --- | --- |
| `DATABASE_URL` | اتصال PostgreSQL بحساب المالك؛ التطبيق يتحول داخلياً للدور المقيّد `future_path_app` في كل معاملة. |
| `SESSION_SECRET` | مفتاح توقيع كوكي الرسائل المؤقتة (32 حرفاً على الأقل). |
| `APP_BASE_URL` | العنوان العام، يُستخدم في الروابط المطلقة. |
| `COOKIE_SECURE` | `true` على HTTPS فقط. |
| `DEMO_MODE` | `1` لإظهار لافتات "بيانات تجريبية". |
| `SMTP_*` | اختياري؛ عند تعبئته يُرسل رابط إعادة التعيين بالبريد بدل الرابط الإداري اليدوي. |

## الأمان

- تفعيل RLS على كل الجداول الشخصية والطلبات، والاتصال دائماً بدور `future_path_app` (NOLOGIN, NOBYPASSRLS) مع `app.user_id` في كل معاملة.
- صلاحية المسؤول لا تُمنح من نموذج التسجيل إطلاقاً؛ تُدار فقط عبر جدول `admin_roles` بإجراء SQL من المالك.
- كلمات المرور مخزّنة بـ scrypt، والجلسات مخزّنة في الخادم (يُخزَّن تجزئة SHA-256 للرمز فقط).
- CSRF مزدوج (كوكي + جلسة)، وكوكي الجلسة `HttpOnly` + `SameSite=Lax`، ورؤوس حماية وCSP.
- لا تُشارك بيانات الطالب تلقائياً؛ تُرسل لقطة السيرة مع الطلب الذي يقدّمه الطالب بنفسه.

## النسخ الاحتياطي

```bash
pg_dump --format=custom --no-owner --file=future_path_$(date +%F).dump "$DATABASE_URL"
```

للاستعادة إلى قاعدة فارغة:

```bash
pg_restore --no-owner --exit-on-error -d "$DATABASE_URL" future_path_2026-11-25.dump
```

على Supabase يمكن أخذ نسخة من لوحة المشروع (Database → Backups) إضافةً إلى الأمر أعلاه عبر Connection String.

## القيود المعروفة

- بدون ذكاء اصطناعي، وبدون حسابات للشركات، وبدون إشعارات — وفق نطاق المرحلة.
- إعادة تعيين كلمة المرور تعمل عبر رابط يديره المسؤول من لوحة الإدارة، إلى أن تُضاف إعدادات SMTP.
- تصدير السيرة يتم بالطباعة/حفظ PDF من المتصفح (تنسيق A4 جاهز)؛ لا يوجد مولّد PDF على الخادم.
- الظهور العام للفرص يتطلب توثيقاً من مسؤول (حالة "موثقة منشورة").
