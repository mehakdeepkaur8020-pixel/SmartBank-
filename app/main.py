from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager
from pathlib import Path
from sqlalchemy.orm import Session

from app.config import settings
from app.database import init_db, get_db
from app.services.faq_service import seed_default_faqs
from app.utils.dependencies import get_current_user_optional, get_template_context

from app.routers import auth, customer, employee, admin, reports, chatbot

BASE_DIR = Path(__file__).resolve().parent

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables and default FAQs on startup
    init_db()
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        seed_default_faqs(db)
    finally:
        db.close()
    yield

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Cross-Platform Bank Management System with Hybrid AI Customer Support Chatbot",
    lifespan=lifespan
)

# Static and Templates
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
UPLOAD_ROOT = BASE_DIR.parent / "uploads"
UPLOAD_ROOT.mkdir(exist_ok=True, parents=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_ROOT)), name="uploads")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Include Routers
app.include_router(auth.router)
app.include_router(customer.router)
app.include_router(employee.router)
app.include_router(admin.router)
app.include_router(reports.router)
app.include_router(chatbot.router)

@app.get("/", response_class=HTMLResponse)
def index_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user_optional(request, db)
    if user:
        if user.role == "admin":
            return RedirectResponse(url="/admin/dashboard", status_code=303)
        elif user.role == "employee":
            return RedirectResponse(url="/employee/dashboard", status_code=303)
        return RedirectResponse(url="/customer/dashboard", status_code=303)

    ctx = get_template_context(request, None, db)
    return templates.TemplateResponse(request=request, name="index.html", context=ctx)

@app.get("/health")
def health_check():
    return {
        "status": "online",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "ai_provider": settings.AI_PROVIDER,
        "ai_active": bool(settings.GEMINI_API_KEY)
    }

@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return templates.TemplateResponse(request=request, name="404.html", context={}, status_code=404)

@app.exception_handler(500)
async def server_error_handler(request: Request, exc):
    return templates.TemplateResponse(request=request, name="500.html", context={"error": str(exc)}, status_code=500)
