from __future__ import annotations

from copy import deepcopy

from autonomous_betting_agent.advisory_model_readiness import apply_model_readiness_fields, model_readiness_diagnostics, model_readiness_summary
from autonomous_betting_agent.model_status_constants import (
    DUPLICATE_HEAVY_SAMPLE,
    NEEDS_EVENT_IDENTITY,
    NEEDS_GRADED_ROWS,
    NEEDS_MORE_COMPLETED_EVENTS,
    NEEDS_OUTCOME_DIVERSITY,
    NEEDS_PROBABILITY_FIELD,
    NEEDS_RESULT_FIELD,
    NEEDS_SELECTION_FIELD,
    READY_FOR_OBSERVATION_ONLY,
    SHADOW_READY,
)
from autonomous_betting_agent.model_status_results import brier_score, outcome_value, probability_value


def _row(i: int, result: str = "win", prob: float = 0.60, **extra):
    row = {"event_id": f"event-{i}", "prediction": "Team A", "model_probability": prob, "result": result}
    row.update(extra)
    return row


def test_missing_fields_return_expected_statuses():
    assert model_readiness_diagnostics([{"event_id": "e1", "prediction": "A", "model_probability": 0.6}])["advisory_shadow_readiness_status"] == NEEDS_RESULT_FIELD
    assert model_readiness_diagnostics([{"event_id": "e1", "prediction": "A", "result": "win"}])["advisory_shadow_readiness_status"] == NEEDS_PROBABILITY_FIELD
    assert model_readiness_diagnostics([{"event_id": "e1", "model_probability": 0.6, "result": "win"}])["advisory_shadow_readiness_status"] == NEEDS_SELECTION_FIELD
    assert model_readiness_diagnostics([{"prediction": "A", "model_probability": 0.6, "result": "win"}])["advisory_shadow_readiness_status"] == NEEDS_EVENT_IDENTITY


def test_zero_usable_and_small_sample_statuses():
    assert model_readiness_diagnostics([_row(1, "pending")])["advisory_shadow_readiness_status"] == NEEDS_GRADED_ROWS
    rows = [_row(i, "win" if i % 2 else "loss") for i in range(1, 20)]
    assert model_readiness_diagnostics(rows)["advisory_shadow_readiness_status"] == NEEDS_MORE_COMPLETED_EVENTS


def test_outcome_diversity_and_duplicate_heavy():
    rows = [_row(i, "win") for i in range(1, 60)]
    assert model_readiness_diagnostics(rows)["advisory_shadow_readiness_status"] == NEEDS_OUTCOME_DIVERSITY
    duplicate_rows = [_row(1, "win" if i % 2 else "loss") for i in range(60)]
    assert model_readiness_diagnostics(duplicate_rows)["advisory_shadow_readiness_status"] == DUPLICATE_HEAVY_SAMPLE


def test_push_cancel_pending_are_excluded_from_usable_counts():
    rows = [_row(1, "win"), _row(2, "loss"), _row(3, "push"), _row(4, "cancelled"), _row(5, "pending")]
    diag = model_readiness_diagnostics(rows)
    assert diag["advisory_shadow_win_count"] == 1
    assert diag["advisory_shadow_loss_count"] == 1
    assert diag["advisory_shadow_push_count"] == 1
    assert diag["advisory_shadow_cancel_count"] == 1
    assert diag["advisory_shadow_graded_usable_count"] == 2


def test_multiple_rows_same_event_count_as_one_unique_event():
    rows = [_row(1, "win"), _row(1, "loss"), _row(2, "win")]
    diag = model_readiness_diagnostics(rows)
    assert diag["advisory_shadow_unique_event_count"] == 2
    assert diag["advisory_shadow_duplicate_row_count"] == 1


def test_probability_percent_conversion_and_brier():
    rows = [_row(1, "win", 60), _row(2, "loss", 40)]
    assert probability_value(rows[0]) == 0.6
    available, score = brier_score(rows, "result")
    assert available is True
    assert score is not None


def test_ready_status_and_observation_only_fields():
    rows = [_row(i, "win" if i % 2 else "loss", 0.6) for i in range(1, 120)]
    diag = model_readiness_diagnostics(rows)
    assert diag["advisory_shadow_readiness_status"] == SHADOW_READY
    assert diag["advisory_shadow_observation_only"] is True
    assert diag["advisory_shadow_live_mutation_allowed"] is False


def test_apply_fields_does_not_mutate_input():
    rows = [_row(1, "win"), _row(2, "loss")]
    before = deepcopy(rows)
    out = apply_model_readiness_fields(rows)
    assert rows == before
    assert "advisory_shadow_readiness_status" in out[0]


def test_summary_frame_has_shadow_fields():
    frame = model_readiness_summary([_row(1, "win"), _row(2, "loss")])
    assert "advisory_shadow_readiness_status" in frame.columns
    assert "advisory_shadow_readiness_score" in frame.columns
