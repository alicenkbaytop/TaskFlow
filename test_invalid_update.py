from app.agent.tools import update_task_tool
from app.database import SessionLocal

db = SessionLocal()

try:
    result = update_task_tool(db=db, task_id=999999, task_data={"priority": "urgent"})

    print("Tool result:")
    print(result)

finally:
    db.close()
