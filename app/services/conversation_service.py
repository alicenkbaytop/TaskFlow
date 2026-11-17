from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models import Conversation, Message


def create_conversation(db: Session):
    conversation = Conversation()

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


def get_conversation(db: Session, conversation_id: int):
    return db.get(Conversation, conversation_id)


def get_conversation_history(
    db: Session,
    conversation_id: int,
):
    statement = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
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


def get_conversations(db: Session):
    statement = select(Conversation).order_by(Conversation.created_at.desc())

    return db.scalars(statement).all()
