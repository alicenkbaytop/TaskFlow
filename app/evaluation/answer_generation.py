from app.services.llm_service import (
    generate_chat_message,
)
from app.services.model_router import generate_with_fallback, provider_order


def generate_contextual_answer(question: str, contexts: list[str]) -> str:
    context_text = "\n\n".join(contexts)
    messages = [
        {
            "role": "system",
            "content": (
                "Answer only from supplied task information. "
                "Say when it is insufficient."
            ),
        },
        {
            "role": "user",
            "content": f"Task information:\n{context_text}\n\nQuestion: {question}",
        },
    ]
    response, _ = generate_with_fallback(
        lambda route: generate_chat_message(route, messages, []),
        routes=provider_order("evaluation"),
    )
    return response.get("content", "")
