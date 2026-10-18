import datetime
from sqlalchemy import (
    Column, Integer, BigInteger, String, Text, Boolean, Float, DateTime, ForeignKey, Index
)
from sqlalchemy.orm import relationship
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(120), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), default="customer", nullable=False)  # customer, employee, admin
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    # Relationships
    customer_profile = relationship("Customer", back_populates="user", uselist=False, cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user")
    chat_conversations = relationship("ChatConversation", back_populates="user", cascade="all, delete-orphan")
    application_reviews = relationship("AccountApplication", foreign_keys="AccountApplication.reviewed_by_user_id", back_populates="reviewer")

class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    first_name = Column(String(50), nullable=False)
    last_name = Column(String(50), nullable=False)
    phone = Column(String(20), nullable=False)
    address = Column(Text, nullable=False)
    date_of_birth = Column(String(20), nullable=True)
    national_id = Column(String(50), unique=True, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="customer_profile")
    accounts = relationship("Account", back_populates="customer", cascade="all, delete-orphan")
    loans = relationship("Loan", back_populates="customer", cascade="all, delete-orphan")
    applications = relationship("AccountApplication", back_populates="customer", cascade="all, delete-orphan")

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)
    account_number = Column(String(20), unique=True, index=True, nullable=False)
    account_type = Column(String(20), default="SAVINGS", nullable=False)  # SAVINGS, CURRENT
    balance_cents = Column(BigInteger, default=0, nullable=False)
    status = Column(String(20), default="ACTIVE", nullable=False)  # ACTIVE, INACTIVE, FROZEN, CLOSED
    currency = Column(String(3), default="INR", nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    # Relationships
    customer = relationship("Customer", back_populates="accounts")
    sent_transactions = relationship("Transaction", foreign_keys="Transaction.source_account_id", back_populates="source_account")
    received_transactions = relationship("Transaction", foreign_keys="Transaction.destination_account_id", back_populates="destination_account")

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    transaction_reference = Column(String(36), unique=True, index=True, nullable=False)
    source_account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)
    destination_account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)
    transaction_type = Column(String(20), nullable=False)  # DEPOSIT, WITHDRAWAL, TRANSFER, REVERSAL
    amount_cents = Column(BigInteger, nullable=False)
    balance_after_cents = Column(BigInteger, nullable=True)
    description = Column(String(255), nullable=False)
    status = Column(String(20), default="COMPLETED", nullable=False)  # COMPLETED, FAILED, REVERSED
    idempotency_key = Column(String(64), unique=True, index=True, nullable=True)
    parent_transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True, nullable=False)

    # Relationships
    source_account = relationship("Account", foreign_keys=[source_account_id], back_populates="sent_transactions")
    destination_account = relationship("Account", foreign_keys=[destination_account_id], back_populates="received_transactions")
    parent_transaction = relationship("Transaction", remote_side=[id])
    reviews = relationship("TransactionReview", back_populates="transaction", cascade="all, delete-orphan")

class TransactionReview(Base):
    __tablename__ = "transaction_reviews"

    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(Integer, ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False)
    flag_reason = Column(String(255), nullable=False)
    status = Column(String(20), default="PENDING", nullable=False)  # PENDING, APPROVED, DISMISSED
    reviewed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    review_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    reviewed_at = Column(DateTime, nullable=True)

    # Relationships
    transaction = relationship("Transaction", back_populates="reviews")
    reviewer = relationship("User", foreign_keys=[reviewed_by_user_id])

class Loan(Base):
    __tablename__ = "loans"

    id = Column(Integer, primary_key=True, index=True)
    loan_reference = Column(String(36), unique=True, index=True, nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)
    category = Column(String(30), nullable=False)  # EDUCATION, PERSONAL, HOME, VEHICLE
    amount_cents = Column(BigInteger, nullable=False)
    interest_rate_percent = Column(Float, default=7.5, nullable=False)
    term_months = Column(Integer, nullable=False)
    purpose = Column(Text, nullable=False)
    monthly_income_cents = Column(BigInteger, nullable=False)
    status = Column(String(20), default="PENDING", nullable=False)  # PENDING, APPROVED, REJECTED, CLOSED
    approved_amount_cents = Column(BigInteger, default=0, nullable=False)
    outstanding_balance_cents = Column(BigInteger, default=0, nullable=False)
    reviewed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    review_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    reviewed_at = Column(DateTime, nullable=True)

    # Relationships
    customer = relationship("Customer", back_populates="loans")
    reviewer = relationship("User", foreign_keys=[reviewed_by_user_id])
    repayments = relationship("LoanRepayment", back_populates="loan", cascade="all, delete-orphan")

class LoanRepayment(Base):
    __tablename__ = "loan_repayments"

    id = Column(Integer, primary_key=True, index=True)
    repayment_reference = Column(String(36), unique=True, index=True, nullable=False)
    loan_id = Column(Integer, ForeignKey("loans.id", ondelete="CASCADE"), nullable=False)
    amount_cents = Column(BigInteger, nullable=False)
    payment_method = Column(String(30), default="ACCOUNT_DEBIT", nullable=False)
    notes = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    # Relationships
    loan = relationship("Loan", back_populates="repayments")

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(100), nullable=False)
    message = Column(Text, nullable=False)
    notification_type = Column(String(30), default="INFO", nullable=False)  # INFO, TRANSACTION, LOAN, SECURITY
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="notifications")

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = Column(String(50), nullable=False)
    entity_type = Column(String(50), nullable=True)
    entity_id = Column(String(50), nullable=True)
    details = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True, nullable=False)

    # Relationships
    user = relationship("User", back_populates="audit_logs")

class FAQ(Base):
    __tablename__ = "faqs"

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String(50), nullable=False)
    question = Column(String(255), nullable=False)
    answer = Column(Text, nullable=False)
    keywords = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

class ChatConversation(Base):
    __tablename__ = "chat_conversations"

    id = Column(String(36), primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    status = Column(String(20), default="ACTIVE", nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="chat_conversations")
    messages = relationship("ChatMessage", back_populates="conversation", cascade="all, delete-orphan", order_by="ChatMessage.created_at")

class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(String(36), ForeignKey("chat_conversations.id", ondelete="CASCADE"), nullable=False)
    sender_type = Column(String(20), nullable=False)  # USER, ASSISTANT
    message_text = Column(Text, nullable=False)
    intent_category = Column(String(50), nullable=True)
    response_mode = Column(String(30), nullable=True)  # FAQ, AI, TOOL_ASSISTED, FALLBACK
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    # Relationships
    conversation = relationship("ChatConversation", back_populates="messages")


class AccountApplication(Base):
    __tablename__ = "account_applications"

    id = Column(Integer, primary_key=True, index=True)
    application_reference = Column(String(36), unique=True, index=True, nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)
    account_type = Column(String(20), default="SAVINGS", nullable=False)  # SAVINGS, CURRENT
    status = Column(String(20), default="PENDING_REVIEW", nullable=False)  # PENDING_REVIEW, UNDER_REVIEW, APPROVED, REJECTED
    initial_deposit_cents = Column(BigInteger, default=0, nullable=False)
    occupation = Column(String(100), nullable=True)
    annual_income_cents = Column(BigInteger, default=0, nullable=True)
    source_of_funds = Column(String(100), nullable=True)
    branch_code = Column(String(20), default="SBIN0001", nullable=False)
    signature_image_path = Column(String(255), nullable=True)
    video_verification_status = Column(String(30), default="COMPLETED", nullable=False)  # PENDING, COMPLETED, WAIVED
    video_verification_notes = Column(Text, nullable=True)
    reviewed_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    review_decision_notes = Column(Text, nullable=True)
    created_account_id = Column(Integer, ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True, nullable=False)
    reviewed_at = Column(DateTime, nullable=True)

    # Relationships
    customer = relationship("Customer", back_populates="applications")
    reviewer = relationship("User", foreign_keys=[reviewed_by_user_id], back_populates="application_reviews")
    created_account = relationship("Account", foreign_keys=[created_account_id])
    documents = relationship("ApplicationDocument", back_populates="application", cascade="all, delete-orphan")
    review_history = relationship("ApplicationReviewHistory", back_populates="application", cascade="all, delete-orphan", order_by="ApplicationReviewHistory.created_at")


class ApplicationDocument(Base):
    __tablename__ = "application_documents"

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("account_applications.id", ondelete="CASCADE"), nullable=False)
    document_type = Column(String(50), nullable=False)  # AADHAAR, PAN, PASSPORT, VOTER_ID, SALARY_SLIP
    document_number = Column(String(50), nullable=True)
    file_path = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    mime_type = Column(String(100), nullable=False)
    uploaded_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    # Relationships
    application = relationship("AccountApplication", back_populates="documents")


class ApplicationReviewHistory(Base):
    __tablename__ = "application_review_history"

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("account_applications.id", ondelete="CASCADE"), nullable=False)
    action = Column(String(50), nullable=False)  # SUBMITTED, DOCUMENT_UPLOADED, UNDER_REVIEW, APPROVED, REJECTED
    actor_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    # Relationships
    application = relationship("AccountApplication", back_populates="review_history")
    actor = relationship("User", foreign_keys=[actor_user_id])

