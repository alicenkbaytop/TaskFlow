from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import TaskEmbedding

EMBEDDING_DIMENSIONS = 768


def embedding_provider_configured() -> bool:
    settings = get_settings()
    provider = settings.ai_provider.strip().lower()
    return provider == "ollama" or (
        provider == "gemini" and bool(settings.gemini_api_key)
    )


def create_embedding(text: str) -> list[float]:
    settings = get_settings()
    if settings.ai_provider.strip().lower() == "ollama":
        from openai import OpenAI

        client = OpenAI(
            api_key="ollama",
            base_url=f"{settings.ollama_base_url.rstrip('/')}/",
            timeout=120,
            max_retries=0,
        )
        result = client.embeddings.create(
            model=settings.ollama_embedding_model,
            input=text,
        )
        vector = result.data[0].embedding
    else:
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=settings.gemini_api_key)
        result = client.models.embed_content(
            model=settings.gemini_embedding_model,
            contents=text,
            config=types.EmbedContentConfig(
                output_dimensionality=EMBEDDING_DIMENSIONS
            ),
        )
        vector = result.embeddings[0].values
    if len(vector) != EMBEDDING_DIMENSIONS:
        raise ValueError(
            f"Embedding provider returned {len(vector)} dimensions; "
            f"expected {EMBEDDING_DIMENSIONS}"
        )
    return list(vector)


def index_task(
    db: Session, user_id: str, task_id: int, title: str, description: str | None
):
    content = f"Title: {title}\nDescription: {description or ''}"
    vector = create_embedding(content)
    row = db.get(TaskEmbedding, task_id)
    if row is None:
        row = TaskEmbedding(
            task_id=task_id, user_id=user_id, content=content, embedding=vector
        )
        db.add(row)
    else:
        row.user_id, row.content, row.embedding = user_id, content, vector
    db.commit()


def delete_task_vector(db: Session, task_id: int):
    row = db.get(TaskEmbedding, task_id)
    if row:
        db.delete(row)
        db.commit()


def search_similar_tasks(db: Session, user_id: str, query: str, limit: int = 5):
    if db.bind.dialect.name != "postgresql":
        raise RuntimeError("Semantic search requires PostgreSQL with pgvector")
    vector = create_embedding(query)
    distance = TaskEmbedding.embedding.cosine_distance(vector)
    rows = db.execute(
        select(TaskEmbedding, distance.label("distance"))
        .where(TaskEmbedding.user_id == user_id)
        .order_by(distance)
        .limit(limit)
    ).all()
    return [
        {"task_id": row.task_id, "score": 1 - float(distance)}
        for row, distance in rows
        if distance is not None
    ]
