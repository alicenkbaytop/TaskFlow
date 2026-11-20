from ragas import evaluate
from sqlalchemy.orm import Session

from app.evaluation.answer_dataset import build_answer_dataset
from app.evaluation.metrics import create_evaluation_metrics


def run_retrieval_evaluation(db: Session, user_id: str):
    dataset = build_answer_dataset(db, user_id)

    # Configure the evaluation metrics.
    metrics = create_evaluation_metrics()

    # Evaluate retrieval quality.
    result = evaluate(
        dataset=dataset,
        metrics=metrics,
        raise_exceptions=True,
    )

    return result
