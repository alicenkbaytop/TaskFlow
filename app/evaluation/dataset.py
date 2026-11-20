from ragas import EvaluationDataset, SingleTurnSample

# Fictional TaskFlow examples for evaluation
evaluation_samples = [
    SingleTurnSample(
        user_input="Which task is related to the quarterly budget?",
        reference_contexts=[
            "Task: Prepare quarterly budget report. "
            "Notes: Collect department expenses and "
            "prepare the Q4 financial summary."
        ],
        reference=(
            "Prepare the quarterly budget report by "
            "collecting department expenses and preparing "
            "the Q4 financial summary."
        ),
    ),
    SingleTurnSample(
        user_input="What do I need to finish before the client demo?",
        reference_contexts=[
            "Task: Prepare client demo. "
            "Notes: Finish the dashboard integration "
            "and verify the API responses before Friday."
        ],
        reference=(
            "Finish the dashboard integration and verify "
            "the API responses before Friday."
        ),
    ),
    SingleTurnSample(
        user_input="Which task involves fixing authentication?",
        reference_contexts=[
            "Task: Fix login authentication. "
            "Notes: Investigate JWT validation errors "
            "and resolve expired token handling."
        ],
        reference=(
            "Fix login authentication by investigating "
            "JWT validation errors and expired token handling."
        ),
    ),
]


# Create the Ragas evaluation dataset
evaluation_dataset = EvaluationDataset(
    samples=evaluation_samples,
    name="taskflow-evaluation",
)
