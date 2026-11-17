from app.schemas import TaskUpdate
from pydantic import ValidationError

try:
    data = TaskUpdate(priority="urgent")
    print("Validation passed:", data)

except ValidationError as error:
    print("Validation failed:")
    print(error)
