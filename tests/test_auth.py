import pytest
from app.utils.security import (
    generate_session_token,
    verify_session_token,
    verify_password,
    hash_password
)
from app.config import settings

def test_password_hashing():
    pw = "SecretSecurePass123"
    hashed = hash_password(pw)
    assert verify_password(pw, hashed) is True
    assert verify_password("WrongPass", hashed) is False

def test_session_token_generation_and_verification():
    token = generate_session_token(user_id=42, role="customer", username="testuser")
    assert token is not None
    payload = verify_session_token(token)
    assert payload is not None
    assert payload["sub"] == 42
    assert payload["role"] == "customer"
    assert payload["username"] == "testuser"

def test_tampered_session_token_rejected():
    token = generate_session_token(user_id=42, role="customer", username="testuser")
    parts = token.split(".")
    tampered = f"{parts[0]}.wrongsignature"
    assert verify_session_token(tampered) is None

def test_login_valid(client, test_users):
    response = client.post(
        "/auth/login",
        data={"username_or_email": "test_alice", "password": "Pass@1234"},
        follow_redirects=False
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/customer/dashboard"
    assert settings.SESSION_COOKIE_NAME in response.cookies

def test_login_invalid(client):
    response = client.post(
        "/auth/login",
        data={"username_or_email": "test_alice", "password": "WrongPassword"},
        follow_redirects=False
    )
    assert response.status_code == 400
    assert "Invalid username/email or password" in response.text

def test_logout(client):
    response = client.get("/auth/logout", follow_redirects=False)
    assert response.status_code == 303
    cookie = response.cookies.get(settings.SESSION_COOKIE_NAME)
    assert cookie is None or cookie == ""

def test_role_restriction_customer_cannot_access_admin(client, test_users):
    token = generate_session_token(user_id=test_users["alice"].id, role="customer", username="test_alice")
    client.cookies.set(settings.SESSION_COOKIE_NAME, token)
    response = client.get("/admin/dashboard")
    assert response.status_code == 403

def test_role_restriction_employee_cannot_access_admin(client, test_users):
    token = generate_session_token(user_id=test_users["emp"].id, role="employee", username="test_emp")
    client.cookies.set(settings.SESSION_COOKIE_NAME, token)
    response = client.get("/admin/dashboard")
    assert response.status_code == 403
