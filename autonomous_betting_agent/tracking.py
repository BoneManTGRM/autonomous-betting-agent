from __future__ import annotations

import csv
import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from statistics import mean
from typing import Any, Iterable, Mapping, Sequence

from .learning import clamp_probability, log_loss as probability_log_loss

RESULT_WIN = "won"
RESULT_LOSS = "lost"
RESULT_PUSH = "push"
RESULT_PENDING = "pending"


@dataclass(frozen=True)
class SelectionPolicy:
    """Rules used to reduce weak picks and keep only stronger candidates.

    This does not guarantee profit. It increases selectivity by requiring the
    calibrated probability to clear the sportsbook implied probability by a
    measurable edge.
    """

    min_pick_probability: float = 0.54
    min_edge: float = 0.025
    strong_pick_probability: float = 0.60
    strong_edge: float = 0.05
    max_overround: float | None = 0.08


@dataclass(frozen=True)
class SelectionDecision:
    decision: str
    reason: str
    edge: float | None
    implied_probability: float | None
    expected_value: float | None


@dataclass(frozen=True)
class PredictionLedgerRow:
    event_name: str
    sport: str = ""
    predicted_winner: str = ""
    actual_winner: str = ""
    model_probability: float | None = None
    calibrated_probability: float | None = None
    sportsbook_odds: float | None = None
    implied_probability: float | None = None
    edge: float | None = None
    expected_value: float | None = None
    result: str = RESULT_PENDING
    stake: float = 1.0
    profit_loss: float | None = None
    closing_odds: float | None = None
    closing_implied_probability: float | None = None
    closing_line_value: float | None = None
    confidence_bucket: str = "unknown"
    decision: str = "UNRATED"
    decision_reason: str = ""
    bookmaker_count: int | None = None
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GroupSummary:
    name: str
    picks: int
    wins: int
    losses: int
    pushes: int
    hit_rate: float | None
    average_calibrated_probability: float | None
    brier_score: float | None
    log_loss: float | None
    profit_loss: float
    roi: float | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TrackingReport:
    total_rows: int
    resolved_picks: int
    wins: int
    losses: int
    pushes: int
    hit_rate: float | None
    average_model_probability: float | None
    average_calibrated_probability: float | None
    brier_score: float | None
    log_loss: float | None
    profit_loss: float
    roi: float | None
    average_edge: float | None
    average_closing_line_value: float | None
    by_decision: list[GroupSummary] = field(default_factory=list)
    by_confidence_bucket: list[GroupSummary] = field(default_factory=list)
    by_sport: list[GroupSummary] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "by_decision": [item.to_dict() for item in self.by_decision],
            "by_confidence_bucket": [item.to_dict() for item in self.by_confidence_bucket],
            "by_sport": [item.to_dict() for item in self.by_sport],
        }


def decimal_to_implied_probability(decimal_odds: float | None) -> float | None:
    if decimal_odds is None or decimal_odds <= 1.0:
        return None
    return 1.0 / decimal_odds


def expected_value(probability: float | None, decimal_odds: float | None) -> float | None:
    if probability is None or decimal_odds is None or decimal_odds <= 1.0:
        return None
    return clamp_probability(probability) * decimal_odds - 1.0


def confidence_bucket(probability: float | None) -> str:
    if probability is None:
        return "unknown"
    probability = clamp_probability(probability)
    percent = probability * 100.0
    if percent < 50.0:
        return "under 50%"
    if percent < 55.0:
        return "50-55%"
    if percent < 60.0:
        return "55-60%"
    if percent < 65.0:
        return "60-65%"
    if percent < 70.0:
        return "65-70%"
    if percent < 80.0:
        return "70-80%"
    return "80%+"


def normalize_result(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"won", "win", "w", "correct", "hit", "true", "yes", "1"}:
        return RESULT_WIN
    if text in {"lost", "loss", "l", "incorrect", "miss", "false", "no", "0"}:
        return RESULT_LOSS
    if text in {"push", "void", "tie", "draw_refund", "refund"}:
        return RESULT_PUSH
    return RESULT_PENDING


def compute_profit_loss(result: str, decimal_odds: float | None, stake: float = 1.0) -> float | None:
    result = normalize_result(result)
    if result == RESULT_WIN:
        if decimal_odds is None or decimal_odds <= 1.0:
            return None
        return stake * (decimal_odds - 1.0)
    if result == RESULT_LOSS:
        return -stake
    if result == RESULT_PUSH:
        return 0.0
    return None


def choose_decision(
    calibrated_probability: float | None,
    sportsbook_odds: float | None,
    *,
    market_overround: float | None = None,
    policy: SelectionPolicy = SelectionPolicy(),
) -> SelectionDecision:
    implied = decimal_to_implied_probability(sportsbook_odds)
    ev = expected_value(calibrated_probability, sportsbook_odds)
    if calibrated_probability is None or implied is None or ev is None:
        return SelectionDecision("AVOID", "missing probability or sportsbook odds", None, implied, ev)

    probability = clamp_probability(calibrated_probability)
    edge = probability - implied
    if market_overround is not None and policy.max_overround is not None and market_overround > policy.max_overround:
        return SelectionDecision("AVOID", "market overround is too high", edge, implied, ev)
    if probability >= policy.strong_pick_probability and edge >= policy.strong_edge and ev > 0.0:
        return SelectionDecision("STRONG", "probability and edge cleared strong thresholds", edge, implied, ev)
    if probability >= policy.min_pick_probability and edge >= policy.min_edge and ev > 0.0:
        return SelectionDecision("WATCH", "positive edge cleared minimum thresholds", edge, implied, ev)
    return SelectionDecision("AVOID", "edge or probability below threshold", edge, implied, ev)


def enrich_row(row: PredictionLedgerRow, policy: SelectionPolicy = SelectionPolicy()) -> PredictionLedgerRow:
    probability = row.calibrated_probability if row.calibrated_probability is not None else row.model_probability
    implied = row.implied_probability if row.implied_probability is not None else decimal_to_implied_probability(row.sportsbook_odds)
    edge = row.edge if row.edge is not None else (None if probability is None or implied is None else probability - implied)
    ev = row.expected_value if row.expected_value is not None else expected_value(probability, row.sportsbook_odds)
    result = normalize_result(row.result)
    profit_loss = row.profit_loss if row.profit_loss is not None else compute_profit_loss(result, row.sportsbook_odds, row.stake)
    closing_implied = row.closing_implied_probability if row.closing_implied_probability is not None else decimal_to_implied_probability(row.closing_odds)
    clv = row.closing_line_value
    if clv is None and implied is not None and closing_implied is not None:
        clv = closing_implied - implied
    decision = choose_decision(probability, row.sportsbook_odds, policy=policy)
    return PredictionLedgerRow(
        event_name=row.event_name,
        sport=row.sport,
        predicted_winner=row.predicted_winner,
        actual_winner=row.actual_winner,
        model_probability=row.model_probability,
        calibrated_probability=row.calibrated_probability,
        sportsbook_odds=row.sportsbook_odds,
        implied_probability=implied,
        edge=edge,
        expected_value=ev,
        result=result,
        stake=row.stake,
        profit_loss=profit_loss,
        closing_odds=row.closing_odds,
        closing_implied_probability=closing_implied,
        closing_line_value=clv,
        confidence_bucket=confidence_bucket(probability),
        decision=decision.decision if row.decision in {"", "UNRATED"} else row.decision,
        decision_reason=decision.reason if not row.decision_reason else row.decision_reason,
        bookmaker_count=row.bookmaker_count,
        notes=row.notes,
    )


def summarize_tracking(rows: Sequence[PredictionLedgerRow]) -> TrackingReport:
    enriched = [enrich_row(row) for row in rows]
    resolved = [row for row in enriched if row.result in {RESULT_WIN, RESULT_LOSS, RESULT_PUSH}]
    wins = sum(1 for row in resolved if row.result == RESULT_WIN)
    losses = sum(1 for row in resolved if row.result == RESULT_LOSS)
    pushes = sum(1 for row in resolved if row.result == RESULT_PUSH)
    decisions = _summarize_groups(resolved, lambda row: row.decision or "UNRATED")
    buckets = _summarize_groups(resolved, lambda row: row.confidence_bucket)
    sports = _summarize_groups(resolved, lambda row: row.sport or "unknown")
    return TrackingReport(
        total_rows=len(enriched),
        resolved_picks=len(resolved),
        wins=wins,
        losses=losses,
        pushes=pushes,
        hit_rate=_safe_rate(wins, wins + losses),
        average_model_probability=_mean_values(row.model_probability for row in resolved),
        average_calibrated_probability=_mean_values(row.calibrated_probability for row in resolved),
        brier_score=_brier(resolved),
        log_loss=_log_loss(resolved),
        profit_loss=sum(row.profit_loss for row in resolved if row.profit_loss is not None),
        roi=_roi(resolved),
        average_edge=_mean_values(row.edge for row in resolved),
        average_closing_line_value=_mean_values(row.closing_line_value for row in resolved),
        by_decision=decisions,
        by_confidence_bucket=buckets,
        by_sport=sports,
    )


def read_prediction_csv(path: str | Path) -> list[PredictionLedgerRow]:
    rows: list[PredictionLedgerRow] = []
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for index, raw in enumerate(reader, start=2):
            normalized = {_clean_key(key): value for key, value in raw.items() if key is not None}
            rows.append(_row_from_mapping(normalized, index))
    return rows


def write_ledger_csv(rows: Sequence[PredictionLedgerRow], path: str | Path) -> None:
    enriched = [enrich_row(row) for row in rows]
    fieldnames = list(PredictionLedgerRow("example").to_dict().keys())
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in enriched:
            writer.writerow(row.to_dict())


def write_report_json(report: TrackingReport, path: str | Path) -> None:
    Path(path).write_text(json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _row_from_mapping(row: Mapping[str, Any], index: int) -> PredictionLedgerRow:
    model_probability = _probability(row, ("model_probability", "predicted_probability", "probability", "favorite_probability"))
    calibrated_probability = _probability(row, ("calibrated_probability", "adjusted_probability"))
    sportsbook_odds = _float(row, ("sportsbook_odds", "best_price", "average_price", "avg_price", "decimal_odds", "odds", "price"))
    closing_odds = _float(row, ("closing_odds", "closing_price", "close_price"))
    stake = _float(row, ("stake", "unit_stake", "units")) or 1.0
    result = normalize_result(_text(row, ("result", "outcome", "win_loss", "graded_result", "status")))
    predicted = _text(row, ("predicted_winner", "prediction", "pick", "favored_side", "favorite"))
    actual = _text(row, ("actual_winner", "winner", "winning_side", "final_winner"))
    if result == RESULT_PENDING and predicted and actual:
        result = RESULT_WIN if predicted.strip().lower() == actual.strip().lower() else RESULT_LOSS
    return PredictionLedgerRow(
        event_name=_text(row, ("event_name", "event", "game", "match", "fixture")) or f"row {index}",
        sport=_text(row, ("sport", "league", "competition")),
        predicted_winner=predicted,
        actual_winner=actual,
        model_probability=model_probability,
        calibrated_probability=calibrated_probability,
        sportsbook_odds=sportsbook_odds,
        implied_probability=_probability(row, ("implied_probability", "sportsbook_implied_probability")),
        edge=_probability(row, ("edge", "model_edge")),
        expected_value=_float(row, ("expected_value", "ev", "unit_edge")),
        result=result,
        stake=stake,
        profit_loss=_float(row, ("profit_loss", "p_l", "pl", "units_profit_loss")),
        closing_odds=closing_odds,
        closing_implied_probability=_probability(row, ("closing_implied_probability", "closing_probability")),
        closing_line_value=_probability(row, ("closing_line_value", "clv")),
        confidence_bucket=_text(row, ("confidence_bucket", "bucket")) or "unknown",
        decision=_text(row, ("decision", "recommendation", "grade")) or "UNRATED",
        decision_reason=_text(row, ("decision_reason", "reason")),
        bookmaker_count=_int(row, ("bookmaker_count", "books", "source_count")),
        notes=_text(row, ("notes", "note")),
    )


def _summarize_groups(rows: Sequence[PredictionLedgerRow], key_fn) -> list[GroupSummary]:
    groups: dict[str, list[PredictionLedgerRow]] = {}
    for row in rows:
        groups.setdefault(str(key_fn(row)), []).append(row)
    summaries = [_summarize_group(name, group_rows) for name, group_rows in groups.items()]
    return sorted(summaries, key=lambda item: (-item.picks, item.name))


def _summarize_group(name: str, rows: Sequence[PredictionLedgerRow]) -> GroupSummary:
    wins = sum(1 for row in rows if row.result == RESULT_WIN)
    losses = sum(1 for row in rows if row.result == RESULT_LOSS)
    pushes = sum(1 for row in rows if row.result == RESULT_PUSH)
    profit_loss = sum(row.profit_loss for row in rows if row.profit_loss is not None)
    return GroupSummary(
        name=name,
        picks=len(rows),
        wins=wins,
        losses=losses,
        pushes=pushes,
        hit_rate=_safe_rate(wins, wins + losses),
        average_calibrated_probability=_mean_values(row.calibrated_probability for row in rows),
        brier_score=_brier(rows),
        log_loss=_log_loss(rows),
        profit_loss=profit_loss,
        roi=_roi(rows),
    )


def _brier(rows: Sequence[PredictionLedgerRow]) -> float | None:
    values = []
    for row in rows:
        probability = row.calibrated_probability if row.calibrated_probability is not None else row.model_probability
        if probability is None or row.result not in {RESULT_WIN, RESULT_LOSS}:
            continue
        outcome = 1 if row.result == RESULT_WIN else 0
        values.append((clamp_probability(probability) - outcome) ** 2)
    return mean(values) if values else None


def _log_loss(rows: Sequence[PredictionLedgerRow]) -> float | None:
    values = []
    for row in rows:
        probability = row.calibrated_probability if row.calibrated_probability is not None else row.model_probability
        if probability is None or row.result not in {RESULT_WIN, RESULT_LOSS}:
            continue
        values.append(probability_log_loss(probability, 1 if row.result == RESULT_WIN else 0))
    return mean(values) if values else None


def _roi(rows: Sequence[PredictionLedgerRow]) -> float | None:
    staked = sum(row.stake for row in rows if row.result in {RESULT_WIN, RESULT_LOSS})
    if staked <= 0.0:
        return None
    profit_loss = sum(row.profit_loss for row in rows if row.profit_loss is not None)
    return profit_loss / staked


def _safe_rate(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else numerator / denominator


def _mean_values(values: Iterable[float | None]) -> float | None:
    clean = [float(value) for value in values if value is not None]
    return mean(clean) if clean else None


def _clean_key(value: str) -> str:
    return value.strip().lower().replace(" ", "_").replace("-", "_")


def _text(row: Mapping[str, Any], keys: Iterable[str]) -> str:
    for key in keys:
        value = row.get(_clean_key(key))
        if value not in (None, ""):
            return str(value).strip()
    return ""


def _float(row: Mapping[str, Any], keys: Iterable[str]) -> float | None:
    for key in keys:
        value = row.get(_clean_key(key))
        if value in (None, ""):
            continue
        text = str(value).strip().replace("%", "")
        try:
            return float(text)
        except ValueError:
            continue
    return None


def _int(row: Mapping[str, Any], keys: Iterable[str]) -> int | None:
    value = _float(row, keys)
    return None if value is None else int(value)


def _probability(row: Mapping[str, Any], keys: Iterable[str]) -> float | None:
    value = _float(row, keys)
    if value is None:
        return None
    if 1.0 < value <= 100.0:
        value /= 100.0
    if -1.0 <= value <= 1.0:
        return value
    return None
