from sqlalchemy.orm import Session
from typing import Optional
from app.models.models import User, Customer, Account
from app.schemas.schemas import UserRegister
from app.utils.security import (
    hash_password,
    verify_password,
    currency_to_cents
)
from app.services.account_service import create_customer_profile, create_account
from app.services.audit_service import log_action
from app.services.notification_service import create_notification

def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()

def get_user_by_username(db: Session, username: str) -> Optional[User]:
    return db.query(User).filter(User.username == username.strip().lower()).first()

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email.strip().lower()).first()

def register_user(
    db: Session,
    reg_data: UserRegister,
    role: str = "customer",
    ip_address: Optional[str] = None
) -> User:
    """Register a new user and create customer profile + initial account if role is customer."""
    # Check if username or email exists
    if get_user_by_username(db, reg_data.username):
        raise ValueError("Username already taken. Please choose another.")
    if get_user_by_email(db, reg_data.email):
        raise ValueError("Email already registered. Please login or use a different email.")

    # Create User
    user = User(
        username=reg_data.username.strip().lower(),
        email=reg_data.email.strip().lower(),
        password_hash=hash_password(reg_data.password),
        role=role,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # If customer, create profile. Account opening strictly requires Video KYC and document upload.
    if role == "customer":
        cust = create_customer_profile(
            db=db,
            user_id=user.id,
            first_name=reg_data.first_name,
            last_name=reg_data.last_name,
            phone=reg_data.phone,
            address=reg_data.address
        )

        create_notification(
            db=db,
            user_id=user.id,
            title="Welcome to SmartBank!",
            message="Registration successful! Please complete your Video KYC verification and document upload to open your bank account.",
            notification_type="SECURITY"
        )

    log_action(
        db=db,
        action="USER_REGISTRATION",
        user_id=user.id,
        entity_type="User",
        entity_id=str(user.id),
        details=f"Registered user {user.username} with role {role}",
        ip_address=ip_address
    )

    return user

def authenticate_user(
    db: Session,
    username_or_email: str,
    password: str,
    ip_address: Optional[str] = None
) -> Optional[User]:
    """Authenticate credentials and return user if active."""
    identifier = username_or_email.strip().lower()
    user = db.query(User).filter(
        (User.username == identifier) | (User.email == identifier)
    ).first()

    if not user:
        return None

    if not user.is_active:
        raise PermissionError("Account is deactivated. Please contact bank administration.")

    if not verify_password(password, user.password_hash):
        log_action(
            db=db,
            action="LOGIN_FAILED",
            user_id=user.id,
            entity_type="User",
            entity_id=str(user.id),
            details=f"Failed login attempt for {user.username}",
            ip_address=ip_address
        )
        return None

    log_action(
        db=db,
        action="LOGIN_SUCCESS",
        user_id=user.id,
        entity_type="User",
        entity_id=str(user.id),
        details=f"Successful login for {user.username}",
        ip_address=ip_address
    )
    return user

def change_password(
    db: Session,
    user_id: int,
    old_password: str,
    new_password: str
) -> bool:
    """Change user password safely."""
    user = get_user_by_id(db, user_id)
    if not user:
        raise ValueError("User not found.")

    if not verify_password(old_password, user.password_hash):
        raise ValueError("Current password is incorrect.")

    user.password_hash = hash_password(new_password)
    db.commit()

    log_action(
        db=db,
        action="PASSWORD_CHANGE",
        user_id=user.id,
        entity_type="User",
        entity_id=str(user.id),
        details="User password updated successfully"
    )
    create_notification(
        db=db,
        user_id=user.id,
        title="Password Changed",
        message="Your account password was recently updated.",
        notification_type="SECURITY"
    )
    return True

def update_user_role(
    db: Session,
    target_user_id: int,
    new_role: str,
    admin_user_id: int
) -> User:
    """Change role of a user (admin only)."""
    user = get_user_by_id(db, target_user_id)
    if not user:
        raise ValueError("User not found.")

    old_role = user.role
    user.role = new_role.lower()
    db.commit()
    db.refresh(user)

    log_action(
        db=db,
        action="ROLE_CHANGE",
        user_id=admin_user_id,
        entity_type="User",
        entity_id=str(user.id),
        details=f"Role changed from {old_role} to {new_role} for user {user.username}"
    )
    return user

def toggle_user_active(
    db: Session,
    target_user_id: int,
    admin_user_id: int
) -> User:
    """Activate or deactivate a user account."""
    user = get_user_by_id(db, target_user_id)
    if not user:
        raise ValueError("User not found.")

    user.is_active = not user.is_active
    db.commit()
    db.refresh(user)

    log_action(
        db=db,
        action="USER_STATUS_CHANGE",
        user_id=admin_user_id,
        entity_type="User",
        entity_id=str(user.id),
        details=f"User {user.username} active status set to {user.is_active}"
    )
    return user
