"""
SmartBank Demo Data Seeder Script (Indian Currency INR & Realistic Profiles)
Initializes database tables and creates realistic Indian banking data for:
- 1 System Administrator
- 1 Bank Employee
- 2 Customers (Priya Patel, Aarav Sharma) with multiple accounts, transactions, loans, repayments, and notifications
- 1 Pending Account Application with document and live video KYC record for testing employee verification
- Large-transaction monitoring flag (> ₹5,00,000 threshold)
- Complete Indian banking FAQ knowledge base
"""

import sys
import os
import datetime
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.database import engine, Base, SessionLocal
from app.models.models import (
    User, Customer, Account, Transaction, TransactionReview,
    Loan, LoanRepayment, Notification, AuditLog, FAQ,
    AccountApplication, ApplicationDocument, ApplicationReviewHistory
)
from app.utils.security import hash_password, generate_txn_reference
from app.services.faq_service import seed_default_faqs

def utcnow():
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)

def seed_database(reset: bool = True):
    print("Initializing database tables...")
    if reset:
        print("Resetting database schema for fresh Indian Rupee (INR) dataset...")
        Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        print("Seeding Indian Banking FAQs...")
        seed_default_faqs(db)

        print("Creating Administrator user...")
        admin_user = User(
            username="admin",
            email="admin@smartbank.local",
            password_hash=hash_password("Admin@123"),
            role="admin",
            is_active=True
        )
        db.add(admin_user)

        print("Creating Bank Employee user...")
        employee_user = User(
            username="employee",
            email="employee@smartbank.local",
            password_hash=hash_password("Employee@123"),
            role="employee",
            is_active=True
        )
        db.add(employee_user)
        db.commit()

        print("Creating Customer 1 (Priya Patel)...")
        priya_user = User(
            username="priya",
            email="priya@example.com",
            password_hash=hash_password("Priya@123"),
            role="customer",
            is_active=True
        )
        db.add(priya_user)
        db.commit()

        priya_cust = Customer(
            user_id=priya_user.id,
            first_name="Priya",
            last_name="Patel",
            phone="+91 98201 45678",
            address="Flat 602, Sea Breeze Towers, Worli, Mumbai, Maharashtra - 400018",
            national_id="IND-PAN-ABCDE1234F",
            date_of_birth="1994-06-18"
        )
        db.add(priya_cust)
        db.commit()

        # Priya Accounts in INR
        priya_acc1 = Account(
            customer_id=priya_cust.id,
            account_number="SBIN40129841",
            account_type="SAVINGS",
            balance_cents=28500000,  # ₹2,85,000.00
            status="ACTIVE",
            currency="INR"
        )
        priya_acc2 = Account(
            customer_id=priya_cust.id,
            account_number="SBIN40129842",
            account_type="CURRENT",
            balance_cents=125000000,  # ₹12,50,000.00
            status="ACTIVE",
            currency="INR"
        )
        db.add_all([priya_acc1, priya_acc2])
        db.commit()

        print("Creating Customer 2 (Aarav Sharma)...")
        aarav_user = User(
            username="aarav",
            email="aarav@example.com",
            password_hash=hash_password("Aarav@123"),
            role="customer",
            is_active=True
        )
        db.add(aarav_user)
        db.commit()

        aarav_cust = Customer(
            user_id=aarav_user.id,
            first_name="Aarav",
            last_name="Sharma",
            phone="+91 98450 12345",
            address="42 Green Glen Layout, Bellandur, Bengaluru, Karnataka - 560103",
            national_id="IND-PAN-PQRS9876T",
            date_of_birth="1992-11-24"
        )
        db.add(aarav_cust)
        db.commit()

        # Aarav Account in INR
        aarav_acc = Account(
            customer_id=aarav_cust.id,
            account_number="SBIN50831920",
            account_type="SAVINGS",
            balance_cents=14500000,  # ₹1,45,000.00
            status="ACTIVE",
            currency="INR"
        )
        db.add(aarav_acc)
        db.commit()

        print("Seeding realistic INR transactions...")
        t1 = Transaction(
            transaction_reference="TXN-INIT-PRIYA1",
            destination_account_id=priya_acc1.id,
            transaction_type="DEPOSIT",
            amount_cents=15000000,  # ₹1,50,000.00
            balance_after_cents=15000000,
            description="Initial Opening Deposit via NEFT",
            status="COMPLETED",
            created_at=utcnow() - datetime.timedelta(days=15)
        )
        t2 = Transaction(
            transaction_reference="TXN-PAYROLL-PRIYA",
            destination_account_id=priya_acc1.id,
            transaction_type="DEPOSIT",
            amount_cents=16000000,  # ₹1,60,000.00
            balance_after_cents=31000000,
            description="Monthly Corporate Salary Credit",
            status="COMPLETED",
            created_at=utcnow() - datetime.timedelta(days=10)
        )
        t3 = Transaction(
            transaction_reference="TXN-IMPS-PRIYA-AARAV",
            source_account_id=priya_acc1.id,
            destination_account_id=aarav_acc.id,
            transaction_type="TRANSFER",
            amount_cents=2000000,  # ₹20,000.00
            balance_after_cents=29000000,
            description="IMPS Fund Transfer - Shared House Rent",
            status="COMPLETED",
            created_at=utcnow() - datetime.timedelta(days=3)
        )
        t4 = Transaction(
            transaction_reference="TXN-ATM-PRIYA",
            source_account_id=priya_acc1.id,
            transaction_type="WITHDRAWAL",
            amount_cents=500000,  # ₹5,000.00
            balance_after_cents=28500000,
            description="Branch ATM Cash Withdrawal",
            status="COMPLETED",
            created_at=utcnow() - datetime.timedelta(days=1)
        )
        # Large commercial wire deposit (> ₹5,00,000 threshold for staff monitoring demonstration)
        t5_large = Transaction(
            transaction_reference="TXN-RTGS-LARGE",
            destination_account_id=priya_acc2.id,
            transaction_type="DEPOSIT",
            amount_cents=125000000,  # ₹12,50,000.00
            balance_after_cents=125000000,
            description="RTGS Commercial Vendor Settlement",
            status="COMPLETED",
            created_at=utcnow() - datetime.timedelta(hours=6)
        )
        db.add_all([t1, t2, t3, t4, t5_large])
        db.commit()

        print("Seeding high-value transaction monitoring flag...")
        rev = TransactionReview(
            transaction_id=t5_large.id,
            flag_reason="High-value RTGS deposit: ₹12,50,000.00 exceeds institutional ₹5,00,000.00 monitoring threshold.",
            status="PENDING"
        )
        db.add(rev)
        db.commit()

        print("Seeding loans and repayments in INR...")
        priya_loan = Loan(
            loan_reference="LN-EDU-2026-P1",
            customer_id=priya_cust.id,
            category="EDUCATION",
            amount_cents=80000000,  # ₹8,00,000.00
            interest_rate_percent=8.5,
            term_months=36,
            purpose="Higher studies in Data Science & Cloud Computing at IIT Bombay",
            monthly_income_cents=16000000,  # ₹1,60,000.00
            status="APPROVED",
            approved_amount_cents=80000000,
            outstanding_balance_cents=75000000,  # ₹7,50,000.00 after repayment
            reviewed_by_user_id=employee_user.id,
            review_reason="Approved based on excellent credit score and verified salary slip.",
            created_at=utcnow() - datetime.timedelta(days=20),
            reviewed_at=utcnow() - datetime.timedelta(days=18)
        )
        db.add(priya_loan)
        db.commit()

        repayment = LoanRepayment(
            repayment_reference="REP-2026-IN01",
            loan_id=priya_loan.id,
            amount_cents=5000000,  # ₹50,000.00
            payment_method="ACCOUNT_DEBIT",
            notes="First monthly loan installment via auto-debit",
            created_at=utcnow() - datetime.timedelta(days=5)
        )
        db.add(repayment)

        # Aarav Pending Home Loan
        aarav_loan = Loan(
            loan_reference="LN-HOME-2026-A1",
            customer_id=aarav_cust.id,
            category="HOME",
            amount_cents=350000000,  # ₹35,00,000.00
            interest_rate_percent=7.5,
            term_months=180,
            purpose="Apartment purchase in Whitefield, Bengaluru",
            monthly_income_cents=14000000,  # ₹1,40,000.00
            status="PENDING",
            approved_amount_cents=0,
            outstanding_balance_cents=0,
            created_at=utcnow() - datetime.timedelta(days=2)
        )
        db.add(aarav_loan)
        db.commit()

        print("Seeding pending Account Opening Application for KYC Verification queue...")
        demo_app = AccountApplication(
            application_reference="APP-20261011-9481",
            customer_id=aarav_cust.id,
            account_type="CURRENT",
            status="PENDING_REVIEW",
            initial_deposit_cents=2500000,  # ₹25,000.00
            occupation="Tech Consultant & Entrepreneur",
            annual_income_cents=180000000,  # ₹18,00,000.00
            source_of_funds="Business Consulting",
            branch_code="SBIN0002",
            video_verification_status="COMPLETED",
            video_verification_notes="Live webcam session completed. Face match confidence 98.4%."
        )
        db.add(demo_app)
        db.flush()

        app_doc = ApplicationDocument(
            application_id=demo_app.id,
            document_type="PAN",
            document_number="PQRS9876T",
            file_path="uploads/documents/pan_card_specimen.pdf",
            original_filename="Aarav_Sharma_PAN_Card.pdf",
            file_size_bytes=245800,
            mime_type="application/pdf"
        )
        db.add(app_doc)

        app_hist = ApplicationReviewHistory(
            application_id=demo_app.id,
            action="SUBMITTED",
            notes="Customer submitted application with PAN verification and completed video KYC."
        )
        db.add(app_hist)

        print("Seeding customer notifications...")
        n1 = Notification(
            user_id=priya_user.id,
            title="Welcome to SmartBank India",
            message="Your Savings account SBIN40129841 is active and ready for NEFT/IMPS transfers.",
            notification_type="INFO",
            is_read=True
        )
        n2 = Notification(
            user_id=priya_user.id,
            title="Education Loan Sanctioned",
            message="Congratulations! Your Education loan LN-EDU-2026-P1 for ₹8,00,000.00 has been sanctioned.",
            notification_type="LOAN",
            is_read=False
        )
        n3 = Notification(
            user_id=aarav_user.id,
            title="KYC Application Received",
            message="Your Current account application APP-20261011-9481 is currently under review by our operations team.",
            notification_type="INFO",
            is_read=False
        )
        db.add_all([n1, n2, n3])

        print("Seeding institutional audit logs...")
        log1 = AuditLog(
            user_id=admin_user.id,
            action="SYSTEM_INIT",
            entity_type="System",
            details="Database schema initialized with Indian Rupee (INR) core configurations",
            ip_address="127.0.0.1"
        )
        log2 = AuditLog(
            user_id=employee_user.id,
            action="LOAN_APPROVAL",
            entity_type="Loan",
            entity_id=str(priya_loan.id),
            details=f"Sanctioned Education loan {priya_loan.loan_reference} for ₹8,00,000.00",
            ip_address="127.0.0.1"
        )
        db.add_all([log1, log2])
        db.commit()

        print("\n========================================================")
        print("SmartBank Indian Rupee (INR) Database Successfully Seeded!")
        print("========================================================")
        print("Platform Credentials:")
        print("  [Admin]     admin@smartbank.local      /  Admin@123")
        print("  [Employee]  employee@smartbank.local   /  Employee@123")
        print("  [Customer]  priya@example.com          /  Priya@123")
        print("  [Customer]  aarav@example.com          /  Aarav@123")
        print("========================================================\n")

    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
