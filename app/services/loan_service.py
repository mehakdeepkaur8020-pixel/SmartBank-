import datetime
from sqlalchemy.orm import Session
from typing import List, Optional
from app.models.models import Loan, LoanRepayment, Customer, Account, Transaction
from app.schemas.schemas import LoanApplication, LoanReview
from app.utils.security import (
    currency_to_cents,
    cents_to_currency,
    generate_loan_reference,
    generate_repayment_reference,
    generate_txn_reference
)
from app.services.audit_service import log_action
from app.services.notification_service import create_notification

def apply_for_loan(
    db: Session,
    customer_id: int,
    app_data: LoanApplication
) -> Loan:
    """Submit a loan application on behalf of a customer."""
    requested_cents = currency_to_cents(app_data.amount)
    income_cents = currency_to_cents(app_data.monthly_income)

    loan = Loan(
        loan_reference=generate_loan_reference(),
        customer_id=customer_id,
        category=app_data.category.upper(),
        amount_cents=requested_cents,
        interest_rate_percent=7.5,  # Fixed demo rate
        term_months=app_data.term_months,
        purpose=app_data.purpose.strip(),
        monthly_income_cents=income_cents,
        status="PENDING",
        approved_amount_cents=0,
        outstanding_balance_cents=0
    )
    db.add(loan)
    db.commit()
    db.refresh(loan)

    # Notify customer
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if customer and customer.user_id:
        create_notification(
            db=db,
            user_id=customer.user_id,
            title="Loan Application Submitted",
            message=f"Your {loan.category} loan application for {cents_to_currency(requested_cents)} ({loan.loan_reference}) has been received and is pending review.",
            notification_type="LOAN"
        )
        log_action(
            db=db,
            action="LOAN_APPLICATION",
            user_id=customer.user_id,
            entity_type="Loan",
            entity_id=str(loan.id),
            details=f"Applied for {loan.category} loan of {cents_to_currency(requested_cents)}"
        )

    return loan

def review_loan(
    db: Session,
    loan_id: int,
    review_data: LoanReview,
    reviewer_user_id: int
) -> Loan:
    """Approve or reject a loan application (Bank Employee or Admin)."""
    loan = db.query(Loan).filter(Loan.id == loan_id).first()
    if not loan:
        raise ValueError("Loan application not found.")

    if loan.status != "PENDING":
        raise ValueError(f"Loan is already in '{loan.status}' status and cannot be re-reviewed.")

    loan.reviewed_by_user_id = reviewer_user_id
    loan.review_reason = review_data.reason.strip()
    loan.reviewed_at = datetime.datetime.utcnow()

    if review_data.decision.upper() == "APPROVED":
        loan.status = "APPROVED"
        # Determine approved amount (defaults to requested amount if not specified)
        if review_data.approved_amount and review_data.approved_amount > 0:
            loan.approved_amount_cents = currency_to_cents(review_data.approved_amount)
        else:
            loan.approved_amount_cents = loan.amount_cents
            
        loan.outstanding_balance_cents = loan.approved_amount_cents
    else:
        loan.status = "REJECTED"
        loan.approved_amount_cents = 0
        loan.outstanding_balance_cents = 0

    db.commit()
    db.refresh(loan)

    # Notify customer
    if loan.customer and loan.customer.user_id:
        msg = (
            f"Congratulations! Your {loan.category} loan ({loan.loan_reference}) has been APPROVED for {cents_to_currency(loan.approved_amount_cents)}."
            if loan.status == "APPROVED"
            else f"Your {loan.category} loan ({loan.loan_reference}) was REJECTED. Reason: {loan.review_reason}."
        )
        create_notification(
            db=db,
            user_id=loan.customer.user_id,
            title=f"Loan Decision: {loan.status}",
            message=msg,
            notification_type="LOAN"
        )

    log_action(
        db=db,
        action=f"LOAN_{loan.status}",
        user_id=reviewer_user_id,
        entity_type="Loan",
        entity_id=str(loan.id),
        details=f"Loan {loan.loan_reference} decision {loan.status}. Reason: {loan.review_reason}"
    )

    return loan

def make_loan_repayment(
    db: Session,
    loan_id: int,
    from_account_number: str,
    amount: float,
    notes: Optional[str] = None,
    customer_id: Optional[int] = None
) -> LoanRepayment:
    """Record a loan repayment, debit customer account, and update outstanding balance."""
    loan = db.query(Loan).filter(Loan.id == loan_id).first()
    if not loan:
        raise ValueError("Loan not found.")

    if customer_id and loan.customer_id != customer_id:
        raise PermissionError("Access denied: You do not own this loan.")

    if loan.status != "APPROVED":
        raise ValueError(f"Cannot repay loan with status '{loan.status}'.")

    if loan.outstanding_balance_cents <= 0:
        raise ValueError("Loan has already been fully paid off.")

    repay_cents = currency_to_cents(amount)
    if repay_cents <= 0:
        raise ValueError("Repayment amount must be strictly positive.")

    # Cap repayment to current outstanding balance
    if repay_cents > loan.outstanding_balance_cents:
        repay_cents = loan.outstanding_balance_cents

    # Check and debit source account
    acc = db.query(Account).filter(Account.account_number == from_account_number.strip().upper()).first()
    if not acc:
        raise ValueError(f"Account '{from_account_number}' not found.")

    if customer_id and acc.customer_id != customer_id:
        raise PermissionError("You can only make repayments from your own accounts.")

    if acc.status != "ACTIVE":
        raise ValueError(f"Account '{acc.account_number}' is not active.")

    if acc.balance_cents < repay_cents:
        raise ValueError(
            f"Insufficient account balance. Available: {cents_to_currency(acc.balance_cents)}, Required: {cents_to_currency(repay_cents)}."
        )

    try:
        # Debit account
        acc.balance_cents -= repay_cents
        txn = Transaction(
            transaction_reference=generate_txn_reference(),
            source_account_id=acc.id,
            transaction_type="WITHDRAWAL",
            amount_cents=repay_cents,
            balance_after_cents=acc.balance_cents,
            description=f"Loan Repayment for {loan.loan_reference}",
            status="COMPLETED"
        )
        db.add(txn)

        # Update loan balance
        loan.outstanding_balance_cents -= repay_cents
        if loan.outstanding_balance_cents == 0:
            loan.status = "CLOSED"

        repayment = LoanRepayment(
            repayment_reference=generate_repayment_reference(),
            loan_id=loan.id,
            amount_cents=repay_cents,
            payment_method="ACCOUNT_DEBIT",
            notes=notes.strip() if notes else f"Installment payment for {loan.loan_reference}"
        )
        db.add(repayment)
        db.commit()
        db.refresh(repayment)

        # Notification
        if loan.customer and loan.customer.user_id:
            close_msg = " Loan is now fully paid and closed!" if loan.status == "CLOSED" else f" Remaining balance: {cents_to_currency(loan.outstanding_balance_cents)}."
            create_notification(
                db=db,
                user_id=loan.customer.user_id,
                title="Loan Repayment Successful",
                message=f"Repayment of {cents_to_currency(repay_cents)} received for {loan.loan_reference}.{close_msg}",
                notification_type="LOAN"
            )

        return repayment
    except Exception as e:
        db.rollback()
        raise e

def get_customer_loans(db: Session, customer_id: int) -> List[Loan]:
    """Retrieve all loan applications for a customer."""
    return db.query(Loan).filter(Loan.customer_id == customer_id).order_by(Loan.created_at.desc()).all()

def get_all_loans(db: Session, status: Optional[str] = None) -> List[Loan]:
    """Retrieve loans for staff members with optional status filter."""
    query = db.query(Loan)
    if status:
        query = query.filter(Loan.status == status.upper())
    return query.order_by(Loan.created_at.desc()).all()
