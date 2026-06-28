from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from autonomous_betting_agent.adaptive_repair_runner import combined_rows, hash_rows, rows_from_csv_bytes, run_adaptive_repair_scan, system_source_adapters, uploaded_source
from autonomous_betting_agent.dynamic_odds_predictor import build_phase3e_report
from autonomous_betting_agent.pick_hold_store import normalize_workspace_id
from autonomous_betting_agent.reparodynamics_audit import write_reparodynamics_audit_event_from_runner_report
from autonomous_betting_agent.reparodynamics_phase3e_audit import write_phase3e_dynamic_odds_audit_event
from autonomous_betting_agent.reparodynamics_repair_memory import load_repair_memory, repair_memory_to_frames, save_repair_memory, stable_memory_run_id, update_repair_memory
from autonomous_betting_agent.reparodynamics_shadow_backtest import build_phase3c_report
from autonomous_betting_agent.sidebar_nav import render_app_sidebar
from autonomous_betting_agent.ui_i18n import localize_dataframe

st.set_page_config(page_title="Shadow Mode Results", layout="wide")
LANG = render_app_sidebar("shadow_mode_results", language_key="shadow_mode_results_language", selector="radio")

TEXT = {
    "en": {
        "title": "Shadow Mode Results",
        "caption": "Phase 3E Dynamic Odds Predictor Shadow. Live behavior stays unchanged.",
        "warning": "Shadow Mode results are simulation-only. Dynamic Odds Predictor does not change live picks, model probability, EV, stake, bankroll, proof ledgers, or raw data.",
        "workspace": "Workspace ID",
        "include_system": "Include available local system sources",
        "upload": "Optional graded CSV",
        "uploaded": "Uploaded rows loaded",
        "run": "Run Phase 3E Dynamic Odds Shadow comparison",
        "save": "Save Phase 3E to Repair Memory",
        "saved": "Saved to Repair Memory. No live repairs were activated.",
        "already_saved": "Already saved to Repair Memory.",
        "open_reparodynamics": "Open Reparodynamics page",
        "baseline": "Baseline Metrics",
        "dynamic": "Dynamic Metrics",
        "comparison": "Dynamic vs Baseline Comparison",
        "lr": "LR Breakdown",
        "dynamic_rows": "Dynamic Rows",
        "blockers": "Data Blockers",
        "watchlists": "Watchlists",
        "manual": "Manual Review Queue",
        "safety": "Safety Gates",
        "memory": "Repair Memory Preview",
        "phase3c": "Phase 3C Backtest",
        "empty": "No rows in this section.",
        "no_data": "Run a Phase 3E Shadow scan to show results.",
        "audit_written": "Phase 3E audit event written. Live mutation remains forbidden.",
        "rows": "Rows",
        "completed": "Completed",
        "lr_training": "LR training rows",
        "lr_eval": "LR evaluation rows",
        "dynamic_applied": "Dynamic Applied LIVE",
    },
    "es": {
        "title": "Resultados Shadow Mode",
        "caption": "Dynamic Odds Predictor Shadow Fase 3E. El comportamiento en vivo no cambia.",
        "warning": "Los resultados Shadow Mode son solo simulacion. Dynamic Odds Predictor no cambia picks en vivo, probabilidad del modelo, EV, stake, bankroll, ledgers de prueba ni datos crudos.",
        "workspace": "ID del espacio de trabajo",
        "include_system": "Incluir fuentes locales disponibles del sistema",
        "upload": "CSV calificado opcional",
        "uploaded": "Filas subidas cargadas",
        "run": "Ejecutar comparacion Shadow de Dynamic Odds Fase 3E",
        "save": "Guardar Fase 3E en Repair Memory",
        "saved": "Guardado en Repair Memory. No se activaron reparaciones en vivo.",
        "already_saved": "Ya guardado en Repair Memory.",
        "open_reparodynamics": "Abrir pagina Reparodynamics",
        "baseline": "Metricas baseline",
        "dynamic": "Metricas dinamicas",
        "comparison": "Comparacion dinamica vs baseline",
        "lr": "Desglose LR",
        "dynamic_rows": "Filas dinamicas",
        "blockers": "Bloqueadores de datos",
        "watchlists": "Listas de observacion",
        "manual": "Cola de revision manual",
        "safety": "Compuertas de seguridad",
        "memory": "Vista previa de Repair Memory",
        "phase3c": "Backtest Fase 3C",
        "empty": "No hay filas en esta seccion.",
        "no_data": "Ejecuta un escaneo Shadow Fase 3E para mostrar resultados.",
        "audit_written": "Evento de auditoria Fase 3E escrito. La mutacion en vivo sigue prohibida.",
        "rows": "Filas",
        "completed": "Completadas",
        "lr_training": "Filas entrenamiento LR",
        "lr_eval": "Filas evaluacion LR",
        "dynamic_applied": "Dynamic aplicado EN VIVO",
    },
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT["en"]).get(key, key)


def show_frame(frame: pd.DataFrame | None) -> None:
    if frame is None or frame.empty:
        st.info(t("empty"))
    else:
        st.dataframe(localize_dataframe(frame, LANG), use_container_width=True, hide_index=True)


def show_rows(rows: Any) -> None:
    show_frame(pd.DataFrame(list(rows or [])))


def one_row(data: dict[str, Any] | None) -> pd.DataFrame:
    return pd.DataFrame([dict(data or {})])


def scan_rows(uploaded_rows: list[dict[str, Any]] | None, uploaded_name: str, include_system: bool) -> list[dict[str, Any]]:
    sources = []
    if uploaded_rows is not None:
        sources.append(uploaded_source("uploaded_csv_rows", uploaded_rows, source_hash=hash_rows(uploaded_rows), source_path=uploaded_name))
    if include_system:
        sources.extend(system_source_adapters())
    return combined_rows(sources)


st.title(t("title"))
st.caption(t("caption"))
st.warning(t("warning"))
st.page_link("pages/reparodynamics.py", label=t("open_reparodynamics"))

workspace_id = normalize_workspace_id(st.text_input(t("workspace"), value=st.session_state.get("aba_test_window_id", "test_01")))
st.session_state["aba_test_window_id"] = workspace_id
include_system = st.checkbox(t("include_system"), value=True)
uploaded_rows = None
uploaded_bytes = None
uploaded_name = "shadow_mode_phase3e_upload.csv"
upload = st.file_uploader(t("upload"), type=["csv"], key="shadow_mode_results_phase3e_upload")
if upload is not None:
    uploaded_bytes = upload.getvalue()
    uploaded_name = upload.name
    uploaded_rows = rows_from_csv_bytes(uploaded_bytes)
    st.success(f"{t('uploaded')}: {len(uploaded_rows)}")
    show_frame(pd.DataFrame(uploaded_rows).head(50))

if st.button(t("run"), type="primary"):
    rows = scan_rows(uploaded_rows, uploaded_name, include_system)
    phase3c_report = build_phase3c_report(rows)
    phase3c_report["memory_run_id"] = stable_memory_run_id(phase3c_report)
    phase3e_report = build_phase3e_report(rows)
    runner_report = run_adaptive_repair_scan(uploaded_rows=uploaded_rows, uploaded_filename=uploaded_name, uploaded_bytes=uploaded_bytes, include_system_sources=include_system)
    write_reparodynamics_audit_event_from_runner_report(runner_report, source="Shadow Mode Results Phase 3E", phase3c_report=phase3c_report)
    write_phase3e_dynamic_odds_audit_event(phase3e_report, source="Shadow Mode Results Phase 3E Dynamic Odds")
    st.session_state["phase3c_latest_report"] = phase3c_report
    st.session_state["phase3e_latest_report"] = phase3e_report
    st.session_state["shadow_mode_latest_report"] = runner_report.to_dict()
    st.success(t("audit_written"))

report = st.session_state.get("phase3e_latest_report")
phase3c = st.session_state.get("phase3c_latest_report")

if report:
    memory = load_repair_memory(workspace_id)
    run_id = str(report.get("memory_run_id") or report.get("dynamic_shadow_run_id") or "")
    if run_id and run_id in set(str(item) for item in memory.get("saved_run_ids", [])):
        st.info(t("already_saved"))
    elif st.button(t("save")):
        memory = update_repair_memory(memory, report, source="Shadow Mode Results Phase 3E")
        memory = save_repair_memory(memory, workspace_id)
        st.session_state["phase3d_repair_memory"] = memory
        st.success(t("saved"))

if not report:
    st.info(t("no_data"))
else:
    counts = dict(report.get("summary_counts", {}) or {})
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric(t("rows"), report.get("rows_scanned", 0))
    c2.metric(t("completed"), report.get("completed_rows_used", 0))
    c3.metric(t("lr_training"), report.get("lr_training_rows", 0))
    c4.metric(t("lr_eval"), report.get("lr_evaluation_rows", 0))
    c5.metric(t("dynamic_applied"), counts.get("dynamic_odds_applied_live_count", 0))
    tabs = st.tabs([t("baseline"), t("dynamic"), t("comparison"), t("lr"), t("dynamic_rows"), t("blockers"), t("watchlists"), t("manual"), t("safety"), t("phase3c"), t("memory")])
    with tabs[0]:
        show_frame(one_row(report.get("baseline_metrics", {}) or {}))
    with tabs[1]:
        show_frame(one_row(report.get("dynamic_metrics", {}) or {}))
    with tabs[2]:
        show_frame(one_row(report.get("comparison_metrics", {}) or {}))
    with tabs[3]:
        show_rows(list(((report.get("lr_model_summary", {}) or {}).get("lr_by_feature", {}) or {}).values()))
    with tabs[4]:
        rows_frame = pd.DataFrame(list(report.get("dynamic_rows", []) or []))
        if not rows_frame.empty:
            wanted = ["event", "event_id", "sport", "league", "market_type", "decimal_odds", "current_model_probability", "dynamic_probability", "dynamic_edge", "dynamic_no_vig_edge", "dynamic_EV", "dynamic_signal_status"]
            cols = [column for column in wanted if column in rows_frame.columns]
            show_frame(rows_frame[cols] if cols else rows_frame)
        else:
            st.info(t("empty"))
    with tabs[5]:
        show_rows(report.get("data_blockers", []))
    with tabs[6]:
        show_rows(report.get("watchlists", []))
    with tabs[7]:
        show_rows(report.get("manual_review_queue", []))
    with tabs[8]:
        show_frame(one_row(report.get("safety_gates", {}) or {}))
    with tabs[9]:
        show_rows((phase3c or {}).get("shadow_tested_repairs", []))
    with tabs[10]:
        memory = st.session_state.get("phase3d_repair_memory") or load_repair_memory(workspace_id)
        frames = repair_memory_to_frames(memory)
        show_frame(frames["summary"])
