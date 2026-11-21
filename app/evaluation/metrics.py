from ragas.metrics.collections import (
    ContextPrecisionWithReference,
    ContextRecall,
    Faithfulness,
)

from app.evaluation.llm import create_evaluator_llm


def create_evaluation_metrics():
    evaluator_llm = create_evaluator_llm()

    context_recall = ContextRecall(llm=evaluator_llm)

    context_precision = ContextPrecisionWithReference(llm=evaluator_llm)

    faithfulness = Faithfulness(llm=evaluator_llm)

    return [
        context_recall,
        context_precision,
        faithfulness,
    ]
