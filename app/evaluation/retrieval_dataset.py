from ragas import EvaluationDataset, SingleTurnSample

from app.evaluation.dataset import evaluation_samples
from app.evaluation.retrieval import retrieve_task_contexts


def build_retrieval_dataset(db, user_id: str):
    samples = []

    for sample in evaluation_samples:
        # Retrieve actual contexts from the user's pgvector rows.
        retrieved_contexts = retrieve_task_contexts(
            db=db,
            user_id=user_id,
            query=sample.user_input,
        )

        evaluation_sample = SingleTurnSample(
            user_input=sample.user_input,
            reference_contexts=sample.reference_contexts,
            retrieved_contexts=retrieved_contexts,
            reference=sample.reference,
        )

        samples.append(evaluation_sample)

    return EvaluationDataset(samples=samples)
