from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Conversation, Message


def create_conversation(db: Session, user_id: str):
    conversation = Conversation(user_id=user_id)

    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    return conversation


def get_conversation(db: Session, user_id: str, conversation_id: int):
    return db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id, Conversation.user_id == user_id
        )
    )


def get_conversation_history(
    db: Session,
    user_id: str,
    conversation_id: int,
):
    statement = (
        select(Message)
        .join(Conversation)
        .where(
            Message.conversation_id == conversation_id, Conversation.user_id == user_id
        )
        .order_by(Message.id.asc())
    )

    messages = db.scalars(statement).all()

    return [
        {
            "role": message.role,
            "content": message.content,
            "created_at": message.created_at,
        }
        for message in messages
    ]


def get_conversations(db: Session, user_id: str):
    statement = (
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.updated_at.desc(), Conversation.id.desc())
    )

    return db.scalars(statement).all()
