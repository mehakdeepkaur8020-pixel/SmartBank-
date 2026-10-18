# SmartBank — Indian Digital Bank Management System with Hybrid AI Chatbot

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![Currency](https://img.shields.io/badge/Currency-INR%20(%E2%82%B9)-success.svg)]()
[![Security](https://img.shields.io/badge/Password%20Hashing-Argon2id-critical.svg)](https://github.com/hynek/argon2-cffi)
[![UI Theme](https://img.shields.io/badge/Theme-Midnight%20Navy%20%26%20Emerald-informational.svg)]()

SmartBank is a full-stack Indian core digital banking web platform built with FastAPI, SQLite, SQLAlchemy, Bootstrap 5, and Chart.js. The platform features role-based access control (Customer, Bank Employee, and Admin), Indian Rupee (₹) fixed-precision monetary calculations, paperless Video KYC account opening, official ReportLab PDF statements with account masking, institutional staff reports, and a floating **Hybrid AI Customer Support Chatbot**.

---

## 🌟 Key Modules & Capabilities

1. **Indian Currency (INR) & Financial Standards:**
   - Standard Indian numbering system formatting throughout (e.g. `₹1,25,000.00`, `₹12,50,000.00`).
   - Integer paise representation (`BigInteger`) eliminating floating-point rounding errors.
   - Realistic Indian banking conventions: IFSC (`SBIN0001842`), PAN, Aadhaar, NEFT, IMPS, and RTGS clearing mechanisms.

2. **Paperless Account Opening & Video KYC Workflow:**
   - Digital application process starting in `PENDING_REVIEW` status.
   - Government ID & Address Proof document upload (`uploads/documents/`).
   - HTML5 digital signature pad (`uploads/signatures/`).
   - Live camera facial video verification session preview.
   - Real-time customer tracking portal (`/customer/application-status`).
   - Employee review and one-click account generation & activation (`/employee/applications`).

3. **Role-Based Portals:**
   - **Customer Portal:** Multi-account portfolio, cash deposits, withdrawals, instant NEFT/IMPS transfers, loan applications, loan repayments, official statements, and floating AI assistant.
   - **Employee Operations:** Customer directory, operational account controls (`ACTIVE`, `FROZEN`, `INACTIVE`, `CLOSED`), KYC applications queue, loan underwriting approval/rejection, high-value transaction monitoring flag reviews (> ₹5,00,000 threshold), and traceable compensating transaction reversals.
   - **Employee Reports Dashboard (`/employee/reports`):** Interactive institutional analytics, summary metrics, and one-click PDF & CSV exports for Transactions, Accounts, Loans, and KYC Applications.
   - **Administrator Oversight:** System metrics, RBAC user elevation/deactivation, tamper-evident audit trail, and chatbot FAQ knowledge base editor.

4. **Hybrid AI Customer Support Chatbot:**
   - **Instant Quick-Reply Navigation:** Interactive quick-reply pills that execute queries immediately upon clicking.
   - **TF-IDF & Cosine Similarity FAQ Engine:** Matches customer questions against official Indian banking policies without requiring external network access.
   - **Secure Personal-Data Tools:** Authenticated queries (`"what is my balance?"`, `"check my application status"`, `"loan status"`, etc.) derive permissions strictly from the authenticated session.
   - **Google Gemini Generative AI:** Optional natural language formulation when `GEMINI_API_KEY` is provided in `.env`, with automatic fallback to local FAQ Assistant mode.

5. **Modern Midnight Navy & Emerald Design:**
   - Premium digital banking visual system with deep midnight navy surfaces (`#081226`), rich emerald accents (`#10b981`), subtle card elevations, and responsive navigation.
   - Commercial landing page showcasing 10 core banking services with zero demo credentials leaked on the user interface.

---

## 🚀 Quick Start Guide (Windows)

### Prerequisites
* Python 3.10 or higher installed.
* Windows PowerShell or Command Prompt.

### 1. Setup Virtual Environment & Install Dependencies
Open your terminal in the project directory:
```powershell
cd c:\Users\meahk\Downloads\bankManagementSystem
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
```

### 2. Initialize Database & Demo Records
Seed realistic Indian accounts, transactions, KYC applications, and banking FAQs:
```powershell
.\.venv\Scripts\python scripts\seed_demo_data.py
```

### 3. Launch Application
Double-click `run.bat` or run via terminal:
```powershell
.\run.bat
# or
.\.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Open your browser to: **[http://127.0.0.1:8000](http://127.0.0.1:8000)**

---

## 🔑 Demo Login Credentials

The database is seeded with realistic Indian banking records for immediate testing:

| Role | Username / Email | Password | Seeded Data & Access |
| :--- | :--- | :--- | :--- |
| **Admin** | `admin@smartbank.local` | `Admin@123` | System metrics, User RBAC controls, Tamper-evident Audit Trail, FAQ database editor |
| **Employee** | `employee@smartbank.local` | `Employee@123` | KYC Applications Queue, Institutional Reports (PDF/CSV), Loan reviews, Flagged RTGS reviews, Transaction reversals |
| **Customer 1** | `priya@example.com` | `Priya@123` | Priya Patel: Savings (`SBIN40129841`, ₹2,85,000.00), Current (`SBIN40129842`, ₹12,50,000.00), Approved Education Loan (₹8,00,000.00) |
| **Customer 2** | `aarav@example.com` | `Aarav@123` | Aarav Sharma: Savings (`SBIN50831920`, ₹45,000.00), Pending Home Loan (₹35,00,000.00), Pending KYC Account Opening Application |

---

## 📱 Mobile Network Access (Local Wi-Fi)

To test the application on smartphones or tablets connected to the same Wi-Fi network:

1. Check your computer's local IP address using `ipconfig` (e.g., `192.168.1.50`).
2. Start the server bound to `0.0.0.0`:
   ```powershell
   .\.venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```
3. Open `http://<YOUR_LOCAL_IP>:8000` (e.g., `http://192.168.1.50:8000`) on your mobile browser.

---

## 🤖 Chatbot AI Provider Configuration

SmartBank operates in two distinct operational modes:

### Mode A: FAQ Assistant Mode (Default, Zero-Cost)
When no external API key is configured, SmartBank runs automatically in **FAQ Assistant** mode:
* Fast TF-IDF cosine similarity matching retrieves answers from the local Indian banking knowledge base.
* Authenticated customers can retrieve live account balances, recent transactions, loan updates, and KYC application statuses.
* 100% offline-compatible with zero network requests or API costs.

### Mode B: Google Gemini AI Mode (Optional)
To enable natural language answer synthesis:
1. Obtain an API key from Google AI Studio.
2. Configure `.env`:
   ```env
   AI_ENABLED=True
   AI_PROVIDER=gemini
   GEMINI_API_KEY=your_gemini_api_key_here
   GEMINI_MODEL=gemini-2.5-flash
   ```
3. Restart the server. The floating chat widget will display **AI Mode**.

---

## 🎓 Evaluator Walkthrough & Feature Tour

Follow this flow when presenting the project:

### 1. Commercial Landing Page & Authentication
1. Navigate to `http://127.0.0.1:8000`.
2. Inspect the modern midnight navy hero banner and the **10 real banking service cards** (Zero demo credentials displayed on the public UI).
3. Click **Customer Sign In** to open `/auth/login`. Demonstrate the tabbed role switcher (`Customer`, `Bank Employee`, `Administrator`).

### 2. Customer Experience & Indian Rupee (INR) Management
1. Log in as Customer **Priya Patel** (`priya@example.com` / `Priya@123`).
2. View her accounts in Indian Rupee format:
   - Savings (`SBIN40129841`): `₹2,85,000.00`
   - Current (`SBIN40129842`): `₹12,50,000.00`
3. Click **Transfer Money** to perform an instant transfer to Aarav's account (`SBIN50831920`).
4. Navigate to **Statement** -> click **Download PDF Statement**. Inspect the generated ReportLab PDF with masked account numbers (`SBIN••••9841`) and official bank styling.

### 3. Account Opening & Paperless Video KYC
1. From the customer navigation, click **Open Account / KYC** (`/customer/apply-account`).
2. Demonstrate the 4-step workflow:
   - Account Selection (Savings / Current) & Employment details.
   - Government ID document file upload.
   - Digital signature pad drawn using HTML5 Canvas.
   - Live camera facial verification preview button.
3. Submit or view real-time tracking at `/customer/application-status`.

### 4. Floating Hybrid AI Chatbot
1. Click the floating robot button in the bottom right corner.
2. Click the quick-reply pill **Check Balance** — verify that it executes immediately on click without needing text input.
3. Click **Application Status** — show personalized KYC tracking response.
4. Ask a general query: *"What are the NEFT charges?"* or *"What is the minimum balance?"*. Show verified answers retrieved from the FAQ engine.

### 5. Employee Operations & Institutional Reports
1. Sign in as Bank Employee (`employee@smartbank.local` / `Employee@123`).
2. Go to **KYC Verification Queue** (`/employee/applications`):
   - Review pending application `APP-20261011-9481` submitted by Aarav Sharma.
   - Inspect uploaded documents and digital signature.
   - Click **Approve Application** — show atomic Indian account number generation (`SBIN...`) and instant customer activation.
3. Go to **Reports & Analytics** (`/employee/reports`):
   - Switch between **Transactions**, **Accounts Register**, **Loan Portfolio**, and **KYC Applications**.
   - Download the official institutional PDF report and CSV spreadsheet.
4. Go to **Monitoring Review** to inspect the high-value RTGS deposit flag (> ₹5,00,000 threshold).
5. Go to **Transactions** and demonstrate a traceable compensating reversal.

### 6. Administration & Governance
1. Sign in as Administrator (`admin@smartbank.local` / `Admin@123`).
2. View transaction breakdown donut chart and system oversight metrics.
3. Access **User & Role Management (RBAC)** to activate/deactivate accounts or change roles.
4. Access **Security Audit Trail** (`/admin/audit-logs`) to view tamper-evident records of all logins, fund transfers, document downloads, and staff reviews.

---

## 📁 Project Directory Structure

```
bankManagementSystem/
├── app/
│   ├── models/             # SQLAlchemy ORM models (User, Customer, Account, Txn, Loan, KYC, FAQ)
│   ├── schemas/            # Pydantic schemas for validation and API serialization
│   ├── routers/            # FastAPI route handlers (auth, customer, employee, admin, reports, chat)
│   ├── services/           # Business logic (accounts, transactions, loans, PDF/CSV reports, AI chatbot)
│   ├── templates/          # Jinja2 templates styled with midnight navy & emerald theme
│   ├── static/             # Custom CSS styling and responsive chatbot JavaScript
│   ├── utils/              # Security (Argon2id, session HMAC), Indian currency math, dependencies
│   ├── config.py           # Configuration, upload directories, and environment loading
│   ├── database.py         # SQLAlchemy engine and database session provider
│   └── main.py             # FastAPI application entrypoint and route mounting
├── scripts/                # Database initialization and demo seeding scripts
├── uploads/                # Secured storage for KYC documents and digital signatures
│   ├── documents/          # Uploaded Aadhaar/PAN identity proofs
│   └── signatures/         # Base64 digital signatures exported as PNG images
├── run.bat                 # Windows one-click startup batch script
├── run.ps1                 # PowerShell startup script
├── requirements.txt        # Python dependency manifest
└── README.md               # Complete platform documentation and evaluator guide
```

---

## ⚖️ Academic Disclaimer
SmartBank was developed for academic demonstration purposes. All bank account numbers, identities, and financial transactions are fictional.
