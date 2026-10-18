import pytest
from app.services.report_service import generate_statement_pdf, generate_transactions_csv
from app.models.models import Account
from app.utils.security import generate_session_token
from app.config import settings

def test_generate_pdf_statement_bytes(db_session, test_users):
    acc = db_session.query(Account).filter(Account.account_number == "SBTEST0001").first()
    cust = test_users["alice"].customer_profile
    
    pdf_bytes = generate_statement_pdf(
        account=acc,
        customer=cust,
        transactions=[]
    )
    assert pdf_bytes is not None
    assert len(pdf_bytes) > 0
    # PDF magic bytes
    assert pdf_bytes.startswith(b"%PDF-")

def test_generate_transactions_csv(db_session, test_users):
    csv_str = generate_transactions_csv([])
    assert "Reference,Date,Type" in csv_str

def test_customer_cannot_download_other_customer_statement(client, test_users):
    # Log in as Alice
    token = generate_session_token(user_id=test_users["alice"].id, role="customer", username="test_alice")
    client.cookies.set(settings.SESSION_COOKIE_NAME, token)
    
    # Try downloading Bob's account SBTEST0002
    response = client.get("/reports/statement/pdf?account_number=SBTEST0002")
    assert response.status_code == 403
    assert "Unauthorized" in response.text
