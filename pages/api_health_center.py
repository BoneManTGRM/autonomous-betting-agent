from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.api_health_service import (
    API_HEALTH_PROVIDERS,
    build_api_health_report,
    export_api_health_report_json,
    validate_api_health_report,
)
from autonomous_betting_agent.commercial_platform_tools import normalize_workspace_id
from autonomous_betting_agent.row_normalizer import safe_text
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title="Odds/API Health Center", layout="wide")
LANG = render_app_sidebar("api_health_center", language_key="api_health_center_language")

API_HEALTH_PREVIEW_KEY = "api_health_center_preview"
API_HEALTH_EVENTS_KEY = "api_health_center_events"

TEXT = {
    "en": {
        "title": "Odds/API Health Center",
        "caption": "Read-only data-source health view for API status, stale data, fallback usage, and report data-completeness.",
        "workspace_id": "Workspace ID",
        "provider": "Provider",
        "status_code": "Status code",
        "success_count": "Success count",
        "error_count": "Error count",
        "records_count": "Records count",
        "latency_ms": "Latency ms",
        "data_age_minutes": "Data age minutes",
        "fallback_active": "Fallback active",
        "context_available": "Context available",
        "odds_available": "Odds available",
        "add_event": "Add health event to preview",
        "clear_events": "Clear preview events",
        "run_health_check": "Run API health check",
        "event_ready": "Health event added to in-memory preview. No files were written.",
        "events_cleared": "Preview events cleared in memory.",
        "report_ready": "API health report generated in memory. No files were written.",
        "api_ok": "API OK",
        "api_degraded": "API DEGRADED",
        "api_stale": "API STALE",
        "api_down": "API DOWN",
        "fallback_active_status": "FALLBACK ACTIVE",
        "report_not_complete": "REPORT NOT DATA-COMPLETE",
        "data_complete": "DATA COMPLETE",
        "data_incomplete": "DATA INCOMPLETE",
        "usage_events": "Health events",
        "provider_results": "Provider results",
        "report_summary": "Report summary",
        "validation": "Report validation",
        "download_report": "Download API health JSON",
        "no_report": "Run an API health check to view report details.",
    },
    "es": {
        "title": "Centro de Salud Odds/API",
        "caption": "Vista solo lectura para estado de APIs, datos stale, fallback y completitud de reportes.",
        "workspace_id": "ID de workspace",
        "provider": "Proveedor",
        "status_code": "Código de estado",
        "success_count": "Éxitos",
        "error_count": "Errores",
        "records_count": "Registros",
        "latency_ms": "Latencia ms",
        "data_age_minutes": "Edad de datos minutos",
        "fallback_active": "Fallback activo",
        "context_available": "Contexto disponible",
        "odds_available": "Odds disponibles",
        "add_event": "Agregar evento de salud a la vista previa",
        "clear_events": "Limpiar eventos de vista previa",
        "run_health_check": "Ejecutar revisión de salud API",
        "event_ready": "Evento de salud agregado a vista previa en memoria. No se escribieron archivos.",
        "events_cleared": "Eventos de vista previa limpiados en memoria.",
        "report_ready": "Reporte de salud API generado en memoria. No se escribieron archivos.",
        "api_ok": "API OK",
        "api_degraded": "API DEGRADED",
        "api_stale": "API STALE",
        "api_down": "API DOWN",
        "fallback_active_status": "FALLBACK ACTIVE",
        "report_not_complete": "REPORT NOT DATA-COMPLETE",
        "data_complete": "DATA COMPLETE",
        "data_incomplete": "DATA INCOMPLETE",
        "usage_events": "Eventos de salud",
        "provider_results": "Resultados por proveedor",
        "report_summary": "Resumen del reporte",
        "validation": "Validación del reporte",
        "download_report": "Descargar JSON de salud API",
        "no_report": "Ejecuta una revisión de salud API para ver detalles del reporte.",
    },
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT["en"]).get(key, key)


def _hash_fragment(value: str | None) -> str:
    return safe_text(value).split("_")[-1][:12] or "nohash"


def _report_filename(report: dict) -> str:
    return f"aba_api_health_{safe_text(report.get('workspace_id'))}_{_hash_fragment(report.get('report_hash'))}.json"


def _event_rows() -> list[dict]:
    return list(st.session_state.get(API_HEALTH_EVENTS_KEY) or [])


st.title(t("title"))
st.caption(t("caption"))

workspace_id = normalize_workspace_id(st.text_input(t("workspace_id"), value=st.session_state.get("aba_test_window_id", "test_01"), key="api_health_workspace_id"))

cols = st.columns(5)
provider = cols[0].selectbox(t("provider"), API_HEALTH_PROVIDERS, index=0, key="api_health_provider")
status_code = cols[1].number_input(t("status_code"), min_value=0, value=200, step=1, key="api_health_status_code")
success_count = cols[2].number_input(t("success_count"), min_value=0, value=1, step=1, key="api_health_success_count")
error_count = cols[3].number_input(t("error_count"), min_value=0, value=0, step=1, key="api_health_error_count")
records_count = cols[4].number_input(t("records_count"), min_value=0, value=0, step=1, key="api_health_records_count")

cols2 = st.columns(5)
latency_ms = cols2[0].number_input(t("latency_ms"), min_value=0, value=0, step=100, key="api_health_latency_ms")
data_age_minutes = cols2[1].number_input(t("data_age_minutes"), min_value=0.0, value=0.0, step=1.0, key="api_health_data_age_minutes")
fallback_active = cols2[2].checkbox(t("fallback_active"), value=False, key="api_health_fallback_active")
context_available = cols2[3].checkbox(t("context_available"), value=True, key="api_health_context_available")
odds_available = cols2[4].checkbox(t("odds_available"), value=True, key="api_health_odds_available")

left, middle, right = st.columns(3)
with left:
    if st.button(t("add_event"), key="api_health_add_event"):
        events = _event_rows()
        events.append({
            "workspace_id": workspace_id,
            "provider": provider,
            "endpoint": "manual_preview",
            "status_code": int(status_code),
            "success_count": int(success_count),
            "error_count": int(error_count),
            "records_count": int(records_count),
            "latency_ms": int(latency_ms),
            "data_age_minutes": float(data_age_minutes),
            "fallback_active": bool(fallback_active),
            "context_available": bool(context_available),
            "odds_available": bool(odds_available),
        })
        st.session_state[API_HEALTH_EVENTS_KEY] = events
        st.info(t("event_ready"))
with middle:
    if st.button(t("clear_events"), key="api_health_clear_events"):
        st.session_state[API_HEALTH_EVENTS_KEY] = []
        st.session_state[API_HEALTH_PREVIEW_KEY] = {}
        st.info(t("events_cleared"))
with right:
    if st.button(t("run_health_check"), key="api_health_run_health_check"):
        report = build_api_health_report(workspace_id, _event_rows())
        st.session_state[API_HEALTH_PREVIEW_KEY] = report
        st.info(t("report_ready"))

st.markdown(f"### {t('usage_events')}")
st.dataframe(pd.DataFrame(_event_rows()), use_container_width=True, hide_index=True)

report = st.session_state.get(API_HEALTH_PREVIEW_KEY, {})
if not report:
    st.info(t("no_report"))
    st.stop()

validation = validate_api_health_report(report)
status_key = {
    "API OK": "api_ok",
    "API DEGRADED": "api_degraded",
    "API STALE": "api_stale",
    "API DOWN": "api_down",
    "FALLBACK ACTIVE": "fallback_active_status",
    "REPORT NOT DATA-COMPLETE": "report_not_complete",
}.get(report.get("status"), "report_not_complete")
data_key = "data_complete" if report.get("data_complete") else "data_incomplete"
st.write({t(status_key): True, t(data_key): True})

metrics = st.columns(6)
metrics[0].metric("status", safe_text(report.get("status")))
metrics[1].metric("data_complete", str(bool(report.get("data_complete"))))
metrics[2].metric("providers", report.get("provider_count", 0))
metrics[3].metric("down", report.get("down_provider_count", 0))
metrics[4].metric("stale/fallback", int(report.get("stale_provider_count", 0)) + int(report.get("fallback_provider_count", 0)))
metrics[5].metric("report_hash", safe_text(report.get("report_hash"))[:18])

st.markdown(f"### {t('report_summary')}")
st.json({
    "schema_version": report.get("schema_version"),
    "workspace_id": report.get("workspace_id"),
    "report_id": report.get("report_id"),
    "report_hash": report.get("report_hash"),
    "status": report.get("status"),
    "overall_passed": report.get("overall_passed"),
    "data_complete": report.get("data_complete"),
    "check_count": report.get("check_count"),
    "provider_count": report.get("provider_count"),
    "down_provider_count": report.get("down_provider_count"),
    "stale_provider_count": report.get("stale_provider_count"),
    "fallback_provider_count": report.get("fallback_provider_count"),
    "degraded_provider_count": report.get("degraded_provider_count"),
    "warning_count": len(report.get("warnings") or []),
    "error_count": len(report.get("errors") or []),
})

st.markdown(f"### {t('provider_results')}")
st.dataframe(pd.DataFrame(report.get("provider_results") or []), use_container_width=True, hide_index=True)

with st.expander(t("validation"), expanded=False):
    st.json(validation)

st.download_button(
    t("download_report"),
    export_api_health_report_json(report, public_safe=True).encode("utf-8"),
    file_name=_report_filename(report),
    mime="application/json",
    key=f"api_health_report_json_{safe_text(report.get('report_hash'))}",
)
