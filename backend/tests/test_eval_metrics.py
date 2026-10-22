from app.eval.metrics import (
    check_refusal,
    mean_reciprocal_rank,
    precision_at_k,
    recall_at_k,
)


def test_precision_at_k_penalizes_missing_results_when_k_exceeds_result_count():
    assert precision_at_k(["contains evidence"], ["evidence"], k=5) == 0.2


def test_retrieval_metrics_handle_empty_and_adversarial_inputs():
    assert precision_at_k([], ["evidence"], k=5) == 0.0
    assert recall_at_k([], ["evidence"]) == 0.0
    assert mean_reciprocal_rank(["irrelevant"], ["evidence"]) == 0.0


def test_refusal_detection_accepts_clear_uncertainty_without_fixed_template():
    assert check_refusal("I don't know based on the provided context.") is True
    assert check_refusal("There is no mention of that subject in the context.") is True
