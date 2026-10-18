from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    APP_NAME: str = "SmartBank"
    APP_VERSION: str = "2.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    SECRET_KEY: str = "smartbank-super-secret-key-change-in-production-2026-btech"
    SESSION_COOKIE_NAME: str = "smartbank_session"
    SESSION_EXPIRE_HOURS: int = 8
    
    # Database
    DATABASE_URL: str = f"sqlite:///{BASE_DIR}/smartbank.db"
    TEST_DATABASE_URL: str = f"sqlite:///{BASE_DIR}/smartbank_test.db"
    
    # Currency (Indian Rupee INR)
    CURRENCY_CODE: str = "INR"
    CURRENCY_SYMBOL: str = "₹"
    
    # Rule-Based Monitoring Thresholds (in Paise: ₹5,00,000.00 = 50,000,000 paise)
    LARGE_TRANSACTION_THRESHOLD_CENTS: int = 50000000  # ₹5,00,000.00
    RAPID_TXN_VELOCITY_LIMIT: int = 5  # 5 txns in 60s
    
    # File Uploads Directory
    UPLOAD_DIR: str = str(BASE_DIR / "uploads")
    MAX_UPLOAD_SIZE_BYTES: int = 5 * 1024 * 1024  # 5 MB
    
    # Chatbot & AI Configuration
    AI_ENABLED: bool = True
    AI_PROVIDER: str = "gemini"  # "gemini" or "disabled"
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-2.5-flash"
    CHATBOT_CONFIDENCE_THRESHOLD: float = 0.25
    
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()

UPLOAD_DIR = settings.UPLOAD_DIR
DOCUMENT_DIR = str(BASE_DIR / "uploads" / "documents")
SIGNATURE_DIR = str(BASE_DIR / "uploads" / "signatures")

# Ensure required directories exist
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(DOCUMENT_DIR, exist_ok=True)
os.makedirs(SIGNATURE_DIR, exist_ok=True)
