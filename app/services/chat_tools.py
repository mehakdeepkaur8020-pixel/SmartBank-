import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.models.models import User, Customer, Account, Transaction, Loan, LoanRepayment, AccountApplication
from app.utils.security import cents_to_currency

def get_customer_from_user_id(user_id: int, db: Session) -> Optional[Customer]:
    """Helper to safely obtain the customer associated strictly with the authenticated user ID."""
    if not user_id:
        return None
    return db.query(Customer).filter(Customer.user_id == user_id).first()

def get_my_account_summary(user_id: int, db: Session) -> Dict[str, Any]:
    """Retrieve verified summary of the authenticated customer's own accounts."""
    customer = get_customer_from_user_id(user_id, db)
    if not customer:
        return {
            "success": False,
            "error": "No customer profile found for this user account.",
            "data": None
        }

    accounts = db.query(Account).filter(Account.customer_id == customer.id).all()
    if not accounts:
        return {
            "success": True,
            "customer_name": customer.full_name,
            "accounts_count": 0,
            "accounts": [],
            "message": "You currently do not have any active bank accounts."
        }

    summary_list = []
    total_balance_cents = 0
    for acc in accounts:
        total_balance_cents += acc.balance_cents
        summary_list.append({
            "account_number": acc.account_number,
            "account_type": acc.account_type,
            "balance": cents_to_currency(acc.balance_cents),
            "status": acc.status
        })

    return {
        "success": True,
        "customer_name": customer.full_name,
        "accounts_count": len(accounts),
        "total_balance": cents_to_currency(total_balance_cents),
        "accounts": summary_list
    }

def get_my_recent_transactions(user_id: int, limit: int, db: Session) -> Dict[str, Any]:
    """Retrieve the customer's most recent transactions (safely capped between 1 and 10)."""
    customer = get_customer_from_user_id(user_id, db)
    if not customer:
        return {"success": False, "error": "Customer profile not found."}

    capped_limit = max(1, min(limit or 5, 10))
    account_ids = [acc.id for acc in customer.accounts]
    if not account_ids:
        return {"success": True, "transactions": [], "message": "No accounts found."}

    txns = db.query(Transaction).filter(
        or_(
            Transaction.source_account_id.in_(account_ids),
            Transaction.destination_account_id.in_(account_ids)
        )
    ).order_by(Transaction.created_at.desc()).limit(capped_limit).all()

    formatted_txns = []
    for t in txns:
        formatted_txns.append({
            "reference": t.transaction_reference,
            "date": t.created_at.strftime("%Y-%m-%d %H:%M"),
            "type": t.transaction_type,
            "amount": cents_to_currency(t.amount_cents),
            "status": t.status,
            "description": t.description
        })

    return {
        "success": True,
        "count": len(formatted_txns),
        "transactions": formatted_txns
    }

def get_my_transactions_by_date(
    user_id: int,
    start_date: Optional[str],
    end_date: Optional[str],
    db: Session
) -> Dict[str, Any]:
    """Retrieve transactions for a specific date range."""
    customer = get_customer_from_user_id(user_id, db)
    if not customer:
        return {"success": False, "error": "Customer profile not found."}

    account_ids = [acc.id for acc in customer.accounts]
    if not account_ids:
        return {"success": True, "transactions": [], "message": "No accounts found."}

    query = db.query(Transaction).filter(
        or_(
            Transaction.source_account_id.in_(account_ids),
            Transaction.destination_account_id.in_(account_ids)
        )
    )

    try:
        if start_date:
            s_dt = datetime.datetime.strptime(start_date.strip(), "%Y-%m-%d")
            query = query.filter(Transaction.created_at >= s_dt)
        if end_date:
            e_dt = datetime.datetime.strptime(end_date.strip(), "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            query = query.filter(Transaction.created_at <= e_dt)
    except Exception:
        return {"success": False, "error": "Invalid date format. Please use YYYY-MM-DD."}

    txns = query.order_by(Transaction.created_at.desc()).limit(15).all()

    formatted_txns = []
    for t in txns:
        formatted_txns.append({
            "reference": t.transaction_reference,
            "date": t.created_at.strftime("%Y-%m-%d"),
            "type": t.transaction_type,
            "amount": cents_to_currency(t.amount_cents),
            "description": t.description
        })

    return {
        "success": True,
        "count": len(formatted_txns),
        "transactions": formatted_txns
    }

def get_my_loan_status(user_id: int, db: Session) -> Dict[str, Any]:
    """Retrieve verified status and details of the customer's loan applications."""
    customer = get_customer_from_user_id(user_id, db)
    if not customer:
        return {"success": False, "error": "Customer profile not found."}

    loans = db.query(Loan).filter(Loan.customer_id == customer.id).order_by(Loan.created_at.desc()).all()
    if not loans:
        return {
            "success": True,
            "has_loans": False,
            "message": "You currently do not have any loan applications recorded."
        }

    loan_list = []
    for l in loans:
        loan_list.append({
            "loan_reference": l.loan_reference,
            "category": l.category,
            "requested_amount": cents_to_currency(l.amount_cents),
            "approved_amount": cents_to_currency(l.approved_amount_cents),
            "outstanding_balance": cents_to_currency(l.outstanding_balance_cents),
            "status": l.status,
            "applied_date": l.created_at.strftime("%Y-%m-%d")
        })

    return {
        "success": True,
        "has_loans": True,
        "loans": loan_list
    }

def get_my_loan_repayments(user_id: int, db: Session) -> Dict[str, Any]:
    """Retrieve repayment history on the customer's loans."""
    customer = get_customer_from_user_id(user_id, db)
    if not customer:
        return {"success": False, "error": "Customer profile not found."}

    loan_ids = [l.id for l in customer.loans]
    if not loan_ids:
        return {"success": True, "repayments": [], "message": "No loans found."}

    repayments = db.query(LoanRepayment).filter(
        LoanRepayment.loan_id.in_(loan_ids)
    ).order_by(LoanRepayment.created_at.desc()).limit(10).all()

    repay_list = []
    for r in repayments:
        repay_list.append({
            "reference": r.repayment_reference,
            "loan_reference": r.loan.loan_reference if r.loan else "N/A",
            "amount": cents_to_currency(r.amount_cents),
            "date": r.created_at.strftime("%Y-%m-%d %H:%M"),
            "payment_method": r.payment_method
        })

    return {
        "success": True,
        "count": len(repay_list),
        "repayments": repay_list
    }

def get_my_statement_page_link(user_id: int, db: Session) -> Dict[str, Any]:
    """Provide verified navigation instructions and link for generating reports."""
    customer = get_customer_from_user_id(user_id, db)
    if not customer:
        return {"success": False, "error": "Customer profile not found."}

    return {
        "success": True,
        "url": "/reports/statement",
        "title": "Account Statement & Reports",
        "instructions": "Navigate to the Reports page to generate and download statements in PDF or CSV format."
    }

def get_my_application_status(user_id: int, db: Session) -> Dict[str, Any]:
    """Retrieve verified status and details of the customer's account applications."""
    customer = get_customer_from_user_id(user_id, db)
    if not customer:
        return {"success": False, "error": "Customer profile not found."}

    applications = db.query(AccountApplication).filter(
        AccountApplication.customer_id == customer.id
    ).order_by(AccountApplication.created_at.desc()).all()

    if not applications:
        return {
            "success": True,
            "has_applications": False,
            "message": "You do not have any pending or submitted account applications."
        }

    app_list = []
    for app in applications:
        app_list.append({
            "reference": app.application_reference,
            "account_type": app.account_type,
            "status": app.status,
            "initial_deposit": cents_to_currency(app.initial_deposit_cents),
            "video_verification": app.video_verification_status,
            "created_at": app.created_at.strftime("%Y-%m-%d %H:%M"),
            "notes": app.review_decision_notes or "Under review by our operations verification team."
        })

    return {
        "success": True,
        "has_applications": True,
        "applications": app_list
    }

