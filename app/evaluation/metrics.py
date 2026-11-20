from ragas.metrics import (
    Faithfulness,
    LLMContextPrecisionWithReference,
    LLMContextRecall,
)

from app.evaluation.llm import create_evaluator_llm


def create_evaluation_metrics():
    evaluator_llm = create_evaluator_llm()

    context_recall = LLMContextRecall(llm=evaluator_llm)

    context_precision = LLMContextPrecisionWithReference(llm=evaluator_llm)

    faithfulness = Faithfulness(llm=evaluator_llm)

    return [
        context_recall,
        context_precision,
        faithfulness,
    ]
