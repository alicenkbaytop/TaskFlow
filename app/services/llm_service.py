import json
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy.orm import Session

from app.agent.tools import (
    complete_task_tool,
    create_task_tool,
    delete_task_tool,
    find_relevant_tasks_tool,
    get_task_tool,
    list_tasks_tool,
    search_tasks_tool,
    update_task_tool,
)
from app.core.config import get_settings
from app.schemas import TaskUpdate
from app.services.conversation_service import (
    get_conversation_history,
    save_message,
)
from app.services.model_router import resolve_route

CHAT_ROUTE = resolve_route("chat")
AI_PROVIDER = CHAT_ROUTE.provider
MODEL_NAME = CHAT_ROUTE.model
MAX_ROUNDS = 5
MAX_PREVIOUS_MESSAGES = 10


def get_llm_client(provider: str | None = None):
    from openai import OpenAI

    settings = get_settings()
    provider = provider or resolve_route("chat").provider
    if provider == "ollama":
        return OpenAI(
            api_key="ollama",
            base_url=f"{settings.ollama_base_url.rstrip('/')}/",
            timeout=settings.ai_timeout_seconds,
            max_retries=0,
        )
    raise RuntimeError("OpenAI-compatible client is only used with Ollama")


def get_gemini_client():
    from google import genai
    from google.genai import types

    settings = get_settings()
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured")
    return genai.Client(
        api_key=settings.gemini_api_key,
        http_options=types.HttpOptions(
            timeout=int(get_settings().ai_timeout_seconds * 1000),
            retry_options=types.HttpRetryOptions(attempts=1),
        ),
    )


def generate_gemini_message(
    messages: list[dict], function_tools: list[dict], model: str | None = None
):
    import uuid

    from google.genai import types

    settings = get_settings()
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured")

    client = get_gemini_client()

    system_instructions = []
    contents = []
    call_names = {}

    for message in messages:
        role = message.get("role")
        if role == "system":
            if message.get("content"):
                system_instructions.append(message["content"])
        elif role == "user":
            contents.append(
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=message.get("content", ""))],
                )
            )
        elif role == "assistant":
            stored_content = message.get("_gemini_content")
            if stored_content:
                contents.append(types.Content.model_validate(stored_content))
                for call in message.get("tool_calls", []):
                    call_names[call["id"]] = call["function"]["name"]
                continue
            parts = []
            if message.get("content"):
                parts.append(types.Part.from_text(text=message["content"]))
            for call in message.get("tool_calls", []):
                function = call["function"]
                arguments = json.loads(function.get("arguments") or "{}")
                call_names[call["id"]] = function["name"]
                parts.append(
                    types.Part.from_function_call(name=function["name"], args=arguments)
                )
            if parts:
                contents.append(types.Content(role="model", parts=parts))
        elif role == "tool":
            function_name = call_names.get(message.get("tool_call_id"))
            if not function_name:
                raise RuntimeError("Gemini tool response has no matching function call")
            try:
                result = json.loads(message.get("content", "{}"))
            except json.JSONDecodeError:
                result = {"result": message.get("content", "")}
            if not isinstance(result, dict):
                result = {"result": result}
            contents.append(
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_function_response(
                            name=function_name,
                            response=result,
                        )
                    ],
                )
            )

    declarations = []
    for item in function_tools:
        function = item["function"]
        parameters = dict(function.get("parameters") or {})
        parameters.setdefault("type", "object")
        declarations.append(
            types.FunctionDeclaration(
                name=function["name"],
                description=function.get("description", ""),
                parameters_json_schema=parameters,
            )
        )

    config = types.GenerateContentConfig(
        system_instruction="\n\n".join(system_instructions) or None,
        tools=(
            [types.Tool(function_declarations=declarations)] if declarations else None
        ),
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    response = client.models.generate_content(
        model=model or resolve_route("chat").model,
        contents=contents,
        config=config,
    )

    text_parts = []
    tool_calls = []
    candidates = response.candidates or []
    if candidates and candidates[0].content:
        for part in candidates[0].content.parts or []:
            if part.text:
                text_parts.append(part.text)
            function_call = part.function_call
            if function_call:
                tool_calls.append(
                    {
                        "id": function_call.id or uuid.uuid4().hex,
                        "type": "function",
                        "function": {
                            "name": function_call.name,
                            "arguments": json.dumps(function_call.args or {}),
                        },
                    }
                )

    raw_content = (
        candidates[0].content.model_dump(mode="json", exclude_none=True)
        if candidates and candidates[0].content
        else None
    )
    return {
        "content": "".join(text_parts),
        "tool_calls": tool_calls,
        "_gemini_content": raw_content,
    }


def generate_chat_message(route, messages: list[dict], function_tools: list[dict]):
    if route.provider == "gemini":
        return generate_gemini_message(messages, function_tools, model=route.model)
    if route.provider == "ollama":
        response = get_llm_client(provider=route.provider).chat.completions.create(
            model=route.model,
            messages=messages,
            tools=function_tools,
        )
        choice = response.choices[0].message
        return {
            "content": choice.content or "",
            "tool_calls": [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.function.name,
                        "arguments": call.function.arguments,
                    },
                }
                for call in (choice.tool_calls or [])
            ],
        }
    raise RuntimeError(f"Unsupported AI provider: {route.provider}")


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
            "description": (
                "Permanently delete a task when the user explicitly requests deletion."
            ),
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


def execute_tool(db: Session, user_id: str, tool_name: str, arguments: dict):
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

        if tool_name == "create_task":
            return tool_function(db=db, user_id=user_id, task_data=data)
        if tool_name == "update_task":
            return tool_function(
                db=db,
                user_id=user_id,
                task_id=data["task_id"],
                task_data=data["task_data"],
            )
        return tool_function(db=db, user_id=user_id, **data)

    except ValidationError as error:
        return {
            "error": "Invalid tool arguments",
            "details": error.errors(),
        }


def ask_gemini(
    db: Session, user_id: str, conversation_id: int, user_message: str
) -> str:

    # Import here to avoid a circular import
    from app.agent.workflow import run_agent

    # Retrieve previous conversation messages
    history = get_conversation_history(
        db=db,
        user_id=user_id,
        conversation_id=conversation_id,
    )

    # Keep only the 10 most recent previous messages
    history = history[-MAX_PREVIOUS_MESSAGES:]

    # Save the new user message to PostgreSQL.
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
        user_id=user_id,
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
