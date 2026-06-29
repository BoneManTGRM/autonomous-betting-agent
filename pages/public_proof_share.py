from __future__ import annotations

import hashlib

import pandas as pd
import streamlit as st

from autonomous_betting_agent.commercial_platform_tools import normalize_workspace_id
from autonomous_betting_agent.proof_package_integrity_service import build_proof_package_qa_report
from autonomous_betting_agent.proof_package_service import (
    build_client_summary_package,
    build_public_proof_package,
    export_proof_package_csv_bundle,
    export_proof_package_json,
    export_proof_package_markdown,
    package_is_proof_ready,
    validate_public_package_redactions,
)
from autonomous_betting_agent.row_normalizer import safe_text
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title="Public Proof Share", layout="wide")
LANG = render_app_sidebar("public_proof_share", language_key="public_proof_share_language")

PUBLIC_SHARE_PACKAGE_TYPES = ("public", "client")
PUBLIC_SHARE_PACKAGE_PREVIEW_KEY = "public_proof_share_package_preview"
PUBLIC_SHARE_FINGERPRINT_KEY = "public_proof_share_input_fingerprint"
PUBLIC_SHARE_QA_PREVIEW_KEY = "public_proof_share_qa_preview"
PUBLIC_SHARE_BLOCKED_FIELDS = (
    "private",
    "internal_review",
    "private_export_csv",
    "private_export_json",
    "private_export_hash",
    "previous_row_hash",
    "correction_reason",
    "source_file",
    "api_key",
    "secret",
    "token",
    "bearer",
    "password",
    "/home/",
    "/mnt/",
    "data/private",
    ".env",
)

TEXT = {
    "en": {
        "title": "Public Proof Share",
        "caption": "Read-only public/client-safe proof view. Private audit fields are never shown here.",
        "workspace_id": "Workspace ID",
        "package_type": "package_type",
        "build_preview": "Build public proof preview",
        "proof_caption": "Ledger-backed packages are proof-grade only when proof_ready=true. Provisional or empty packages are not final proof.",
        "preview_ready": "Public proof preview built. Downloads use this package_hash until inputs change.",
        "no_preview": "Build a public/client proof preview to view share-safe proof.",
        "stale_preview": "Current workspace/package type does not match the displayed preview. Build a new preview before downloading.",
        "redaction_failed": "Redaction validation failed. Public/client downloads are blocked.",
        "not_proof_ready": "This package is not proof-ready. Do not present it as final proof.",
        "proof_ready": "proof_ready",
        "proof_grade": "proof_grade",
        "ledger_backed": "ledger_backed",
        "selected_source": "selected_source",
        "ledger_integrity_status": "ledger_integrity_status",
        "dashboard_ready": "dashboard_ready",
        "package_id": "package_id",
        "package_hash": "package_hash",
        "public_export_hash": "public_export_hash",
        "qa_report_hash": "qa_report_hash",
        "record": "Record",
        "roi": "ROI",
        "profit_units": "Profit Units",
        "average_clv": "Average CLV",
        "unique_events": "Unique Events",
        "top_ev": "Top +EV Picks",
        "no_top_ev": "No playable positive-EV picks available.",
        "verification_manifest": "verification_manifest",
        "redaction_status": "redaction_status",
        "qa_status": "QA status",
        "warnings_errors": "Warnings / errors",
        "download_json": "Download public proof JSON",
        "download_markdown": "Download public proof Markdown",
        "download_csv": "Download public proof CSV",
    },
    "es": {
        "title": "Compartir Prueba Pública",
        "caption": "Vista solo lectura segura para público/cliente. Los campos privados de auditoría nunca se muestran aquí.",
        "workspace_id": "ID de workspace",
        "package_type": "package_type",
        "build_preview": "Crear vista previa pública de prueba",
        "proof_caption": "Los paquetes respaldados por ledger son de grado prueba solo cuando proof_ready=true. Los paquetes provisionales o vacíos no son prueba final.",
        "preview_ready": "Vista previa pública creada. Las descargas usan este package_hash hasta que cambien las entradas.",
        "no_preview": "Crea una vista previa public/client para ver prueba segura para compartir.",
        "stale_preview": "El workspace/package type actual no coincide con la vista previa mostrada. Crea una nueva vista previa antes de descargar.",
        "redaction_failed": "Falló la validación de redacción. Las descargas public/client están bloqueadas.",
        "not_proof_ready": "Este paquete no está listo como prueba. No lo presentes como prueba final.",
        "proof_ready": "proof_ready",
        "proof_grade": "proof_grade",
        "ledger_backed": "ledger_backed",
        "selected_source": "selected_source",
        "ledger_integrity_status": "ledger_integrity_status",
        "dashboard_ready": "dashboard_ready",
        "package_id": "package_id",
        "package_hash": "package_hash",
        "public_export_hash": "public_export_hash",
        "qa_report_hash": "qa_report_hash",
        "record": "Récord",
        "roi": "ROI",
        "profit_units": "Unidades de ganancia",
        "average_clv": "CLV promedio",
        "unique_events": "Eventos únicos",
        "top_ev": "Top +EV",
        "no_top_ev": "No hay picks positivos +EV jugables disponibles.",
        "verification_manifest": "verification_manifest",
        "redaction_status": "redaction_status",
        "qa_status": "Estado QA",
        "warnings_errors": "Advertencias / errores",
        "download_json": "Descargar JSON de prueba pública",
        "download_markdown": "Descargar Markdown de prueba pública",
        "download_csv": "Descargar CSV de prueba pública",
    },
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT["en"]).get(key, key)


def public_share_fingerprint(workspace_id: str, package_type: str, package_id: str, package_hash: str) -> str:
    payload = "|".join([safe_text(workspace_id), safe_text(package_type), safe_text(package_id), safe_text(package_hash)])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _package_builder(package_type: str):
    return build_client_summary_package if package_type == "client" else build_public_proof_package


def _hash_fragment(package: dict) -> str:
    return safe_text(package.get("package_hash")).split("_")[-1][:12] or "nohash"


def _filename(package: dict, suffix: str) -> str:
    workspace_id = safe_text(package.get("workspace_id")) or "default"
    package_type = safe_text(package.get("package_type")) or "public"
    return f"aba_public_proof_share_{workspace_id}_{package_type}_{_hash_fragment(package)}.{suffix}"


def _preview_matches(package: dict, workspace_id: str, package_type: str) -> bool:
    if not package:
        return False
    current = public_share_fingerprint(workspace_id, package_type, safe_text(package.get("package_id")), safe_text(package.get("package_hash")))
    return st.session_state.get(PUBLIC_SHARE_FINGERPRINT_KEY) == current


def _redaction_passed(package: dict) -> bool:
    return bool(validate_public_package_redactions(package).get("passed"))


def _safe_top_picks(package: dict) -> pd.DataFrame:
    rows = []
    for pick in package.get("top_positive_ev_picks") or []:
        rows.append({
            "event": pick.get("event", ""),
            "pick": pick.get("pick", ""),
            "market": pick.get("market", ""),
            "sportsbook": pick.get("sportsbook", ""),
            "decimal_odds": pick.get("decimal_odds", ""),
            "model_probability": pick.get("model_probability", ""),
            "edge": pick.get("edge", ""),
            "no_vig_edge": pick.get("no_vig_edge", ""),
            "expected_value": pick.get("expected_value", ""),
            "clv": pick.get("clv", ""),
            "report_lane": pick.get("report_lane", ""),
            "odds_verified": pick.get("odds_verified", ""),
        })
    return pd.DataFrame(rows)


def _render_downloads(package: dict, stale: bool, redaction_ok: bool) -> None:
    disabled = stale or not redaction_ok
    package_hash = safe_text(package.get("package_hash")) or "nohash"
    json_text = export_proof_package_json(package)
    markdown_text = export_proof_package_markdown(package)
    csv_bundle = export_proof_package_csv_bundle(package)
    col1, col2 = st.columns(2)
    col1.download_button(
        t("download_json"),
        json_text.encode("utf-8"),
        file_name=_filename(package, "json"),
        mime="application/json",
        disabled=disabled,
        key=f"public_proof_share_json_{package_hash}",
    )
    col2.download_button(
        t("download_markdown"),
        markdown_text.encode("utf-8"),
        file_name=_filename(package, "md"),
        mime="text/markdown",
        disabled=disabled,
        key=f"public_proof_share_markdown_{package_hash}",
    )
    for filename, csv_text in csv_bundle.items():
        st.download_button(
            f"{t('download_csv')}: {filename}",
            safe_text(csv_text).encode("utf-8"),
            file_name=f"{_filename(package, 'csv').rsplit('.', 1)[0]}_{filename}",
            mime="text/csv",
            disabled=disabled,
            key=f"public_proof_share_csv_{package_hash}_{filename}",
        )


st.title(t("title"))
st.caption(t("caption"))
st.caption(t("proof_caption"))

workspace_id = normalize_workspace_id(st.text_input(t("workspace_id"), value=st.session_state.get("aba_test_window_id", "test_01"), key="public_proof_share_workspace_id"))
package_type = st.selectbox(t("package_type"), PUBLIC_SHARE_PACKAGE_TYPES, index=0, key="public_proof_share_package_type")

if st.button(t("build_preview"), key="public_proof_share_build_preview"):
    package = _package_builder(package_type)(workspace_id)
    qa_report = build_proof_package_qa_report(workspace_id, package_type=package_type)
    fingerprint = public_share_fingerprint(workspace_id, package_type, safe_text(package.get("package_id")), safe_text(package.get("package_hash")))
    st.session_state[PUBLIC_SHARE_PACKAGE_PREVIEW_KEY] = package
    st.session_state[PUBLIC_SHARE_QA_PREVIEW_KEY] = qa_report
    st.session_state[PUBLIC_SHARE_FINGERPRINT_KEY] = fingerprint
    st.info(t("preview_ready"))

package = st.session_state.get(PUBLIC_SHARE_PACKAGE_PREVIEW_KEY, {})
qa_report = st.session_state.get(PUBLIC_SHARE_QA_PREVIEW_KEY, {})

if not package:
    st.info(t("no_preview"))
    st.stop()

stale = not _preview_matches(package, workspace_id, package_type)
redaction_ok = _redaction_passed(package)
proof_ready = package_is_proof_ready(package)
if stale:
    st.error(t("stale_preview"))
if not redaction_ok:
    st.error(t("redaction_failed"))
if not proof_ready:
    st.warning(t("not_proof_ready"))

status_cols = st.columns(4)
status_cols[0].metric(t("proof_ready"), str(proof_ready))
status_cols[1].metric(t("proof_grade"), safe_text(package.get("proof_grade")))
status_cols[2].metric(t("ledger_backed"), str(bool(package.get("ledger_backed"))))
status_cols[3].metric(t("selected_source"), safe_text(package.get("selected_source")))

hash_cols = st.columns(4)
hash_cols[0].metric(t("package_id"), safe_text(package.get("package_id"))[:28])
hash_cols[1].metric(t("package_hash"), safe_text(package.get("package_hash"))[:28])
hash_cols[2].metric(t("public_export_hash"), safe_text(package.get("public_export_hash"))[:28])
hash_cols[3].metric(t("qa_report_hash"), safe_text(qa_report.get("qa_report_hash"))[:28])

perf_cols = st.columns(5)
perf_cols[0].metric(t("record"), f"{package.get('wins', 0)}-{package.get('losses', 0)}")
perf_cols[1].metric(t("roi"), package.get("ROI", 0))
perf_cols[2].metric(t("profit_units"), package.get("profit_units", 0))
perf_cols[3].metric(t("average_clv"), package.get("average_CLV", ""))
perf_cols[4].metric(t("unique_events"), package.get("unique_events", 0))

st.markdown(f"### {t('top_ev')}")
top_frame = _safe_top_picks(package)
if top_frame.empty:
    st.info(t("no_top_ev"))
else:
    st.dataframe(top_frame, use_container_width=True, hide_index=True)

with st.expander(t("verification_manifest"), expanded=False):
    st.json(package.get("verification_manifest") or {})
with st.expander(t("redaction_status"), expanded=False):
    st.json(validate_public_package_redactions(package))
with st.expander(t("qa_status"), expanded=False):
    st.json({
        "qa_report_hash": qa_report.get("qa_report_hash"),
        "overall_passed": qa_report.get("overall_passed"),
        "export_integrity_passed": qa_report.get("export_integrity_passed"),
        "public_client_safety_passed": qa_report.get("public_client_safety_passed"),
        "proof_grade_rules_passed": qa_report.get("proof_grade_rules_passed"),
        "top_positive_ev_safety_passed": qa_report.get("top_positive_ev_safety_passed"),
        "download_bundle_passed": qa_report.get("download_bundle_passed"),
        "stale_preview_contract_passed": qa_report.get("stale_preview_contract_passed"),
    })
with st.expander(t("warnings_errors"), expanded=False):
    st.json({
        "package_warnings": package.get("warnings") or [],
        "package_errors": package.get("errors") or [],
        "qa_warnings": qa_report.get("warnings") or [],
        "qa_errors": qa_report.get("errors") or [],
    })

_render_downloads(package, stale, redaction_ok)
