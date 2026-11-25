import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.gzip import GZipMiddleware

from .config import BASE_DIR, settings
from .db import close_pool, init_pool
from .routers import admin, applications, auth, dashboard, discover, opportunities, profile, public, skills
from .web import RedirectLogin, SessionMiddleware, login_url, render

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_pool()
    yield
    close_pool()


app = FastAPI(title="FUTURE PATH | مستقبلك", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(SessionMiddleware)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "app" / "static")), name="static")

app.include_router(public.router)
app.include_router(auth.router)
app.include_router(auth.account_router)
app.include_router(dashboard.router)
app.include_router(profile.router)
app.include_router(discover.router)
app.include_router(skills.router)
app.include_router(opportunities.router)
app.include_router(applications.router)
app.include_router(admin.router)


@app.exception_handler(RedirectLogin)
async def redirect_login_handler(request: Request, exc: RedirectLogin):
    return RedirectResponse(login_url(exc.next_path), status_code=303)


@app.exception_handler(HTTPException)
async def http_error_handler(request: Request, exc: HTTPException):
    if exc.status_code == 403:
        return render(request, "errors/403.html", status_code=403)
    if exc.status_code == 404:
        return render(request, "errors/404.html", status_code=404)
    return render(request, "errors/error.html", code=exc.status_code, message=exc.detail, status_code=exc.status_code)


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    logging.getLogger("futurepath").exception("unhandled error")
    if request.url.path.startswith("/healthz"):
        return JSONResponse({"ok": False}, status_code=500)
    return render(request, "errors/500.html", status_code=500)


@app.get("/healthz")
def healthz():
    from .db import tx

    with tx() as conn:
        conn.execute("select 1")
    return {"ok": True, "app": "future-path"}
