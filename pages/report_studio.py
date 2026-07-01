from __future__ import annotations

import importlib
from typing import Any

import pandas as pd
import streamlit as st

from autonomous_betting_agent.commercial_platform_tools import load_persistent_ledger, normalize_workspace_id
import autonomous_betting_agent.magazine_book_export as magazine_book_export
from autonomous_betting_agent.magazine_display_guard import PATCH_VERSION as MAGAZINE_DISPLAY_GUARD_VERSION, install as install_magazine_display_guard
from autonomous_betting_agent.magazine_live_api_enrichment import ENRICHMENT_VERSION, enrich_rows_with_live_api_data, install as install_magazine_live_api_enrichment
from autonomous_betting_agent.magazine_report_polish_patch import install as install_magazine_report_polish
from autonomous_betting_agent.magazine_sale_ready_patch import apply_magazine_sale_ready_patch
from autonomous_betting_agent.pick_hold_store import load_first_available
from autonomous_betting_agent.report_studio_service import ReportStudioFilters, build_report_studio_state
from autonomous_betting_agent.report_studio_ui import render_premium_card_deck, render_status_dashboard
from autonomous_betting_agent.row_normalizer import normalize_frame
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

magazine_book_export = apply_magazine_sale_ready_patch(install_magazine_live_api_enrichment(importlib.reload(magazine_book_export)))
install_magazine_report_polish()
magazine_book_export = install_magazine_display_guard(magazine_book_export)

st.set_page_config(page_title="Report Studio", layout="wide")
LANG = render_app_sidebar("report_studio", language_key="report_studio_language", selector="radio")
NO_MARKET_EXPORT_VERSION = "no_market_metric_v10"
ACTIVE_EXPORT_VERSION = f"{magazine_book_export.MAGAZINE_STYLE_VERSION}:{NO_MARKET_EXPORT_VERSION}:{ENRICHMENT_VERSION}:{MAGAZINE_DISPLAY_GUARD_VERSION}"
if st.session_state.get("report_studio_active_export_version") != ACTIVE_EXPORT_VERSION:
    st.cache_data.clear()
    st.session_state["report_studio_active_export_version"] = ACTIVE_EXPORT_VERSION

TEXT = {"cards": "Premium Cards", "magazine": "Magazine Report", "copy": "WhatsApp / Telegram", "audit": "Learning Audit", "proof": "Analyst Proof", "exports": "Exports", "images": "Images", "profile_json": "Profile JSON", "feed_json": "App Feed", "diagnostics": "Diagnostics", "publisher": "Proof Publisher"}
HANDOFF_KEYS = ("odds_lock_pro_locked_rows", "public_proof_dashboard_refresh_rows", "pro_predictor_high_confidence_rows", "pro_predictor_latest_rows", "what_are_the_odds_latest_rows", "ara_latest_predictions")


def t(key: str) -> str:
    return TEXT.get(key, key.replace("_", " ").title())


def _rows_to_frame(rows: Any) -> pd.DataFrame:
    if isinstance(rows, pd.DataFrame):
        return rows.copy()
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def load_current_session_rows() -> tuple[str, pd.DataFrame]:
    for key in HANDOFF_KEYS:
        frame = _rows_to_frame(st.session_state.get(key) or [])
        if not frame.empty:
            return f"session:{key}", frame
    return "", pd.DataFrame()


def load_saved_handoff_rows(workspace_id: str) -> tuple[str, pd.DataFrame]:
    key, rows = load_first_available(HANDOFF_KEYS, workspace_id)
    frame = _rows_to_frame(rows)
    return (f"saved:{key}", frame) if not frame.empty else ("", pd.DataFrame())


def load_persistent_ledger_rows(workspace_id: str) -> tuple[str, pd.DataFrame]:
    persistent = load_persistent_ledger(workspace_id=workspace_id, active_only=False)
    return ("persistent_proof_ledger", persistent) if persistent is not None and not persistent.empty else ("", pd.DataFrame())


def source_mode(source: str) -> str:
    if source.startswith("uploaded:"):
        return "uploaded"
    if source.startswith("session:"):
        return "current-run"
    if source.startswith("saved:"):
        return "saved-handoff"
    if source == "persistent_proof_ledger":
        return "ledger-history"
    return "none"


def rows_from_saved_sources(workspace_id: str) -> tuple[str, pd.DataFrame]:
    for loader in (load_current_session_rows, lambda: load_saved_handoff_rows(workspace_id), lambda: load_persistent_ledger_rows(workspace_id)):
        source, frame = loader()
        if not frame.empty:
            return source, frame
    return "", pd.DataFrame()


def read_uploaded_rows() -> tuple[str, pd.DataFrame]:
    uploads = st.file_uploader("Upload CSV rows", type=["csv"], accept_multiple_files=True)
    frames = [pd.read_csv(upload).assign(source_file=upload.name) for upload in uploads or []]
    return ("uploaded:manual", pd.concat(frames, ignore_index=True, sort=False)) if frames else ("", pd.DataFrame())


def choose_report_studio_source(saved_source: str, saved_rows: pd.DataFrame, upload_source: str, upload_rows: pd.DataFrame) -> tuple[str, pd.DataFrame, str]:
    if upload_rows is not None and not upload_rows.empty:
        return upload_source, upload_rows, source_mode(upload_source)
    if saved_rows is not None and not saved_rows.empty:
        return saved_source, saved_rows, source_mode(saved_source)
    return "", pd.DataFrame(), "none"


st.title("Report Studio")
workspace_id = normalize_workspace_id(st.text_input("Client / Workspace ID", value=st.session_state.get("aba_test_window_id", "test_01")))
st.session_state["aba_test_window_id"] = workspace_id
upload_source, upload_rows = read_uploaded_rows()
saved_source, saved_rows = rows_from_saved_sources(workspace_id)
source_note, raw, source_mode_value = choose_report_studio_source(saved_source, saved_rows, upload_source, upload_rows)
st.caption(f"Source: {source_note or 'none'} · Source mode: {source_mode_value} · Rows: {len(raw)}")
if source_note == "persistent_proof_ledger":
    st.warning("Magazine is using saved proof history because no current prediction rows were found. Run Pro Predictor/Odds Lock Pro or upload the newest CSV before exporting.")
if raw.empty:
    st.warning("No rows found.")
    st.stop()

state = build_report_studio_state(normalize_frame(raw), None, filters=ReportStudioFilters(max_rows=75, language=LANG), source_note=f"{source_note} ({source_mode_value})")
cards = state.cards
rows = enrich_rows_with_live_api_data([row.to_dict() for _, row in cards.iterrows()])
preview_png = magazine_book_export.render_full_pick_magazine_page_png(rows[0], page_number=1, total_pages=len(rows), language=LANG) if rows else b""
tabs = st.tabs([t("cards"), t("magazine"), t("copy"), t("audit"), t("proof"), t("exports"), t("images"), t("profile_json"), t("feed_json"), t("diagnostics"), t("publisher")])
with tabs[0]:
    st.markdown(render_premium_card_deck(cards, language=LANG), unsafe_allow_html=True)
with tabs[1]:
    st.download_button("Download Magazine Report PNG", preview_png, file_name="magazine_preview.png", mime="image/png")
    st.image(preview_png, caption="Generated magazine report preview", use_container_width=True)
with tabs[2]:
    st.write("Copy export available from report bundle.")
with tabs[3]:
    st.write(state.audit or "No graded calibration data available yet.")
with tabs[4]:
    st.dataframe(cards, use_container_width=True, hide_index=True)
with tabs[5]:
    st.download_button("Download CSV", cards.to_csv(index=False), file_name="report.csv", mime="text/csv")
with tabs[6]:
    st.info("Magazine exports for the full report and one selected full page.")
with tabs[7]:
    st.json({})
with tabs[8]:
    st.json({})
with tabs[9]:
    st.json({"source": source_note, "source_mode": source_mode_value, "active_export_version": ACTIVE_EXPORT_VERSION})
with tabs[10]:
    st.subheader("Proof Publisher")
    st.write({})
