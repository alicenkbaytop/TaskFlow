from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.conversation_service import (
    create_conversation,
    get_conversation,
    get_conversation_history,
    get_conversations,
)
from app.services.llm_service import ask_ollama

router = APIRouter()


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    answer: str


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
def chat(request: ChatRequest):
    answer = ask_ollama(request.message)

    return ChatResponse(answer=answer)


@router.get("/conversations", response_model=list[ConversationSummary])
def list_conversations(db: Session = Depends(get_db)):
    conversations = get_conversations(db)

    return conversations


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationDetail,
)
def retrieve_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
):
    conversation = get_conversation(db, conversation_id)

    if conversation is None:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found",
        )

    messages = get_conversation_history(
        db=db,
        conversation_id=conversation_id,
    )

    return {
        "id": conversation.id,
        "title": conversation.title,
        "created_at": conversation.created_at,
        "messages": messages,
    }
