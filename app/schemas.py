from typing import Literal
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, field_validator


class TaskCreate(BaseModel):
    title: str
    description: str | None = None
    priority: Literal["low", "medium", "high"] = "medium"
    due_date: date | None = None


class TaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    description: str | None = None
    priority: Literal["low", "medium", "high"] | None = None
    status: Literal["pending", "in_progress", "completed"] | None = None
    due_date: date | None = None


class TaskResponse(BaseModel):
    id: int
    title: str
    description: str | None
    status: Literal["pending", "in_progress", "completed"]
    priority: Literal["low", "medium", "high"]
    due_date: date | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def convert_to_warsaw_time(cls, value):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)

        return value.astimezone(ZoneInfo("Europe/Warsaw"))
