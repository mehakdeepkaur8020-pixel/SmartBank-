from fastapi import APIRouter, Depends, HTTPException, Request, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pathlib import Path
from typing import Optional
from app.database import get_db
from app.models.models import User, Customer, Account, Transaction, Loan, AuditLog, FAQ
from app.utils.dependencies import require_admin, get_template_context
from app.services.auth_service import update_user_role, toggle_user_active
from app.utils.security import cents_to_currency

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))
router = APIRouter(prefix="/admin", tags=["Administrator Portal"])

@router.get("/dashboard", response_class=HTMLResponse)
def admin_dashboard(
    request: Request,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    ctx = get_template_context(request, user, db)

    total_users = db.query(User).count()
    total_customers = db.query(Customer).count()
    active_accounts = db.query(Account).filter(Account.status == "ACTIVE").count()
    total_txns = db.query(Transaction).count()
    pending_loans = db.query(Loan).filter(Loan.status == "PENDING").count()

    recent_logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(8).all()
    recent_users = db.query(User).order_by(User.created_at.desc()).limit(5).all()

    deposit_count = db.query(Transaction).filter(Transaction.transaction_type == "DEPOSIT").count()
    withdraw_count = db.query(Transaction).filter(Transaction.transaction_type == "WITHDRAWAL").count()
    transfer_count = db.query(Transaction).filter(Transaction.transaction_type == "TRANSFER").count()

    ctx.update({
        "total_users": total_users,
        "total_customers": total_customers,
        "active_accounts": active_accounts,
        "total_transactions": total_txns,
        "pending_loans": pending_loans,
        "recent_logs": recent_logs,
        "recent_users": recent_users,
        "txn_chart_data": [deposit_count, withdraw_count, transfer_count]
    })
    return templates.TemplateResponse(request=request, name="admin/dashboard.html", context=ctx)

@router.get("/users", response_class=HTMLResponse)
def admin_users(
    request: Request,
    msg: Optional[str] = None,
    error: Optional[str] = None,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    ctx = get_template_context(request, user, db)
    users = db.query(User).order_by(User.created_at.desc()).all()
    ctx.update({"users": users, "message": msg, "error": error})
    return templates.TemplateResponse(request=request, name="admin/users.html", context=ctx)

@router.post("/users/{target_user_id}/role")
def change_role_action(
    target_user_id: int,
    role: str = Form(...),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    try:
        update_user_role(db, target_user_id, role, admin_user_id=user.id)
        return RedirectResponse(url="/admin/users?msg=Role+updated+successfully.", status_code=303)
    except Exception as e:
        return RedirectResponse(url=f"/admin/users?error={str(e)}", status_code=303)

@router.post("/users/{target_user_id}/toggle-active")
def toggle_active_action(
    target_user_id: int,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    if target_user_id == user.id:
        return RedirectResponse(url="/admin/users?error=You+cannot+deactivate+your+own+account.", status_code=303)
    try:
        u = toggle_user_active(db, target_user_id, admin_user_id=user.id)
        st = "activated" if u.is_active else "deactivated"
        return RedirectResponse(url=f"/admin/users?msg=User+{u.username}+{st}.", status_code=303)
    except Exception as e:
        return RedirectResponse(url=f"/admin/users?error={str(e)}", status_code=303)

@router.get("/audit-logs", response_class=HTMLResponse)
def admin_audit_logs(
    request: Request,
    action: Optional[str] = None,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    ctx = get_template_context(request, user, db)
    query = db.query(AuditLog)
    if action:
        query = query.filter(AuditLog.action == action.upper())
    logs = query.order_by(AuditLog.created_at.desc()).limit(150).all()
    ctx.update({"logs": logs, "filter_action": action})
    return templates.TemplateResponse(request=request, name="admin/audit_logs.html", context=ctx)

@router.get("/faqs", response_class=HTMLResponse)
def admin_faqs(
    request: Request,
    msg: Optional[str] = None,
    error: Optional[str] = None,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    ctx = get_template_context(request, user, db)
    faqs = db.query(FAQ).order_by(FAQ.id.asc()).all()
    ctx.update({"faqs": faqs, "message": msg, "error": error})
    return templates.TemplateResponse(request=request, name="admin/faqs.html", context=ctx)

@router.post("/faqs/new")
def add_faq_action(
    category: str = Form(...),
    question: str = Form(...),
    keywords: str = Form(...),
    answer: str = Form(...),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    try:
        faq = FAQ(
            category=category.strip(),
            question=question.strip(),
            keywords=keywords.strip(),
            answer=answer.strip(),
            is_active=True
        )
        db.add(faq)
        db.commit()
        return RedirectResponse(url="/admin/faqs?msg=New+FAQ+entry+added+successfully.", status_code=303)
    except Exception as e:
        return RedirectResponse(url=f"/admin/faqs?error={str(e)}", status_code=303)
