from app.agent.tools import search_tasks_tool
from app.database import SessionLocal

db = SessionLocal()

try:
    results = search_tasks_tool(db=db, title="FastAPI")

    for task in results:
        print(task)

finally:
    db.close()
