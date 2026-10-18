import hmac
import hashlib
import base64
import json
import time
import uuid
import re
import os
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Dict, Any
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHash
from app.config import settings

ph = PasswordHasher(
    time_cost=2,
    memory_cost=19456,  # 19 MiB
    parallelism=1,
    hash_len=32,
    salt_len=16
)

def hash_password(password: str) -> str:
    """Hash a password using Argon2id."""
    return ph.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    """Verify a plain password against an Argon2id hash."""
    try:
        return ph.verify(hashed, password)
    except (VerifyMismatchError, InvalidHash):
        return False

# --- Stateless HMAC-SHA256 Signed Session Tokens ---

def generate_session_token(user_id: int, role: str, username: str) -> str:
    """Generate a tamper-proof signed session token."""
    expires_at = int(time.time()) + (settings.SESSION_EXPIRE_HOURS * 3600)
    payload = {
        "sub": user_id,
        "role": role,
        "username": username,
        "exp": expires_at,
        "nonce": uuid.uuid4().hex[:8]
    }
    payload_json = json.dumps(payload, separators=(',', ':'))
    payload_b64 = base64.urlsafe_b64encode(payload_json.encode('utf-8')).decode('utf-8').rstrip('=')
    signature = hmac.new(
        settings.SECRET_KEY.encode('utf-8'),
        payload_b64.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return f"{payload_b64}.{signature}"

def verify_session_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify session token integrity and expiration. Returns payload dict or None."""
    if not token or "." not in token:
        return None
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None
        payload_b64, signature = parts
        
        expected_sig = hmac.new(
            settings.SECRET_KEY.encode('utf-8'),
            payload_b64.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(signature, expected_sig):
            return None
        
        padded_b64 = payload_b64 + '=' * (-len(payload_b64) % 4)
        payload_json = base64.urlsafe_b64decode(padded_b64.encode('utf-8')).decode('utf-8')
        payload = json.loads(payload_json)
        
        if payload.get("exp", 0) < int(time.time()):
            return None
            
        return payload
    except Exception:
        return None

# --- Precise Monetary Calculations in INR (Indian Numbering System) ---

def currency_to_cents(amount_val: Any) -> int:
    """
    Convert a string or numeric amount into integer paise/cents using Decimal.
    Example: '125000.50' -> 12500050.
    """
    if amount_val is None:
        raise ValueError("Amount cannot be empty.")
    try:
        clean_str = str(amount_val).strip().replace(',', '').replace('₹', '').replace('$', '')
        d = Decimal(clean_str)
        if d <= 0:
            raise ValueError("Amount must be greater than zero.")
        cents = int((d * Decimal(100)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
        return cents
    except Exception as e:
        if isinstance(e, ValueError):
            raise
        raise ValueError(f"Invalid monetary amount: {amount_val}")

def format_indian_number(amount_decimal: Decimal) -> str:
    """
    Format a decimal into the Indian numbering system.
    Examples:
      125000.00 -> 1,25,000.00
      1500000.50 -> 15,00,000.50
      5420.50 -> 5,420.50
      350.00 -> 350.00
    """
    is_negative = amount_decimal < Decimal(0)
    pos_val = abs(amount_decimal)
    
    parts = f"{pos_val:.2f}".split(".")
    integer_part = parts[0]
    decimal_part = parts[1]
    
    if len(integer_part) <= 3:
        formatted_int = integer_part
    else:
        last_three = integer_part[-3:]
        remaining = integer_part[:-3]
        groups = []
        while len(remaining) > 2:
            groups.insert(0, remaining[-2:])
            remaining = remaining[:-2]
        if remaining:
            groups.insert(0, remaining)
        formatted_int = ",".join(groups) + "," + last_three
        
    result = f"{formatted_int}.{decimal_part}"
    return f"-{result}" if is_negative else result

def cents_to_currency(cents: int, include_symbol: bool = True) -> str:
    """
    Convert integer paise/cents to formatted Indian Rupee (INR) string.
    Example: 12500000 -> '₹1,25,000.00'
    """
    if cents is None:
        cents = 0
    d = Decimal(cents) / Decimal(100)
    formatted = format_indian_number(d)
    if include_symbol:
        return f"{settings.CURRENCY_SYMBOL}{formatted}"
    return formatted

# --- Masking & Security Identifiers ---

def mask_account_number(account_number: str) -> str:
    """Mask account number showing only prefix and last 4 digits (e.g., SB••••5678)."""
    if not account_number or len(account_number) < 6:
        return account_number or ""
    prefix = account_number[:2]
    suffix = account_number[-4:]
    return f"{prefix}••••{suffix}"

def generate_account_number() -> str:
    """Generate a unique 12-digit Indian banking style account number (e.g. SBIN40019283)."""
    random_digits = "".join([str(uuid.uuid4().int % 10) for _ in range(8)])
    return f"SBIN40{random_digits}"

def generate_application_reference() -> str:
    """Generate a unique application reference number."""
    return f"APP-2026-{uuid.uuid4().hex[:8].upper()}"

def generate_txn_reference() -> str:
    """Generate a unique transaction reference."""
    return f"TXN-IN-{uuid.uuid4().hex[:10].upper()}"

def generate_loan_reference() -> str:
    """Generate a unique loan reference."""
    return f"LN-IN-{uuid.uuid4().hex[:8].upper()}"

def generate_repayment_reference() -> str:
    """Generate a unique repayment reference."""
    return f"REP-IN-{uuid.uuid4().hex[:8].upper()}"

def generate_safe_upload_filename(original_filename: str, prefix: str = "doc") -> str:
    """Generate a randomized safe filename preventing directory traversal and overwrite."""
    ext = os.path.splitext(original_filename)[1].lower()
    if ext not in [".jpg", ".jpeg", ".png", ".pdf", ".webp"]:
        ext = ".pdf"
    safe_name = f"{prefix}_{uuid.uuid4().hex[:16]}{ext}"
    return safe_name

def sanitize_text(text: str) -> str:
    """XSS protection by stripping HTML tags."""
    if not text:
        return ""
    clean = re.sub(r'<[^>]*?>', '', text)
    return clean.strip()
