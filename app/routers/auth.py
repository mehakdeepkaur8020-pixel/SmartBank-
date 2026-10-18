from fastapi import APIRouter, Depends, HTTPException, Request, Form, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pathlib import Path
from typing import Optional
from app.database import get_db
from app.models.models import User
from app.schemas.schemas import UserRegister
from app.services.auth_service import (
    register_user,
    authenticate_user,
    change_password,
    get_user_by_id
)
from app.utils.security import generate_session_token
from app.utils.dependencies import get_current_user, get_current_user_optional, get_template_context
from app.config import settings

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))
router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, msg: Optional[str] = None, error: Optional[str] = None, db: Session = Depends(get_db)):
    user = get_current_user_optional(request, db)
    if user:
        if user.role == "admin":
            return RedirectResponse(url="/admin/dashboard", status_code=303)
        elif user.role == "employee":
            return RedirectResponse(url="/employee/dashboard", status_code=303)
        return RedirectResponse(url="/customer/dashboard", status_code=303)

    ctx = get_template_context(request, None, db)
    ctx.update({"message": msg, "error": error})
    return templates.TemplateResponse(request=request, name="auth/login.html", context=ctx)

@router.post("/login")
def login_action(
    request: Request,
    response: Response,
    username_or_email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    client_ip = request.client.host if request.client else None
    try:
        user = authenticate_user(db, username_or_email, password, ip_address=client_ip)
        if not user:
            ctx = get_template_context(request, None, db)
            ctx.update({"error": "Invalid username/email or password.", "username_or_email": username_or_email})
            return templates.TemplateResponse(request=request, name="auth/login.html", context=ctx, status_code=400)

        # Generate secure session token
        token = generate_session_token(user_id=user.id, role=user.role, username=user.username)
        
        target_url = "/customer/dashboard"
        if user.role == "admin":
            target_url = "/admin/dashboard"
        elif user.role == "employee":
            target_url = "/employee/dashboard"

        redirect = RedirectResponse(url=target_url, status_code=status.HTTP_303_SEE_OTHER)
        redirect.set_cookie(
            key=settings.SESSION_COOKIE_NAME,
            value=token,
            max_age=settings.SESSION_EXPIRE_HOURS * 3600,
            httponly=True,
            samesite="lax",
            secure=not settings.DEBUG
        )
        return redirect

    except PermissionError as pe:
        ctx = get_template_context(request, None, db)
        ctx.update({"error": str(pe), "username_or_email": username_or_email})
        return templates.TemplateResponse(request=request, name="auth/login.html", context=ctx, status_code=403)
    except Exception as e:
        ctx = get_template_context(request, None, db)
        ctx.update({"error": "An unexpected error occurred during login. Please try again.", "username_or_email": username_or_email})
        return templates.TemplateResponse(request=request, name="auth/login.html", context=ctx, status_code=500)

@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request, error: Optional[str] = None, db: Session = Depends(get_db)):
    user = get_current_user_optional(request, db)
    if user:
        return RedirectResponse(url="/customer/dashboard", status_code=303)
    ctx = get_template_context(request, None, db)
    ctx.update({"error": error})
    return templates.TemplateResponse(request=request, name="auth/register.html", context=ctx)

@router.post("/register")
def register_action(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    first_name: str = Form(...),
    last_name: str = Form(...),
    phone: str = Form(...),
    address: str = Form(...),
    account_type: str = Form("SAVINGS"),
    initial_deposit: float = Form(0.0),
    db: Session = Depends(get_db)
):
    if password != confirm_password:
        ctx = get_template_context(request, None, db)
        ctx.update({
            "error": "Passwords do not match.",
            "form": locals()
        })
        return templates.TemplateResponse(request=request, name="auth/register.html", context=ctx, status_code=400)

    try:
        reg_data = UserRegister(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            address=address,
            account_type=account_type,
            initial_deposit=initial_deposit
        )
        client_ip = request.client.host if request.client else None
        user = register_user(db, reg_data, role="customer", ip_address=client_ip)
        
        # Log in newly registered customer directly and redirect to Video KYC verification
        token = generate_session_token(user_id=user.id, role=user.role, username=user.username)
        redirect = RedirectResponse(
            url="/customer/apply-account?msg=Registration+successful!+Please+complete+Video+KYC+and+document+upload+to+open+your+bank+account.",
            status_code=status.HTTP_303_SEE_OTHER
        )
        redirect.set_cookie(
            key=settings.SESSION_COOKIE_NAME,
            value=token,
            max_age=settings.SESSION_EXPIRE_HOURS * 3600,
            httponly=True,
            samesite="lax",
            secure=not settings.DEBUG
        )
        return redirect

    except ValueError as ve:
        ctx = get_template_context(request, None, db)
        ctx.update({"error": str(ve), "form": locals()})
        return templates.TemplateResponse(request=request, name="auth/register.html", context=ctx, status_code=400)
    except Exception as e:
        ctx = get_template_context(request, None, db)
        ctx.update({"error": f"Registration failed: {str(e)}", "form": locals()})
        return templates.TemplateResponse(request=request, name="auth/register.html", context=ctx, status_code=400)

@router.get("/logout")
def logout():
    redirect = RedirectResponse(url="/auth/login?msg=You+have+been+logged+out+successfully.", status_code=status.HTTP_303_SEE_OTHER)
    redirect.delete_cookie(key=settings.SESSION_COOKIE_NAME)
    return redirect

@router.get("/profile", response_class=HTMLResponse)
def profile_page(request: Request, msg: Optional[str] = None, error: Optional[str] = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ctx = get_template_context(request, user, db)
    ctx.update({"message": msg, "error": error, "customer": user.customer_profile})
    return templates.TemplateResponse(request=request, name="auth/profile.html", context=ctx)

@router.post("/change-password")
def change_password_action(
    request: Request,
    old_password: str = Form(...),
    new_password: str = Form(...),
    confirm_new_password: str = Form(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if new_password != confirm_new_password:
        return RedirectResponse(url="/auth/profile?error=New+passwords+do+not+match.", status_code=303)
    if len(new_password) < 8:
        return RedirectResponse(url="/auth/profile?error=New+password+must+be+at+least+8+characters.", status_code=303)

    try:
        change_password(db, user.id, old_password, new_password)
        return RedirectResponse(url="/auth/profile?msg=Password+updated+successfully.", status_code=303)
    except Exception as e:
        return RedirectResponse(url=f"/auth/profile?error={str(e)}", status_code=303)
