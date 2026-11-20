from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.rate_limit import limiter
from app.database import get_db
from app.services.conversation_service import (
    create_conversation,
    get_conversation,
    get_conversation_history,
    get_conversations,
)
from app.services.llm_service import ask_gemini

router = APIRouter()


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: int | None = None


class ChatResponse(BaseModel):
    answer: str
    conversation_id: int


class ConversationSummary(BaseModel):
    id: int
    title: str
    created_at: datetime


class MessageResponse(BaseModel):
    role: str
    content: str


class ConversationDetail(BaseModel):
    id: int
    title: str
    created_at: datetime
    messages: list[MessageResponse]


@router.post("/", response_model=ChatResponse)
@limiter.limit("20/minute")
def chat(
    body: ChatRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    conversation = (
        get_conversation(db, user["id"], body.conversation_id)
        if body.conversation_id is not None
        else create_conversation(db, user["id"])
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    answer = ask_gemini(db, user["id"], conversation.id, body.message)

    return ChatResponse(answer=answer, conversation_id=conversation.id)


@router.get("/conversations", response_model=list[ConversationSummary])
@limiter.limit("120/minute")
def list_conversations(
    request: Request,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    conversations = get_conversations(db, user["id"])

    return conversations


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationDetail,
)
@limiter.limit("120/minute")
def retrieve_conversation(
    request: Request,
    conversation_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    conversation = get_conversation(db, user["id"], conversation_id)

    if conversation is None:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found",
        )

    messages = get_conversation_history(
        db=db,
        user_id=user["id"],
        conversation_id=conversation_id,
    )

    return {
        "id": conversation.id,
        "title": conversation.title,
        "created_at": conversation.created_at,
        "messages": messages,
    }
