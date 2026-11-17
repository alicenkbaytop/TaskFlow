from fastapi import FastAPI
from app.api.tasks import router as tasks_router
from app.api.chat import router as chat_router

app = FastAPI()

app.include_router(tasks_router, prefix="/tasks", tags=["tasks"])
app.include_router(chat_router, prefix="/chat", tags=["chat"])
