from typing import Any, Mapping, Sequence

import pandas as pd

from autonomous_betting_agent.dashboard_data_service import build_dashboard_data
from autonomous_betting_agent.performance_ledger_service import rows_for_dashboard

SESSION_DASHBOARD_KEYS = (
    "odds_lock_pro_locked_rows",
    "public_proof_dashboard_refresh_rows",
    "pro_predictor_high_confidence_rows",
    "pro_predictor_latest_rows",
    "report_studio_latest_rows",
    "proof_center_latest_rows",
    "dashboard_saved_handoff_rows",
    "learning_memory_rows",
    "ara_latest_predictions",
)

DASHBOARD_COMPATIBILITY_FIELDS = (
    "event",
    "public_event",
    "market_type",
    "market",
    "pick",
    "prediction",
    "public_pick",
    "sportsbook",
    "bookmaker",
    "book",
    "decimal_odds",
    "decimal_price",
    "model_probability",
    "raw_implied_probability",
    "no_vig_implied_probability",
    "edge",
    "model_market_edge",
    "no_vig_edge",
    "expected_value",
    "expected_value_per_unit",
    "clv",
    "manual_clv",
    "stake_units",
    "result",
    "profit_units",
    "report_lane",
    "official_publish_ready",
    "odds_verified",
    "proof_id",
    "locked_at_utc",
    "source_key",
)


def _workspace(value: Any) -> str:
    cleaned = str(value or "").strip().replace(" ", "_").lower()
    return cleaned or "default"


def _as_frame(rows: Any) -> pd.DataFrame:
    if rows is None:
        return pd.DataFrame()
    if isinstance(rows, pd.DataFrame):
        return rows.copy(deep=True)
    try:
        return pd.DataFrame([dict(row) for row in rows])
    except Exception:
        return pd.DataFrame()


def _concat(frames: Sequence[pd.DataFrame]) -> pd.DataFrame:
    usable = [frame for frame in frames if frame is not None and not frame.empty]
    return pd.concat(usable, ignore_index=True, sort=False) if usable else pd.DataFrame()


def _compatibility_frame(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy(deep=True) if frame is not None else pd.DataFrame()
    if out.empty:
        for field in DASHBOARD_COMPATIBILITY_FIELDS:
            out[field] = []
        return out
    if "event" in out.columns and "public_event" not in out.columns:
        out["public_event"] = out["event"]
    if "pick" in out.columns:
        if "prediction" not in out.columns:
            out["prediction"] = out["pick"]
        if "public_pick" not in out.columns:
            out["public_pick"] = out["pick"]
    if "sportsbook" in out.columns:
        if "bookmaker" not in out.columns:
            out["bookmaker"] = out["sportsbook"]
        if "book" not in out.columns:
            out["book"] = out["sportsbook"]
    if "market_type" in out.columns and "market" not in out.columns:
        out["market"] = out["market_type"]
    if "decimal_odds" in out.columns and "decimal_price" not in out.columns:
        out["decimal_price"] = out["decimal_odds"]
    if "edge" in out.columns and "model_market_edge" not in out.columns:
        out["model_market_edge"] = out["edge"]
    if "expected_value" in out.columns and "expected_value_per_unit" not in out.columns:
        out["expected_value_per_unit"] = out["expected_value"]
    if "clv" in out.columns and "manual_clv" not in out.columns:
        out["manual_clv"] = out["clv"]
    for field in DASHBOARD_COMPATIBILITY_FIELDS:
        if field not in out.columns:
            out[field] = ""
    return out


def load_ledger_dashboard_rows(workspace_id: str) -> pd.DataFrame:
    return _compatibility_frame(rows_for_dashboard(_workspace(workspace_id)))


def load_session_dashboard_rows(session_state: Mapping[str, Any] | None, keys: Sequence[str] | None = None) -> pd.DataFrame:
    if not session_state:
        return _compatibility_frame(pd.DataFrame())
    frames: list[pd.DataFrame] = []
    for key in keys or SESSION_DASHBOARD_KEYS:
        if key not in session_state:
            continue
        frame = _as_frame(session_state.get(key))
        if frame.empty:
            continue
        frame = frame.copy(deep=True)
        if "source_key" not in frame.columns:
            frame["source_key"] = key
        frames.append(frame)
    return _compatibility_frame(_concat(frames))


def load_uploaded_dashboard_rows(uploaded_frames: Sequence[Any] | None) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for item in uploaded_frames or []:
        frame = _as_frame(item)
        if frame.empty:
            continue
        frame = frame.copy(deep=True)
        if "source_key" not in frame.columns:
            frame["source_key"] = "uploaded_csv"
        frames.append(frame)
    return _compatibility_frame(_concat(frames))


def choose_dashboard_rows(
    workspace_id: str,
    session_state: Mapping[str, Any] | None = None,
    uploaded_frames: Sequence[Any] | None = None,
) -> dict[str, Any]:
    warnings: list[str] = []
    ledger_rows = load_ledger_dashboard_rows(workspace_id)
    session_rows = load_session_dashboard_rows(session_state)
    uploaded_rows = load_uploaded_dashboard_rows(uploaded_frames)
    if not ledger_rows.empty:
        selected_source = "ledger"
        selected = ledger_rows
    elif not session_rows.empty:
        selected_source = "session"
        selected = session_rows
        warnings.append("Using session/saved handoff rows because persistent ledger rows are empty.")
    elif not uploaded_rows.empty:
        selected_source = "uploaded"
        selected = uploaded_rows
        warnings.append("Using uploaded fallback because ledger and session rows are empty.")
    else:
        selected_source = "empty"
        selected = _compatibility_frame(pd.DataFrame())
        warnings.append("No ledger, session, or uploaded dashboard rows found.")
    return {
        "selected_source": selected_source,
        "rows": _compatibility_frame(selected),
        "ledger_rows": ledger_rows,
        "session_rows": session_rows,
        "uploaded_rows": uploaded_rows,
        "warnings": warnings,
    }


def dashboard_source_summary(
    workspace_id: str,
    session_state: Mapping[str, Any] | None = None,
    uploaded_frames: Sequence[Any] | None = None,
) -> dict[str, Any]:
    choice = choose_dashboard_rows(workspace_id, session_state=session_state, uploaded_frames=uploaded_frames)
    return {
        "selected_source": choice["selected_source"],
        "ledger_rows": int(len(choice["ledger_rows"])),
        "session_rows": int(len(choice["session_rows"])),
        "uploaded_rows": int(len(choice["uploaded_rows"])),
        "selected_rows": int(len(choice["rows"])),
        "warnings": list(choice.get("warnings", [])),
    }


def build_dashboard_from_ledger(
    workspace_id: str,
    session_state: Mapping[str, Any] | None = None,
    uploaded_frames: Sequence[Any] | None = None,
    learning_rows: pd.DataFrame | Sequence[Mapping[str, Any]] | None = None,
    api_usage: Mapping[str, Any] | None = None,
    bankroll: float = 1000.0,
    unit_size: float = 10.0,
    max_daily_fraction: float = 0.05,
) -> dict[str, Any]:
    choice = choose_dashboard_rows(workspace_id, session_state=session_state, uploaded_frames=uploaded_frames)
    dashboard = build_dashboard_data(
        choice["rows"],
        learning_rows=learning_rows,
        api_usage=api_usage,
        bankroll=bankroll,
        unit_size=unit_size,
        max_daily_fraction=max_daily_fraction,
    )
    dashboard["sync_summary"] = dashboard_source_summary(workspace_id, session_state=session_state, uploaded_frames=uploaded_frames)
    return dashboard
