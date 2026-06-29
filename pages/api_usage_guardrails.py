from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from autonomous_betting_agent.api_usage_guardrail_service import (
    API_USAGE_PROVIDERS,
    API_USAGE_TIERS,
    build_api_usage_guardrail_report,
    export_api_usage_guardrail_report_json,
    validate_api_usage_guardrail_report,
)
from autonomous_betting_agent.commercial_platform_tools import normalize_workspace_id
from autonomous_betting_agent.row_normalizer import safe_text
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title="API Usage Guardrails", layout="wide")
LANG = render_app_sidebar("api_usage_guardrails", language_key="api_usage_guardrails_language")

API_USAGE_GUARDRAIL_PREVIEW_KEY = "api_usage_guardrail_preview"

TEXT = {
    "en": {
        "title": "API Usage + Cost Guardrails",
        "caption": "Read-only SaaS-prep view for API calls, cache efficiency, cost estimates, provider limits, and overage warnings.",
        "workspace_id": "Workspace ID",
        "tier": "Tier",
        "provider": "Provider",
        "calls": "Calls",
        "cache_hits": "Cache hits",
        "estimated_cost": "Estimated cost USD",
        "add_event": "Add usage event to preview",
        "clear_events": "Clear preview events",
        "run_guardrail": "Run API guardrail check",
        "event_ready": "Usage event added to in-memory preview. No files were written.",
        "events_cleared": "Preview events cleared in memory.",
        "report_ready": "API usage guardrail report generated in memory. No files were written.",
        "api_ok": "API OK",
        "api_warning": "API WARNING",
        "api_high_usage": "API HIGH USAGE",
        "api_blocked": "API BLOCKED",
        "cache_ok": "CACHE OK",
        "cache_warning": "CACHE WARNING",
        "cost_ok": "COST OK",
        "cost_warning": "COST WARNING",
        "usage_events": "Usage events",
        "provider_results": "Provider results",
        "report_summary": "Report summary",
        "validation": "Report validation",
        "download_report": "Download API usage guardrail JSON",
        "no_report": "Run an API guardrail check to view report details.",
    },
    "es": {
        "title": "Guardrails de Uso y Costo de APIs",
        "caption": "Vista solo lectura para preparación SaaS: llamadas API, cache, costos estimados, límites por proveedor y alertas de sobreuso.",
        "workspace_id": "ID de workspace",
        "tier": "Tier",
        "provider": "Proveedor",
        "calls": "Llamadas",
        "cache_hits": "Cache hits",
        "estimated_cost": "Costo estimado USD",
        "add_event": "Agregar evento de uso a la vista previa",
        "clear_events": "Limpiar eventos de vista previa",
        "run_guardrail": "Ejecutar revisión de guardrails API",
        "event_ready": "Evento de uso agregado a la vista previa en memoria. No se escribieron archivos.",
        "events_cleared": "Eventos de vista previa limpiados en memoria.",
        "report_ready": "Reporte de guardrails API generado en memoria. No se escribieron archivos.",
        "api_ok": "API OK",
        "api_warning": "API WARNING",
        "api_high_usage": "API HIGH USAGE",
        "api_blocked": "API BLOCKED",
        "cache_ok": "CACHE OK",
        "cache_warning": "CACHE WARNING",
        "cost_ok": "COST OK",
        "cost_warning": "COST WARNING",
        "usage_events": "Eventos de uso",
        "provider_results": "Resultados por proveedor",
        "report_summary": "Resumen del reporte",
        "validation": "Validación del reporte",
        "download_report": "Descargar JSON de guardrails API",
        "no_report": "Ejecuta una revisión de guardrails API para ver detalles del reporte.",
    },
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT["en"]).get(key, key)


def _hash_fragment(value: str | None) -> str:
    return safe_text(value).split("_")[-1][:12] or "nohash"


def _report_filename(report: dict) -> str:
    return f"aba_api_usage_guardrail_{safe_text(report.get('workspace_id'))}_{safe_text(report.get('tier'))}_{_hash_fragment(report.get('report_hash'))}.json"


def _event_rows() -> list[dict]:
    return list(st.session_state.get("api_usage_guardrail_events") or [])


st.title(t("title"))
st.caption(t("caption"))

workspace_id = normalize_workspace_id(st.text_input(t("workspace_id"), value=st.session_state.get("aba_test_window_id", "test_01"), key="api_usage_workspace_id"))
tier = st.selectbox(t("tier"), API_USAGE_TIERS, index=0, key="api_usage_tier")

cols = st.columns(4)
provider = cols[0].selectbox(t("provider"), API_USAGE_PROVIDERS, index=0, key="api_usage_provider")
calls = cols[1].number_input(t("calls"), min_value=0, value=0, step=1, key="api_usage_calls")
cache_hits = cols[2].number_input(t("cache_hits"), min_value=0, value=0, step=1, key="api_usage_cache_hits")
estimated_cost = cols[3].number_input(t("estimated_cost"), min_value=0.0, value=0.0, step=0.01, key="api_usage_estimated_cost")

left, middle, right = st.columns(3)
with left:
    if st.button(t("add_event"), key="api_usage_add_event"):
        events = _event_rows()
        events.append({
            "workspace_id": workspace_id,
            "provider": provider,
            "endpoint": "manual_preview",
            "calls": int(calls),
            "cache_hits": int(cache_hits),
            "estimated_cost_usd": float(estimated_cost),
        })
        st.session_state["api_usage_guardrail_events"] = events
        st.info(t("event_ready"))
with middle:
    if st.button(t("clear_events"), key="api_usage_clear_events"):
        st.session_state["api_usage_guardrail_events"] = []
        st.session_state[API_USAGE_GUARDRAIL_PREVIEW_KEY] = {}
        st.info(t("events_cleared"))
with right:
    if st.button(t("run_guardrail"), key="api_usage_run_guardrail"):
        report = build_api_usage_guardrail_report(workspace_id, tier, _event_rows())
        st.session_state[API_USAGE_GUARDRAIL_PREVIEW_KEY] = report
        st.info(t("report_ready"))

st.markdown(f"### {t('usage_events')}")
st.dataframe(pd.DataFrame(_event_rows()), use_container_width=True, hide_index=True)

report = st.session_state.get(API_USAGE_GUARDRAIL_PREVIEW_KEY, {})
if not report:
    st.info(t("no_report"))
    st.stop()

validation = validate_api_usage_guardrail_report(report)
status_key = {
    "API OK": "api_ok",
    "API WARNING": "api_warning",
    "API HIGH USAGE": "api_high_usage",
    "API BLOCKED": "api_blocked",
}.get(report.get("status"), "api_blocked")
cache_status = t("cache_ok") if float(report.get("cache_hit_rate") or 0.0) >= float((report.get("tier_limits") or {}).get("min_cache_hit_rate", 0.0)) else t("cache_warning")
cost_status = t("cost_ok") if report.get("overall_passed") else t("cost_warning")
st.write({t(status_key): True, cache_status: True, cost_status: True})

metrics = st.columns(6)
metrics[0].metric("status", safe_text(report.get("status")))
metrics[1].metric("total_calls", report.get("total_calls", 0))
metrics[2].metric("billable_calls", report.get("total_billable_calls", 0))
metrics[3].metric("cache_hit_rate", report.get("cache_hit_rate", 0.0))
metrics[4].metric("estimated_cost_usd", report.get("estimated_total_cost_usd", 0.0))
metrics[5].metric("report_hash", safe_text(report.get("report_hash"))[:18])

st.markdown(f"### {t('report_summary')}")
st.json({
    "schema_version": report.get("schema_version"),
    "workspace_id": report.get("workspace_id"),
    "tier": report.get("tier"),
    "report_id": report.get("report_id"),
    "report_hash": report.get("report_hash"),
    "status": report.get("status"),
    "overall_passed": report.get("overall_passed"),
    "event_count": report.get("event_count"),
    "total_calls": report.get("total_calls"),
    "total_billable_calls": report.get("total_billable_calls"),
    "cache_hit_rate": report.get("cache_hit_rate"),
    "estimated_total_cost_usd": report.get("estimated_total_cost_usd"),
    "warning_count": len(report.get("warnings") or []),
    "error_count": len(report.get("errors") or []),
})

st.markdown(f"### {t('provider_results')}")
st.dataframe(pd.DataFrame(report.get("provider_results") or []), use_container_width=True, hide_index=True)

with st.expander(t("validation"), expanded=False):
    st.json(validation)

st.download_button(
    t("download_report"),
    export_api_usage_guardrail_report_json(report, public_safe=True).encode("utf-8"),
    file_name=_report_filename(report),
    mime="application/json",
    key=f"api_usage_guardrail_report_json_{safe_text(report.get('report_hash'))}",
)
