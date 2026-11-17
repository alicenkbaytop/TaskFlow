from app.services.vector_service import delete_task_vector, client

delete_task_vector(999)

print(client.count(collection_name="tasks"))

client.close()
