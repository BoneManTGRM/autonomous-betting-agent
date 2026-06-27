from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.adaptive_repair_runner import rows_from_csv_bytes, run_adaptive_repair_scan
from autonomous_betting_agent.reparodynamics_audit import (
    audit_event_display_rows,
    latest_reparodynamics_audit_event,
    write_reparodynamics_audit_event_from_runner_report,
)
from autonomous_betting_agent.reparodynamics_doctrine import get_reparodynamics_doctrine
from autonomous_betting_agent.reparodynamics_shadow_results import shadow_result_rows, shadow_summary
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title="Reparodynamics", layout="wide")
LANG = render_app_sidebar("reparodynamics", language_key="reparodynamics_language", selector="radio")

TEXT = {
    "en": {
        "title": "Reparodynamics",
        "caption": "Measured self-repair doctrine and Phase 3B Shadow Mode control panel.",
        "warning": "Phase 3B can evaluate repair candidates in Shadow Mode. It writes audit records and comparison tables, but live predictions remain unchanged.",
        "phase": "Current phase",
        "mode": "Operating mode",
        "repair": "Repair activation",
        "shadow": "Shadow Mode",
        "tgrm": "TGRM",
        "rye": "RYE",
        "controls": "Phase 3B scan controls",
        "include_system": "Include available local system sources",
        "upload": "Optional graded CSV for this scan",
        "loaded": "Loaded uploaded rows",
        "run": "Run Phase 3B Shadow Mode scan",
        "success": "Shadow Mode scan completed. Audit event written.",
        "audit": "Latest audit event",
        "summary": "Shadow Mode summary",
        "candidates": "Shadow Mode candidates",
        "no_run": "No audit event recorded yet.",
        "no_candidates": "No Shadow Mode candidates generated.",
        "forbidden": "Forbidden in Phase 3B",
        "status": "Activation status",
    },
    "es": {
        "title": "Reparodynamics",
        "caption": "Doctrina de autorreparación medida y panel Fase 3B Shadow Mode.",
        "warning": "La Fase 3B puede evaluar candidatos de reparación en Shadow Mode. Escribe auditoría y tablas de comparación, pero las predicciones en vivo no cambian.",
        "phase": "Fase actual",
        "mode": "Modo operativo",
        "repair": "Activación de reparación",
        "shadow": "Shadow Mode",
        "tgrm": "TGRM",
        "rye": "RYE",
        "controls": "Controles de escaneo Fase 3B",
        "include_system": "Incluir fuentes locales disponibles del sistema",
        "upload": "CSV calificado opcional para este escaneo",
        "loaded": "Filas subidas cargadas",
        "run": "Ejecutar escaneo Fase 3B Shadow Mode",
        "success": "Escaneo Shadow Mode completado. Evento de auditoría escrito.",
        "audit": "Último evento de auditoría",
        "summary": "Resumen Shadow Mode",
        "candidates": "Candidatos Shadow Mode",
        "no_run": "Todavía no hay evento de auditoría registrado.",
        "no_candidates": "No se generaron candidatos Shadow Mode.",
        "forbidden": "Prohibido en Fase 3B",
        "status": "Estado de activación",
    },
}

ES = {
    "Phase 3B": "Fase 3B",
    "Shadow Mode evaluation": "Evaluación Shadow Mode",
    "Forbidden": "Prohibido",
    "ON": "ENCENDIDO",
    "OFF": "APAGADO",
    "NO DATA": "SIN DATOS",
    "YES": "SÍ",
    "NO": "NO",
    "Phase 3B Shadow Mode; live mutation forbidden": "Fase 3B Shadow Mode; mutación en vivo prohibida",
    "ABA may test repairs in Shadow Mode, but live repair remains forbidden.": "ABA puede probar reparaciones en Shadow Mode, pero la reparación en vivo sigue prohibida.",
}

FIELD_ES = {
    "Last Reparodynamics Run": "Última ejecución Reparodynamics",
    "Source": "Fuente",
    "Rows scanned": "Filas escaneadas",
    "Unique events scanned": "Eventos únicos escaneados",
    "Duplicates detected": "Duplicados detectados",
    "New patterns detected": "Patrones nuevos detectados",
    "Drift detected": "Deriva detectada",
    "Repair candidates generated": "Candidatos de reparación generados",
    "Shadow Mode": "Shadow Mode",
    "Live Mutation": "Mutación en vivo",
    "Reason": "Razón",
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT["en"]).get(key, key)


def v(value: object) -> str:
    text = str(value or "")
    return ES.get(text, text) if LANG == "es" else text


def audit_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    if LANG != "es":
        return rows
    return [{"field": FIELD_ES.get(row["field"], row["field"]), "value": v(row["value"])} for row in rows]


def table(items: object) -> pd.DataFrame:
    values = list(items or [])
    return pd.DataFrame({t("forbidden"): values})


doctrine = get_reparodynamics_doctrine()
st.title(t("title"))
st.caption(t("caption"))
st.warning(t("warning"))
st.page_link("pages/shadow_mode_results.py", label=t("summary"))

cols = st.columns(6)
cols[0].metric(t("phase"), v(doctrine.get("current_phase", "")))
cols[1].metric(t("mode"), v(doctrine.get("operating_mode", "")))
cols[2].metric(t("repair"), v(doctrine.get("repair_activation", "")))
cols[3].metric(t("shadow"), v(doctrine.get("shadow_mode_activation", "")))
cols[4].metric(t("tgrm"), v(doctrine.get("tgrm_activation", "")))
cols[5].metric(t("rye"), v(doctrine.get("rye_activation", "")))

st.subheader(t("controls"))
include_system = st.checkbox(t("include_system"), value=True)
uploaded_rows = None
uploaded_bytes = None
uploaded_name = "reparodynamics_upload.csv"
upload = st.file_uploader(t("upload"), type=["csv"], key="reparodynamics_phase3b_upload")
if upload is not None:
    uploaded_bytes = upload.getvalue()
    uploaded_name = upload.name
    uploaded_rows = rows_from_csv_bytes(uploaded_bytes)
    st.success(f"{t('loaded')}: {len(uploaded_rows)}")
    st.dataframe(pd.DataFrame(uploaded_rows).head(50), use_container_width=True)

if st.button(t("run"), type="primary"):
    report = run_adaptive_repair_scan(uploaded_rows=uploaded_rows, uploaded_filename=uploaded_name, uploaded_bytes=uploaded_bytes, include_system_sources=include_system)
    st.session_state["shadow_mode_latest_report"] = report.to_dict()
    audit_event = write_reparodynamics_audit_event_from_runner_report(report, source="Reparodynamics Phase 3B scan")
    st.success(t("success"))
    summary = shadow_summary(report)
    candidates = shadow_result_rows(report)
    st.subheader(t("summary"))
    st.json(summary)
    st.subheader(t("candidates"))
    if candidates:
        st.dataframe(pd.DataFrame(candidates), use_container_width=True, hide_index=True)
    else:
        st.info(t("no_candidates"))
else:
    audit_event = latest_reparodynamics_audit_event()

st.subheader(t("audit"))
if audit_event is None:
    st.info(t("no_run"))
else:
    st.dataframe(pd.DataFrame(audit_rows(audit_event_display_rows(audit_event))), use_container_width=True, hide_index=True)

st.subheader(t("forbidden"))
st.dataframe(table(doctrine.get("forbidden_actions", [])), use_container_width=True, hide_index=True)

st.subheader(t("status"))
st.dataframe(
    pd.DataFrame(
        [
            {"control": "live_mutation", "status": v(doctrine.get("live_mutation", ""))},
            {"control": "repair_activation", "status": v(doctrine.get("repair_activation", ""))},
            {"control": "shadow_mode_activation", "status": v(doctrine.get("shadow_mode_activation", ""))},
            {"control": "tgrm_activation", "status": v(doctrine.get("tgrm_activation", ""))},
            {"control": "rye_activation", "status": v(doctrine.get("rye_activation", ""))},
        ]
    ),
    use_container_width=True,
    hide_index=True,
)

st.success(v(doctrine.get("final_rule", "")))
