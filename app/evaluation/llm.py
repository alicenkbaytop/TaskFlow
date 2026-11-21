"""Ragas adapter that sends evaluator generations through TaskFlow's router."""

import asyncio
import json

from pydantic import ValidationError
from ragas.llms.base import InstructorBaseRagasLLM

from app.services.llm_service import generate_chat_message
from app.services.model_router import generate_with_fallback, provider_order


class RoutedEvaluationLLM(InstructorBaseRagasLLM):
    def generate(self, prompt: str, response_model):
        schema = response_model.model_json_schema()
        messages = [
            {
                "role": "system",
                "content": (
                    "Return a JSON object that matches the supplied response schema. "
                    "Use only the supplied evaluation prompt."
                ),
            },
            {"role": "user", "content": prompt},
        ]

        def generate_and_validate(route):
            response = generate_chat_message(
                route, messages, [], response_schema=schema
            )
            try:
                return response_model.model_validate_json(response.get("content", ""))
            except (ValidationError, json.JSONDecodeError) as error:
                invalid_output = ValueError(
                    f"{route.provider} returned invalid structured output"
                )
                invalid_output.status_code = 422
                raise invalid_output from error

        result, _route = generate_with_fallback(
            generate_and_validate,
            routes=provider_order("evaluation"),
        )
        return result

    async def agenerate(self, prompt: str, response_model):
        return await asyncio.to_thread(self.generate, prompt, response_model)


def create_evaluator_llm():
    return RoutedEvaluationLLM()
