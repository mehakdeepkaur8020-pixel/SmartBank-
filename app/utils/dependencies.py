from fastapi import Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from typing import Optional, List
from app.database import get_db
from app.models.models import User, Notification
from app.utils.security import verify_session_token, cents_to_currency
from app.config import settings

def get_current_user_optional(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    """Retrieve current user from session cookie if present and valid."""
    token = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if not token:
        return None

    payload = verify_session_token(token)
    if not payload:
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    return user

def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Ensure user is logged in. Redirect to login for HTML requests, 401 for API."""
    user = get_current_user_optional(request, db)
    if not user:
        if "text/html" in request.headers.get("accept", ""):
            raise HTTPException(
                status_code=status.HTTP_303_SEE_OTHER,
                detail="Authentication required",
                headers={"Location": "/auth/login?msg=Please+login+to+continue"}
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    return user

def require_role(allowed_roles: List[str]):
    """Enforce role-based access control."""
    def role_checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You do not have permissions for this resource."
            )
        return user
    return role_checker

require_customer = require_role(["customer"])
require_employee = require_role(["employee", "admin"])
require_admin = require_role(["admin"])

def get_template_context(request: Request, user: Optional[User], db: Session) -> dict:
    """Build standard template context with user, notifications, and helper functions."""
    unread_count = 0
    notifications = []
    if user:
        unread_count = db.query(Notification).filter(
            Notification.user_id == user.id,
            Notification.is_read == False
        ).count()
        notifications = db.query(Notification).filter(
            Notification.user_id == user.id
        ).order_by(Notification.created_at.desc()).limit(5).all()

    return {
        "request": request,
        "current_user": user,
        "unread_notifications_count": unread_count,
        "recent_notifications": notifications,
        "app_name": settings.APP_NAME,
        "currency_symbol": settings.CURRENCY_SYMBOL,
        "cents_to_currency": cents_to_currency,
        "ai_enabled": settings.AI_ENABLED,
        "ai_active": bool(settings.GEMINI_API_KEY)
    }
