import os

from app.database import SessionLocal
from app.evaluation.runner import run_retrieval_evaluation


def main():
    db = SessionLocal()

    try:
        user_id = os.environ.get("TASKFLOW_EVAL_USER_ID")
        if not user_id:
            raise RuntimeError(
                "Set TASKFLOW_EVAL_USER_ID to an account containing evaluation tasks"
            )
        result = run_retrieval_evaluation(db, user_id)
        print("\nTaskFlow Retrieval Evaluation Results:")
        print(result)
    finally:
        db.close()


if __name__ == "__main__":
    main()
