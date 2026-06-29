import json
from pathlib import Path
from typing import Any, Mapping

import pandas as pd
import streamlit as st

from autonomous_betting_agent.commercial_platform_tools import load_persistent_ledger, normalize_workspace_id
from autonomous_betting_agent.dashboard_data_service import build_dashboard_data
from autonomous_betting_agent.dashboard_ui import dashboard_json_text, dashboard_tables, status_cards
from autonomous_betting_agent.pick_hold_store import load_first_available
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title="Dashboard", layout="wide")
LANG = render_app_sidebar("dashboard", language_key="dashboard_language", selector="radio")

TEXT = {
    "en": {
        "title": "Dashboard",
        "caption": "Real dashboard values from saved rows, proof ledger rows, learning rows, uploaded CSVs, bankroll settings, and API usage data.",
        "workspace": "Client / Workspace ID",
        "input": "Input rows",
        "source": "Source",
        "upload": "Upload dashboard CSV rows",
        "learning_upload": "Optional learning CSV rows",
        "settings": "Bankroll / API settings",
        "bankroll": "Current bankroll",
        "unit_size": "Unit size",
        "max_daily_fraction": "Max daily exposure fraction",
        "api_used": "API calls used",
        "api_limit": "API call limit",
        "status_cards": "Status Cards",
        "top_picks": "Top Positive-EV Picks",
        "odds_lock": "Odds Lock Pro Summary",
        "bankroll_summary": "Bankroll Summary",
        "proof_summary": "Proof Summary",
        "clv_summary": "CLV Summary",
        "roi_summary": "ROI Summary",
        "recent_activity": "Recent Activity",
        "upcoming_events": "Upcoming Events",
        "json_contract": "Full Dashboard JSON Contract",
        "download_json": "Download dashboard JSON",
        "empty": "No saved or uploaded rows found. Dashboard is showing the empty safety path.",
    },
    "es": {
        "title": "Dashboard",
        "caption": "Valores reales del dashboard desde filas guardadas, proof ledger, aprendizaje, CSVs subidos, bankroll y uso de APIs.",
        "workspace": "ID de cliente / workspace",
        "input": "Filas de entrada",
        "source": "Fuente",
        "upload": "Subir CSV para dashboard",
        "learning_upload": "CSV opcional de aprendizaje",
        "settings": "Bankroll / uso de API",
        "bankroll": "Bankroll actual",
        "unit_size": "Tamaño de unidad",
        "max_daily_fraction": "Exposición diaria máxima",
        "api_used": "Llamadas API usadas",
        "api_limit": "Límite de llamadas API",
        "status_cards": "Tarjetas de estado",
        "top_picks": "Top picks +EV",
        "odds_lock": "Resumen Odds Lock Pro",
        "bankroll_summary": "Resumen de bankroll",
        "proof_summary": "Resumen de prueba",
        "clv_summary": "Resumen CLV",
        "roi_summary": "Resumen ROI",
        "recent_activity": "Actividad reciente",
        "upcoming_events": "Próximos eventos",
        "json_contract": "Contrato JSON completo del dashboard",
        "download_json": "Descargar JSON del dashboard",
        "empty": "No se encontraron filas guardadas o subidas. El dashboard muestra la ruta segura vacía.",
    },
}

HANDOFF_KEYS = (
    "odds_lock_pro_locked_rows",
    "public_proof_dashboard_refresh_rows",
    "pro_predictor_high_confidence_rows",
    "pro_predictor_latest_rows",
    "what_are_the_odds_latest_rows",
    "ara_latest_predictions",
)

LEARNING_SESSION_KEYS = (
    "learning_memory_rows",
    "ara_learning_memory_rows",
    "learning_latest_rows",
    "learn_memory_latest_rows",
    "graded_upload_rows",
)

API_USAGE_KEYS = (
    "dashboard_api_usage",
    "aba_api_usage",
    "api_usage_summary",
    "odds_api_usage",
)

REPO_ROOT = Path(__file__).resolve().parents[1]
ARA_MEMORY_PATH = REPO_ROOT / "data" / "ara_learning_memory.csv"


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT["en"]).get(key, key)


def _read_uploads(uploads: list[Any] | None) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for upload in uploads or []:
        try:
            frame = pd.read_csv(upload)
            frame["source_file"] = getattr(upload, "name", "uploaded.csv")
            frames.append(frame)
        except Exception as exc:
            st.warning(f"{getattr(upload, 'name', 'upload')}: {exc}")
    return pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()


def _session_rows(keys: tuple[str, ...]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for key in keys:
        rows = st.session_state.get(key)
        if rows is None:
            continue
        if isinstance(rows, pd.DataFrame):
            frame = rows.copy(deep=True)
        else:
            try:
                frame = pd.DataFrame(list(rows))
            except Exception:
                continue
        if not frame.empty:
            frame["source_key"] = key
            frames.append(frame)
    return pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()


def _load_saved_rows(workspace_id: str) -> tuple[str, pd.DataFrame]:
    try:
        persistent = load_persistent_ledger(workspace_id=workspace_id, active_only=False)
        if persistent is not None and not persistent.empty:
            frame = persistent.copy(deep=True)
            frame["source_key"] = "persistent_proof_ledger"
            return "persistent_proof_ledger", frame
    except Exception:
        pass
    session_frame = _session_rows(HANDOFF_KEYS)
    if not session_frame.empty:
        return "session_state", session_frame
    try:
        key, rows = load_first_available(HANDOFF_KEYS, workspace_id)
        frame = pd.DataFrame(rows)
        if rows and not frame.empty:
            frame["source_key"] = f"saved:{key}"
            return f"saved:{key}", frame
    except Exception:
        pass
    return "none", pd.DataFrame()


def _load_learning_rows(uploaded_learning: pd.DataFrame) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    session_frame = _session_rows(LEARNING_SESSION_KEYS)
    if not session_frame.empty:
        frames.append(session_frame)
    if ARA_MEMORY_PATH.exists():
        try:
            file_frame = pd.read_csv(ARA_MEMORY_PATH)
            file_frame["source_key"] = "data/ara_learning_memory.csv"
            frames.append(file_frame)
        except Exception:
            pass
    if uploaded_learning is not None and not uploaded_learning.empty:
        frames.append(uploaded_learning)
    return pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()


def _api_usage_from_state(manual_used: int, manual_limit: int) -> dict[str, Any]:
    for key in API_USAGE_KEYS:
        value = st.session_state.get(key)
        if isinstance(value, Mapping):
            data = dict(value)
            data.setdefault("sources", [key])
            return data
    return {"used_calls": manual_used, "call_limit": manual_limit, "sources": ["manual_dashboard_input"]}


def _render_metrics(dashboard: dict[str, Any]) -> None:
    st.subheader(t("status_cards"))
    cards = status_cards(dashboard)
    for start in range(0, len(cards), 5):
        columns = st.columns(5)
        for column, card in zip(columns, cards[start:start + 5]):
            column.metric(card["label"], card["value"], help=card.get("help") or None)


def _render_table(title: str, frame: pd.DataFrame) -> None:
    st.subheader(title)
    if frame.empty:
        st.info("No rows available.")
    else:
        st.dataframe(frame, use_container_width=True, hide_index=True)


st.title(t("title"))
st.caption(t("caption"))

with st.expander(t("input"), expanded=True):
    workspace_input = st.text_input(t("workspace"), value=st.session_state.get("aba_test_window_id", "test_01"))
    workspace_id = normalize_workspace_id(workspace_input)
    st.session_state["aba_test_window_id"] = workspace_id
    saved_source, saved_rows = _load_saved_rows(workspace_id)
    dashboard_uploads = st.file_uploader(t("upload"), type=["csv"], accept_multiple_files=True, key="dashboard_rows_upload")
    uploaded_rows = _read_uploads(dashboard_uploads)
    learning_uploads = st.file_uploader(t("learning_upload"), type=["csv"], accept_multiple_files=True, key="dashboard_learning_upload")
    uploaded_learning_rows = _read_uploads(learning_uploads)
    row_frames = [frame for frame in (saved_rows, uploaded_rows) if frame is not None and not frame.empty]
    rows = pd.concat(row_frames, ignore_index=True, sort=False) if row_frames else pd.DataFrame()
    learning_rows = _load_learning_rows(uploaded_learning_rows)
    source_note = saved_source
    if not uploaded_rows.empty:
        source_note = f"{source_note}, uploaded_csv" if source_note != "none" else "uploaded_csv"
    st.caption(f"{t('source')}: {source_note}")

with st.expander(t("settings"), expanded=False):
    bankroll = st.number_input(t("bankroll"), min_value=0.0, value=float(st.session_state.get("dashboard_bankroll", 1000.0)), step=50.0)
    unit_size = st.number_input(t("unit_size"), min_value=0.0, value=float(st.session_state.get("dashboard_unit_size", 10.0)), step=1.0)
    max_daily_fraction = st.number_input(t("max_daily_fraction"), min_value=0.0, max_value=1.0, value=float(st.session_state.get("dashboard_max_daily_fraction", 0.05)), step=0.01)
    api_used = st.number_input(t("api_used"), min_value=0, value=int(st.session_state.get("dashboard_api_used", 0)), step=100)
    api_limit = st.number_input(t("api_limit"), min_value=0, value=int(st.session_state.get("dashboard_api_limit", 0)), step=100)

api_usage = _api_usage_from_state(int(api_used), int(api_limit))
dashboard = build_dashboard_data(
    rows,
    learning_rows=learning_rows,
    api_usage=api_usage,
    bankroll=float(bankroll),
    unit_size=float(unit_size),
    max_daily_fraction=float(max_daily_fraction),
)

tables = dashboard_tables(dashboard)

if rows.empty:
    st.warning(t("empty"))

_render_metrics(dashboard)

left, right = st.columns([2, 1])
with left:
    _render_table(t("top_picks"), tables["top_positive_ev_picks"])
with right:
    _render_table(t("odds_lock"), tables["odds_lock_summary"])
    _render_table(t("bankroll_summary"), tables["bankroll_summary"])

proof_col, clv_col, roi_col = st.columns(3)
with proof_col:
    _render_table(t("proof_summary"), tables["proof_summary"])
with clv_col:
    _render_table(t("clv_summary"), tables["clv_summary"])
with roi_col:
    _render_table(t("roi_summary"), tables["roi_summary"])

activity_col, event_col = st.columns(2)
with activity_col:
    _render_table(t("recent_activity"), tables["recent_activity"])
with event_col:
    _render_table(t("upcoming_events"), tables["upcoming_events"])

json_text = dashboard_json_text(dashboard)
with st.expander(t("json_contract"), expanded=False):
    st.code(json_text, language="json")
    st.download_button(
        t("download_json"),
        data=json_text.encode("utf-8"),
        file_name=f"dashboard_{workspace_id}.json",
        mime="application/json",
        key="dashboard_json_download",
    )
