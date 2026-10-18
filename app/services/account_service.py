import os
import base64
import datetime
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional
from app.models.models import (
    Customer, Account, Transaction, User,
    AccountApplication, ApplicationDocument, ApplicationReviewHistory, Notification
)
from app.utils.security import (
    generate_account_number, generate_txn_reference, cents_to_currency,
    generate_application_reference, generate_safe_upload_filename
)
from app.config import UPLOAD_DIR, SIGNATURE_DIR, DOCUMENT_DIR
from app.services.audit_service import log_action

def create_customer_profile(
    db: Session,
    user_id: int,
    first_name: str,
    last_name: str,
    phone: str,
    address: str,
    national_id: Optional[str] = None,
    date_of_birth: Optional[str] = None
) -> Customer:
    """Create a customer profile for a registered user."""
    customer = Customer(
        user_id=user_id,
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        phone=phone.strip(),
        address=address.strip(),
        national_id=national_id.strip() if national_id else None,
        date_of_birth=date_of_birth
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer

def create_account(
    db: Session,
    customer_id: int,
    account_type: str = "SAVINGS",
    initial_deposit_cents: int = 0
) -> Account:
    """Create a new bank account with unique account number and optional initial deposit."""
    # Ensure unique account number
    while True:
        acc_num = generate_account_number()
        exists = db.query(Account).filter(Account.account_number == acc_num).first()
        if not exists:
            break

    account = Account(
        customer_id=customer_id,
        account_number=acc_num,
        account_type=account_type.upper(),
        balance_cents=initial_deposit_cents,
        status="ACTIVE",
        currency="INR"
    )
    db.add(account)
    db.commit()
    db.refresh(account)

    if initial_deposit_cents > 0:
        # Record initial deposit transaction
        txn = Transaction(
            transaction_reference=generate_txn_reference(),
            destination_account_id=account.id,
            transaction_type="DEPOSIT",
            amount_cents=initial_deposit_cents,
            balance_after_cents=initial_deposit_cents,
            description="Initial Account Opening Deposit",
            status="COMPLETED"
        )
        db.add(txn)
        db.commit()

    return account

def get_customer_by_user_id(db: Session, user_id: int) -> Optional[Customer]:
    """Retrieve customer profile by user ID."""
    return db.query(Customer).filter(Customer.user_id == user_id).first()

def get_customer_accounts(db: Session, customer_id: int) -> List[Account]:
    """Retrieve all accounts belonging to a customer."""
    return db.query(Account).filter(Account.customer_id == customer_id).all()

def get_account_by_number(db: Session, account_number: str) -> Optional[Account]:
    """Look up an account by its unique account number."""
    return db.query(Account).filter(Account.account_number == account_number.strip().upper()).first()

def update_account_status(
    db: Session,
    account_number: str,
    new_status: str,
    reviewer_user_id: int
) -> Account:
    """Update account operational status (ACTIVE, INACTIVE, FROZEN, CLOSED)."""
    account = get_account_by_number(db, account_number)
    if not account:
        raise ValueError(f"Account '{account_number}' not found.")

    old_status = account.status
    account.status = new_status.upper()
    db.commit()
    db.refresh(account)

    log_action(
        db=db,
        action="ACCOUNT_STATUS_CHANGE",
        user_id=reviewer_user_id,
        entity_type="Account",
        entity_id=str(account.id),
        details=f"Account {account.account_number} status changed from {old_status} to {new_status}"
    )
    return account

def get_all_customers_with_accounts(
    db: Session,
    search_term: Optional[str] = None
) -> List[Customer]:
    """Search and list customers with accounts for staff members."""
    query = db.query(Customer)
    if search_term:
        term = f"%{search_term.strip()}%"
        query = query.filter(
            or_(
                Customer.first_name.ilike(term),
                Customer.last_name.ilike(term),
                Customer.phone.ilike(term),
                Customer.national_id.ilike(term),
                Customer.accounts.any(Account.account_number.ilike(term))
            )
        )
    return query.order_by(Customer.created_at.desc()).all()


# --- Account Application & Verification Workflow ---

def submit_account_application(
    db: Session,
    customer_id: int,
    account_type: str = "SAVINGS",
    initial_deposit_cents: int = 0,
    occupation: Optional[str] = "Professional",
    annual_income_cents: int = 0,
    source_of_funds: Optional[str] = "Salary",
    branch_code: str = "SBIN0001",
    signature_data: Optional[str] = None,
    video_verification_status: str = "COMPLETED"
) -> AccountApplication:
    """Submit a new bank account opening application with KYC details, signature, and verification."""
    # Generate unique application reference
    while True:
        app_ref = generate_application_reference()
        exists = db.query(AccountApplication).filter(AccountApplication.application_reference == app_ref).first()
        if not exists:
            break

    # Save signature image if provided
    signature_path = None
    if signature_data:
        try:
            # Handle data URL e.g. "data:image/png;base64,..."
            if "," in signature_data:
                _, b64data = signature_data.split(",", 1)
            else:
                b64data = signature_data
            sig_bytes = base64.b64decode(b64data)
            sig_filename = f"sig_{app_ref.lower()}.png"
            full_sig_path = os.path.join(SIGNATURE_DIR, sig_filename)
            with open(full_sig_path, "wb") as f:
                f.write(sig_bytes)
            signature_path = f"uploads/signatures/{sig_filename}"
        except Exception:
            signature_path = None

    application = AccountApplication(
        application_reference=app_ref,
        customer_id=customer_id,
        account_type=account_type.upper(),
        status="PENDING_REVIEW",
        initial_deposit_cents=initial_deposit_cents,
        occupation=occupation,
        annual_income_cents=annual_income_cents,
        source_of_funds=source_of_funds,
        branch_code=branch_code,
        signature_image_path=signature_path,
        video_verification_status=video_verification_status,
        video_verification_notes="Live browser camera verification session completed and recorded."
    )
    db.add(application)
    db.flush()

    # Add initial history entry
    history = ApplicationReviewHistory(
        application_id=application.id,
        action="SUBMITTED",
        notes=f"Application submitted online with {account_type.upper()} account request."
    )
    db.add(history)

    # Customer notification
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if customer:
        notif = Notification(
            user_id=customer.user_id,
            title="Account Application Submitted",
            message=f"Your {account_type} account application #{app_ref} has been received and is currently under review by our operations team.",
            notification_type="INFO"
        )
        db.add(notif)

    db.commit()
    db.refresh(application)
    return application


def save_application_document(
    db: Session,
    application_id: int,
    document_type: str,
    document_number: Optional[str],
    file_bytes: bytes,
    original_filename: str,
    mime_type: str
) -> ApplicationDocument:
    """Store an uploaded KYC verification document on disk and record in database."""
    safe_name = generate_safe_upload_filename(original_filename, prefix=f"doc_{document_type.lower()}_")
    full_path = os.path.join(DOCUMENT_DIR, safe_name)
    with open(full_path, "wb") as f:
        f.write(file_bytes)

    rel_path = f"uploads/documents/{safe_name}"
    doc = ApplicationDocument(
        application_id=application_id,
        document_type=document_type.upper(),
        document_number=document_number.strip() if document_number else None,
        file_path=rel_path,
        original_filename=original_filename,
        file_size_bytes=len(file_bytes),
        mime_type=mime_type
    )
    db.add(doc)

    history = ApplicationReviewHistory(
        application_id=application_id,
        action="DOCUMENT_UPLOADED",
        notes=f"KYC document uploaded: {document_type.upper()} ({original_filename})"
    )
    db.add(history)

    db.commit()
    db.refresh(doc)
    return doc


def get_customer_applications(db: Session, customer_id: int) -> List[AccountApplication]:
    """Retrieve all account applications for a customer."""
    return db.query(AccountApplication).filter(
        AccountApplication.customer_id == customer_id
    ).order_by(AccountApplication.created_at.desc()).all()


def get_application_by_reference(db: Session, reference: str) -> Optional[AccountApplication]:
    """Look up an application by its unique reference string."""
    return db.query(AccountApplication).filter(
        AccountApplication.application_reference == reference.strip()
    ).first()


def get_application_by_id(db: Session, application_id: int) -> Optional[AccountApplication]:
    """Look up an application by its primary key."""
    return db.query(AccountApplication).filter(AccountApplication.id == application_id).first()


def get_all_applications(db: Session, status: Optional[str] = None) -> List[AccountApplication]:
    """Retrieve all applications for staff review, optionally filtered by status."""
    query = db.query(AccountApplication)
    if status:
        query = query.filter(AccountApplication.status == status.upper())
    return query.order_by(AccountApplication.created_at.desc()).all()


def review_account_application(
    db: Session,
    application_id: int,
    reviewer_user_id: int,
    decision: str,
    notes: str
) -> AccountApplication:
    """Approve or reject a customer account application with full audit trail and account creation."""
    app = get_application_by_id(db, application_id)
    if not app:
        raise ValueError(f"Application #{application_id} not found.")

    if app.status in ["APPROVED", "REJECTED"]:
        raise ValueError(f"Application has already been resolved with status {app.status}.")

    decision_clean = decision.strip().upper()
    now = datetime.datetime.utcnow()
    app.reviewed_by_user_id = reviewer_user_id
    app.review_decision_notes = notes
    app.reviewed_at = now

    if decision_clean == "APPROVED":
        # Create the verified bank account
        account = create_account(
            db=db,
            customer_id=app.customer_id,
            account_type=app.account_type,
            initial_deposit_cents=app.initial_deposit_cents
        )
        app.status = "APPROVED"
        app.created_account_id = account.id

        history = ApplicationReviewHistory(
            application_id=app.id,
            action="APPROVED",
            actor_user_id=reviewer_user_id,
            notes=f"Application approved. Account created: {account.account_number} ({account.account_type}). Reviewer notes: {notes}"
        )
        db.add(history)

        # Notify customer
        customer = db.query(Customer).filter(Customer.id == app.customer_id).first()
        if customer:
            notif = Notification(
                user_id=customer.user_id,
                title="Account Approved and Activated!",
                message=f"Congratulations! Your {app.account_type} account has been verified and opened. Your account number is {account.account_number}.",
                notification_type="INFO"
            )
            db.add(notif)

        log_action(
            db=db,
            action="ACCOUNT_APPLICATION_APPROVED",
            user_id=reviewer_user_id,
            entity_type="AccountApplication",
            entity_id=str(app.id),
            details=f"Application {app.application_reference} approved. Account {account.account_number} generated."
        )

    elif decision_clean == "REJECTED":
        app.status = "REJECTED"
        history = ApplicationReviewHistory(
            application_id=app.id,
            action="REJECTED",
            actor_user_id=reviewer_user_id,
            notes=f"Application rejected. Reason: {notes}"
        )
        db.add(history)

        customer = db.query(Customer).filter(Customer.id == app.customer_id).first()
        if customer:
            notif = Notification(
                user_id=customer.user_id,
                title="Account Application Update",
                message=f"Your account application #{app.application_reference} could not be approved at this time. Reason: {notes}",
                notification_type="SECURITY"
            )
            db.add(notif)

        log_action(
            db=db,
            action="ACCOUNT_APPLICATION_REJECTED",
            user_id=reviewer_user_id,
            entity_type="AccountApplication",
            entity_id=str(app.id),
            details=f"Application {app.application_reference} rejected. Reason: {notes}"
        )
    else:
        raise ValueError(f"Invalid review decision '{decision}'. Must be APPROVED or REJECTED.")

    db.commit()
    db.refresh(app)
    return app

