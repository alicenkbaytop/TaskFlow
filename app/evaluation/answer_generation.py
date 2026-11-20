from app.services.llm_service import (
    AI_PROVIDER,
    MODEL_NAME,
    generate_gemini_message,
    get_llm_client,
)


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
    if AI_PROVIDER == "gemini":
        response = generate_gemini_message(messages, [])
        return response["content"]

    response = get_llm_client().chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
    )
    return response.choices[0].message.content or ""
