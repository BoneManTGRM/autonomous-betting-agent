from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import pandas as pd

from .report_product_layer import decimal_price, has_verified_odds, pct, safe_float, safe_text, tennis_blocked

GRADE_COLUMNS = (
    "result", "final_result", "grade", "outcome", "bet_result", "status", "settled_status",
    "win_loss", "final_grade", "pick_result", "settlement_status",
)
PNL_COLUMNS = ("profit_loss", "pnl", "profit", "net_profit", "roi", "return_units", "units")

WIN_TOKENS = {"win", "won", "winner", "w", "graded_win", "cash", "cashed", "success"}
LOSS_TOKENS = {"loss", "lost", "loser", "l", "graded_loss", "failed", "lose"}
PUSH_TOKENS = {"push", "void", "tie", "draw", "refund", "returned", "half_push"}
CANCEL_TOKENS = {"cancel", "cancelled", "canceled", "postponed", "abandoned", "no contest", "no_action", "n/a"}
PENDING_TOKENS = {"pending", "open", "ungraded", "not graded", "scheduled", "live", "unknown"}


@dataclass(frozen=True)
class CalibrationRule:
    min_sample: int = 25
    min_roi: float = 0.01
    min_win_rate_over_breakeven: float = 0.02


def normalize_grade(row: Mapping[str, Any]) -> str:
    for name in GRADE_COLUMNS:
        raw = safe_text(row.get(name)).lower().replace("_", " ").strip()
        if not raw:
            continue
        if raw in WIN_TOKENS or raw.startswith("win"):
            return "WIN"
        if raw in LOSS_TOKENS or raw.startswith("loss") or raw.startswith("lost"):
            return "LOSS"
        if raw in PUSH_TOKENS or any(token in raw for token in ("push", "void", "refund")):
            return "PUSH"
        if raw in CANCEL_TOKENS or any(token in raw for token in ("cancel", "postpon", "abandon")):
            return "CANCELLED"
        if raw in PENDING_TOKENS or any(token in raw for token in ("pending", "open", "scheduled")):
            return "PENDING"
    return "UNKNOWN"


def profit_units(row: Mapping[str, Any]) -> float | None:
    for name in PNL_COLUMNS:
        value = safe_float(row.get(name))
        if value is not None:
            return value
    grade = normalize_grade(row)
    price = decimal_price(row)
    if grade == "WIN" and price is not None:
        return price - 1.0
    if grade == "LOSS":
        return -1.0
    if grade in {"PUSH", "CANCELLED"}:
        return 0.0
    return None


def model_lean(model_prob: float | None) -> str:
    if model_prob is None:
        return "Unknown"
    if model_prob >= 0.72:
        return "Strong"
    if model_prob >= 0.62:
        return "Medium"
    return "Low"


def price_value(edge: float | None, ev: float | None) -> str:
    if edge is None or ev is None:
        return "Unknown"
    if edge >= 0.02 and ev >= 0.02:
        return "Positive"
    if edge > 0 and ev > 0:
        return "Thin"
    return "Negative at listed odds"


def data_issue_reason(row: Mapping[str, Any]) -> str:
    if tennis_blocked(row):
        return "Unsupported sport"
    if not has_verified_odds(row):
        return "Missing or unverified odds"
    if row.get("model_probability") is None:
        return "Missing independent model probability"
    return ""


def official_status(row: Mapping[str, Any]) -> str:
    if data_issue_reason(row):
        return "Data Blocked"
    if bool(row.get("official_publish_ready") or row.get("publish_ready")):
        return "Official +EV"
    value = safe_text(row.get("price_value_label"))
    if value == "Thin":
        return "Watchlist"
    return "Research / Not Official"


def learning_status(grade: str, blocked: bool) -> str:
    if blocked:
        return "Excluded: data blocked"
    if grade in {"WIN", "LOSS", "PUSH", "CANCELLED"}:
        return "Included in calibration"
    if grade == "PENDING":
        return "Needs grading"
    return "Needs grading"


def consumer_action(row: Mapping[str, Any]) -> str:
    blocked_reason = safe_text(row.get("data_issue_reason"))
    if blocked_reason:
        return f"Blocked: {blocked_reason}"
    if bool(row.get("official_publish_ready") or row.get("publish_ready")):
        return "Official +EV Play"
    value = safe_text(row.get("price_value_label"))
    lean = safe_text(row.get("model_lean_label"))
    if value == "Thin":
        return "Watchlist / thin value"
    if value == "Negative at listed odds" and lean in {"Strong", "Medium"}:
        return "Price Watch / Research"
    return "Research / Track for Learning"


def report_lane_v2(row: Mapping[str, Any]) -> str:
    grade = safe_text(row.get("result_status"))
    if grade == "WIN":
        return "graded_winner"
    if grade == "LOSS":
        return "graded_loss"
    blocked = safe_text(row.get("data_issue_reason"))
    if blocked == "Unsupported sport":
        return "unsupported_sport"
    if blocked:
        return "data_blocked"
    if bool(row.get("official_publish_ready") or row.get("publish_ready")):
        return "official_ev_play"
    if safe_text(row.get("price_value_label")) == "Thin":
        return "strong_prediction_price_watch"
    if safe_text(row.get("model_lean_label")) in {"Strong", "Medium"}:
        return "learning_candidate"
    return "research_play"


def apply_learning_layer(cards: pd.DataFrame) -> pd.DataFrame:
    frame = pd.DataFrame(cards).copy()
    if frame.empty:
        return frame
    records: list[dict[str, Any]] = []
    for _, row in frame.iterrows():
        item = row.to_dict()
        grade = normalize_grade(item)
        blocked_reason = data_issue_reason(item)
        edge = item.get("model_market_edge")
        ev = item.get("expected_value_per_unit")
        official_ready = bool(item.get("publish_ready")) and not blocked_reason
        enriched = dict(item)
        enriched["result_status"] = grade
        enriched["profit_units"] = profit_units(item)
        enriched["model_lean_label"] = model_lean(item.get("model_probability"))
        enriched["price_value_label"] = price_value(edge, ev)
        enriched["data_issue_reason"] = blocked_reason
        enriched["official_publish_ready"] = official_ready
        enriched["client_report_ready"] = not bool(blocked_reason)
        enriched["learning_ready"] = (not bool(blocked_reason)) and grade in {"WIN", "LOSS", "PUSH", "CANCELLED"}
        enriched["official_status_label"] = official_status(enriched)
        enriched["learning_status"] = learning_status(grade, bool(blocked_reason))
        enriched["consumer_action"] = consumer_action(enriched)
        enriched["report_lane_v2"] = report_lane_v2(enriched)
        if enriched.get("report_lane") == "no_play" and not blocked_reason:
            enriched["report_lane"] = "research"
        enriched["recommended_action"] = enriched["consumer_action"]
        enriched["public_action"] = enriched["consumer_action"]
        records.append(enriched)
    return pd.DataFrame(records)


def edge_bucket(value: Any) -> str:
    edge = safe_float(value)
    if edge is None:
        return "unknown"
    if edge < -0.05:
        return "below -5%"
    if edge < -0.03:
        return "-5% to -3%"
    if edge < -0.01:
        return "-3% to -1%"
    if edge < 0:
        return "-1% to 0%"
    if edge < 0.01:
        return "0% to +1%"
    if edge < 0.02:
        return "+1% to +2%"
    return "+2% and higher"


def probability_bucket(value: Any) -> str:
    prob = safe_float(value)
    if prob is None:
        return "unknown"
    if prob > 1:
        prob = prob / 100.0
    if prob < 0.55:
        return "50-55%"
    if prob < 0.60:
        return "55-60%"
    if prob < 0.65:
        return "60-65%"
    if prob < 0.70:
        return "65-70%"
    if prob < 0.75:
        return "70-75%"
    return "75%+"


def _break_even_roi(frame: pd.DataFrame) -> float:
    if frame.empty or "decimal_price" not in frame.columns:
        return 0.0
    prices = pd.to_numeric(frame["decimal_price"], errors="coerce").dropna()
    if prices.empty:
        return 0.0
    return float((1.0 / prices.mean()) if prices.mean() > 0 else 0.0)


def summarize_group(frame: pd.DataFrame, group_col: str, *, rule: CalibrationRule | None = None) -> pd.DataFrame:
    rule = rule or CalibrationRule()
    if frame.empty or group_col not in frame.columns:
        return pd.DataFrame(columns=[group_col, "sample_size", "wins", "losses", "pushes", "win_rate", "roi", "suggestion"])
    rows = []
    for key, group in frame.groupby(group_col, dropna=False):
        graded = group[group["result_status"].isin(["WIN", "LOSS", "PUSH", "CANCELLED"])]
        wins = int(graded["result_status"].eq("WIN").sum())
        losses = int(graded["result_status"].eq("LOSS").sum())
        pushes = int(graded["result_status"].isin(["PUSH", "CANCELLED"]).sum())
        decisions = wins + losses
        win_rate = wins / decisions if decisions else 0.0
        pnl = pd.to_numeric(graded.get("profit_units", pd.Series(dtype=float)), errors="coerce").fillna(0.0)
        roi = float(pnl.sum() / decisions) if decisions else 0.0
        breakeven = _break_even_roi(graded)
        if decisions >= rule.min_sample and roi > rule.min_roi and win_rate > breakeven + rule.min_win_rate_over_breakeven:
            suggestion = "Research upgrade candidate"
        elif decisions and roi > 0:
            suggestion = "Calibration opportunity / needs larger sample"
        elif decisions:
            suggestion = "Monitor / no promotion"
        else:
            suggestion = "Needs grading"
        rows.append({group_col: key, "sample_size": int(len(graded)), "wins": wins, "losses": losses, "pushes": pushes, "win_rate": win_rate, "roi": roi, "suggestion": suggestion})
    return pd.DataFrame(rows).sort_values(["roi", "win_rate", "sample_size"], ascending=[False, False, False])


def calibration_audit(cards: pd.DataFrame, *, min_sample: int = 25) -> dict[str, pd.DataFrame]:
    frame = apply_learning_layer(cards)
    if frame.empty:
        return {}
    frame["edge_bucket"] = frame["model_market_edge"].map(edge_bucket) if "model_market_edge" in frame.columns else "unknown"
    frame["model_probability_bucket"] = frame["model_probability"].map(probability_bucket) if "model_probability" in frame.columns else "unknown"
    if "market_type" not in frame.columns:
        frame["market_type"] = frame.get("prediction", pd.Series(dtype=str)).map(lambda x: safe_text(x).split(":")[0] if safe_text(x) else "unknown")
    rule = CalibrationRule(min_sample=min_sample)
    return {
        "by_sport": summarize_group(frame, "sport", rule=rule) if "sport" in frame.columns else pd.DataFrame(),
        "by_league": summarize_group(frame, "league", rule=rule) if "league" in frame.columns else pd.DataFrame(),
        "by_market_type": summarize_group(frame, "market_type", rule=rule),
        "by_edge_bucket": summarize_group(frame, "edge_bucket", rule=rule),
        "by_model_probability_bucket": summarize_group(frame, "model_probability_bucket", rule=rule),
        "by_report_lane": summarize_group(frame, "report_lane_v2", rule=rule),
        "negative_edge_winners": frame[(pd.to_numeric(frame.get("model_market_edge", pd.Series(dtype=float)), errors="coerce") < 0) & frame["result_status"].eq("WIN")].copy(),
    }
