from ragas.llms import llm_factory

from app.services.llm_service import (
    AI_PROVIDER,
    MODEL_NAME,
    get_gemini_client,
    get_llm_client,
)


def create_evaluator_llm():

    if AI_PROVIDER == "gemini":
        client = get_gemini_client()
        provider = "google"
    else:
        client = get_llm_client()
        provider = "openai"

    # Create an LLM that Ragas can use for evaluation
    evaluator_llm = llm_factory(
        MODEL_NAME,
        provider=provider,
        client=client,
    )

    return evaluator_llm
