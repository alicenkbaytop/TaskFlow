import requests

OLLAMA_URL = "http://localhost:11434/api/chat"

# Describe the tool to the model
tools = [
    {
        "type": "function",
        "function": {
            "name": "list_tasks",
            "description": "Retrieve tasks from TaskFlow. Use this when the user asks to see or find their tasks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status_filter": {
                        "type": "string",
                        "enum": ["pending", "in_progress", "completed"],
                        "description": "Filter tasks by status.",
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["low", "medium", "high"],
                        "description": "Filter tasks by priority.",
                    },
                },
            },
        },
    }
]

response = requests.post(
    OLLAMA_URL,
    json={
        "model": "qwen2.5:3b",
        "messages": [
            {"role": "user", "content": "Show me all my high-priority tasks."}
        ],
        "tools": tools,
        "stream": False,
    },
    timeout=120,
)

response.raise_for_status()

result = response.json()
message = result["message"]

print("Model response:")
print(message)

print("\nTool calls:")
print(message.get("tool_calls", []))
