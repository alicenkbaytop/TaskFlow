import json

from app.agent.tools import list_tasks_tool
from app.database import SessionLocal

# Arguments returned by Ollama
tool_arguments = {"priority": "high"}

# Open a database session
db = SessionLocal()

try:
    # Execute the actual Python function
    tasks = list_tasks_tool(db=db, **tool_arguments)

    print("Tasks returned by the tool:")
    print(json.dumps(tasks, indent=4))

finally:
    db.close()
