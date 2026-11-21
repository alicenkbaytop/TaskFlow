import hashlib
import json
import logging
import time

from langgraph.graph import END, START, StateGraph
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from app.agent.state import AgentState
from app.core.config import get_settings
from app.database import SessionLocal
from app.services.llm_service import (
    execute_tool,
    generate_chat_message,
    tools,
)
from app.services.model_router import (
    generate_with_fallback,
    provider_order,
    resolve_route,
    route_for_task,
    task_importance,
)
from app.services.provider_reliability import with_retries

logger = logging.getLogger(__name__)

tracer = trace.get_tracer(__name__)

MAX_TOOL_ROUNDS = 5


class AIWorkflowError(RuntimeError):
    """Controlled AI provider failure safe to return to an authenticated user."""


# -------------------------
# Agent Node
# -------------------------


def agent_node(state: AgentState):
    start_time = time.perf_counter()
    settings = get_settings()
    latest_user_message = next(
        (
            message.get("content", "")
            for message in reversed(state["messages"])
            if message.get("role") == "user"
        ),
        "",
    )
    if state.get("active_provider"):
        route = resolve_route("chat", state["active_provider"])
        importance = task_importance(latest_user_message)
    else:
        route, importance = route_for_task(latest_user_message)
    retry_count = 0
    assistant_message = None

    with tracer.start_as_current_span("agent.llm_request") as span:
        span.set_attribute("llm.provider", route.provider)
        span.set_attribute("llm.model", route.model)
        span.set_attribute("ai.task_importance", importance)

        try:
            routes = provider_order("chat", route.provider)
            result, actual_route = generate_with_fallback(
                lambda candidate: with_retries(
                    lambda: generate_chat_message(candidate, state["messages"], tools),
                    attempts=settings.ai_retry_attempts,
                    base_delay_seconds=settings.ai_retry_base_seconds,
                ),
                routes=routes,
            )
            assistant_message, retry_count = result
            route = actual_route

            duration = (time.perf_counter() - start_time) * 1000
            span.set_attribute("llm.success", True)
            span.set_attribute("llm.provider", route.provider)
            span.set_attribute("llm.model", route.model)
            span.set_attribute("llm.retry_count", retry_count - 1)
            span.set_attribute("llm.fallback_used", route != routes[0])
            span.set_attribute("llm.latency_ms", duration)

        except Exception as error:
            span.set_attribute("llm.success", False)
            span.set_attribute("error.type", type(error).__name__)
            span.set_status(Status(StatusCode.ERROR, type(error).__name__))
            span.set_attribute(
                "llm.latency_ms", (time.perf_counter() - start_time) * 1000
            )
            status_code = getattr(error, "status_code", None) or getattr(
                error, "code", None
            )
            logger.error(
                "AI request failed: provider=%s model=%s type=%s status=%s",
                route.provider,
                route.model,
                type(error).__name__,
                status_code,
            )
            error_type = type(error).__name__
            if error_type == "AuthenticationError" or status_code in (401, 403):
                answer = f"The {route.provider} provider rejected its credentials."
            elif error_type == "RateLimitError" or status_code == 429:
                answer = f"The {route.provider} provider rate limit was reached."
            elif "Timeout" in error_type or status_code == 504:
                answer = "The AI provider did not respond in time. Please try again."
            elif error_type == "APIConnectionError":
                answer = (
                    "TaskFlow could not connect to the AI provider. "
                    "Check the configured AI provider credentials and network."
                )
            elif status_code == 404:
                answer = (
                    f"AI model '{route.model}' is unavailable. "
                    "Check the selected provider and model setting."
                )
            elif status_code == 503:
                answer = (
                    "The AI provider is temporarily unavailable (503). "
                    "Please try again in a few minutes."
                )
            elif isinstance(error, RuntimeError) and "GEMINI_API_KEY" in str(error):
                answer = "GEMINI_API_KEY is not configured in the backend environment."
            elif isinstance(error, RuntimeError) and "API_KEY is not configured" in str(
                error
            ):
                answer = str(error)
            elif isinstance(error, RuntimeError):
                answer = str(error)
            else:
                answer = (
                    "The AI provider could not complete the request. "
                    "Check the FastAPI logs for the provider error."
                )
            return {"answer": answer, "failed": True, "error_message": answer}

    logger.info(
        "AI provider: %s | model: %s | Duration: %.2f ms",
        route.provider,
        route.model,
        duration,
    )

    generated_message = assistant_message
    assistant_message = {
        "role": "assistant",
        "content": generated_message.get("content", ""),
    }
    if response_tool_calls := generated_message.get("tool_calls"):
        assistant_message["tool_calls"] = response_tool_calls
    if gemini_content := generated_message.get("_gemini_content"):
        assistant_message["_gemini_content"] = gemini_content

    # Add the LLM response to the conversation context
    updated_messages = state["messages"] + [assistant_message]

    tool_calls = assistant_message.get("tool_calls", [])

    # If the model requests more tools than allowed
    if tool_calls and state["tool_rounds"] >= MAX_TOOL_ROUNDS:
        return {
            "messages": updated_messages,
            "active_provider": route.provider,
            "answer": (
                "I couldn't complete the request within the allowed tool-call limit."
            ),
        }

    # If the model has finished answering
    if not tool_calls:
        return {
            "messages": updated_messages,
            "active_provider": route.provider,
            "answer": assistant_message.get("content", ""),
        }

    return {
        "messages": updated_messages,
    }


# -------------------------
# Tool Node
# -------------------------


def tool_node(state: AgentState):

    messages = list(state["messages"])
    assistant_message = messages[-1]

    tool_calls = assistant_message.get("tool_calls", [])
    executed_tools = dict(state.get("executed_tools", {}))

    for tool_call in tool_calls:
        function = tool_call["function"]

        tool_name = function["name"]
        try:
            arguments = json.loads(function["arguments"])
        except (TypeError, json.JSONDecodeError):
            arguments = None

        action_key = hashlib.sha256(
            json.dumps(
                {"tool": tool_name, "arguments": arguments},
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            ).encode("utf-8")
        ).hexdigest()

        if action_key in executed_tools:
            tool_result = executed_tools[action_key]
            with tracer.start_as_current_span("agent.tool_deduplicated") as span:
                span.set_attribute("tool.name", tool_name)
                span.set_attribute("tool.deduplicated", True)
                span.set_attribute("tool.success", "error" not in tool_result)
                if "error" in tool_result:
                    span.set_attribute("tool.error", True)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": json.dumps(tool_result, default=str),
                }
            )
            continue

        start_time = time.perf_counter()
        with tracer.start_as_current_span("agent.tool_execution") as span:
            span.set_attribute("tool.name", tool_name)

            db = SessionLocal()

            try:
                tool_result = execute_tool(
                    db=db,
                    user_id=state["user_id"],
                    tool_name=tool_name,
                    arguments=arguments,
                )
                if arguments is None:
                    tool_result = {"error": "Invalid tool arguments"}

                span.set_attribute("tool.success", "error" not in tool_result)
                if "error" in tool_result:
                    span.set_attribute("tool.error", True)

            except Exception as error:
                tool_result = {"error": "Tool execution failed", "tool": tool_name}

                span.set_attribute("tool.success", False)
                span.set_attribute("error.type", type(error).__name__)
                span.set_status(Status(StatusCode.ERROR, type(error).__name__))

            finally:
                db.close()
                span.set_attribute(
                    "tool.latency_ms", (time.perf_counter() - start_time) * 1000
                )

        executed_tools[action_key] = tool_result

        duration = (time.perf_counter() - start_time) * 1000

        logger.info(
            "Tool: %s | Duration: %.2f ms",
            tool_name,
            duration,
        )
        # Return either the successful result or error to the selected provider.
        messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "content": json.dumps(tool_result, default=str),
            }
        )

    return {
        "messages": messages,
        "tool_rounds": state["tool_rounds"] + 1,
        "executed_tools": executed_tools,
    }


# -------------------------
# Conditional Routing
# -------------------------


def should_continue(state: AgentState):

    if state["answer"]:
        return "end"

    return "tools"


# -------------------------
# Build Graph
# -------------------------


def build_agent_graph():

    graph = StateGraph(AgentState)

    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)

    graph.add_edge(START, "agent")

    graph.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "end": END,
        },
    )

    graph.add_edge("tools", "agent")

    return graph.compile()


agent_graph = build_agent_graph()


# -------------------------
# Run Agent
# -------------------------


def run_agent(
    conversation_id: int,
    user_id: str,
    messages: list[dict],
):

    initial_state = {
        "conversation_id": conversation_id,
        "user_id": user_id,
        "messages": messages,
        "answer": "",
        "tool_rounds": 0,
        "failed": False,
        "error_message": "",
        "active_provider": None,
        "executed_tools": {},
    }

    try:
        with tracer.start_as_current_span("langgraph.workflow") as span:
            start = time.perf_counter()
            result = agent_graph.invoke(
                initial_state,
                config={"recursion_limit": 20},
            )
            span.set_attribute("langgraph.success", not result.get("failed", False))
            span.set_attribute("langgraph.tool_rounds", result.get("tool_rounds", 0))
            span.set_attribute(
                "langgraph.latency_ms", (time.perf_counter() - start) * 1000
            )

        if result.get("failed"):
            raise AIWorkflowError(result.get("error_message") or "AI request failed")
        return result["answer"]

    except AIWorkflowError:
        raise
    except Exception as error:
        logger.error("AI workflow failed: %s", type(error).__name__)
        raise AIWorkflowError(
            "The AI workflow encountered an unexpected error."
        ) from error
