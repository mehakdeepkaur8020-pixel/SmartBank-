from fastapi import APIRouter, Depends, HTTPException, Request, Form, status, Response
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pathlib import Path
from typing import Optional, List, Dict, Any
import os
import datetime
from app.database import get_db
from app.models.models import (
    User, Customer, Account, Transaction, TransactionReview, Loan,
    AccountApplication, ApplicationDocument
)
from app.schemas.schemas import LoanReview
from app.utils.dependencies import require_employee, get_template_context
from app.services.account_service import (
    get_all_customers_with_accounts, update_account_status, get_account_by_number,
    get_all_applications, get_application_by_id, review_account_application
)
from app.services.transaction_service import get_all_transactions, reverse_transaction
from app.services.loan_service import get_all_loans, review_loan
from app.services.report_service import (
    generate_transactions_csv, generate_loans_csv, generate_accounts_csv,
    generate_employee_report_pdf
)
from app.utils.security import cents_to_currency, mask_account_number

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))
router = APIRouter(prefix="/employee", tags=["Employee Portal"])

@router.get("/dashboard", response_class=HTMLResponse)
def employee_dashboard(
    request: Request,
    user: User = Depends(require_employee),
    db: Session = Depends(get_db)
):
    ctx = get_template_context(request, user, db)
    
    total_customers = db.query(Customer).count()
    active_accounts = db.query(Account).filter(Account.status == "ACTIVE").count()
    pending_loans_count = db.query(Loan).filter(Loan.status == "PENDING").count()
    flagged_reviews_count = db.query(TransactionReview).filter(TransactionReview.status == "PENDING").count()
    pending_apps_count = db.query(AccountApplication).filter(AccountApplication.status == "PENDING_REVIEW").count()
    
    recent_transactions = db.query(Transaction).order_by(Transaction.created_at.desc()).limit(8).all()
    pending_loans = db.query(Loan).filter(Loan.status == "PENDING").limit(5).all()
    flagged_reviews = db.query(TransactionReview).filter(TransactionReview.status == "PENDING").limit(5).all()
    pending_apps = db.query(AccountApplication).filter(AccountApplication.status == "PENDING_REVIEW").order_by(AccountApplication.created_at.desc()).limit(5).all()

    ctx.update({
        "total_customers": total_customers,
        "active_accounts": active_accounts,
        "pending_loans_count": pending_loans_count,
        "flagged_reviews_count": flagged_reviews_count,
        "pending_apps_count": pending_apps_count,
        "recent_transactions": recent_transactions,
        "pending_loans": pending_loans,
        "flagged_reviews": flagged_reviews,
        "pending_apps": pending_apps
    })
    return templates.TemplateResponse(request=request, name="employee/dashboard.html", context=ctx)

@router.get("/customers", response_class=HTMLResponse)
def employee_customers(
    request: Request,
    search: Optional[str] = None,
    msg: Optional[str] = None,
    error: Optional[str] = None,
    user: User = Depends(require_employee),
    db: Session = Depends(get_db)
):
    ctx = get_template_context(request, user, db)
    customers = get_all_customers_with_accounts(db, search_term=search)
    ctx.update({"customers": customers, "search_term": search, "message": msg, "error": error})
    return templates.TemplateResponse(request=request, name="employee/customers.html", context=ctx)

@router.get("/customers/{customer_id}", response_class=HTMLResponse)
def employee_customer_detail(
    request: Request,
    customer_id: int,
    user: User = Depends(require_employee),
    db: Session = Depends(get_db)
):
    ctx = get_template_context(request, user, db)
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found.")
    ctx.update({"customer": customer, "accounts": customer.accounts, "loans": customer.loans})
    return templates.TemplateResponse(request=request, name="employee/customer_detail.html", context=ctx)

@router.post("/accounts/{account_number}/status")
def change_account_status(
    account_number: str,
    status: str = Form(...),
    customer_id: Optional[int] = Form(None),
    user: User = Depends(require_employee),
    db: Session = Depends(get_db)
):
    try:
        update_account_status(db, account_number, status, reviewer_user_id=user.id)
        redirect_url = f"/employee/customers/{customer_id}?msg=Status+updated" if customer_id else "/employee/customers?msg=Status+updated"
        return RedirectResponse(url=redirect_url, status_code=303)
    except Exception as e:
        redirect_url = f"/employee/customers/{customer_id}?error={str(e)}" if customer_id else f"/employee/customers?error={str(e)}"
        return RedirectResponse(url=redirect_url, status_code=303)

@router.get("/loans", response_class=HTMLResponse)
def employee_loans(
    request: Request,
    status: Optional[str] = None,
    msg: Optional[str] = None,
    error: Optional[str] = None,
    user: User = Depends(require_employee),
    db: Session = Depends(get_db)
):
    ctx = get_template_context(request, user, db)
    loans = get_all_loans(db, status=status)
    ctx.update({"loans": loans, "filter_status": status, "message": msg, "error": error})
    return templates.TemplateResponse(request=request, name="employee/loans.html", context=ctx)

@router.post("/loans/{loan_id}/review")
def review_loan_action(
    loan_id: int,
    decision: str = Form(...),
    reason: str = Form(...),
    approved_amount: Optional[float] = Form(None),
    user: User = Depends(require_employee),
    db: Session = Depends(get_db)
):
    try:
        review_data = LoanReview(
            decision=decision,
            reason=reason,
            approved_amount=approved_amount
        )
        review_loan(db, loan_id, review_data, reviewer_user_id=user.id)
        return RedirectResponse(url=f"/employee/loans?msg=Loan+{decision.lower()}+successfully.", status_code=303)
    except Exception as e:
        return RedirectResponse(url=f"/employee/loans?error={str(e)}", status_code=303)

@router.get("/transactions", response_class=HTMLResponse)
def employee_transactions(
    request: Request,
    search: Optional[str] = None,
    txn_type: Optional[str] = None,
    msg: Optional[str] = None,
    error: Optional[str] = None,
    user: User = Depends(require_employee),
    db: Session = Depends(get_db)
):
    ctx = get_template_context(request, user, db)
    txns = get_all_transactions(db, search_ref=search, txn_type=txn_type, limit=100)
    ctx.update({"transactions": txns, "search": search, "txn_type": txn_type, "message": msg, "error": error})
    return templates.TemplateResponse(request=request, name="employee/transactions.html", context=ctx)

@router.post("/transactions/{transaction_id}/reverse")
def reverse_txn_action(
    transaction_id: int,
    reason: str = Form(...),
    user: User = Depends(require_employee),
    db: Session = Depends(get_db)
):
    try:
        rev_txn = reverse_transaction(db, transaction_id, employee_user_id=user.id, reason=reason)
        return RedirectResponse(
            url=f"/employee/transactions?msg=Transaction+reversed+successfully.+Compensating+entry:+{rev_txn.transaction_reference}",
            status_code=303
        )
    except Exception as e:
        return RedirectResponse(url=f"/employee/transactions?error={str(e)}", status_code=303)

@router.get("/monitoring", response_class=HTMLResponse)
def employee_monitoring(
    request: Request,
    msg: Optional[str] = None,
    error: Optional[str] = None,
    user: User = Depends(require_employee),
    db: Session = Depends(get_db)
):
    ctx = get_template_context(request, user, db)
    reviews = db.query(TransactionReview).order_by(TransactionReview.created_at.desc()).all()
    ctx.update({"reviews": reviews, "message": msg, "error": error})
    return templates.TemplateResponse(request=request, name="employee/monitoring.html", context=ctx)

@router.post("/monitoring/{review_id}/resolve")
def resolve_review_action(
    review_id: int,
    decision: str = Form(...),  # APPROVED or DISMISSED
    notes: str = Form("Reviewed by employee"),
    user: User = Depends(require_employee),
    db: Session = Depends(get_db)
):
    rev = db.query(TransactionReview).filter(TransactionReview.id == review_id).first()
    if rev:
        rev.status = decision.upper()
        rev.reviewed_by_user_id = user.id
        rev.review_notes = notes
        import datetime
        rev.reviewed_at = datetime.datetime.utcnow()
        db.commit()
    return RedirectResponse(url="/employee/monitoring?msg=Review+status+updated.", status_code=303)


# --- Account Opening Applications & KYC Verification ---

@router.get("/applications", response_class=HTMLResponse)
def employee_applications(
    request: Request,
    status: Optional[str] = None,
    msg: Optional[str] = None,
    error: Optional[str] = None,
    user: User = Depends(require_employee),
    db: Session = Depends(get_db)
):
    ctx = get_template_context(request, user, db)
    applications = get_all_applications(db, status=status)
    ctx.update({
        "applications": applications,
        "filter_status": status,
        "message": msg,
        "error": error
    })
    return templates.TemplateResponse(request=request, name="employee/applications.html", context=ctx)


@router.get("/applications/{application_id}", response_class=HTMLResponse)
def employee_application_detail(
    request: Request,
    application_id: int,
    user: User = Depends(require_employee),
    db: Session = Depends(get_db)
):
    ctx = get_template_context(request, user, db)
    app = get_application_by_id(db, application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found.")
    ctx.update({"application": app})
    return templates.TemplateResponse(request=request, name="employee/application_detail.html", context=ctx)


@router.post("/applications/{application_id}/review")
def review_application_action(
    application_id: int,
    decision: str = Form(...),
    notes: str = Form(...),
    user: User = Depends(require_employee),
    db: Session = Depends(get_db)
):
    try:
        app = review_account_application(
            db=db,
            application_id=application_id,
            reviewer_user_id=user.id,
            decision=decision,
            notes=notes
        )
        return RedirectResponse(
            url=f"/employee/applications?msg=Application+{app.application_reference}+{decision.lower()}+successfully.",
            status_code=303
        )
    except Exception as e:
        return RedirectResponse(url=f"/employee/applications/{application_id}?error={str(e)}", status_code=303)


@router.get("/applications/documents/{document_id}")
def serve_application_document(
    document_id: int,
    user: User = Depends(require_employee),
    db: Session = Depends(get_db)
):
    doc = db.query(ApplicationDocument).filter(ApplicationDocument.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    from app.config import BASE_DIR
    full_path = os.path.join(BASE_DIR, doc.file_path)
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="Document file not found on disk.")

    return FileResponse(
        path=full_path,
        media_type=doc.mime_type,
        filename=doc.original_filename
    )


# --- Institutional Reports Dashboard & Exports ---

@router.get("/reports", response_class=HTMLResponse)
def employee_reports_dashboard(
    request: Request,
    report_type: str = "transactions",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    user: User = Depends(require_employee),
    db: Session = Depends(get_db)
):
    ctx = get_template_context(request, user, db)

    # Date parsing
    s_dt = None
    e_dt = None
    try:
        if start_date:
            s_dt = datetime.datetime.strptime(start_date.strip(), "%Y-%m-%d")
        if end_date:
            e_dt = datetime.datetime.strptime(end_date.strip(), "%Y-%m-%d").replace(hour=23, minute=59, second=59)
    except Exception:
        pass

    # Aggregated Stats
    total_tx_vol = db.query(Transaction).filter(Transaction.status == "COMPLETED").count()
    from sqlalchemy import func
    total_tx_val_cents = db.query(func.coalesce(func.sum(Transaction.amount_cents), 0)).filter(Transaction.status == "COMPLETED").scalar()
    total_acc_count = db.query(Account).count()
    total_acc_val_cents = db.query(func.coalesce(func.sum(Account.balance_cents), 0)).scalar()
    total_loan_count = db.query(Loan).count()
    total_loan_disbursed_cents = db.query(func.coalesce(func.sum(Loan.approved_amount_cents), 0)).scalar()

    records = []
    if report_type == "transactions":
        q = db.query(Transaction)
        if s_dt:
            q = q.filter(Transaction.created_at >= s_dt)
        if e_dt:
            q = q.filter(Transaction.created_at <= e_dt)
        records = q.order_by(Transaction.created_at.desc()).limit(100).all()

    elif report_type == "accounts":
        q = db.query(Account)
        if s_dt:
            q = q.filter(Account.created_at >= s_dt)
        if e_dt:
            q = q.filter(Account.created_at <= e_dt)
        records = q.order_by(Account.created_at.desc()).limit(100).all()

    elif report_type == "loans":
        q = db.query(Loan)
        if s_dt:
            q = q.filter(Loan.created_at >= s_dt)
        if e_dt:
            q = q.filter(Loan.created_at <= e_dt)
        records = q.order_by(Loan.created_at.desc()).limit(100).all()

    elif report_type == "applications":
        q = db.query(AccountApplication)
        if s_dt:
            q = q.filter(AccountApplication.created_at >= s_dt)
        if e_dt:
            q = q.filter(AccountApplication.created_at <= e_dt)
        records = q.order_by(AccountApplication.created_at.desc()).limit(100).all()

    ctx.update({
        "report_type": report_type,
        "start_date": start_date or "",
        "end_date": end_date or "",
        "records": records,
        "total_tx_vol": total_tx_vol,
        "total_tx_val_formatted": cents_to_currency(total_tx_val_cents),
        "total_acc_count": total_acc_count,
        "total_acc_val_formatted": cents_to_currency(total_acc_val_cents),
        "total_loan_count": total_loan_count,
        "total_loan_disbursed_formatted": cents_to_currency(total_loan_disbursed_cents)
    })
    return templates.TemplateResponse(request=request, name="employee/reports.html", context=ctx)


@router.get("/reports/csv")
def employee_reports_csv_download(
    report_type: str = "transactions",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    user: User = Depends(require_employee),
    db: Session = Depends(get_db)
):
    s_dt = None
    e_dt = None
    try:
        if start_date:
            s_dt = datetime.datetime.strptime(start_date.strip(), "%Y-%m-%d")
        if end_date:
            e_dt = datetime.datetime.strptime(end_date.strip(), "%Y-%m-%d").replace(hour=23, minute=59, second=59)
    except Exception:
        pass

    if report_type == "accounts":
        q = db.query(Account)
        if s_dt: q = q.filter(Account.created_at >= s_dt)
        if e_dt: q = q.filter(Account.created_at <= e_dt)
        csv_content = generate_accounts_csv(q.order_by(Account.created_at.desc()).all())
        filename = f"smartbank_accounts_{datetime.date.today()}.csv"

    elif report_type == "loans":
        q = db.query(Loan)
        if s_dt: q = q.filter(Loan.created_at >= s_dt)
        if e_dt: q = q.filter(Loan.created_at <= e_dt)
        csv_content = generate_loans_csv(q.order_by(Loan.created_at.desc()).all())
        filename = f"smartbank_loans_{datetime.date.today()}.csv"

    else:
        q = db.query(Transaction)
        if s_dt: q = q.filter(Transaction.created_at >= s_dt)
        if e_dt: q = q.filter(Transaction.created_at <= e_dt)
        csv_content = generate_transactions_csv(q.order_by(Transaction.created_at.desc()).all())
        filename = f"smartbank_transactions_{datetime.date.today()}.csv"

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/reports/pdf")
def employee_reports_pdf_download(
    report_type: str = "transactions",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    user: User = Depends(require_employee),
    db: Session = Depends(get_db)
):
    s_dt = None
    e_dt = None
    try:
        if start_date:
            s_dt = datetime.datetime.strptime(start_date.strip(), "%Y-%m-%d")
        if end_date:
            e_dt = datetime.datetime.strptime(end_date.strip(), "%Y-%m-%d").replace(hour=23, minute=59, second=59)
    except Exception:
        pass

    if report_type == "accounts":
        q = db.query(Account)
        if s_dt: q = q.filter(Account.created_at >= s_dt)
        if e_dt: q = q.filter(Account.created_at <= e_dt)
        accounts = q.order_by(Account.created_at.desc()).limit(150).all()

        headers = ["Account No", "Customer", "Type", "Balance", "Status", "Date"]
        rows = []
        for a in accounts:
            rows.append([
                a.account_number,
                a.customer.full_name if a.customer else "N/A",
                a.account_type,
                cents_to_currency(a.balance_cents),
                a.status,
                a.created_at.strftime("%Y-%m-%d")
            ])
        summary = {
            "Total Accounts": str(len(accounts)),
            "Active Accounts": str(sum(1 for a in accounts if a.status == "ACTIVE")),
            "Total Assets": cents_to_currency(sum(a.balance_cents for a in accounts))
        }
        title = "Customer Accounts Audit Report"
        filename = f"smartbank_accounts_report_{datetime.date.today()}.pdf"

    elif report_type == "loans":
        q = db.query(Loan)
        if s_dt: q = q.filter(Loan.created_at >= s_dt)
        if e_dt: q = q.filter(Loan.created_at <= e_dt)
        loans = q.order_by(Loan.created_at.desc()).limit(150).all()

        headers = ["Reference", "Borrower", "Category", "Approved Amt", "Balance", "Status"]
        rows = []
        for l in loans:
            rows.append([
                l.loan_reference,
                l.customer.full_name if l.customer else "N/A",
                l.category,
                cents_to_currency(l.approved_amount_cents),
                cents_to_currency(l.outstanding_balance_cents),
                l.status
            ])
        summary = {
            "Total Applications": str(len(loans)),
            "Approved Loans": str(sum(1 for l in loans if l.status == "APPROVED")),
            "Disbursed Value": cents_to_currency(sum(l.approved_amount_cents for l in loans))
        }
        title = "Loan Portfolio Operations Report"
        filename = f"smartbank_loans_report_{datetime.date.today()}.pdf"

    else:
        q = db.query(Transaction)
        if s_dt: q = q.filter(Transaction.created_at >= s_dt)
        if e_dt: q = q.filter(Transaction.created_at <= e_dt)
        txns = q.order_by(Transaction.created_at.desc()).limit(150).all()

        headers = ["Date", "Reference", "Type", "Amount", "Status", "Description"]
        rows = []
        for t in txns:
            rows.append([
                t.created_at.strftime("%Y-%m-%d"),
                t.transaction_reference,
                t.transaction_type,
                cents_to_currency(t.amount_cents),
                t.status,
                t.description[:20]
            ])
        summary = {
            "Transactions": str(len(txns)),
            "Total Volume": cents_to_currency(sum(t.amount_cents for t in txns)),
            "Completed": str(sum(1 for t in txns if t.status == "COMPLETED"))
        }
        title = "Transaction Clearing & Settlement Report"
        filename = f"smartbank_transactions_report_{datetime.date.today()}.pdf"

    pdf_bytes = generate_employee_report_pdf(
        title=title,
        subtitle=f"Filter: {start_date or 'Start'} to {end_date or 'Present'}",
        summary_stats=summary,
        headers=headers,
        rows=rows,
        landscape_mode=True
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

