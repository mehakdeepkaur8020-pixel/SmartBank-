import datetime
from fastapi import APIRouter, Depends, HTTPException, Request, Form, status, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pathlib import Path
from typing import Optional, List
from app.database import get_db
from app.models.models import User, Customer, Account, Transaction, Loan, AccountApplication, ApplicationDocument
from app.schemas.schemas import LoanApplication
from app.utils.dependencies import require_customer, get_template_context
from app.services.account_service import (
    get_customer_by_user_id, get_customer_accounts, create_account,
    submit_account_application, save_application_document, get_customer_applications,
    get_application_by_reference
)
from app.services.transaction_service import deposit, withdraw, transfer, get_transactions_for_account
from app.services.loan_service import apply_for_loan, get_customer_loans, make_loan_repayment
from app.services.notification_service import mark_notification_as_read, mark_all_notifications_as_read
from app.utils.security import cents_to_currency, currency_to_cents

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))
router = APIRouter(prefix="/customer", tags=["Customer Portal"])

@router.get("/dashboard", response_class=HTMLResponse)
def customer_dashboard(
    request: Request,
    msg: Optional[str] = None,
    error: Optional[str] = None,
    user: User = Depends(require_customer),
    db: Session = Depends(get_db)
):
    ctx = get_template_context(request, user, db)
    cust = get_customer_by_user_id(db, user.id)
    accounts = get_customer_accounts(db, cust.id) if cust else []
    
    total_balance_cents = sum(acc.balance_cents for acc in accounts)
    
    # Get recent transactions across all accounts
    account_ids = [acc.id for acc in accounts]
    recent_txns = []
    if account_ids:
        from sqlalchemy import or_
        recent_txns = db.query(Transaction).filter(
            or_(
                Transaction.source_account_id.in_(account_ids),
                Transaction.destination_account_id.in_(account_ids)
            )
        ).order_by(Transaction.created_at.desc()).limit(6).all()

    loans = get_customer_loans(db, cust.id) if cust else []
    active_loans = [l for l in loans if l.status in ("PENDING", "APPROVED")]
    applications = get_customer_applications(db, cust.id) if cust else []

    ctx.update({
        "customer": cust,
        "accounts": accounts,
        "total_balance_formatted": cents_to_currency(total_balance_cents),
        "recent_transactions": recent_txns,
        "loans": active_loans,
        "applications": applications,
        "message": msg,
        "error": error
    })
    return templates.TemplateResponse(request=request, name="customer/dashboard.html", context=ctx)

@router.get("/accounts", response_class=HTMLResponse)
def customer_accounts_page(
    request: Request,
    msg: Optional[str] = None,
    error: Optional[str] = None,
    user: User = Depends(require_customer),
    db: Session = Depends(get_db)
):
    ctx = get_template_context(request, user, db)
    cust = get_customer_by_user_id(db, user.id)
    accounts = get_customer_accounts(db, cust.id) if cust else []
    ctx.update({"accounts": accounts, "customer": cust, "message": msg, "error": error})
    return templates.TemplateResponse(request=request, name="customer/accounts.html", context=ctx)

@router.post("/accounts/new")
def open_additional_account(
    request: Request,
    user: User = Depends(require_customer)
):
    # Enforce KYC verification: All account creations must go through the KYC workflow
    return RedirectResponse(
        url="/customer/apply-account?msg=All+accounts+require+verified+KYC+documents+and+review.",
        status_code=303
    )

@router.get("/open-account")
def open_account_get_alias():
    return RedirectResponse(url="/customer/apply-account", status_code=303)

@router.post("/open-account")
def open_account_post_alias():
    return RedirectResponse(url="/customer/apply-account", status_code=303)


@router.get("/deposit", response_class=HTMLResponse)
def deposit_page(
    request: Request,
    msg: Optional[str] = None,
    error: Optional[str] = None,
    user: User = Depends(require_customer),
    db: Session = Depends(get_db)
):
    ctx = get_template_context(request, user, db)
    cust = get_customer_by_user_id(db, user.id)
    accounts = [acc for acc in get_customer_accounts(db, cust.id) if acc.status == "ACTIVE"] if cust else []
    ctx.update({"accounts": accounts, "message": msg, "error": error})
    return templates.TemplateResponse(request=request, name="customer/deposit.html", context=ctx)

@router.post("/deposit")
def deposit_action(
    request: Request,
    account_number: str = Form(...),
    amount: float = Form(...),
    description: str = Form("Cash Deposit"),
    user: User = Depends(require_customer),
    db: Session = Depends(get_db)
):
    cust = get_customer_by_user_id(db, user.id)
    account = db.query(Account).filter(Account.account_number == account_number.strip().upper()).first()
    if not account or account.customer_id != cust.id:
        return RedirectResponse(url="/customer/deposit?error=Unauthorized+account+selection.", status_code=303)

    try:
        deposit(db, account_number, amount, description=description, user_id=user.id)
        return RedirectResponse(
            url=f"/customer/dashboard?msg=Successfully+deposited+{cents_to_currency(currency_to_cents(amount))}+into+{account_number}.",
            status_code=303
        )
    except Exception as e:
        return RedirectResponse(url=f"/customer/deposit?error={str(e)}", status_code=303)

@router.get("/withdraw", response_class=HTMLResponse)
def withdraw_page(
    request: Request,
    msg: Optional[str] = None,
    error: Optional[str] = None,
    user: User = Depends(require_customer),
    db: Session = Depends(get_db)
):
    ctx = get_template_context(request, user, db)
    cust = get_customer_by_user_id(db, user.id)
    accounts = [acc for acc in get_customer_accounts(db, cust.id) if acc.status == "ACTIVE"] if cust else []
    ctx.update({"accounts": accounts, "message": msg, "error": error})
    return templates.TemplateResponse(request=request, name="customer/withdraw.html", context=ctx)

@router.post("/withdraw")
def withdraw_action(
    request: Request,
    account_number: str = Form(...),
    amount: float = Form(...),
    description: str = Form("Cash Withdrawal"),
    user: User = Depends(require_customer),
    db: Session = Depends(get_db)
):
    cust = get_customer_by_user_id(db, user.id)
    account = db.query(Account).filter(Account.account_number == account_number.strip().upper()).first()
    if not account or account.customer_id != cust.id:
        return RedirectResponse(url="/customer/withdraw?error=Unauthorized+account+selection.", status_code=303)

    try:
        withdraw(db, account_number, amount, description=description, user_id=user.id)
        return RedirectResponse(
            url=f"/customer/dashboard?msg=Successfully+withdrew+{cents_to_currency(currency_to_cents(amount))}+from+{account_number}.",
            status_code=303
        )
    except Exception as e:
        return RedirectResponse(url=f"/customer/withdraw?error={str(e)}", status_code=303)

@router.get("/transfer", response_class=HTMLResponse)
def transfer_page(
    request: Request,
    msg: Optional[str] = None,
    error: Optional[str] = None,
    user: User = Depends(require_customer),
    db: Session = Depends(get_db)
):
    ctx = get_template_context(request, user, db)
    cust = get_customer_by_user_id(db, user.id)
    accounts = [acc for acc in get_customer_accounts(db, cust.id) if acc.status == "ACTIVE"] if cust else []
    ctx.update({"accounts": accounts, "message": msg, "error": error})
    return templates.TemplateResponse(request=request, name="customer/transfer.html", context=ctx)

@router.post("/transfer")
def transfer_action(
    request: Request,
    source_account_number: str = Form(...),
    destination_account_number: str = Form(...),
    amount: float = Form(...),
    description: str = Form("Funds Transfer"),
    user: User = Depends(require_customer),
    db: Session = Depends(get_db)
):
    cust = get_customer_by_user_id(db, user.id)
    src_acc = db.query(Account).filter(Account.account_number == source_account_number.strip().upper()).first()
    if not src_acc or src_acc.customer_id != cust.id:
        return RedirectResponse(url="/customer/transfer?error=Unauthorized+source+account.", status_code=303)

    try:
        transfer(
            db=db,
            source_account_number=source_account_number,
            destination_account_number=destination_account_number,
            amount=amount,
            description=description,
            user_id=user.id
        )
        return RedirectResponse(
            url=f"/customer/dashboard?msg=Successfully+transferred+{cents_to_currency(currency_to_cents(amount))}+to+{destination_account_number}.",
            status_code=303
        )
    except Exception as e:
        return RedirectResponse(url=f"/customer/transfer?error={str(e)}", status_code=303)

@router.get("/transactions", response_class=HTMLResponse)
def customer_transactions_page(
    request: Request,
    account_id: Optional[int] = None,
    txn_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    user: User = Depends(require_customer),
    db: Session = Depends(get_db)
):
    ctx = get_template_context(request, user, db)
    cust = get_customer_by_user_id(db, user.id)
    accounts = get_customer_accounts(db, cust.id) if cust else []
    account_ids = [acc.id for acc in accounts]

    query_acc_id = account_id if account_id in account_ids else None
    
    from sqlalchemy import or_
    query = db.query(Transaction)
    if query_acc_id:
        query = query.filter(
            or_(
                Transaction.source_account_id == query_acc_id,
                Transaction.destination_account_id == query_acc_id
            )
        )
    else:
        query = query.filter(
            or_(
                Transaction.source_account_id.in_(account_ids),
                Transaction.destination_account_id.in_(account_ids)
            )
        )

    if txn_type:
        query = query.filter(Transaction.transaction_type == txn_type.upper())

    if start_date:
        try:
            s_dt = datetime.datetime.strptime(start_date, "%Y-%m-%d")
            query = query.filter(Transaction.created_at >= s_dt)
        except Exception:
            pass

    if end_date:
        try:
            e_dt = datetime.datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            query = query.filter(Transaction.created_at <= e_dt)
        except Exception:
            pass

    txns = query.order_by(Transaction.created_at.desc()).limit(50).all()

    ctx.update({
        "accounts": accounts,
        "transactions": txns,
        "selected_account_id": query_acc_id,
        "selected_type": txn_type,
        "start_date": start_date,
        "end_date": end_date
    })
    return templates.TemplateResponse(request=request, name="customer/transactions.html", context=ctx)

@router.get("/loans", response_class=HTMLResponse)
def customer_loans_page(
    request: Request,
    msg: Optional[str] = None,
    error: Optional[str] = None,
    user: User = Depends(require_customer),
    db: Session = Depends(get_db)
):
    ctx = get_template_context(request, user, db)
    cust = get_customer_by_user_id(db, user.id)
    loans = get_customer_loans(db, cust.id) if cust else []
    accounts = [acc for acc in get_customer_accounts(db, cust.id) if acc.status == "ACTIVE"] if cust else []
    ctx.update({"loans": loans, "accounts": accounts, "message": msg, "error": error})
    return templates.TemplateResponse(request=request, name="customer/loans.html", context=ctx)

@router.post("/loans/apply")
def loan_apply_action(
    request: Request,
    category: str = Form(...),
    amount: float = Form(...),
    term_months: int = Form(...),
    monthly_income: float = Form(...),
    purpose: str = Form(...),
    user: User = Depends(require_customer),
    db: Session = Depends(get_db)
):
    cust = get_customer_by_user_id(db, user.id)
    if not cust:
        raise HTTPException(status_code=404, detail="Customer not found.")

    try:
        app_data = LoanApplication(
            category=category,
            amount=amount,
            term_months=term_months,
            monthly_income=monthly_income,
            purpose=purpose
        )
        loan = apply_for_loan(db, cust.id, app_data)
        return RedirectResponse(
            url=f"/customer/loans?msg=Loan+application+{loan.loan_reference}+submitted+successfully.",
            status_code=303
        )
    except Exception as e:
        return RedirectResponse(url=f"/customer/loans?error={str(e)}", status_code=303)

@router.post("/loans/{loan_id}/repay")
def loan_repay_action(
    request: Request,
    loan_id: int,
    from_account_number: str = Form(...),
    amount: float = Form(...),
    user: User = Depends(require_customer),
    db: Session = Depends(get_db)
):
    cust = get_customer_by_user_id(db, user.id)
    try:
        make_loan_repayment(
            db=db,
            loan_id=loan_id,
            from_account_number=from_account_number,
            amount=amount,
            customer_id=cust.id
        )
        return RedirectResponse(
            url="/customer/loans?msg=Loan+repayment+processed+successfully.",
            status_code=303
        )
    except Exception as e:
        return RedirectResponse(url=f"/customer/loans?error={str(e)}", status_code=303)

@router.get("/notifications", response_class=HTMLResponse)
def notifications_page(
    request: Request,
    user: User = Depends(require_customer),
    db: Session = Depends(get_db)
):
    ctx = get_template_context(request, user, db)
    from app.services.notification_service import get_user_notifications
    notifs = get_user_notifications(db, user.id, limit=30)
    ctx.update({"all_notifications": notifs})
    return templates.TemplateResponse(request=request, name="customer/notifications.html", context=ctx)

@router.post("/notifications/mark-read/{notification_id}")
def mark_notif_read_action(
    notification_id: int,
    user: User = Depends(require_customer),
    db: Session = Depends(get_db)
):
    mark_notification_as_read(db, notification_id, user.id)
    return RedirectResponse(url="/customer/notifications", status_code=303)

@router.post("/notifications/mark-all-read")
def mark_all_notif_read_action(
    user: User = Depends(require_customer),
    db: Session = Depends(get_db)
):
    mark_all_notifications_as_read(db, user.id)
    return RedirectResponse(url="/customer/notifications", status_code=303)


# --- Account Application & Video KYC Verification ---

@router.get("/apply-account", response_class=HTMLResponse)
def apply_account_page(
    request: Request,
    msg: Optional[str] = None,
    error: Optional[str] = None,
    user: User = Depends(require_customer),
    db: Session = Depends(get_db)
):
    ctx = get_template_context(request, user, db)
    cust = get_customer_by_user_id(db, user.id)
    ctx.update({
        "customer": cust,
        "message": msg,
        "error": error
    })
    return templates.TemplateResponse(request=request, name="customer/apply_account.html", context=ctx)


@router.post("/apply-account")
async def apply_account_action(
    request: Request,
    account_type: str = Form("SAVINGS"),
    initial_deposit: float = Form(0.0),
    occupation: str = Form("Professional"),
    annual_income: float = Form(0.0),
    source_of_funds: str = Form("Salary"),
    branch_code: str = Form("SBIN0001"),
    document_type: str = Form("AADHAAR"),
    document_number: Optional[str] = Form(None),
    signature_data: Optional[str] = Form(None),
    video_verification_confirmed: Optional[str] = Form("yes"),
    document_file: Optional[UploadFile] = File(None),
    user: User = Depends(require_customer),
    db: Session = Depends(get_db)
):
    cust = get_customer_by_user_id(db, user.id)
    if not cust:
        raise HTTPException(status_code=404, detail="Customer profile not found.")

    try:
        init_cents = currency_to_cents(initial_deposit) if initial_deposit > 0 else 0
        income_cents = currency_to_cents(annual_income) if annual_income > 0 else 0

        # Submit Application
        app = submit_account_application(
            db=db,
            customer_id=cust.id,
            account_type=account_type,
            initial_deposit_cents=init_cents,
            occupation=occupation,
            annual_income_cents=income_cents,
            source_of_funds=source_of_funds,
            branch_code=branch_code,
            signature_data=signature_data,
            video_verification_status="COMPLETED" if video_verification_confirmed else "PENDING"
        )

        # Handle document file upload if provided
        if document_file and document_file.filename:
            content = await document_file.read()
            if len(content) > 0:
                save_application_document(
                    db=db,
                    application_id=app.id,
                    document_type=document_type,
                    document_number=document_number,
                    file_bytes=content,
                    original_filename=document_file.filename,
                    mime_type=document_file.content_type or "application/octet-stream"
                )

        return RedirectResponse(
            url=f"/customer/application-status?msg=Application+{app.application_reference}+submitted+successfully!+Our+operations+team+is+verifying+your+documents.",
            status_code=303
        )
    except Exception as e:
        ctx = get_template_context(request, user, db)
        ctx.update({
            "customer": cust,
            "error": f"Failed to submit application: {str(e)}"
        })
        return templates.TemplateResponse(request=request, name="customer/apply_account.html", context=ctx, status_code=400)


@router.get("/application-status", response_class=HTMLResponse)
def application_status_page(
    request: Request,
    msg: Optional[str] = None,
    error: Optional[str] = None,
    user: User = Depends(require_customer),
    db: Session = Depends(get_db)
):
    ctx = get_template_context(request, user, db)
    cust = get_customer_by_user_id(db, user.id)
    applications = get_customer_applications(db, cust.id) if cust else []
    ctx.update({
        "customer": cust,
        "applications": applications,
        "message": msg,
        "error": error
    })
    return templates.TemplateResponse(request=request, name="customer/application_status.html", context=ctx)

