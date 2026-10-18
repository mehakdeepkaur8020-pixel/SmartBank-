from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List, Any
import datetime
from decimal import Decimal

# --- User & Auth Schemas ---

class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8)
    first_name: str = Field(..., min_length=1, max_length=50)
    last_name: str = Field(..., min_length=1, max_length=50)
    phone: str = Field(..., min_length=7, max_length=20)
    address: str = Field(..., min_length=3)
    account_type: str = Field("SAVINGS", pattern="^(SAVINGS|CURRENT)$")
    initial_deposit: Optional[float] = Field(0.0, ge=0.0)

class UserLogin(BaseModel):
    username_or_email: str
    password: str

class PasswordChange(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=8)

class UserOut(BaseModel):
    id: int
    username: str
    email: str
    role: str
    is_active: bool
    created_at: datetime.datetime

    class Config:
        from_attributes = True

# --- Customer Profile Schemas ---

class CustomerOut(BaseModel):
    id: int
    user_id: int
    first_name: str
    last_name: str
    full_name: str
    phone: str
    address: str
    date_of_birth: Optional[str] = None
    national_id: Optional[str] = None
    created_at: datetime.datetime

    class Config:
        from_attributes = True

# --- Account Schemas ---

class AccountCreate(BaseModel):
    customer_id: int
    account_type: str = Field("SAVINGS", pattern="^(SAVINGS|CURRENT)$")
    initial_deposit: Optional[float] = Field(0.0, ge=0.0)

class AccountStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(ACTIVE|INACTIVE|FROZEN|CLOSED)$")

class AccountOut(BaseModel):
    id: int
    customer_id: int
    account_number: str
    account_type: str
    balance_cents: int
    balance_formatted: Optional[str] = None
    status: str
    currency: str
    created_at: datetime.datetime

    class Config:
        from_attributes = True

# --- Transaction Schemas ---

class DepositRequest(BaseModel):
    account_number: str
    amount: float = Field(..., gt=0.0)
    description: Optional[str] = "Cash Deposit"
    idempotency_key: Optional[str] = None

class WithdrawRequest(BaseModel):
    account_number: str
    amount: float = Field(..., gt=0.0)
    description: Optional[str] = "Cash Withdrawal"
    idempotency_key: Optional[str] = None

class TransferRequest(BaseModel):
    source_account_number: str
    destination_account_number: str
    amount: float = Field(..., gt=0.0)
    description: Optional[str] = "Funds Transfer"
    idempotency_key: Optional[str] = None

    @field_validator('destination_account_number')
    @classmethod
    def accounts_must_differ(cls, v, info):
        if 'source_account_number' in info.data and v == info.data['source_account_number']:
            raise ValueError("Destination account must be different from source account.")
        return v

class TransactionOut(BaseModel):
    id: int
    transaction_reference: str
    source_account_id: Optional[int] = None
    destination_account_id: Optional[int] = None
    transaction_type: str
    amount_cents: int
    amount_formatted: Optional[str] = None
    balance_after_cents: Optional[int] = None
    balance_after_formatted: Optional[str] = None
    description: str
    status: str
    created_at: datetime.datetime

    class Config:
        from_attributes = True

# --- Loan Schemas ---

class LoanApplication(BaseModel):
    category: str = Field(..., pattern="^(EDUCATION|PERSONAL|HOME|VEHICLE)$")
    amount: float = Field(..., gt=0.0)
    term_months: int = Field(..., ge=1, le=360)
    monthly_income: float = Field(..., gt=0.0)
    purpose: str = Field(..., min_length=5)

class LoanReview(BaseModel):
    decision: str = Field(..., pattern="^(APPROVED|REJECTED)$")
    reason: str = Field(..., min_length=3)
    approved_amount: Optional[float] = None

class LoanRepaymentCreate(BaseModel):
    loan_reference: str
    from_account_number: str
    amount: float = Field(..., gt=0.0)
    notes: Optional[str] = "Loan installment repayment"

class LoanOut(BaseModel):
    id: int
    loan_reference: str
    customer_id: int
    category: str
    amount_cents: int
    amount_formatted: Optional[str] = None
    interest_rate_percent: float
    term_months: int
    purpose: str
    status: str
    approved_amount_cents: int
    approved_amount_formatted: Optional[str] = None
    outstanding_balance_cents: int
    outstanding_balance_formatted: Optional[str] = None
    created_at: datetime.datetime

    class Config:
        from_attributes = True

# --- Chatbot Schemas ---

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)
    conversation_id: Optional[str] = None

class ChatResponse(BaseModel):
    reply: str
    conversation_id: str
    mode: str  # "FAQ", "AI", "TOOL_ASSISTED", "FALLBACK"
    suggestions: List[str] = []
    timestamp: str

# --- Notification & Audit Schemas ---

class NotificationOut(BaseModel):
    id: int
    title: str
    message: str
    notification_type: str
    is_read: bool
    created_at: datetime.datetime

    class Config:
        from_attributes = True

class AuditLogOut(BaseModel):
    id: int
    user_id: Optional[int] = None
    action: str
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    details: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: datetime.datetime

    class Config:
        from_attributes = True


# --- Account Application & Document Schemas ---

class AccountApplicationCreate(BaseModel):
    account_type: str = Field("SAVINGS", pattern="^(SAVINGS|CURRENT)$")
    initial_deposit: float = Field(0.0, ge=0.0)
    occupation: Optional[str] = "Professional"
    annual_income: Optional[float] = Field(0.0, ge=0.0)
    source_of_funds: Optional[str] = "Salary"
    branch_code: Optional[str] = "SBIN0001"
    signature_data: Optional[str] = None  # Base64 data URL from signature canvas
    video_verification_confirmed: Optional[bool] = True

class AccountApplicationReview(BaseModel):
    decision: str = Field(..., pattern="^(APPROVED|REJECTED)$")
    notes: str = Field(..., min_length=3)

class ApplicationDocumentOut(BaseModel):
    id: int
    application_id: int
    document_type: str
    document_number: Optional[str] = None
    original_filename: str
    file_size_bytes: int
    mime_type: str
    uploaded_at: datetime.datetime

    class Config:
        from_attributes = True

class AccountApplicationOut(BaseModel):
    id: int
    application_reference: str
    customer_id: int
    account_type: str
    status: str
    initial_deposit_cents: int
    initial_deposit_formatted: Optional[str] = None
    occupation: Optional[str] = None
    branch_code: str
    video_verification_status: str
    signature_image_path: Optional[str] = None
    created_account_id: Optional[int] = None
    created_at: datetime.datetime
    reviewed_at: Optional[datetime.datetime] = None

    class Config:
        from_attributes = True

