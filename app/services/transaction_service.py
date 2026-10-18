import datetime
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from typing import List, Optional, Tuple, Dict, Any
from app.models.models import Account, Transaction, TransactionReview, User
from app.utils.security import (
    currency_to_cents,
    cents_to_currency,
    generate_txn_reference
)
from app.services.audit_service import log_action
from app.services.notification_service import create_notification
from app.config import settings

def check_idempotency(db: Session, idempotency_key: Optional[str]) -> Optional[Transaction]:
    """Check if a request with this idempotency key was already completed."""
    if not idempotency_key:
        return None
    return db.query(Transaction).filter(Transaction.idempotency_key == idempotency_key).first()

def check_transaction_monitoring_rules(
    db: Session,
    transaction: Transaction
) -> Optional[TransactionReview]:
    """Rule-based transaction monitoring for academic demonstration."""
    flag_reason = None

    # Rule 1: High-value transaction
    if transaction.amount_cents >= settings.LARGE_TRANSACTION_THRESHOLD_CENTS:
        flag_reason = f"High-value transaction: {cents_to_currency(transaction.amount_cents)} exceeds safety threshold."

    # Rule 2: Velocity check (multiple transactions in last 60 seconds)
    if not flag_reason and transaction.source_account_id:
        one_min_ago = datetime.datetime.utcnow() - datetime.timedelta(seconds=60)
        recent_count = db.query(Transaction).filter(
            Transaction.source_account_id == transaction.source_account_id,
            Transaction.created_at >= one_min_ago
        ).count()
        if recent_count >= settings.RAPID_TXN_VELOCITY_LIMIT:
            flag_reason = f"High velocity: {recent_count} transactions detected in the past 60 seconds."

    if flag_reason:
        review = TransactionReview(
            transaction_id=transaction.id,
            flag_reason=flag_reason,
            status="PENDING"
        )
        db.add(review)
        db.commit()
        db.refresh(review)
        return review

    return None

def deposit(
    db: Session,
    account_number: str,
    amount: float,
    description: str = "Cash Deposit",
    idempotency_key: Optional[str] = None,
    user_id: Optional[int] = None
) -> Transaction:
    """Deposit money into an active bank account."""
    if idempotency_key:
        existing = check_idempotency(db, idempotency_key)
        if existing:
            return existing

    amount_cents = currency_to_cents(amount)
    if amount_cents <= 0:
        raise ValueError("Deposit amount must be strictly greater than zero.")

    account = db.query(Account).filter(Account.account_number == account_number.strip().upper()).first()
    if not account:
        raise ValueError(f"Account '{account_number}' not found.")

    if account.status != "ACTIVE":
        raise ValueError(f"Cannot deposit to account with status '{account.status}'.")

    try:
        account.balance_cents += amount_cents
        txn = Transaction(
            transaction_reference=generate_txn_reference(),
            destination_account_id=account.id,
            transaction_type="DEPOSIT",
            amount_cents=amount_cents,
            balance_after_cents=account.balance_cents,
            description=description.strip(),
            status="COMPLETED",
            idempotency_key=idempotency_key
        )
        db.add(txn)
        db.commit()
        db.refresh(txn)

        check_transaction_monitoring_rules(db, txn)

        # Notify customer
        if account.customer and account.customer.user_id:
            create_notification(
                db=db,
                user_id=account.customer.user_id,
                title="Deposit Successful",
                message=f"Credited {cents_to_currency(amount_cents)} to account {account.account_number}. Current balance: {cents_to_currency(account.balance_cents)}.",
                notification_type="TRANSACTION"
            )

        log_action(
            db=db,
            action="DEPOSIT",
            user_id=user_id or (account.customer.user_id if account.customer else None),
            entity_type="Transaction",
            entity_id=str(txn.id),
            details=f"Deposited {cents_to_currency(amount_cents)} to {account.account_number}"
        )

        return txn
    except Exception as e:
        db.rollback()
        raise e

def withdraw(
    db: Session,
    account_number: str,
    amount: float,
    description: str = "Cash Withdrawal",
    idempotency_key: Optional[str] = None,
    user_id: Optional[int] = None
) -> Transaction:
    """Withdraw funds from an active bank account with sufficient balance check."""
    if idempotency_key:
        existing = check_idempotency(db, idempotency_key)
        if existing:
            return existing

    amount_cents = currency_to_cents(amount)
    if amount_cents <= 0:
        raise ValueError("Withdrawal amount must be strictly greater than zero.")

    account = db.query(Account).filter(Account.account_number == account_number.strip().upper()).first()
    if not account:
        raise ValueError(f"Account '{account_number}' not found.")

    if account.status != "ACTIVE":
        raise ValueError(f"Cannot withdraw from account with status '{account.status}'.")

    if account.balance_cents < amount_cents:
        raise ValueError(
            f"Insufficient funds. Requested: {cents_to_currency(amount_cents)}, Available: {cents_to_currency(account.balance_cents)}."
        )

    try:
        account.balance_cents -= amount_cents
        txn = Transaction(
            transaction_reference=generate_txn_reference(),
            source_account_id=account.id,
            transaction_type="WITHDRAWAL",
            amount_cents=amount_cents,
            balance_after_cents=account.balance_cents,
            description=description.strip(),
            status="COMPLETED",
            idempotency_key=idempotency_key
        )
        db.add(txn)
        db.commit()
        db.refresh(txn)

        check_transaction_monitoring_rules(db, txn)

        if account.customer and account.customer.user_id:
            create_notification(
                db=db,
                user_id=account.customer.user_id,
                title="Withdrawal Debited",
                message=f"Debited {cents_to_currency(amount_cents)} from account {account.account_number}. Available balance: {cents_to_currency(account.balance_cents)}.",
                notification_type="TRANSACTION"
            )

        log_action(
            db=db,
            action="WITHDRAWAL",
            user_id=user_id or (account.customer.user_id if account.customer else None),
            entity_type="Transaction",
            entity_id=str(txn.id),
            details=f"Withdrew {cents_to_currency(amount_cents)} from {account.account_number}"
        )

        return txn
    except Exception as e:
        db.rollback()
        raise e

def transfer(
    db: Session,
    source_account_number: str,
    destination_account_number: str,
    amount: float,
    description: str = "Funds Transfer",
    idempotency_key: Optional[str] = None,
    user_id: Optional[int] = None
) -> Transaction:
    """Atomic funds transfer between two accounts with strict verification."""
    if idempotency_key:
        existing = check_idempotency(db, idempotency_key)
        if existing:
            return existing

    amount_cents = currency_to_cents(amount)
    if amount_cents <= 0:
        raise ValueError("Transfer amount must be strictly greater than zero.")

    src_clean = source_account_number.strip().upper()
    dst_clean = destination_account_number.strip().upper()

    if src_clean == dst_clean:
        raise ValueError("Source and destination accounts must be distinct.")

    src_acc = db.query(Account).filter(Account.account_number == src_clean).first()
    dst_acc = db.query(Account).filter(Account.account_number == dst_clean).first()

    if not src_acc:
        raise ValueError(f"Source account '{src_clean}' does not exist.")
    if not dst_acc:
        raise ValueError(f"Destination account '{dst_clean}' does not exist.")

    if src_acc.status != "ACTIVE":
        raise ValueError(f"Source account is '{src_acc.status}'. Cannot initiate transfers.")
    if dst_acc.status != "ACTIVE":
        raise ValueError(f"Destination account is '{dst_acc.status}'. Cannot receive transfers.")

    if src_acc.balance_cents < amount_cents:
        raise ValueError(
            f"Insufficient balance. Required: {cents_to_currency(amount_cents)}, Available: {cents_to_currency(src_acc.balance_cents)}."
        )

    # Atomic transaction execution
    try:
        src_acc.balance_cents -= amount_cents
        dst_acc.balance_cents += amount_cents

        txn = Transaction(
            transaction_reference=generate_txn_reference(),
            source_account_id=src_acc.id,
            destination_account_id=dst_acc.id,
            transaction_type="TRANSFER",
            amount_cents=amount_cents,
            balance_after_cents=src_acc.balance_cents,
            description=description.strip(),
            status="COMPLETED",
            idempotency_key=idempotency_key
        )
        db.add(txn)
        db.commit()
        db.refresh(txn)

        check_transaction_monitoring_rules(db, txn)

        # Send notifications to sender and receiver
        if src_acc.customer and src_acc.customer.user_id:
            create_notification(
                db=db,
                user_id=src_acc.customer.user_id,
                title="Transfer Sent",
                message=f"Transferred {cents_to_currency(amount_cents)} to account {dst_acc.account_number}. Balance: {cents_to_currency(src_acc.balance_cents)}.",
                notification_type="TRANSACTION"
            )

        if dst_acc.customer and dst_acc.customer.user_id:
            create_notification(
                db=db,
                user_id=dst_acc.customer.user_id,
                title="Transfer Received",
                message=f"Received {cents_to_currency(amount_cents)} from account {src_acc.account_number}. Balance: {cents_to_currency(dst_acc.balance_cents)}.",
                notification_type="TRANSACTION"
            )

        log_action(
            db=db,
            action="TRANSFER",
            user_id=user_id or (src_acc.customer.user_id if src_acc.customer else None),
            entity_type="Transaction",
            entity_id=str(txn.id),
            details=f"Transferred {cents_to_currency(amount_cents)} from {src_acc.account_number} to {dst_acc.account_number}"
        )

        return txn
    except Exception as e:
        db.rollback()
        raise e

def reverse_transaction(
    db: Session,
    transaction_id: int,
    employee_user_id: int,
    reason: str
) -> Transaction:
    """
    Controlled reversal of a previous transaction using traceable compensating entries.
    Only authorized employees/admins can execute reversals.
    """
    orig_txn = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not orig_txn:
        raise ValueError("Transaction not found.")

    if orig_txn.status != "COMPLETED":
        raise ValueError(f"Cannot reverse transaction with status '{orig_txn.status}'.")

    # Check if already reversed
    child_rev = db.query(Transaction).filter(Transaction.parent_transaction_id == orig_txn.id).first()
    if child_rev:
        raise ValueError(f"Transaction has already been reversed via {child_rev.transaction_reference}.")

    src_acc = orig_txn.source_account
    dst_acc = orig_txn.destination_account
    amount_cents = orig_txn.amount_cents

    try:
        if orig_txn.transaction_type == "DEPOSIT":
            # Reverse deposit by debiting destination account
            if not dst_acc or dst_acc.balance_cents < amount_cents:
                raise ValueError("Insufficient balance in account to compensate deposit reversal.")
            dst_acc.balance_cents -= amount_cents
            balance_after = dst_acc.balance_cents

            rev_txn = Transaction(
                transaction_reference=generate_txn_reference(),
                source_account_id=dst_acc.id,
                transaction_type="REVERSAL",
                amount_cents=amount_cents,
                balance_after_cents=balance_after,
                description=f"Compensating Reversal for {orig_txn.transaction_reference}: {reason}",
                status="COMPLETED",
                parent_transaction_id=orig_txn.id
            )

        elif orig_txn.transaction_type == "WITHDRAWAL":
            # Reverse withdrawal by crediting source account
            if not src_acc:
                raise ValueError("Source account not available for reversal.")
            src_acc.balance_cents += amount_cents
            balance_after = src_acc.balance_cents

            rev_txn = Transaction(
                transaction_reference=generate_txn_reference(),
                destination_account_id=src_acc.id,
                transaction_type="REVERSAL",
                amount_cents=amount_cents,
                balance_after_cents=balance_after,
                description=f"Compensating Reversal for {orig_txn.transaction_reference}: {reason}",
                status="COMPLETED",
                parent_transaction_id=orig_txn.id
            )

        elif orig_txn.transaction_type == "TRANSFER":
            # Reverse transfer: debit recipient, credit original sender
            if not dst_acc or dst_acc.balance_cents < amount_cents:
                raise ValueError("Recipient account has insufficient balance to reverse transfer.")
            if not src_acc:
                raise ValueError("Source account no longer valid.")

            dst_acc.balance_cents -= amount_cents
            src_acc.balance_cents += amount_cents
            balance_after = src_acc.balance_cents

            rev_txn = Transaction(
                transaction_reference=generate_txn_reference(),
                source_account_id=dst_acc.id,
                destination_account_id=src_acc.id,
                transaction_type="REVERSAL",
                amount_cents=amount_cents,
                balance_after_cents=balance_after,
                description=f"Compensating Reversal for {orig_txn.transaction_reference}: {reason}",
                status="COMPLETED",
                parent_transaction_id=orig_txn.id
            )
        else:
            raise ValueError(f"Cannot reverse transaction type '{orig_txn.transaction_type}'.")

        orig_txn.status = "REVERSED"
        db.add(rev_txn)
        db.commit()
        db.refresh(rev_txn)

        log_action(
            db=db,
            action="TRANSACTION_REVERSAL",
            user_id=employee_user_id,
            entity_type="Transaction",
            entity_id=str(orig_txn.id),
            details=f"Reversed {orig_txn.transaction_reference} creating {rev_txn.transaction_reference}. Reason: {reason}"
        )

        return rev_txn
    except Exception as e:
        db.rollback()
        raise e

def get_transactions_for_account(
    db: Session,
    account_id: int,
    limit: int = 50,
    offset: int = 0,
    txn_type: Optional[str] = None,
    start_date: Optional[datetime.date] = None,
    end_date: Optional[datetime.date] = None
) -> List[Transaction]:
    """Retrieve transaction history for an account with filters."""
    query = db.query(Transaction).filter(
        or_(
            Transaction.source_account_id == account_id,
            Transaction.destination_account_id == account_id
        )
    )

    if txn_type:
        query = query.filter(Transaction.transaction_type == txn_type.upper())

    if start_date:
        start_dt = datetime.datetime.combine(start_date, datetime.time.min)
        query = query.filter(Transaction.created_at >= start_dt)

    if end_date:
        end_dt = datetime.datetime.combine(end_date, datetime.time.max)
        query = query.filter(Transaction.created_at <= end_dt)

    return query.order_by(Transaction.created_at.desc()).offset(offset).limit(limit).all()

def get_all_transactions(
    db: Session,
    limit: int = 100,
    offset: int = 0,
    txn_type: Optional[str] = None,
    status: Optional[str] = None,
    search_ref: Optional[str] = None
) -> List[Transaction]:
    """List transactions across all accounts for bank employees and admin."""
    query = db.query(Transaction)
    if txn_type:
        query = query.filter(Transaction.transaction_type == txn_type.upper())
    if status:
        query = query.filter(Transaction.status == status.upper())
    if search_ref:
        query = query.filter(Transaction.transaction_reference.ilike(f"%{search_ref.strip()}%"))
    return query.order_by(Transaction.created_at.desc()).offset(offset).limit(limit).all()
