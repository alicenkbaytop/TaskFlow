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
    updated_at: datetime


class MessageResponse(BaseModel):
    role: str
    content: str
    created_at: datetime


class ConversationDetail(BaseModel):
    id: int
    title: str
    created_at: datetime
    messages: list[MessageResponse]


class ConversationRename(BaseModel):
    title: str = Field(min_length=1, max_length=200)


@router.post("/conversations", response_model=ConversationSummary, status_code=201)
@limiter.limit("60/minute")
def start_conversation(
    request: Request,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    return create_conversation(db, user["id"])


@router.post("/", response_model=ChatResponse)
@limiter.limit("20/minute")
def chat(
    body: ChatRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    is_new = body.conversation_id is None
    conversation = (
        get_conversation(db, user["id"], body.conversation_id)
        if body.conversation_id is not None
        else create_conversation(db, user["id"])
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    try:
        answer = ask_gemini(db, user["id"], conversation.id, body.message)
    except Exception as error:
        db.rollback()
        if is_new:
            db.delete(conversation)
            db.commit()
        from app.agent.workflow import AIWorkflowError

        if isinstance(error, AIWorkflowError):
            raise HTTPException(status_code=503, detail=str(error)) from error
        raise
    if conversation.title == "New conversation":
        conversation.title = body.message.strip()[:60] or "New conversation"
        db.commit()

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
        "updated_at": conversation.updated_at,
        "messages": messages,
    }


@router.patch("/conversations/{conversation_id}", response_model=ConversationSummary)
@limiter.limit("60/minute")
def rename_conversation(
    conversation_id: int,
    body: ConversationRename,
    request: Request,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    conversation = get_conversation(db, user["id"], conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    conversation.title = body.title.strip()
    db.commit()
    db.refresh(conversation)
    return conversation


@router.delete("/conversations/{conversation_id}", status_code=204)
@limiter.limit("60/minute")
def delete_conversation(
    conversation_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    conversation = get_conversation(db, user["id"], conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    db.delete(conversation)
    db.commit()
