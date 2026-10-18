import re
import uuid
import datetime
import httpx
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session
from app.config import settings
from app.models.models import ChatConversation, ChatMessage, User
from app.services.faq_service import find_best_faq_match
from app.services.chat_tools import (
    get_my_account_summary,
    get_my_recent_transactions,
    get_my_transactions_by_date,
    get_my_loan_status,
    get_my_loan_repayments,
    get_my_statement_page_link,
    get_my_application_status
)

# --- AI Provider Interface ---

class AIProviderAdapter:
    """Pluggable adapter for external generative AI providers (e.g., Google Gemini)."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-2.5-flash"):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model = model or settings.GEMINI_MODEL
        self.timeout_seconds = 8.0

    def is_available(self) -> bool:
        return bool(self.api_key and settings.AI_ENABLED and settings.AI_PROVIDER != "disabled")

    async def generate_response(self, prompt: str, context: str) -> Optional[str]:
        """Call Gemini API via REST endpoint with timeout and exception handling."""
        if not self.is_available():
            return None

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        
        system_instruction = (
            "You are the SmartBank AI Banking Assistant. Your tone is professional, polite, and helpful. "
            "STRICT RULES:\n"
            "1. ONLY answer using the provided GROUNDING CONTEXT. Do not invent any numbers, balances, account details, or banking policies.\n"
            "2. Never ask for or mention passwords, PINs, OTPs, or CVVs.\n"
            "3. If the context does not contain the answer, politely state you do not have that information and suggest contacting bank support.\n"
            "4. Keep responses concise (under 3 sentences) unless listing specific transaction/account records provided in context.\n"
        )
        
        full_user_content = f"GROUNDING CONTEXT:\n{context}\n\nUSER QUESTION:\n{prompt}"

        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": full_user_content}]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 300
            }
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates and "content" in candidates[0]:
                        parts = candidates[0]["content"].get("parts", [])
                        if parts and "text" in parts[0]:
                            return parts[0]["text"].strip()
                return None
        except Exception:
            # Safe failure fallback without breaking the application
            return None

ai_adapter = AIProviderAdapter()

# --- Intent Classification Patterns ---

BALANCE_PATTERNS = [
    r"\b(balance|how much money|account summary|check balance|my funds|my money)\b"
]
TRANSACTION_PATTERNS = [
    r"\b(recent transactions|transaction history|last transaction|my transactions|recent activity|past payments)\b"
]
LOAN_PATTERNS = [
    r"\b(loan status|my loan|approved loan|check loan|loan progress|loan application status)\b"
]
REPAYMENT_PATTERNS = [
    r"\b(loan repayment|repayments|paid installments|installment record)\b"
]
STATEMENT_PATTERNS = [
    r"\b(download statement|get statement|account statement|pdf statement|statement page)\b"
]
APPLICATION_STATUS_PATTERNS = [
    r"\b(application status|my application|account application|track application|account verification status|kyc status)\b"
]
TRANSFER_NAV_PATTERNS = [
    r"\b(where to transfer|transfer money page|how to send money|how to transfer)\b"
]
GREETING_PATTERNS = [
    r"^(hi|hello|hey|good morning|good afternoon|good evening|greetings)\b"
]

def classify_intent(message: str) -> str:
    """Classify the incoming user query into intent categories."""
    clean = message.lower().strip()

    for pattern in GREETING_PATTERNS:
        if re.search(pattern, clean):
            return "GREETING"

    for pattern in BALANCE_PATTERNS:
        if re.search(pattern, clean):
            return "PERSONAL_BALANCE"

    for pattern in TRANSACTION_PATTERNS:
        if re.search(pattern, clean):
            return "PERSONAL_TRANSACTIONS"

    for pattern in APPLICATION_STATUS_PATTERNS:
        if re.search(pattern, clean):
            return "PERSONAL_APPLICATION_STATUS"

    for pattern in LOAN_PATTERNS:
        if re.search(pattern, clean):
            return "PERSONAL_LOAN_STATUS"

    for pattern in REPAYMENT_PATTERNS:
        if re.search(pattern, clean):
            return "PERSONAL_LOAN_REPAYMENTS"

    for pattern in STATEMENT_PATTERNS:
        if re.search(pattern, clean):
            return "PERSONAL_STATEMENT"

    for pattern in TRANSFER_NAV_PATTERNS:
        if re.search(pattern, clean):
            return "TRANSFER_NAVIGATION"

    return "GENERAL_FAQ"

# --- Hybrid Pipeline Execution ---

async def process_chat_message(
    db: Session,
    user_message: str,
    user: Optional[User],
    conversation_id: Optional[str] = None
) -> Dict[str, Any]:
    """Execute the full hybrid FAQ + Tool + AI customer support pipeline."""
    # 1. Validation
    clean_msg = user_message.strip()
    if not clean_msg or len(clean_msg) > 1000:
        return {
            "reply": "Please enter a valid message between 1 and 1000 characters.",
            "conversation_id": conversation_id or str(uuid.uuid4()),
            "mode": "FALLBACK",
            "suggestions": ["Check My Balance", "How to Transfer", "Apply for Loan"],
            "timestamp": datetime.datetime.utcnow().strftime("%H:%M")
        }

    # 2. Manage Conversation Session
    if not conversation_id:
        conversation_id = str(uuid.uuid4())
        conv = ChatConversation(
            id=conversation_id,
            user_id=user.id if user else None,
            status="ACTIVE"
        )
        db.add(conv)
        db.commit()
    else:
        conv = db.query(ChatConversation).filter(ChatConversation.id == conversation_id).first()
        if not conv:
            conv = ChatConversation(
                id=conversation_id,
                user_id=user.id if user else None,
                status="ACTIVE"
            )
            db.add(conv)
            db.commit()
        elif user and conv.user_id and conv.user_id != user.id:
            # Prevent accessing another user's conversation ID
            conversation_id = str(uuid.uuid4())
            conv = ChatConversation(
                id=conversation_id,
                user_id=user.id,
                status="ACTIVE"
            )
            db.add(conv)
            db.commit()

    # Record User Message
    user_msg_record = ChatMessage(
        conversation_id=conversation_id,
        sender_type="USER",
        message_text=clean_msg
    )
    db.add(user_msg_record)
    db.commit()

    # 3. Intent Classification
    intent = classify_intent(clean_msg)
    response_mode = "FAQ"
    reply_text = ""
    suggestions = []

    # 4. Handle Greeting
    if intent == "GREETING":
        user_name_prefix = f" {user.username.capitalize()}" if user else ""
        reply_text = (
            f"Hello{user_name_prefix}! I'm the SmartBank Assistant. "
            "I can answer banking FAQs, guide you around SmartBank, and retrieve your account, transaction, or loan status. "
            "Never share your password, PIN, or OTP in chat. How may I help you today?"
        )
        suggestions = ["Check My Balance", "Recent Transactions", "Check Loan Status", "How to Transfer Money"] if user else ["How to open an account", "Supported account types", "Contact support"]
        response_mode = "FAQ"

    # 5. Handle Personal Data Queries (Strict Server-Side Auth Check)
    elif intent in ["PERSONAL_BALANCE", "PERSONAL_TRANSACTIONS", "PERSONAL_APPLICATION_STATUS", "PERSONAL_LOAN_STATUS", "PERSONAL_LOAN_REPAYMENTS", "PERSONAL_STATEMENT"]:
        if not user or user.role != "customer":
            reply_text = "To view your personalized account balance, transactions, application status, or loans, please sign in to your SmartBank customer account first."
            suggestions = ["How do I open an account?", "How do deposits work?", "Contact support"]
            response_mode = "FALLBACK"
        else:
            # User is authenticated customer - call secure backend tool
            tool_context = ""
            if intent == "PERSONAL_BALANCE":
                tool_res = get_my_account_summary(user.id, db)
                if not tool_res["success"]:
                    reply_text = "I cannot retrieve your account summary at this moment. Please check your dashboard."
                    response_mode = "FALLBACK"
                elif tool_res.get("accounts_count", 0) == 0:
                    reply_text = "You do not have any active bank accounts registered yet. You can apply for a new account from your dashboard."
                    response_mode = "TOOL_ASSISTED"
                else:
                    lines = [f"**Account Summary for {tool_res['customer_name']}:**", f"• Total Portfolio Balance: **{tool_res['total_balance']}**\n"]
                    for acc in tool_res["accounts"]:
                        lines.append(f"• **{acc['account_number']}** ({acc['account_type']}): **{acc['balance']}** [{acc['status']}]")
                    reply_text = "\n".join(lines)
                    tool_context = reply_text
                    response_mode = "TOOL_ASSISTED"
                suggestions = ["Recent Transactions", "Track Application", "Check Loan Status", "Download Statement"]

            elif intent == "PERSONAL_APPLICATION_STATUS":
                tool_res = get_my_application_status(user.id, db)
                if not tool_res["success"]:
                    reply_text = "I cannot retrieve your application status at this moment."
                    response_mode = "FALLBACK"
                elif not tool_res["has_applications"]:
                    reply_text = "You do not have any submitted account applications. You can submit a new account opening application with verification anytime from the portal."
                    response_mode = "TOOL_ASSISTED"
                else:
                    lines = ["**Your Account Applications:**"]
                    for a in tool_res["applications"]:
                        lines.append(
                            f"• Ref **{a['reference']}** ({a['account_type']}): Status **{a['status']}** | Verification: {a['video_verification']}\n  Notes: {a['notes']}"
                        )
                    reply_text = "\n".join(lines)
                    tool_context = reply_text
                    response_mode = "TOOL_ASSISTED"
                suggestions = ["Check My Balance", "Recent Transactions", "Download Statement"]

            elif intent == "PERSONAL_TRANSACTIONS":
                tool_res = get_my_recent_transactions(user.id, limit=5, db=db)
                if not tool_res["success"]:
                    reply_text = "I cannot retrieve your transaction history at this moment."
                    response_mode = "FALLBACK"
                elif tool_res["count"] == 0:
                    reply_text = "No recent transactions found on your accounts."
                    response_mode = "TOOL_ASSISTED"
                else:
                    lines = [f"**Your Last {tool_res['count']} Transactions:**"]
                    for t in tool_res["transactions"]:
                        lines.append(f"• {t['date']} | **{t['type']}**: {t['amount']} ({t['description']}) [{t['status']}]")
                    reply_text = "\n".join(lines)
                    tool_context = reply_text
                    response_mode = "TOOL_ASSISTED"
                suggestions = ["Check My Balance", "Track Application", "Check Loan Status", "Download Statement"]

            elif intent == "PERSONAL_LOAN_STATUS":
                tool_res = get_my_loan_status(user.id, db)
                if not tool_res["success"]:
                    reply_text = "I cannot retrieve your loan status right now."
                    response_mode = "FALLBACK"
                elif not tool_res["has_loans"]:
                    reply_text = "You currently have no loan applications on file. You can apply anytime from the Loans menu."
                    response_mode = "TOOL_ASSISTED"
                else:
                    lines = ["**Your Loan Status:**"]
                    for l in tool_res["loans"]:
                        lines.append(
                            f"• **{l['loan_reference']}** ({l['category']}): Status **{l['status']}** | "
                            f"Approved: {l['approved_amount']} | Outstanding: {l['outstanding_balance']}"
                        )
                    reply_text = "\n".join(lines)
                    tool_context = reply_text
                    response_mode = "TOOL_ASSISTED"
                suggestions = ["Apply for Loan", "Check My Balance", "Loan FAQs"]

            elif intent == "PERSONAL_LOAN_REPAYMENTS":
                tool_res = get_my_loan_repayments(user.id, db)
                if not tool_res["success"]:
                    reply_text = "I cannot retrieve your repayment history right now."
                    response_mode = "FALLBACK"
                elif tool_res["count"] == 0:
                    reply_text = "No loan repayment records found for your account."
                    response_mode = "TOOL_ASSISTED"
                else:
                    lines = ["**Recent Loan Repayments:**"]
                    for r in tool_res["repayments"]:
                        lines.append(f"• {r['date']} | Loan {r['loan_reference']}: {r['amount']} ({r['payment_method']})")
                    reply_text = "\n".join(lines)
                    tool_context = reply_text
                    response_mode = "TOOL_ASSISTED"
                suggestions = ["Check Loan Status", "Check My Balance"]

            elif intent == "PERSONAL_STATEMENT":
                tool_res = get_my_statement_page_link(user.id, db)
                reply_text = (
                    "You can generate and download your official bank statements in PDF or CSV format directly from the Reports page.\n"
                    "👉 [Go to Account Statements](/reports/statement)"
                )
                tool_context = reply_text
                response_mode = "TOOL_ASSISTED"
                suggestions = ["Check My Balance", "Recent Transactions"]

            # If AI is active, refine the grounded tool response
            if tool_context and ai_adapter.is_available():
                ai_text = await ai_adapter.generate_response(clean_msg, tool_context)
                if ai_text:
                    reply_text = ai_text
                    response_mode = "AI"

    # 6. Navigation / FAQ
    elif intent == "TRANSFER_NAVIGATION":
        reply_text = (
            "To transfer funds to another SmartBank customer:\n"
            "1. Navigate to **Transactions** -> **Transfer Funds**.\n"
            "2. Select your source account and enter the destination account number.\n"
            "3. Enter the amount and confirm.\n\n"
            "👉 [Click here to open the Transfer page](/customer/transfer)"
        )
        suggestions = ["Check My Balance", "Recent Transactions", "How do deposits work?"]
        response_mode = "FAQ"

    # 7. General Banking FAQ Lookup
    else:
        faq_match, score = find_best_faq_match(db, clean_msg)
        if faq_match and score >= settings.CHATBOT_CONFIDENCE_THRESHOLD:
            context = f"Official FAQ: {faq_match.question}\nAnswer: {faq_match.answer}"
            if ai_adapter.is_available():
                ai_text = await ai_adapter.generate_response(clean_msg, context)
                if ai_text:
                    reply_text = ai_text
                    response_mode = "AI"
                else:
                    reply_text = faq_match.answer
                    response_mode = "FAQ"
            else:
                reply_text = faq_match.answer
                response_mode = "FAQ"

            suggestions = ["How to Transfer Money", "Supported account types", "Check Loan Status"]
        else:
            # Safe Fallback
            reply_text = (
                "I apologize, but I could not find a confirmed answer to your question in the SmartBank knowledge base. "
                "For your safety, I cannot make assumptions about banking rules or account information. "
                "You can browse our FAQs, check your dashboard, or contact our support team at support@smartbank.local."
            )
            response_mode = "FALLBACK"
            suggestions = ["How do I open an account?", "How do deposits work?", "Supported account types", "Contact support"]

    # Record Assistant Message
    asst_msg_record = ChatMessage(
        conversation_id=conversation_id,
        sender_type="ASSISTANT",
        message_text=reply_text,
        intent_category=intent,
        response_mode=response_mode
    )
    db.add(asst_msg_record)
    db.commit()

    return {
        "reply": reply_text,
        "conversation_id": conversation_id,
        "mode": response_mode,
        "suggestions": suggestions,
        "timestamp": datetime.datetime.utcnow().strftime("%H:%M")
    }

def get_conversation_history(db: Session, conversation_id: str, user: Optional[User]) -> List[Dict[str, Any]]:
    """Retrieve verified message history for a conversation session."""
    conv = db.query(ChatConversation).filter(ChatConversation.id == conversation_id).first()
    if not conv:
        return []

    # Ownership check
    if conv.user_id and (not user or conv.user_id != user.id):
        return []

    return [
        {
            "id": m.id,
            "sender": m.sender_type,
            "text": m.message_text,
            "mode": m.response_mode,
            "time": m.created_at.strftime("%H:%M")
        }
        for m in conv.messages
    ]
