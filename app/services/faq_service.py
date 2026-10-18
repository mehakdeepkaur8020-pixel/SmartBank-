import math
import re
from typing import List, Tuple, Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models.models import FAQ

DEFAULT_FAQS = [
    {
        "category": "Accounts",
        "question": "How do I open an account with SmartBank?",
        "keywords": "open account register create new sign up savings current kyc verification video kyc documents",
        "answer": "To open a new account with SmartBank, you must complete our paperless Video KYC & Document Upload process. Upload your government-issued photo ID (Aadhaar or PAN card), draw your digital signature, and complete the live camera verification check. You can begin right now here: [Open Account with Video KYC](/customer/apply-account). Once reviewed by branch staff, your official account is generated and activated."
    },
    {
        "category": "Accounts",
        "question": "How do I track my account opening application status?",
        "keywords": "application status track kyc verification pending approved review",
        "answer": "You can check the real-time progress of your application on the 'Application Status' page under Accounts, or ask this chatbot 'What is my application status?'. Once approved by bank staff, your account is activated and ready for transactions immediately."
    },
    {
        "category": "Accounts",
        "question": "What types of accounts are supported?",
        "keywords": "supported account types savings current options difference",
        "answer": "SmartBank currently supports two types of accounts: 1) Savings Account (designed for personal savings and routine retail banking with interest) and 2) Current Account (designed for businesses with higher transaction volume)."
    },
    {
        "category": "Accounts",
        "question": "What currency does SmartBank use?",
        "keywords": "currency inr rupees rupee symbol format indian numbering",
        "answer": "SmartBank operates entirely in Indian Rupees (₹ - INR) adhering to the standard Indian numbering system (e.g., ₹1,25,000.00)."
    },
    {
        "category": "Accounts",
        "question": "What do the different account statuses mean?",
        "keywords": "account status active inactive frozen closed meaning",
        "answer": "SmartBank accounts have four operational statuses: ACTIVE (full deposit and withdrawal capabilities), INACTIVE (dormant due to inactivity), FROZEN (temporarily locked by bank security/staff; debits restricted), and CLOSED (permanently terminated)."
    },
    {
        "category": "Transactions",
        "question": "How do deposits work in SmartBank?",
        "keywords": "how deposit cash money credit add funds inr rupees",
        "answer": "You can make deposits through the 'Deposit' page under the Transactions menu. Select your target account, specify the amount in INR (₹), and confirm. Funds are credited instantly to your available balance."
    },
    {
        "category": "Transactions",
        "question": "How do withdrawals work?",
        "keywords": "how withdraw cash money debit take out ATM rupees inr",
        "answer": "To withdraw funds, navigate to the 'Withdraw' page under Transactions. Choose your active account and enter the amount in INR (₹). The system verifies that you have sufficient funds before debiting your balance."
    },
    {
        "category": "Transactions",
        "question": "How do I transfer money to another account?",
        "keywords": "how transfer send money pay friend another account neft imps",
        "answer": "To transfer funds, visit the 'Transfer' page. Enter your source account, the recipient's SmartBank account number (e.g., SBIN40129841), and the amount in INR (₹). Transfers are executed atomically and credited to the recipient immediately."
    },
    {
        "category": "Transactions",
        "question": "How can I view my transaction history?",
        "keywords": "transaction history past transactions view records see statement list",
        "answer": "You can view your complete transaction history by visiting the 'Transactions' page from your dashboard or sidebar. You can filter by date range, transaction type (Deposit, Withdrawal, Transfer), and export to CSV."
    },
    {
        "category": "Statements",
        "question": "How do I download an official account statement?",
        "keywords": "download statement pdf export account statement print report inr",
        "answer": "To download an official statement, go to 'Reports' -> 'Account Statement'. Select your account, choose your date range, and click 'Download PDF' for a print-ready document formatted in Indian Rupees (₹) with masked account numbers, or 'Export CSV' for spreadsheet analysis."
    },
    {
        "category": "Loans",
        "question": "How do I apply for a loan?",
        "keywords": "apply loan loan application education home personal vehicle borrow money inr",
        "answer": "To apply for a loan, navigate to the 'Loans' menu and click 'Apply for Loan'. Select the loan category (Education, Personal, Home, or Vehicle), enter your requested amount in INR (₹), desired term (months), and monthly income. Bank staff will review your application."
    },
    {
        "category": "Loans",
        "question": "How do I check the status of my loan application?",
        "keywords": "check loan status pending approved rejected loan progress tracking",
        "answer": "You can check your loan status on the 'Loans' overview page or right here in the chatbot by asking 'What is my loan status?'. Statuses include PENDING (under review), APPROVED, REJECTED, and CLOSED (fully repaid)."
    },
    {
        "category": "Loans",
        "question": "How are loan repayments recorded?",
        "keywords": "repay loan loan repayment pay installment outstanding balance debit inr",
        "answer": "Once a loan is approved, you can make repayments on the 'Loan Details' page by clicking 'Make Repayment'. You select one of your active SmartBank accounts to debit, and the amount in INR (₹) is immediately subtracted from your outstanding loan balance."
    },
    {
        "category": "Security",
        "question": "What should I do if I forgot my password or have login troubleshooting issues?",
        "keywords": "forgot password login trouble reset password cannot sign in lockout",
        "answer": "If you are having trouble logging in, ensure your caps-lock is off and your username/email is entered correctly. If you are already logged in, you can update your password under 'Profile' -> 'Change Password'. For account lockouts, contact a bank employee."
    },
    {
        "category": "Security",
        "question": "Is SmartBank safe and how is my personal information protected?",
        "keywords": "security safety protection encryption passwords secure privacy rbi kyc",
        "answer": "SmartBank employs Argon2id password hashing, secure session management, strict role-based access control, atomic transaction safeguards, and strict KYC verification. Sensitive secrets are never exposed to the frontend or AI chatbot."
    },
    {
        "category": "Support",
        "question": "How do I contact bank customer support or an employee?",
        "keywords": "contact support customer care bank employee help desk phone email branch",
        "answer": "You can contact SmartBank support via email at support@smartbank.co.in or visit our main branch during business hours (Monday to Saturday, 9:30 AM - 4:30 PM). Authorized bank employees can also assist with account updates and KYC reviews."
    },
    {
        "category": "Navigation",
        "question": "Where can I find the transfer money page?",
        "keywords": "where transfer page navigate find transfer menu link",
        "answer": "You can access the transfer page by clicking 'Transactions' in the top navigation or sidebar, and then selecting 'Transfer Funds', or directly visiting /customer/transfer."
    }
]

def seed_default_faqs(db: Session):
    """Seed the FAQ table if it is currently empty."""
    existing_count = db.query(FAQ).count()
    if existing_count == 0:
        for item in DEFAULT_FAQS:
            faq = FAQ(
                category=item["category"],
                question=item["question"],
                keywords=item["keywords"],
                answer=item["answer"],
                is_active=True
            )
            db.add(faq)
        db.commit()

# --- Pure Python TF-IDF Cosine Similarity Engine ---

STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are",
    "aren't", "as", "at", "be", "because", "been", "before", "being", "below", "between", "both",
    "but", "by", "can", "can't", "cannot", "could", "couldn't", "did", "didn't", "do", "does",
    "doesn't", "doing", "don't", "down", "during", "each", "few", "for", "from", "further", "had",
    "hadn't", "has", "hasn't", "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her",
    "here", "here's", "hers", "herself", "him", "himself", "his", "how", "how's", "i", "i'd",
    "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it", "it's", "its", "itself", "let's",
    "me", "more", "most", "mustn't", "my", "myself", "no", "nor", "not", "of", "off", "on", "once",
    "only", "or", "other", "ought", "our", "ours", "ourselves", "out", "over", "own", "same", "shan't",
    "she", "she'd", "she'll", "she's", "should", "shouldn't", "so", "some", "such", "than", "that",
    "that's", "the", "their", "theirs", "them", "themselves", "then", "there", "there's", "these", "they",
    "they'd", "they'll", "they're", "they've", "this", "those", "through", "to", "too", "under", "until",
    "up", "very", "was", "wasn't", "we", "we'd", "we'll", "we're", "we've", "were", "weren't", "what",
    "what's", "when", "when's", "where", "where's", "which", "while", "who", "who's", "whom", "why",
    "why's", "with", "won't", "would", "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your",
    "yours", "yourself", "yourselves", "tell", "please"
}

def tokenize(text: str) -> List[str]:
    """Tokenize and filter stop words."""
    words = re.findall(r'\b[a-zA-Z0-9]+\b', text.lower())
    return [w for w in words if w not in STOPWORDS and len(w) > 1]

class FAQSearchEngine:
    def __init__(self, faqs: List[FAQ]):
        self.faqs = faqs
        self.doc_tokens: List[List[str]] = []
        self.df: Dict[str, int] = {}
        self.n_docs = len(faqs)
        self._build_index()

    def _build_index(self):
        for faq in self.faqs:
            # Combine question and keywords for indexing
            text = f"{faq.question} {faq.keywords}"
            tokens = tokenize(text)
            self.doc_tokens.append(tokens)
            unique_tokens = set(tokens)
            for token in unique_tokens:
                self.df[token] = self.df.get(token, 0) + 1

    def _get_tfidf_vector(self, tokens: List[str]) -> Dict[str, float]:
        tf: Dict[str, int] = {}
        for t in tokens:
            tf[t] = tf.get(t, 0) + 1

        vec: Dict[str, float] = {}
        length_sq = 0.0
        for t, count in tf.items():
            doc_freq = self.df.get(t, 0)
            idf = math.log((self.n_docs + 1) / (doc_freq + 1)) + 1.0
            score = (count / len(tokens)) * idf
            vec[t] = score
            length_sq += score * score

        # Normalize vector
        if length_sq > 0:
            norm = math.sqrt(length_sq)
            for t in vec:
                vec[t] /= norm
        return vec

    def search(self, query: str) -> Tuple[Optional[FAQ], float]:
        """Find the best-matching FAQ using cosine similarity."""
        query_tokens = tokenize(query)
        if not query_tokens or self.n_docs == 0:
            return None, 0.0

        query_vec = self._get_tfidf_vector(query_tokens)
        best_score = 0.0
        best_faq = None

        for idx, faq in enumerate(self.faqs):
            doc_tokens = self.doc_tokens[idx]
            if not doc_tokens:
                continue
            doc_vec = self._get_tfidf_vector(doc_tokens)

            # Cosine similarity (dot product of normalized vectors)
            score = sum(query_vec[t] * doc_vec.get(t, 0.0) for t in query_vec)
            if score > best_score:
                best_score = score
                best_faq = faq

        return best_faq, best_score

def find_best_faq_match(db: Session, query: str) -> Tuple[Optional[FAQ], float]:
    """Retrieve all active FAQs from database and return the top match."""
    faqs = db.query(FAQ).filter(FAQ.is_active == True).all()
    if not faqs:
        seed_default_faqs(db)
        faqs = db.query(FAQ).filter(FAQ.is_active == True).all()
    engine = FAQSearchEngine(faqs)
    return engine.search(query)
