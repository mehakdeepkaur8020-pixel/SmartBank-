import pytest
from app.services.loan_service import (
    apply_for_loan,
    review_loan,
    make_loan_repayment,
    get_customer_loans
)
from app.schemas.schemas import LoanApplication, LoanReview
from app.models.models import Loan, Account

def test_loan_application_and_approval(db_session, test_users):
    cust_a = test_users["alice"].customer_profile
    app_data = LoanApplication(
        category="EDUCATION",
        amount=5000.00,
        term_months=24,
        monthly_income=2500.00,
        purpose="Engineering course fees"
    )
    
    loan = apply_for_loan(db_session, cust_a.id, app_data)
    assert loan.status == "PENDING"
    assert loan.amount_cents == 500000
    
    # Review & Approve
    rev_data = LoanReview(decision="APPROVED", reason="Good income profile", approved_amount=5000.00)
    reviewed = review_loan(db_session, loan.id, rev_data, test_users["emp"].id)
    
    assert reviewed.status == "APPROVED"
    assert reviewed.approved_amount_cents == 500000
    assert reviewed.outstanding_balance_cents == 500000

def test_loan_repayment_updates_balance(db_session, test_users):
    cust_a = test_users["alice"].customer_profile
    app_data = LoanApplication(
        category="PERSONAL",
        amount=1000.00,
        term_months=12,
        monthly_income=2000.00,
        purpose="Equipment upgrade"
    )
    loan = apply_for_loan(db_session, cust_a.id, app_data)
    review_loan(db_session, loan.id, LoanReview(decision="APPROVED", reason="Approved"), test_users["emp"].id)
    
    acc = db_session.query(Account).filter(Account.account_number == "SBTEST0001").first()
    acc_bal_before = acc.balance_cents
    
    repayment = make_loan_repayment(
        db=db_session,
        loan_id=loan.id,
        from_account_number="SBTEST0001",
        amount=300.00,
        customer_id=cust_a.id
    )
    assert repayment.amount_cents == 30000
    
    db_session.refresh(loan)
    db_session.refresh(acc)
    
    assert loan.outstanding_balance_cents == 70000
    assert acc.balance_cents == acc_bal_before - 30000

def test_cross_customer_loan_repayment_forbidden(db_session, test_users):
    cust_b = test_users["bob"].customer_profile
    # Bob applies for loan
    loan = apply_for_loan(
        db_session,
        cust_b.id,
        LoanApplication(category="PERSONAL", amount=500.0, term_months=6, monthly_income=1500.0, purpose="Personal")
    )
    review_loan(db_session, loan.id, LoanReview(decision="APPROVED", reason="Approved by staff"), test_users["emp"].id)
    
    # Alice attempts to repay Bob's loan with her customer ID
    with pytest.raises(PermissionError, match="Access denied"):
        make_loan_repayment(
            db=db_session,
            loan_id=loan.id,
            from_account_number="SBTEST0001",
            amount=100.00,
            customer_id=test_users["alice"].customer_profile.id
        )
