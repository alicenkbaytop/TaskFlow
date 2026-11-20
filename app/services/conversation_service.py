from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Conversation, Message


def create_conversation(db: Session, user_id: str):
    conversation = Conversation(user_id=user_id)

    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    return conversation


def save_message(
    db: Session,
    conversation_id: int,
    role: str,
    content: str,
):
    message = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
    )

    db.add(message)
    db.commit()
    db.refresh(message)

    return message


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
        }
        for message in messages
    ]


def get_conversations(db: Session, user_id: str):
    statement = (
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.created_at.desc())
    )

    return db.scalars(statement).all()
