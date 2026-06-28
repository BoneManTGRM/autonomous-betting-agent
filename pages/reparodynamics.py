from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from autonomous_betting_agent.adaptive_repair_runner import (
    combined_rows,
    hash_rows,
    rows_from_csv_bytes,
    run_adaptive_repair_scan,
    system_source_adapters,
    uploaded_source,
)
from autonomous_betting_agent.dynamic_odds_predictor import build_phase3e_report
from autonomous_betting_agent.pick_hold_store import normalize_workspace_id
from autonomous_betting_agent.reparodynamics_audit import latest_reparodynamics_audit_event, write_reparodynamics_audit_event_from_runner_report
from autonomous_betting_agent.reparodynamics_doctrine import get_reparodynamics_doctrine
from autonomous_betting_agent.reparodynamics_phase3e_audit import write_phase3e_dynamic_odds_audit_event
from autonomous_betting_agent.reparodynamics_repair_memory import (
    load_repair_memory,
    manual_review_decision,
    repair_memory_to_frames,
    save_repair_memory,
    stable_memory_run_id,
    update_repair_memory,
)
from autonomous_betting_agent.reparodynamics_shadow_backtest import build_phase3c_report
from autonomous_betting_agent.sidebar_nav import render_app_sidebar
from autonomous_betting_agent.ui_i18n import localize_dataframe, localize_options, localize_value

st.set_page_config(page_title="Reparodynamics", layout="wide")
LANG = render_app_sidebar("reparodynamics", language_key="reparodynamics_language", selector="radio")

TEXT = {
    "en": {
        "title": "Reparodynamics",
        "caption": "Phase 3E Dynamic Odds Predictor Shadow + Repair Memory. Live behavior stays unchanged.",
        "warning": "Phase 3E is Shadow Mode only. Dynamic Odds Predictor does not change live picks, model probability, EV, stake, bankroll, proof ledgers, or raw data.",
        "workspace": "Workspace ID",
        "include_system": "Include available local system sources",
        "upload": "Optional graded CSV",
        "loaded": "Loaded uploaded rows",
        "run": "Run Phase 3E Dynamic Odds Shadow Test",
        "success": "Phase 3E Dynamic Odds Shadow Test completed. No live behavior changed.",
        "save": "Save Phase 3E results to Repair Memory",
        "already_saved": "Already saved to Repair Memory.",
        "saved": "Saved to Repair Memory.",
        "empty": "No rows in this section.",
        "no_run": "Run Phase 3E to show results.",
        "phase3e": "Phase 3E Dynamic Odds Predictor",
        "lr": "Dynamic LR Breakdown",
        "rows": "Dynamic Value Comparison",
        "memory": "Phase 3D Repair Memory",
        "manual": "Manual Review Gate",
        "phase3c": "Phase 3C Summary",
        "blockers": "Data Blockers",
        "watchlists": "Watchlists",
        "comparison": "Shadow Backtest Comparison",
        "safety": "Safety Gates",
        "audit": "Audit",
        "review_repair": "Repair key",
        "review_action": "Manual decision",
        "reviewer": "Reviewer",
        "review_note": "Manual note",
        "apply_review": "Save manual review decision",
        "review_saved": "Manual review decision saved. No live repairs were activated.",
        "phase": "Current phase",
        "shadow": "Shadow Mode",
        "dynamic_predictor": "Dynamic Odds Predictor",
        "dynamic_live": "Dynamic Odds LIVE",
        "dynamic_applied": "Dynamic Odds Applied LIVE",
        "repair": "Repair activation",
        "model_training": "Model Training",
        "stored_data": "Stored Data Mutation",
        "final_rule": "ABA may store Phase 3E shadow memory and manual labels, but live repair and live Dynamic Odds activation remain forbidden.",
    },
    "es": {
        "title": "Reparodynamics",
        "caption": "Dynamic Odds Predictor Shadow Fase 3E + Repair Memory. El comportamiento en vivo no cambia.",
        "warning": "Fase 3E es solo Shadow Mode. Dynamic Odds Predictor no cambia picks en vivo, probabilidad del modelo, EV, stake, bankroll, ledgers de prueba ni datos crudos.",
        "workspace": "ID del espacio de trabajo",
        "include_system": "Incluir fuentes locales disponibles del sistema",
        "upload": "CSV calificado opcional",
        "loaded": "Filas subidas cargadas",
        "run": "Ejecutar prueba Shadow de Dynamic Odds Fase 3E",
        "success": "Prueba Shadow de Dynamic Odds Fase 3E completada. No cambio el comportamiento en vivo.",
        "save": "Guardar resultados Fase 3E en Repair Memory",
        "already_saved": "Ya guardado en Repair Memory.",
        "saved": "Guardado en Repair Memory.",
        "empty": "No hay filas en esta seccion.",
        "no_run": "Ejecuta Fase 3E para mostrar resultados.",
        "phase3e": "Dynamic Odds Predictor Fase 3E",
        "lr": "Desglose LR dinamico",
        "rows": "Comparacion de valor dinamico",
        "memory": "Repair Memory Fase 3D",
        "manual": "Compuerta de revision manual",
        "phase3c": "Resumen Fase 3C",
        "blockers": "Bloqueadores de datos",
        "watchlists": "Listas de observacion",
        "comparison": "Comparacion Shadow Backtest",
        "safety": "Compuertas de seguridad",
        "audit": "Auditoria",
        "review_repair": "Clave de reparacion",
        "review_action": "Decision manual",
        "reviewer": "Revisor",
        "review_note": "Nota manual",
        "apply_review": "Guardar decision de revision manual",
        "review_saved": "Decision de revision manual guardada. No se activaron reparaciones en vivo.",
        "phase": "Fase actual",
        "shadow": "Shadow Mode",
        "dynamic_predictor": "Dynamic Odds Predictor",
        "dynamic_live": "Dynamic Odds EN VIVO",
        "dynamic_applied": "Dynamic Odds aplicado EN VIVO",
        "repair": "Activacion de reparacion",
        "model_training": "Entrenamiento del modelo",
        "stored_data": "Mutacion de datos guardados",
        "final_rule": "ABA puede guardar memoria Shadow Fase 3E y etiquetas manuales, pero reparacion en vivo y Dynamic Odds en vivo siguen prohibidos.",
    },
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT["en"]).get(key, key)


def metric_value(value: Any) -> str:
    return str(localize_value(value, LANG))


def show_frame(frame: pd.DataFrame | None) -> None:
    if frame is None or frame.empty:
        st.info(t("empty"))
    else:
        st.dataframe(localize_dataframe(frame, LANG), use_container_width=True, hide_index=True)


def show_rows(rows: Any) -> None:
    show_frame(pd.DataFrame(list(rows or [])))


def one_row(data: dict[str, Any] | None) -> pd.DataFrame:
    return pd.DataFrame([dict(data or {})])


def build_scan_rows(uploaded_rows: list[dict[str, Any]] | None, uploaded_name: str, include_system: bool) -> list[dict[str, Any]]:
    sources = []
    if uploaded_rows is not None:
        sources.append(uploaded_source("uploaded_csv_rows", uploaded_rows, source_hash=hash_rows(uploaded_rows), source_path=uploaded_name))
    if include_system:
        sources.extend(system_source_adapters())
    return combined_rows(sources)


def dynamic_summary(report: dict[str, Any] | None) -> dict[str, Any]:
    report = dict(report or {})
    counts = dict(report.get("summary_counts", {}) or {})
    comparison = dict(report.get("comparison_metrics", {}) or {})
    return {
        "rows_scanned": report.get("rows_scanned", 0),
        "completed_rows_used": report.get("completed_rows_used", 0),
        "lr_training_rows": report.get("lr_training_rows", 0),
        "lr_evaluation_rows": report.get("lr_evaluation_rows", 0),
        "evaluation_mode": report.get("evaluation_mode", ""),
        "leakage_guard_enabled": report.get("leakage_guard_enabled", True),
        "train_test_overlap_count": report.get("train_test_overlap_count", 0),
        "walk_forward_windows_evaluated": report.get("walk_forward_windows_evaluated", 0),
        "dynamic_green_count": counts.get("dynamic_green_count", 0),
        "dynamic_yellow_count": counts.get("dynamic_yellow_count", 0),
        "dynamic_red_count": counts.get("dynamic_red_count", 0),
        "ROI_delta": comparison.get("ROI_delta"),
        "profit_units_delta": comparison.get("profit_units_delta"),
        "losses_delta": comparison.get("losses_delta"),
        "calibration_delta": comparison.get("calibration_delta"),
        "overfit_risk": comparison.get("overfit_risk"),
        "decision": comparison.get("decision"),
        "decision_reason": comparison.get("decision_reason"),
        "dynamic_odds_applied_live_count": report.get("dynamic_odds_applied_live_count", 0),
    }


doctrine = get_reparodynamics_doctrine()
st.title(t("title"))
st.caption(t("caption"))
st.warning(t("warning"))
workspace_id = normalize_workspace_id(st.text_input(t("workspace"), value=st.session_state.get("aba_test_window_id", "test_01")))
st.session_state["aba_test_window_id"] = workspace_id
memory = load_repair_memory(workspace_id)

cols = st.columns(8)
cols[0].metric(t("phase"), metric_value(doctrine.get("current_phase", "")))
cols[1].metric(t("shadow"), metric_value(doctrine.get("shadow_mode_activation", "ON")))
cols[2].metric(t("dynamic_predictor"), metric_value(doctrine.get("dynamic_odds_predictor", "SHADOW ONLY")))
cols[3].metric(t("dynamic_live"), metric_value(doctrine.get("dynamic_odds_live_activation", "OFF")))
cols[4].metric(t("dynamic_applied"), int(doctrine.get("dynamic_odds_applied_live_count", 0) or 0))
cols[5].metric(t("repair"), metric_value(doctrine.get("repair_activation", "OFF")))
cols[6].metric(t("model_training"), metric_value(doctrine.get("model_training", "FORBIDDEN")))
cols[7].metric(t("stored_data"), metric_value(doctrine.get("stored_data_mutation", "FORBIDDEN")))

include_system = st.checkbox(t("include_system"), value=True)
uploaded_rows = None
uploaded_bytes = None
uploaded_name = "reparodynamics_phase3e_upload.csv"
upload = st.file_uploader(t("upload"), type=["csv"], key="reparodynamics_phase3e_upload")
if upload is not None:
    uploaded_bytes = upload.getvalue()
    uploaded_name = upload.name
    uploaded_rows = rows_from_csv_bytes(uploaded_bytes)
    st.success(f"{t('loaded')}: {len(uploaded_rows)}")
    show_frame(pd.DataFrame(uploaded_rows).head(50))

if st.button(t("run"), type="primary"):
    scan_rows = build_scan_rows(uploaded_rows, uploaded_name, include_system)
    phase3c_report = build_phase3c_report(scan_rows)
    phase3c_report["memory_run_id"] = stable_memory_run_id(phase3c_report)
    phase3e_report = build_phase3e_report(scan_rows)
    runner_report = run_adaptive_repair_scan(
        uploaded_rows=uploaded_rows,
        uploaded_filename=uploaded_name,
        uploaded_bytes=uploaded_bytes,
        include_system_sources=include_system,
    )
    write_reparodynamics_audit_event_from_runner_report(runner_report, source="Reparodynamics Phase 3E scan", phase3c_report=phase3c_report)
    write_phase3e_dynamic_odds_audit_event(phase3e_report, source="Reparodynamics Phase 3E Dynamic Odds Shadow")
    memory = update_repair_memory(memory, phase3c_report, source="Reparodynamics Phase 3C")
    memory = update_repair_memory(memory, phase3e_report, source="Reparodynamics Phase 3E Dynamic Odds")
    memory = save_repair_memory(memory, workspace_id)
    st.session_state["phase3c_latest_report"] = phase3c_report
    st.session_state["phase3e_latest_report"] = phase3e_report
    st.session_state["phase3d_repair_memory"] = memory
    st.session_state["shadow_mode_latest_report"] = runner_report.to_dict()
    st.success(t("success"))

phase3e = st.session_state.get("phase3e_latest_report")
phase3c = st.session_state.get("phase3c_latest_report")
if phase3e:
    run_id = str(phase3e.get("memory_run_id") or phase3e.get("dynamic_shadow_run_id") or "")
    if run_id and run_id in set(str(item) for item in memory.get("saved_run_ids", [])):
        st.info(t("already_saved"))
    elif st.button(t("save")):
        memory = update_repair_memory(load_repair_memory(workspace_id), phase3e, source="Manual Phase 3E save")
        memory = save_repair_memory(memory, workspace_id)
        st.session_state["phase3d_repair_memory"] = memory
        st.success(t("saved"))

memory = st.session_state.get("phase3d_repair_memory") or load_repair_memory(workspace_id)
frames = repair_memory_to_frames(memory)
items = memory.get("items", {}) or {}
repair_keys = sorted(items.keys())

tabs = st.tabs([t("phase3e"), t("lr"), t("rows"), t("memory"), t("manual"), t("phase3c"), t("blockers"), t("watchlists"), t("comparison"), t("safety"), t("audit")])

with tabs[0]:
    if phase3e:
        show_frame(one_row(dynamic_summary(phase3e)))
        show_frame(one_row(phase3e.get("comparison_metrics", {}) or {}))
    else:
        st.info(t("no_run"))

with tabs[1]:
    lr_items = list(((phase3e or {}).get("lr_model_summary", {}) or {}).get("lr_by_feature", {}).values())
    show_rows(lr_items)

with tabs[2]:
    dynamic_rows = list((phase3e or {}).get("dynamic_rows", []) or [])
    frame = pd.DataFrame(dynamic_rows)
    if not frame.empty:
        wanted = [
            "event",
            "event_id",
            "sport",
            "league",
            "market_type",
            "decimal_odds",
            "current_model_probability",
            "dynamic_probability",
            "dynamic_edge",
            "dynamic_no_vig_edge",
            "dynamic_EV",
            "dynamic_signal_status",
        ]
        cols = [column for column in wanted if column in frame.columns]
        show_frame(frame[cols] if cols else frame)
    else:
        st.info(t("empty"))

with tabs[3]:
    show_frame(frames["summary"])

with tabs[4]:
    if not repair_keys:
        st.info(t("empty"))
    else:
        selected_key = st.selectbox(t("review_repair"), repair_keys, key="manual_repair_key")
        action_display, action_reverse = localize_options(["keep_testing", "reject", "watchlist", "manual_approved_for_future", "clear_manual_decision"], LANG)
        action_label = st.selectbox(t("review_action"), action_display, key="manual_repair_action")
        reviewer = st.text_input(t("reviewer"), value="manual", key="manual_reviewer")
        note = st.text_area(t("review_note"), value="", key="manual_review_note")
        if st.button(t("apply_review")):
            memory = manual_review_decision(load_repair_memory(workspace_id), selected_key, action_reverse[action_label], reviewer=reviewer, note=note)
            memory = save_repair_memory(memory, workspace_id)
            st.session_state["phase3d_repair_memory"] = memory
            st.success(t("review_saved"))
        show_frame(frames["summary"])

with tabs[5]:
    if phase3c:
        show_frame(one_row(phase3c.get("baseline_metrics", {}) or {}))
        st.json(phase3c.get("summary_counts", {}))
    else:
        st.info(t("no_run"))

with tabs[6]:
    show_rows(list((phase3e or phase3c or {}).get("data_blockers", []) or []))

with tabs[7]:
    show_rows(list((phase3e or phase3c or {}).get("watchlists", []) or []))

with tabs[8]:
    show_rows(list((phase3e or phase3c or {}).get("shadow_tested_repairs", []) or []))

with tabs[9]:
    show_frame(one_row((phase3e or phase3c or {}).get("safety_gates", {}) or {}))

with tabs[10]:
    latest = latest_reparodynamics_audit_event()
    if latest is None:
        st.info(t("empty"))
    else:
        st.json(latest.to_dict() if hasattr(latest, "to_dict") else dict(latest))
    show_frame(frames["events"])

st.success(t("final_rule"))
