import pytest
from app.services.transaction_service import (
    deposit,
    withdraw,
    transfer,
    reverse_transaction,
    get_transactions_for_account
)
from app.models.models import Account, Transaction
from app.utils.security import currency_to_cents

def test_valid_deposit(db_session, test_users):
    acc = db_session.query(Account).filter(Account.account_number == "SBTEST0001").first()
    initial_balance = acc.balance_cents
    
    txn = deposit(db_session, "SBTEST0001", amount=150.00, description="Test Deposit")
    assert txn.status == "COMPLETED"
    assert txn.amount_cents == 15000
    
    db_session.refresh(acc)
    assert acc.balance_cents == initial_balance + 15000

def test_withdrawal_exceeding_balance_rejected(db_session, test_users):
    acc = db_session.query(Account).filter(Account.account_number == "SBTEST0001").first()
    initial_balance = acc.balance_cents
    
    with pytest.raises(ValueError, match="Insufficient funds"):
        withdraw(db_session, "SBTEST0001", amount=9999999.00)

    db_session.refresh(acc)
    assert acc.balance_cents == initial_balance

def test_valid_transfer_atomic(db_session, test_users):
    acc_a = db_session.query(Account).filter(Account.account_number == "SBTEST0001").first()
    acc_b = db_session.query(Account).filter(Account.account_number == "SBTEST0002").first()
    
    bal_a_before = acc_a.balance_cents
    bal_b_before = acc_b.balance_cents
    
    txn = transfer(
        db=db_session,
        source_account_number="SBTEST0001",
        destination_account_number="SBTEST0002",
        amount=100.00,
        description="Atomic Test Transfer"
    )
    assert txn.status == "COMPLETED"
    
    db_session.refresh(acc_a)
    db_session.refresh(acc_b)
    
    assert acc_a.balance_cents == bal_a_before - 10000
    assert acc_b.balance_cents == bal_b_before + 10000

def test_transfer_to_same_account_rejected(db_session, test_users):
    with pytest.raises(ValueError, match="must be distinct"):
        transfer(
            db=db_session,
            source_account_number="SBTEST0001",
            destination_account_number="SBTEST0001",
            amount=50.00
        )

def test_transfer_to_nonexistent_account_rejected(db_session, test_users):
    acc_a = db_session.query(Account).filter(Account.account_number == "SBTEST0001").first()
    bal_before = acc_a.balance_cents
    
    with pytest.raises(ValueError, match="does not exist"):
        transfer(
            db=db_session,
            source_account_number="SBTEST0001",
            destination_account_number="SBTEST_DOES_NOT_EXIST",
            amount=50.00
        )

    db_session.refresh(acc_a)
    assert acc_a.balance_cents == bal_before

def test_idempotency_duplicate_protection(db_session, test_users):
    key = "IDEMP-KEY-TEST-12345"
    txn1 = deposit(db_session, "SBTEST0001", amount=25.00, idempotency_key=key)
    # Second call with same idempotency key must return same txn without double crediting
    txn2 = deposit(db_session, "SBTEST0001", amount=25.00, idempotency_key=key)
    
    assert txn1.id == txn2.id
    assert txn1.transaction_reference == txn2.transaction_reference

def test_controlled_transaction_reversal(db_session, test_users):
    # Execute a transfer
    txn = transfer(
        db=db_session,
        source_account_number="SBTEST0001",
        destination_account_number="SBTEST0002",
        amount=50.00,
        description="Transfer to be reversed"
    )
    
    acc_a = db_session.query(Account).filter(Account.account_number == "SBTEST0001").first()
    acc_b = db_session.query(Account).filter(Account.account_number == "SBTEST0002").first()
    bal_a_after_transfer = acc_a.balance_cents
    bal_b_after_transfer = acc_b.balance_cents
    
    # Reverse it
    rev = reverse_transaction(
        db=db_session,
        transaction_id=txn.id,
        employee_user_id=test_users["emp"].id,
        reason="Disputed transfer chargeback"
    )
    assert rev.transaction_type == "REVERSAL"
    assert rev.status == "COMPLETED"
    assert rev.parent_transaction_id == txn.id
    
    db_session.refresh(acc_a)
    db_session.refresh(acc_b)
    
    assert acc_a.balance_cents == bal_a_after_transfer + 5000
    assert acc_b.balance_cents == bal_b_after_transfer - 5000

def test_large_transaction_monitoring_flag(db_session, test_users):
    # Deposit $15,000 (exceeds $10,000 threshold)
    txn = deposit(db_session, "SBTEST0001", amount=15000.00, description="Large Corporate Wire")
    assert txn.status == "COMPLETED"
    assert len(txn.reviews) > 0
    assert "exceeds safety threshold" in txn.reviews[0].flag_reason
