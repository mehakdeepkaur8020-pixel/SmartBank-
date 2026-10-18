import datetime
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pathlib import Path
from typing import Optional
from app.database import get_db
from app.models.models import User, Customer, Account, Transaction, Loan
from app.utils.dependencies import get_current_user, get_template_context
from app.services.account_service import get_customer_by_user_id, get_customer_accounts, get_account_by_number
from app.services.transaction_service import get_transactions_for_account, get_all_transactions
from app.services.loan_service import get_all_loans, get_customer_loans
from app.services.report_service import generate_statement_pdf, generate_transactions_csv, generate_loans_csv
from app.services.audit_service import log_action

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))
router = APIRouter(prefix="/reports", tags=["Reports & Statements"])

@router.get("/statement", response_class=HTMLResponse)
def statement_view(
    request: Request,
    account_number: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    ctx = get_template_context(request, user, db)

    # Determine selectable accounts based on role
    if user.role == "customer":
        cust = get_customer_by_user_id(db, user.id)
        accounts = get_customer_accounts(db, cust.id) if cust else []
    else:
        accounts = db.query(Account).order_by(Account.account_number.asc()).all()

    selected_account = None
    transactions = []
    s_date = None
    e_date = None

    if start_date:
        try:
            s_date = datetime.datetime.strptime(start_date, "%Y-%m-%d").date()
        except Exception:
            pass

    if end_date:
        try:
            e_date = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()
        except Exception:
            pass

    if account_number:
        acc = get_account_by_number(db, account_number)
        if acc:
            if user.role == "customer" and acc.customer.user_id != user.id:
                raise HTTPException(status_code=403, detail="Unauthorized: You cannot access this account statement.")
            selected_account = acc
            transactions = get_transactions_for_account(
                db=db,
                account_id=acc.id,
                limit=100,
                start_date=s_date,
                end_date=e_date
            )
    elif accounts:
        selected_account = accounts[0]
        transactions = get_transactions_for_account(
            db=db,
            account_id=selected_account.id,
            limit=100,
            start_date=s_date,
            end_date=e_date
        )

    ctx.update({
        "accounts": accounts,
        "selected_account": selected_account,
        "transactions": transactions,
        "start_date": start_date or "",
        "end_date": end_date or ""
    })
    return templates.TemplateResponse(request=request, name="reports/statement.html", context=ctx)

@router.get("/statement/pdf")
def download_statement_pdf(
    request: Request,
    account_number: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    acc = get_account_by_number(db, account_number)
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found.")

    if user.role == "customer" and acc.customer.user_id != user.id:
        raise HTTPException(status_code=403, detail="Unauthorized access to account statement.")

    s_date = None
    e_date = None
    if start_date:
        try:
            s_date = datetime.datetime.strptime(start_date, "%Y-%m-%d").date()
        except Exception:
            pass
    if end_date:
        try:
            e_date = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()
        except Exception:
            pass

    txns = get_transactions_for_account(
        db=db,
        account_id=acc.id,
        limit=200,
        start_date=s_date,
        end_date=e_date
    )

    pdf_bytes = generate_statement_pdf(
        account=acc,
        customer=acc.customer,
        transactions=txns,
        start_date=s_date,
        end_date=e_date
    )

    log_action(
        db=db,
        action="STATEMENT_PDF_DOWNLOAD",
        user_id=user.id,
        entity_type="Account",
        entity_id=str(acc.id),
        details=f"Downloaded statement PDF for {acc.account_number}"
    )

    filename = f"SmartBank_Statement_{acc.account_number}_{datetime.date.today()}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.get("/statement/csv")
def download_statement_csv(
    request: Request,
    account_number: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    acc = get_account_by_number(db, account_number)
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found.")

    if user.role == "customer" and acc.customer.user_id != user.id:
        raise HTTPException(status_code=403, detail="Unauthorized access to account statement.")

    s_date = None
    e_date = None
    if start_date:
        try:
            s_date = datetime.datetime.strptime(start_date, "%Y-%m-%d").date()
        except Exception:
            pass
    if end_date:
        try:
            e_date = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()
        except Exception:
            pass

    txns = get_transactions_for_account(
        db=db,
        account_id=acc.id,
        limit=500,
        start_date=s_date,
        end_date=e_date
    )

    csv_data = generate_transactions_csv(txns, acc.account_number)

    log_action(
        db=db,
        action="STATEMENT_CSV_DOWNLOAD",
        user_id=user.id,
        entity_type="Account",
        entity_id=str(acc.id),
        details=f"Downloaded statement CSV for {acc.account_number}"
    )

    filename = f"SmartBank_Statement_{acc.account_number}_{datetime.date.today()}.csv"
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.get("/transactions/csv")
def download_all_transactions_csv(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if user.role == "customer":
        cust = get_customer_by_user_id(db, user.id)
        if not cust or not cust.accounts:
            return Response(content="", media_type="text/csv")
        txns = []
        for acc in cust.accounts:
            txns.extend(get_transactions_for_account(db, acc.id, limit=500))
    else:
        txns = get_all_transactions(db, limit=1000)

    csv_data = generate_transactions_csv(txns)
    filename = f"SmartBank_Transactions_{datetime.date.today()}.csv"
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.get("/loans/csv")
def download_loans_csv(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if user.role == "customer":
        cust = get_customer_by_user_id(db, user.id)
        loans = get_customer_loans(db, cust.id) if cust else []
    else:
        loans = get_all_loans(db)

    csv_data = generate_loans_csv(loans)
    filename = f"SmartBank_Loans_{datetime.date.today()}.csv"
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
