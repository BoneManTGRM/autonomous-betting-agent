from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from autonomous_betting_agent.dynamic_odds_predictor import build_lr_training_rows, learn_lr_multipliers
from autonomous_betting_agent.pick_hold_store import normalize_workspace_id

SCHEMA_VERSION = "dynamic_odds_shadow_model_v1"
SHADOW_ONLY = "SHADOW ONLY"
OFFLINE_ONLY = "OFFLINE_ONLY"
FORBIDDEN = "FORBIDDEN"
MODEL_DIR = Path("data/adaptive_repair/dynamic_odds_shadow_model")
AUDIT_DIR = Path("data/adaptive_repair/dynamic_odds_shadow_audit")

GLOBAL_BASELINE = 0.70
BASELINE_FLOOR = 0.68
MINIMUM_ROWS_BEFORE_LOWERING_BASELINE = 150
MINIMUM_ROWS_BEFORE_SEGMENT_OVERRIDE = 300
BASELINE_PRIOR_WEIGHT = 150

RESULT_KEYS = (
    "result",
    "grade",
    "outcome",
    "official_result",
    "final_result",
    "result_status",
    "pick_result",
    "settled_status",
)
PUSH_TOKENS = ("push", "void", "cancel", "cancelled", "canceled")
WIN_TOKENS = ("win", "won", "w")
LOSS_TOKENS = ("loss", "lost", "l")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _model_path(workspace_id: Any = "test_01") -> Path:
    return MODEL_DIR / f"dynamic_odds_shadow_model_{normalize_workspace_id(workspace_id)}.json"


def model_path_string(workspace_id: Any = "test_01") -> str:
    return str(_model_path(workspace_id))


def _audit_path(workspace_id: Any = "test_01") -> Path:
    return AUDIT_DIR / f"dynamic_odds_shadow_audit_{normalize_workspace_id(workspace_id)}.jsonl"


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(val) for key, val in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, float):
        return round(value, 10)
    if value is None or isinstance(value, (str, int, bool)):
        return value
    return str(value)


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _result_text(row: Mapping[str, Any]) -> str:
    for key in RESULT_KEYS:
        text = _text(row.get(key)).lower()
        if text:
            return text
    return ""


def classify_result(row: Mapping[str, Any]) -> str:
    text = _result_text(row)
    tokens = set(text.replace("_", " ").replace("-", " ").split())
    if not text:
        return "pending"
    if any(token in text for token in PUSH_TOKENS):
        return "push_excluded"
    if tokens & set(WIN_TOKENS) or "won" in text or "win" in text:
        return "win"
    if tokens & set(LOSS_TOKENS) or "lost" in text or "loss" in text:
        return "loss"
    return "pending"


def training_result_stats(rows: Sequence[Mapping[str, Any]] | None) -> dict[str, int]:
    uploaded = len(list(rows or []))
    wins = losses = pushes = pending = 0
    for row in rows or []:
        if not isinstance(row, Mapping):
            continue
        result = classify_result(row)
        if result == "win":
            wins += 1
        elif result == "loss":
            losses += 1
        elif result == "push_excluded":
            pushes += 1
        else:
            pending += 1
    completed = wins + losses
    return {
        "uploaded_rows": uploaded,
        "completed_rows": completed,
        "completed_rows_seen": completed,
        "wins": wins,
        "losses": losses,
        "pushes_excluded": pushes,
        "pending_rows": pending,
    }


def completed_win_loss_rows(rows: Sequence[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
    completed = []
    for row in rows or []:
        if not isinstance(row, Mapping):
            continue
        if classify_result(row) in {"win", "loss"}:
            completed.append(deepcopy(dict(row)))
    return completed


def safety_summary() -> dict[str, Any]:
    return {
        "dynamic_odds_predictor": SHADOW_ONLY,
        "dynamic_odds_live_activation": "OFF",
        "dynamic_odds_applied_live": 0,
        "dynamic_odds_applied_live_count": 0,
        "live_mutation": FORBIDDEN,
        "model_training": FORBIDDEN,
        "official_model_training": FORBIDDEN,
        "live_model_training": FORBIDDEN,
        "stored_data_mutation": FORBIDDEN,
        "repair_activation": "OFF",
        "automatic_live_promotion": FORBIDDEN,
        "shadow_model_training": OFFLINE_ONLY,
    }


def protected_baseline_metrics(wins: int, losses: int, config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    cfg = dict(config or {})
    global_baseline = float(cfg.get("global_baseline", GLOBAL_BASELINE))
    baseline_floor = float(cfg.get("baseline_floor", BASELINE_FLOOR))
    min_lower = int(cfg.get("minimum_rows_before_lowering_baseline", MINIMUM_ROWS_BEFORE_LOWERING_BASELINE))
    min_override = int(cfg.get("minimum_rows_before_segment_override", MINIMUM_ROWS_BEFORE_SEGMENT_OVERRIDE))
    prior_weight = int(cfg.get("baseline_prior_weight", BASELINE_PRIOR_WEIGHT))
    sample = int(wins) + int(losses)
    segment = (float(wins) / sample) if sample else None
    blended = ((global_baseline * prior_weight) + float(wins)) / (prior_weight + sample) if sample else global_baseline
    floor_active = sample < min_lower and blended < baseline_floor
    protected = max(baseline_floor, blended) if sample < min_lower else blended
    if sample >= min_override and segment is not None:
        baseline_source = "strong_segment_observed_with_global_prior"
    elif sample >= min_lower:
        baseline_source = "usable_segment_blended_with_global_prior"
    elif sample > 0:
        baseline_source = "user_global_baseline_prior_with_floor"
    else:
        baseline_source = "user_global_baseline_prior_no_data"
    confidence = "VERY STRONG SAMPLE" if sample >= 300 else "STRONG SAMPLE" if sample >= 150 else "USABLE SAMPLE" if sample >= 75 else "WEAK SAMPLE" if sample >= 25 else "DATA BLOCKED"
    return {
        "global_baseline": round(global_baseline, 6),
        "segment_baseline": round(segment, 6) if segment is not None else None,
        "protected_baseline": round(float(protected), 6),
        "baseline_floor": round(baseline_floor, 6),
        "baseline_floor_active": bool(floor_active),
        "baseline_source": baseline_source,
        "baseline_confidence": confidence,
        "baseline_prior_weight": prior_weight,
        "segment_sample_size": sample,
        "minimum_rows_before_lowering_baseline": min_lower,
        "minimum_rows_before_segment_override": min_override,
        "segment_underperforming": bool(segment is not None and segment < global_baseline),
        "segment_outperforming": bool(segment is not None and segment > global_baseline),
        "baseline_protection_active": bool(sample < min_lower or floor_active),
    }


def model_quality_summary(stats: Mapping[str, Any], lr_model: Mapping[str, Any] | None = None) -> dict[str, Any]:
    completed = int(stats.get("completed_rows_seen") or stats.get("completed_rows") or 0)
    label = "VERY STRONG SAMPLE" if completed >= 300 else "STRONG SAMPLE" if completed >= 150 else "USABLE SAMPLE" if completed >= 75 else "WEAK SAMPLE" if completed >= 25 else "DATA BLOCKED"
    reason = {
        "DATA BLOCKED": "fewer_than_25_completed_win_loss_rows",
        "WEAK SAMPLE": "25_to_74_completed_win_loss_rows",
        "USABLE SAMPLE": "75_to_149_completed_win_loss_rows",
        "STRONG SAMPLE": "150_to_299_completed_win_loss_rows",
        "VERY STRONG SAMPLE": "300_or_more_completed_win_loss_rows",
    }[label]
    feature_values = list(((lr_model or {}).get("lr_by_feature") or {}).values()) if isinstance((lr_model or {}).get("lr_by_feature"), Mapping) else []
    strong = sum(1 for item in feature_values if int(item.get("sample_size") or 0) >= 100)
    weak = sum(1 for item in feature_values if 25 <= int(item.get("sample_size") or 0) < 100)
    insufficient = sum(1 for item in feature_values if int(item.get("sample_size") or 0) < 25)
    return {
        "model_quality_label": label,
        "model_quality_reason": reason,
        "strong_feature_count": strong,
        "weak_feature_count": weak,
        "insufficient_feature_count": insufficient,
    }


def train_dynamic_odds_shadow_model(rows: Sequence[Mapping[str, Any]], workspace_id: Any = "test_01", config: Mapping[str, Any] | None = None, source: str | None = None) -> dict[str, Any]:
    workspace = normalize_workspace_id(workspace_id)
    safe_rows = [deepcopy(dict(row)) for row in rows or [] if isinstance(row, Mapping)]
    stats = training_result_stats(safe_rows)
    completed_rows = completed_win_loss_rows(safe_rows)
    training_rows = build_lr_training_rows(completed_rows, config)
    lr_model = learn_lr_multipliers(completed_rows, config)
    baseline = protected_baseline_metrics(stats["wins"], stats["losses"], config)
    quality = model_quality_summary(stats, lr_model)
    now = utc_now()
    lr_model.update({**baseline, **quality, **stats, "training_rows": int(lr_model.get("training_rows") or len(training_rows))})
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "workspace_id": workspace,
        "created_at_utc": now,
        "last_trained_at_utc": now,
        "updated_at_utc": now,
        "source": source or "graded_upload_shadow_trainer",
        "model_path": model_path_string(workspace),
        "leakage_guard": "ON",
        "lr_model": deepcopy(dict(lr_model or {})),
        **stats,
        **baseline,
        **quality,
        "training_rows_used": int(lr_model.get("training_rows") or 0),
        "feature_count": int(lr_model.get("feature_count") or 0),
        "baseline_success_rate": lr_model.get("baseline_success_rate"),
    }
    payload.update(safety_summary())
    return payload


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def save_dynamic_odds_shadow_model(model: Mapping[str, Any], workspace_id: Any = "test_01") -> dict[str, Any]:
    workspace = normalize_workspace_id(workspace_id or model.get("workspace_id", "test_01"))
    payload = deepcopy(dict(model or {}))
    payload.setdefault("schema_version", SCHEMA_VERSION)
    payload["workspace_id"] = workspace
    payload.setdefault("created_at_utc", utc_now())
    payload["updated_at_utc"] = utc_now()
    payload.setdefault("last_trained_at_utc", payload["updated_at_utc"])
    payload.setdefault("model_path", model_path_string(workspace))
    payload.update(safety_summary())
    _write_json(_model_path(workspace), payload)
    return payload


def write_shadow_training_audit_event(model: Mapping[str, Any], uploaded_rows: int | None = None, model_saved: bool = True) -> dict[str, Any]:
    payload = dict(model or {})
    workspace = normalize_workspace_id(payload.get("workspace_id", "test_01"))
    event = {
        "event_type": "dynamic_odds_shadow_model_training",
        "workspace_id": workspace,
        "timestamp": utc_now(),
        "uploaded_rows": int(uploaded_rows if uploaded_rows is not None else payload.get("uploaded_rows", 0) or 0),
        "completed_rows": int(payload.get("completed_rows_seen") or payload.get("completed_rows") or 0),
        "wins": int(payload.get("wins") or 0),
        "losses": int(payload.get("losses") or 0),
        "pushes_excluded": int(payload.get("pushes_excluded") or 0),
        "feature_count": int(payload.get("feature_count") or 0),
        "baseline_success_rate": payload.get("baseline_success_rate"),
        "global_baseline": payload.get("global_baseline", GLOBAL_BASELINE),
        "protected_baseline": payload.get("protected_baseline"),
        "segment_baseline": payload.get("segment_baseline"),
        "model_quality_label": payload.get("model_quality_label"),
        "baseline_protection_active": bool(payload.get("baseline_protection_active", False)),
        "model_saved": bool(model_saved),
        "model_path": payload.get("model_path", model_path_string(workspace)),
        "leakage_guard": "ON",
        **safety_summary(),
    }
    path = _audit_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_json_safe(event), ensure_ascii=False, sort_keys=True) + "\n")
    return event


def train_and_save_dynamic_odds_shadow_model(rows: Sequence[Mapping[str, Any]], workspace_id: Any = "test_01", config: Mapping[str, Any] | None = None, source: str | None = None) -> dict[str, Any]:
    model = train_dynamic_odds_shadow_model(rows, workspace_id, config, source)
    saved = save_dynamic_odds_shadow_model(model, workspace_id)
    write_shadow_training_audit_event(saved, uploaded_rows=len(list(rows or [])), model_saved=True)
    return saved


def load_dynamic_odds_shadow_model(workspace_id: Any = "test_01") -> dict[str, Any]:
    path = _model_path(workspace_id)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    payload.update(safety_summary())
    return payload


def delete_dynamic_odds_shadow_model(workspace_id: Any = "test_01") -> None:
    try:
        _model_path(workspace_id).unlink(missing_ok=True)
    except Exception:
        pass


clear_dynamic_odds_shadow_model = delete_dynamic_odds_shadow_model


def runtime_lr_model(model_payload: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = dict(model_payload or {})
    lr_model = deepcopy(dict(payload.get("lr_model") or {}))
    if not lr_model and "lr_by_feature" in payload:
        lr_model = deepcopy(payload)
    for key in (
        "workspace_id", "last_trained_at_utc", "completed_rows_seen", "training_rows_used", "wins", "losses", "pushes_excluded",
        "global_baseline", "segment_baseline", "protected_baseline", "baseline_floor", "baseline_floor_active", "baseline_source",
        "baseline_confidence", "baseline_prior_weight", "segment_sample_size", "segment_underperforming", "segment_outperforming",
        "model_quality_label", "model_quality_reason", "baseline_protection_active", "strong_feature_count", "weak_feature_count",
        "insufficient_feature_count",
    ):
        if key in payload and key not in lr_model:
            lr_model[key] = payload[key]
    lr_model["workspace_id"] = payload.get("workspace_id", lr_model.get("workspace_id", ""))
    lr_model["model_source"] = "saved_shadow_model" if payload else "no_model"
    lr_model["last_trained_at_utc"] = payload.get("last_trained_at_utc", lr_model.get("last_trained_at_utc", ""))
    lr_model["dynamic_odds_applied_live_count"] = 0
    lr_model.update(safety_summary())
    return lr_model


def infer_workspace_id(rows: Sequence[Mapping[str, Any]] | None, default: str = "test_01") -> str:
    for row in rows or []:
        if not isinstance(row, Mapping):
            continue
        for key in ("workspace_id", "test_window_id", "active_test_ledger", "ledger_workspace_id"):
            value = str(row.get(key, "") or "").strip()
            if value:
                return normalize_workspace_id(value)
    return normalize_workspace_id(default)


def shadow_model_status(model_payload: Mapping[str, Any] | None, source: str = "saved_model") -> dict[str, Any]:
    payload = dict(model_payload or {})
    lr_model = dict(payload.get("lr_model") or payload)
    return {
        "model_loaded": int(lr_model.get("feature_count") or 0) > 0,
        "model_source": source if payload else "no_model",
        "workspace_id": payload.get("workspace_id", lr_model.get("workspace_id", "")),
        "last_trained_at_utc": payload.get("last_trained_at_utc", lr_model.get("last_trained_at_utc", "")),
        "completed_rows_seen": int(payload.get("completed_rows_seen") or lr_model.get("completed_rows_seen") or 0),
        "training_rows_used": int(payload.get("training_rows_used") or lr_model.get("training_rows") or 0),
        "wins": int(payload.get("wins") or lr_model.get("wins") or 0),
        "losses": int(payload.get("losses") or lr_model.get("losses") or 0),
        "pushes_excluded": int(payload.get("pushes_excluded") or lr_model.get("pushes_excluded") or 0),
        "feature_count": int(payload.get("feature_count") or lr_model.get("feature_count") or 0),
        "baseline_success_rate": payload.get("baseline_success_rate") or lr_model.get("baseline_success_rate"),
        "global_baseline": payload.get("global_baseline", lr_model.get("global_baseline", GLOBAL_BASELINE)),
        "protected_baseline": payload.get("protected_baseline", lr_model.get("protected_baseline")),
        "segment_baseline": payload.get("segment_baseline", lr_model.get("segment_baseline")),
        "model_quality_label": payload.get("model_quality_label", lr_model.get("model_quality_label", "DATA BLOCKED")),
        "baseline_protection_active": bool(payload.get("baseline_protection_active", lr_model.get("baseline_protection_active", False))),
        "leakage_guard": payload.get("leakage_guard", "ON"),
        "dynamic_odds_live_activation": "OFF",
        "dynamic_odds_applied_live_count": 0,
        "shadow_model_training": OFFLINE_ONLY,
    }


def validate_shadow_model_payload(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    data = dict(payload or {})
    if data.get("schema_version") != SCHEMA_VERSION:
        errors.append("invalid_schema_version")
    if not str(data.get("workspace_id", "")).strip():
        errors.append("missing_workspace_id")
    if data.get("dynamic_odds_live_activation", "OFF") != "OFF":
        errors.append("dynamic_odds_live_activation_must_be_OFF")
    if int(data.get("dynamic_odds_applied_live", 0) or 0) != 0:
        errors.append("dynamic_odds_applied_live_must_be_0")
    if int(data.get("dynamic_odds_applied_live_count", 0) or 0) != 0:
        errors.append("dynamic_odds_applied_live_count_must_be_0")
    if data.get("live_mutation", FORBIDDEN) != FORBIDDEN:
        errors.append("live_mutation_must_be_FORBIDDEN")
    if data.get("automatic_live_promotion", FORBIDDEN) != FORBIDDEN:
        errors.append("automatic_live_promotion_must_be_FORBIDDEN")
    lr_model = data.get("lr_model")
    if not isinstance(lr_model, Mapping):
        errors.append("missing_lr_model")
    elif not isinstance(lr_model.get("lr_by_feature"), Mapping):
        errors.append("missing_lr_by_feature")
    return errors


def import_dynamic_odds_shadow_model_json(payload_text: str, workspace_id: Any | None = None) -> dict[str, Any]:
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid_json:{exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("invalid_json_payload")
    errors = validate_shadow_model_payload(payload)
    if errors:
        raise ValueError(";".join(errors))
    target_workspace = normalize_workspace_id(workspace_id or payload.get("workspace_id"))
    payload["workspace_id"] = target_workspace
    payload.update(safety_summary())
    return save_dynamic_odds_shadow_model(payload, target_workspace)


def export_dynamic_odds_shadow_model_json(workspace_id: Any = "test_01") -> str:
    payload = load_dynamic_odds_shadow_model(workspace_id)
    return json.dumps(_json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n" if payload else ""


def feature_influence_rows(model_payload_or_lr_model: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    payload = dict(model_payload_or_lr_model or {})
    lr_model = dict(payload.get("lr_model") or payload)
    lr_by_feature = lr_model.get("lr_by_feature") if isinstance(lr_model.get("lr_by_feature"), Mapping) else {}
    protected = payload.get("protected_baseline", lr_model.get("protected_baseline"))
    global_baseline = payload.get("global_baseline", lr_model.get("global_baseline", GLOBAL_BASELINE))
    rows = []
    for feature, item in sorted(lr_by_feature.items()):
        data = dict(item or {})
        lr = float(data.get("capped_lr") or 1.0)
        sample = int(data.get("sample_size") or 0)
        quality = "STRONG SAMPLE" if sample >= 100 else "WEAK SAMPLE" if sample >= 25 else "NEEDS MORE DATA"
        rows.append({
            "feature": feature,
            "feature_group": data.get("feature_group", ""),
            "feature_value": data.get("feature_value", ""),
            "LR": round(lr, 6),
            "sample_size": sample,
            "wins": int(data.get("wins") or 0),
            "losses": int(data.get("losses") or 0),
            "observed_success_rate": data.get("observed_success_rate"),
            "baseline_success_rate": data.get("baseline_success_rate"),
            "global_baseline": global_baseline,
            "protected_baseline": protected,
            "reason": data.get("reason", ""),
            "quality_label": quality,
            "influence_direction": "boost" if lr > 1.01 else "downgrade" if lr < 0.99 else "neutral",
        })
    return rows
