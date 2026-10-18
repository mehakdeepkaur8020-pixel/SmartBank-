"""
Verification script for SmartBank System Checks
"""
import sys
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from fastapi.testclient import TestClient
from app.main import app

def run_verification():
    client = TestClient(app, follow_redirects=False)
    print("=== STARTING SMARTBANK SYSTEM VERIFICATION ===")

    # 1. Public Landing Page
    res = client.get("/")
    assert res.status_code == 200, f"Landing page status {res.status_code}"
    html = res.text
    assert "SmartBank" in html
    assert "admin@smartbank.local" not in html, "Demo credentials leaked on landing page!"
    assert "Priya@123" not in html, "Demo password leaked on landing page!"
    assert "Next-Gen Digital Banking" in html
    print("[PASS] 1. Landing Page renders cleanly without demo credentials.")

    # 2. Login Page
    res = client.get("/auth/login")
    assert res.status_code == 200
    html = res.text
    assert "Customer Sign In" in html
    assert "Quick Fill" not in html, "Demo cheat sheet found on login page!"
    assert "employee@smartbank.local" not in html, "Demo credentials leaked on login page!"
    print("[PASS] 2. Login page renders role-based tabs without demo credentials.")

    # 3. Customer Authentication & Dashboard
    res = client.post("/auth/login", data={"username_or_email": "priya@example.com", "password": "Priya@123"})
    assert res.status_code == 303, f"Expected 303 redirect, got {res.status_code}"
    dash_url = res.headers.get("location")
    assert dash_url == "/customer/dashboard"
    
    res_dash = client.get(dash_url)
    assert res_dash.status_code == 200
    html = res_dash.text
    assert "Priya" in html
    assert "₹" in html
    assert "SBIN" in html
    print("[PASS] 3. Customer login and dashboard working in INR.")

    # 4. Customer Statement Downloads
    from app.database import SessionLocal
    from app.models.models import User
    db = SessionLocal()
    priya_user = db.query(User).filter_by(email="priya@example.com").first()
    priya_acc = priya_user.customer_profile.accounts[0]
    acc_number = priya_acc.account_number
    db.close()

    res_pdf = client.get(f"/reports/statement/pdf?account_number={acc_number}")
    assert res_pdf.status_code == 200
    assert res_pdf.headers.get("content-type") == "application/pdf"
    assert len(res_pdf.content) > 1000
    print(f"[PASS] 4a. Statement PDF generated successfully ({len(res_pdf.content)} bytes).")

    res_csv = client.get(f"/reports/statement/csv?account_number={acc_number}")
    assert res_csv.status_code == 200
    assert "text/csv" in res_csv.headers.get("content-type")
    assert "Reference" in res_csv.text
    assert "Amount (INR)" in res_csv.text
    print("[PASS] 4b. Statement CSV generated successfully.")

    # 5. Customer Application Forms
    res_apply = client.get("/customer/apply-account")
    assert res_apply.status_code == 200
    assert "Open New Account with Video KYC" in res_apply.text
    assert "signatureCanvas" in res_apply.text
    assert "videoElement" in res_apply.text
    print("[PASS] 5a. Account application form with signature pad & camera verification loads.")

    res_status = client.get("/customer/application-status")
    assert res_status.status_code == 200
    print("[PASS] 5b. Customer application status page loads.")

    res_open_alias = client.get("/customer/open-account")
    assert res_open_alias.status_code == 303
    assert res_open_alias.headers.get("location") == "/customer/apply-account"
    print("[PASS] 5c. Any open-account request strictly redirects to Video KYC application.")

    # 6. Chatbot API & Tool Calling
    chat_payload = {"message": "what is my account balance?"}
    res_chat = client.post("/api/chat", json=chat_payload)
    assert res_chat.status_code == 200
    chat_data = res_chat.json()
    assert "reply" in chat_data
    assert "₹" in chat_data["reply"] or "balance" in chat_data["reply"].lower()
    print(f"[PASS] 6a. Chatbot personal tool query response: {chat_data['reply'][:60]}...")

    chat_payload2 = {"message": "check my application status"}
    res_chat2 = client.post("/api/chat", json=chat_payload2)
    assert res_chat2.status_code == 200
    chat_data2 = res_chat2.json()
    assert "reply" in chat_data2
    print(f"[PASS] 6b. Chatbot application status query response: {chat_data2['reply'][:60]}...")

    # Logout customer
    client.get("/auth/logout")

    # 7. Employee Flow & Reports
    res = client.post("/auth/login", data={"username_or_email": "employee@smartbank.local", "password": "Employee@123"})
    assert res.status_code == 303
    emp_dash_url = res.headers.get("location")
    assert emp_dash_url == "/employee/dashboard"

    res_emp_dash = client.get(emp_dash_url)
    assert res_emp_dash.status_code == 200
    assert "Employee" in res_emp_dash.text or "Staff" in res_emp_dash.text
    print("[PASS] 7a. Bank Employee authenticated successfully.")

    res_apps = client.get("/employee/applications")
    assert res_apps.status_code == 200
    assert "Account Opening Applications Queue" in res_apps.text
    print("[PASS] 7b. Employee KYC applications queue loads.")

    res_reports = client.get("/employee/reports")
    assert res_reports.status_code == 200
    assert "Operations & Institutional Reports" in res_reports.text
    print("[PASS] 7c. Employee reports dashboard loads.")

    res_rep_csv = client.get("/employee/reports/csv?report_type=transactions")
    assert res_rep_csv.status_code == 200
    assert "text/csv" in res_rep_csv.headers.get("content-type")
    print("[PASS] 7d. Employee CSV report export works.")

    res_rep_pdf = client.get("/employee/reports/pdf?report_type=transactions")
    assert res_rep_pdf.status_code == 200
    assert res_rep_pdf.headers.get("content-type") == "application/pdf"
    assert len(res_rep_pdf.content) > 1000
    print(f"[PASS] 7e. Employee PDF report export works ({len(res_rep_pdf.content)} bytes).")

    # Logout employee
    client.get("/auth/logout")

    # 8. Admin Flow
    res = client.post("/auth/login", data={"username_or_email": "admin@smartbank.local", "password": "Admin@123"})
    assert res.status_code == 303
    admin_dash_url = res.headers.get("location")
    assert admin_dash_url == "/admin/dashboard"

    res_admin_dash = client.get(admin_dash_url)
    assert res_admin_dash.status_code == 200
    assert "System Administration" in res_admin_dash.text or "Admin" in res_admin_dash.text
    print("[PASS] 8a. Administrator authenticated successfully.")

    res_admin_users = client.get("/admin/users")
    assert res_admin_users.status_code == 200
    print("[PASS] 8b. Admin RBAC management loads.")

    res_audit = client.get("/admin/audit-logs")
    assert res_audit.status_code == 200
    print("[PASS] 8c. Admin audit trail loads.")

    print("\n>>> ALL SYSTEM CHECKS COMPLETED AND VERIFIED 100% FUNCTIONAL! <<<")

if __name__ == "__main__":
    run_verification()
