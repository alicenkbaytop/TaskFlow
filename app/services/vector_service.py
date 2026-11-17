import requests
from qdrant_client import QdrantClient, models

OLLAMA_URL = "http://localhost:11434/api/embed"
EMBEDDING_MODEL = "nomic-embed-text"

COLLECTION_NAME = "tasks"
VECTOR_SIZE = 768

# Persistent local Qdrant storage
client = QdrantClient(path="./qdrant_data")


def create_embedding(text: str) -> list[float]:
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": EMBEDDING_MODEL,
            "input": text,
        },
        timeout=60,
    )
    response.raise_for_status()

    return response.json()["embeddings"][0]


def ensure_collection():
    if not client.collection_exists(COLLECTION_NAME):
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=models.VectorParams(
                size=VECTOR_SIZE,
                distance=models.Distance.COSINE,
            ),
        )


def index_task(task_id: int, title: str, description: str | None):
    ensure_collection()

    text = f"Title: {title}\nDescription: {description or ''}"
    vector = create_embedding(text)

    client.upsert(
        collection_name=COLLECTION_NAME,
        points=[
            models.PointStruct(
                id=task_id,
                vector=vector,
                payload={
                    "task_id": task_id,
                    "title": title,
                    "description": description,
                },
            )
        ],
    )


def delete_task_vector(task_id: int):
    if client.collection_exists(COLLECTION_NAME):
        client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=models.PointIdsList(points=[task_id]),
        )


def search_similar_tasks(
    query: str,
    limit: int = 5,
    score_threshold: float = 0.45,
):
    ensure_collection()

    query_vector = create_embedding(query)

    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=limit,
        score_threshold=score_threshold,
        with_payload=True,
    )

    return [
        {
            "task_id": point.payload["task_id"],
            "title": point.payload["title"],
            "description": point.payload["description"],
            "score": point.score,
        }
        for point in results.points
    ]
