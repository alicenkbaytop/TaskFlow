import logging
import time

from ragas import EvaluationDataset, SingleTurnSample

from app.evaluation.answer_generation import generate_contextual_answer
from app.evaluation.dataset import evaluation_samples
from app.evaluation.retrieval import retrieve_task_contexts

logger = logging.getLogger(__name__)


def build_answer_dataset(db, user_id: str):
    samples = []

    for sample in evaluation_samples:
        retrieval_start = time.perf_counter()
        # Retrieve actual contexts from the user's pgvector rows.
        retrieved_contexts = retrieve_task_contexts(
            db=db,
            user_id=user_id,
            query=sample.user_input,
        )
        retrieval_duration = (time.perf_counter() - retrieval_start) * 1000
        generation_start = time.perf_counter()
        # Generate an answer using the retrieved contexts.
        answer = generate_contextual_answer(
            question=sample.user_input,
            contexts=retrieved_contexts,
        )
        generation_duration = (time.perf_counter() - generation_start) * 1000
        logger.info(
            "Evaluation latency | Retrieval: %.2f ms | Generation: %.2f ms",
            retrieval_duration,
            generation_duration,
        )
        # Create a complete Ragas evaluation sample.
        evaluation_sample = SingleTurnSample(
            user_input=sample.user_input,
            retrieved_contexts=retrieved_contexts,
            reference_contexts=sample.reference_contexts,
            response=answer,
            reference=sample.reference,
        )

        samples.append(evaluation_sample)

    return EvaluationDataset(samples=samples)
