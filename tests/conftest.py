import pytest
import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.database import Base, get_db
from app.main import app
from app.models.models import User, Customer, Account, FAQ
from app.utils.security import hash_password, generate_session_token
from app.services.faq_service import seed_default_faqs

TEST_DB_URL = "sqlite:///./test_smartbank.db"

test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=test_engine)
    db = TestingSessionLocal()
    seed_default_faqs(db)
    db.close()
    yield
    Base.metadata.drop_all(bind=test_engine)
    if os.path.exists("./test_smartbank.db"):
        try:
            os.remove("./test_smartbank.db")
        except Exception:
            pass

@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

@pytest.fixture
def test_users(db_session):
    """Seed test users for test suites."""
    # Customer A (Alice)
    alice = db_session.query(User).filter(User.username == "test_alice").first()
    if not alice:
        alice = User(
            username="test_alice",
            email="alice_test@example.com",
            password_hash=hash_password("Pass@1234"),
            role="customer",
            is_active=True
        )
        db_session.add(alice)
        db_session.commit()

        cust_a = Customer(
            user_id=alice.id,
            first_name="Alice",
            last_name="Test",
            phone="111-222-3333",
            address="123 Test Street"
        )
        db_session.add(cust_a)
        db_session.commit()

        acc_a = Account(
            customer_id=cust_a.id,
            account_number="SBTEST0001",
            account_type="SAVINGS",
            balance_cents=200000,  # $2,000.00
            status="ACTIVE"
        )
        db_session.add(acc_a)
        db_session.commit()

    # Customer B (Bob)
    bob = db_session.query(User).filter(User.username == "test_bob").first()
    if not bob:
        bob = User(
            username="test_bob",
            email="bob_test@example.com",
            password_hash=hash_password("Pass@1234"),
            role="customer",
            is_active=True
        )
        db_session.add(bob)
        db_session.commit()

        cust_b = Customer(
            user_id=bob.id,
            first_name="Bob",
            last_name="Test",
            phone="444-555-6666",
            address="456 Other Road"
        )
        db_session.add(cust_b)
        db_session.commit()

        acc_b = Account(
            customer_id=cust_b.id,
            account_number="SBTEST0002",
            account_type="SAVINGS",
            balance_cents=50000,  # $500.00
            status="ACTIVE"
        )
        db_session.add(acc_b)
        db_session.commit()

    # Staff Employee
    emp = db_session.query(User).filter(User.username == "test_emp").first()
    if not emp:
        emp = User(
            username="test_emp",
            email="emp_test@example.com",
            password_hash=hash_password("Pass@1234"),
            role="employee",
            is_active=True
        )
        db_session.add(emp)
        db_session.commit()

    # Admin
    admin = db_session.query(User).filter(User.username == "test_admin").first()
    if not admin:
        admin = User(
            username="test_admin",
            email="admin_test@example.com",
            password_hash=hash_password("Pass@1234"),
            role="admin",
            is_active=True
        )
        db_session.add(admin)
        db_session.commit()

    return {
        "alice": alice,
        "bob": bob,
        "emp": emp,
        "admin": admin
    }
