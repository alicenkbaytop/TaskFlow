import json
import requests

from langgraph.graph import StateGraph, START, END

from app.agent.state import AgentState
from app.services.llm_service import (
    OLLAMA_URL,
    MODEL_NAME,
    SYSTEM_PROMPT,
    tools,
    execute_tool,
)

MAX_TOOL_ROUNDS = 5


# -------------------------
# Agent Node
# -------------------------


def agent_node(state: AgentState):

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL_NAME,
                "messages": state["messages"],
                "tools": tools,
                "stream": False,
            },
            timeout=120,
        )

        response.raise_for_status()

    except requests.RequestException:
        return {
            "answer": (
                "Unable to connect to Ollama. "
                "Please check whether the local AI model is running."
            )
        }

    result = response.json()
    assistant_message = result["message"]

    # Add the LLM response to the conversation context
    updated_messages = state["messages"] + [assistant_message]

    tool_calls = assistant_message.get("tool_calls", [])

    # If the model requests more tools than allowed
    if tool_calls and state["tool_rounds"] >= MAX_TOOL_ROUNDS:
        return {
            "messages": updated_messages,
            "answer": (
                "I couldn't complete the request within " "the allowed tool-call limit."
            ),
        }

    # If the model has finished answering
    if not tool_calls:
        return {
            "messages": updated_messages,
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

    for tool_call in tool_calls:

        function = tool_call["function"]

        tool_name = function["name"]
        arguments = function["arguments"]

        try:
            # Execute the existing validated application tool
            tool_result = execute_tool(
                tool_name=tool_name,
                arguments=arguments,
            )

        except Exception as error:
            # Return the error to the LLM instead of stopping the workflow
            tool_result = {
                "error": str(error),
                "tool": tool_name,
            }

        # Return either the successful result or error to Ollama
        messages.append(
            {
                "role": "tool",
                "tool_name": tool_name,
                "content": json.dumps(tool_result, default=str),
            }
        )

    return {
        "messages": messages,
        "tool_rounds": state["tool_rounds"] + 1,
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
    messages: list[dict],
):

    initial_state = {
        "conversation_id": conversation_id,
        "messages": messages,
        "answer": "",
        "tool_rounds": 0,
    }

    try:
        result = agent_graph.invoke(
            initial_state,
            config={"recursion_limit": 20},
        )

        return result["answer"]

    except Exception:
        return "The AI workflow encountered an unexpected error. " "Please try again."
