from app.database import SessionLocal
from app.models import Task

db = SessionLocal()

task = db.get(Task, 1)

if task:
    db.delete(task)
    db.commit()
    print("Task deleted successfully!")
else:
    print("Task not found")

db.close()
