import json
import requests

from datetime import date
from typing import Literal
from pydantic import BaseModel, ConfigDict, ValidationError

from app.database import SessionLocal

from app.agent.tools import (
    list_tasks_tool,
    search_tasks_tool,
    create_task_tool,
    get_task_tool,
    update_task_tool,
    complete_task_tool,
    delete_task_tool,
)
from app.schemas import TaskUpdate
from app.agent.tools import find_relevant_tasks_tool

from sqlalchemy.orm import Session

from app.services.conversation_service import (
    get_conversation_history,
    save_message,
)


OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "qwen2.5:3b"
MAX_ROUNDS = 5
MAX_PREVIOUS_MESSAGES = 10

class ListTasksArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status_filter: Literal["pending", "in_progress", "completed"] | None = None
    priority: Literal["low", "medium", "high"] | None = None


class SearchTasksArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str


class CreateTaskArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    description: str | None = None
    priority: Literal["low", "medium", "high"] = "medium"
    due_date: date | None = None


class GetTaskArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: int


class UpdateTaskArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: int
    task_data: TaskUpdate


class CompleteTaskArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: int


class DeleteTaskArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: int


class SearchRelevantTasksArgs(BaseModel):
    query: str


tools = [
    {
        "type": "function",
        "function": {
            "name": "list_tasks",
            "description": "List tasks, optionally filtered by status or priority.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status_filter": {
                        "type": "string",
                        "enum": ["pending", "in_progress", "completed"],
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["low", "medium", "high"],
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_tasks",
            "description": "Search for tasks by words in their title.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Words to search for in the task title.",
                    },
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_task",
            "description": "Create a new task.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "priority": {
                        "type": "string",
                        "enum": ["low", "medium", "high"],
                    },
                    "due_date": {
                        "type": "string",
                        "description": "Due date in YYYY-MM-DD format.",
                    },
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_task",
            "description": "Get the details of one task using its ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer"},
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_task",
            "description": "Update specified fields of an existing task.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer"},
                    "task_data": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "description": {"type": "string"},
                            "priority": {
                                "type": "string",
                                "enum": ["low", "medium", "high"],
                            },
                            "status": {
                                "type": "string",
                                "enum": ["pending", "in_progress", "completed"],
                            },
                            "due_date": {"type": "string"},
                        },
                    },
                },
                "required": ["task_id", "task_data"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "complete_task",
            "description": "Mark an existing task as completed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer"},
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_task",
            "description": "Permanently delete a task when the user explicitly requests deletion.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer"},
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_relevant_tasks",
            "description": (
                "Find tasks related to a user's question by meaning, "
                "even when the wording is different."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The semantic search query",
                    }
                },
                "required": ["query"],
            },
        },
    },
]

SYSTEM_PROMPT = """
You are TaskFlow, a helpful task management assistant.

You can manage tasks using the tools provided by the application.

Rules:

1. Creating tasks:
   - Use create_task when the user asks to create a task.
   - If the user does not specify a priority, use medium.
   - Do not invent a due date.

2. Finding tasks:
   - Use list_tasks when the user asks to see their tasks.
   - Use search_tasks when the user identifies a task by its title or keywords.
   - Use get_task when the user provides a task ID.

3. Updating tasks:
   - If the user provides a task ID, use update_task directly.
   - If the user identifies a task by title, search for it first.
   - If multiple tasks match, ask the user which one they mean.
   - Only change the fields the user requested.
   - If no task is found, explain that to the user.

4. Completing tasks:
   - Use complete_task when the user asks to mark a task as completed.
   - Find the task first if the user identifies it by title.

5. Deleting tasks:
   - Only delete a task when the user explicitly asks for deletion.
   - Find the task first if the user identifies it by title.
   - If multiple tasks match, ask for clarification.

6. General behavior:
   - Never claim an action succeeded unless the tool result confirms it.
   - Never invent task IDs or task information.
   - If a tool returns an error, explain the error clearly.
   - Be concise and helpful.
   Use find_relevant_tasks when the user asks questions about tasks
    based on their meaning, context, or related concepts.

    Use search_tasks for exact title matching.
    Use get_task when you need a specific task by ID.
    
    SEMANTIC SEARCH RULES:

- Use find_relevant_tasks for questions about task meaning or context.
- Do not invent tasks or task details.
- Only present tasks returned by the search tool.
- If the search returns an empty result list, clearly tell the user
  that no sufficiently relevant tasks were found.
- Do not claim that no tasks exist in the database;
  explain that no relevant matches were found.
- Treat similarity scores as retrieval signals, not proof of relevance.
"""


def execute_tool(tool_name: str, arguments: dict):
    # Each tool has an approved argument schema and Python function.
    tool_map = {
        "list_tasks": (ListTasksArgs, list_tasks_tool),
        "search_tasks": (SearchTasksArgs, search_tasks_tool),
        "create_task": (CreateTaskArgs, create_task_tool),
        "get_task": (GetTaskArgs, get_task_tool),
        "update_task": (UpdateTaskArgs, update_task_tool),
        "complete_task": (CompleteTaskArgs, complete_task_tool),
        "delete_task": (DeleteTaskArgs, delete_task_tool),
        "find_relevant_tasks": (
            SearchRelevantTasksArgs,
            find_relevant_tasks_tool,
        ),
    }

    if tool_name not in tool_map:
        return {"error": f"Unknown tool: {tool_name}"}

    argument_schema, tool_function = tool_map[tool_name]

    try:
        # Validate arguments returned by the LLM.
        validated_args = argument_schema.model_validate(arguments)

        # Convert validated arguments into a Python dictionary.
        data = validated_args.model_dump(exclude_unset=True)

        # Other tools use the SQLite database.
        db = SessionLocal()

        try:
            if tool_name == "create_task":
                return tool_function(db=db, task_data=data)

            if tool_name == "update_task":
                return tool_function(
                    db=db,
                    task_id=data["task_id"],
                    task_data=data["task_data"],
                )

            return tool_function(db=db, **data)

        finally:
            db.close()

    except ValidationError as error:
        return {
            "error": "Invalid tool arguments",
            "details": error.errors(),
        }


def ask_ollama(db: Session, conversation_id: int, user_message: str) -> str:

    # Import here to avoid a circular import
    from app.agent.workflow import run_agent

    # Retrieve previous conversation messages
    history = get_conversation_history(
        db=db,
        conversation_id=conversation_id,
    )

    # Keep only the 10 most recent previous messages
    history = history[-MAX_PREVIOUS_MESSAGES:]

    # Save the new user message in SQLite
    save_message(
        db=db,
        conversation_id=conversation_id,
        role="user",
        content=user_message,
    )

    # Prepare the initial agent context
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *history,
        {"role": "user", "content": user_message},
    ]

    # Execute the LangGraph workflow
    answer = run_agent(
        conversation_id=conversation_id,
        messages=messages,
    )

    # Save the final assistant response
    save_message(
        db=db,
        conversation_id=conversation_id,
        role="assistant",
        content=answer,
    )

    return answer
