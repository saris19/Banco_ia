"""Entry point: Banco de Proyectos de Grado (FastAPI)."""
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from .database import Base, SessionLocal, engine
from .routers import admin, applications, auth, topics
from .seed import seed_demo_data

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")
# In production (HTTPS) the session cookie must only travel over secure connections.
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "0") == "1"


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    if os.getenv("SEED_DEMO_DATA", "1") == "1":
        with SessionLocal() as db:
            seed_demo_data(db)
    yield


app = FastAPI(
    title="Banco de Proyectos de Grado",
    description="Repositorio de temas de grado: publicación, postulación sin duplicados y seguimiento con el asesor.",
    version="0.5.0",
    lifespan=lifespan,
)
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    same_site="lax",
    https_only=COOKIE_SECURE,
    max_age=60 * 60 * 8,
)


@app.middleware("http")
async def disable_api_caching(request: Request, call_next):
    """API responses depend on the logged-in user: no proxy or CDN may cache them."""
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/api/health", include_in_schema=False)
def health_check():
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(topics.router)
app.include_router(applications.router)
app.include_router(admin.router)

# Serves the web interface locally (in production Vercel serves the same folder).
# Mounted last so it never shadows the /api routes.
if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
