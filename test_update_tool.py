from app.database import SessionLocal
from app.schemas import TaskUpdate
from app.services.task_service import update_task

db = SessionLocal()

try:
    # Change only the priority of task 5
    task_data = TaskUpdate(priority="medium")

    updated_task = update_task(
        db=db,
        task_id=5,
        task_data=task_data,
    )

    print("Updated task:")
    print("Title:", updated_task.title)
    print("Priority:", updated_task.priority)
    print("Status:", updated_task.status)

finally:
    db.close()
