from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, List
from app.database import get_db
from app.models.models import User
from app.schemas.schemas import ChatRequest, ChatResponse
from app.utils.dependencies import get_current_user_optional
from app.services.chatbot_service import process_chat_message, get_conversation_history

router = APIRouter(prefix="/api/chat", tags=["SmartBank AI Chatbot"])

@router.post("", response_model=ChatResponse)
async def chat_endpoint(
    req: ChatRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Process incoming chat query through the SmartBank Hybrid AI pipeline.
    Derives user credentials exclusively from the authenticated session.
    """
    current_user = get_current_user_optional(request, db)
    
    result = await process_chat_message(
        db=db,
        user_message=req.message,
        user=current_user,
        conversation_id=req.conversation_id
    )

    return ChatResponse(
        reply=result["reply"],
        conversation_id=result["conversation_id"],
        mode=result["mode"],
        suggestions=result.get("suggestions", []),
        timestamp=result.get("timestamp", "")
    )

@router.get("/history/{conversation_id}")
def get_chat_history(
    conversation_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Retrieve message history for the active conversation."""
    current_user = get_current_user_optional(request, db)
    history = get_conversation_history(db, conversation_id, current_user)
    return {"conversation_id": conversation_id, "messages": history}
