from app.services.vector_service import (
    search_similar_tasks,
    client,
)

results = search_similar_tasks("I need to prepare for a job meeting")

for task in results:
    print(task)

client.close()
