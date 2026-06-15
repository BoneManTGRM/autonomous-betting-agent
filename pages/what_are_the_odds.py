from __future__ import annotations

import io
from typing import Any

import pandas as pd
import streamlit as st

import autonomous_betting_agent  # noqa: F401  # installs global sidebar/report translator
from autonomous_betting_agent.audit import audit_dashboard_metrics, enrich_prediction_frame
from autonomous_betting_agent.mobile_report import ACTIONABLE_TIERS, compact_report_frame, rejection_summary, render_pick_cards
from autonomous_betting_agent.odds_breakdown import build_odds_breakdown

st.set_page_config(page_title="What Are the Odds", layout="wide")

st.sidebar.selectbox("Language / Idioma", ["English", "Español"], key="what_are_the_odds_language")
IS_ES = str(st.session_state.get("global_language", "English")) == "Español"

TEXT = {
    "title": "Qué dicen las cuotas" if IS_ES else "What Are the Odds",
    "caption": "Sube uno o más CSVs. Lee reportes de Predictor Pro, exportaciones de cuotas y archivos de marcadores/props." if IS_ES else "Upload one or more CSVs. Reads Pro Predictor reports, odds exports, and scores/props files.",
    "upload": "Subir archivo(s) CSV" if IS_ES else "Upload CSV file(s)",
    "paste": "O pegar texto CSV" if IS_ES else "Or paste CSV text",
    "auto": "Analizar automáticamente" if IS_ES else "Auto-analyze",
    "refresh": "Analizar / actualizar" if IS_ES else "Analyze / refresh",
    "waiting": "Sube CSVs o pega texto CSV." if IS_ES else "Upload CSVs or paste CSV text.",
    "source": "Fuente" if IS_ES else "Source",
    "input_rows": "Filas de entrada" if IS_ES else "Input rows",
    "main_rows": "Filas del reporte" if IS_ES else "Main report rows",
    "candidates": "Candidatos" if IS_ES else "Candidates",
    "actionable": "Accionables" if IS_ES else "Actionable",
    "missing_odds": "Cuotas faltantes" if IS_ES else "Missing odds",
    "scores": "Marcadores" if IS_ES else "Scores",
    "props": "Props CSV" if IS_ES else "CSV props",
    "quality": "Calidad mínima" if IS_ES else "Minimum quality",
    "candidate_only": "Solo candidatos" if IS_ES else "Candidates only",
    "search": "Buscar evento/pick" if IS_ES else "Search event/pick",
    "summary": "Resumen" if IS_ES else "Summary",
    "best": "Mejor EV / valor" if IS_ES else "Best EV / value",
    "main": "Reporte principal" if IS_ES else "Main report",
    "extras": "Marcadores y props" if IS_ES else "Scores and props",
    "diag": "Diagnóstico" if IS_ES else "Diagnostics",
    "health": "Salud de columnas" if IS_ES else "Column health",
    "download_main": "Descargar reporte principal" if IS_ES else "Download main report",
    "download_props": "Descargar marcadores/props" if IS_ES else "Download scores/props",
    "no_candidates": "No hay candidatos después de filtros." if IS_ES else "No candidates after filters.",
    "odds_only": "Algunas filas son odds_only: se leyeron, pero no tienen probabilidad del modelo." if IS_ES else "Some rows are odds_only: they were read, but no model probability was found.",
    "missing_odds_warning": "Faltan cuotas en parte o todo el reporte. ROI, EV y break-even no son confiables para esas filas." if IS_ES else "Odds are missing for part or all of this report. ROI, EV, and break-even are not reliable for those rows.",
    "best_first": "Mejores picks primero" if IS_ES else "Best picks first",
    "why_rejected": "Por qué fueron rechazados / solo vigilar" if IS_ES else "Why rows were rejected / Watch Only",
    "compact": "Tabla compacta móvil" if IS_ES else "Compact mobile table",
    "technical": "Reporte técnico completo" if IS_ES else "Full technical report",
}


def to_float(value: Any) -> float | None:
    text = str(value or "").replace("%", "").replace(",", "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def pct(value: Any) -> str:
    if value in (None, ""):
        return ""
    try:
        return f"{float(value) * 100:.1f}%"
    except (TypeError, ValueError):
        return ""


def read_inputs() -> tuple[str, pd.DataFrame | None]:
    uploads = st.file_uploader(TEXT["upload"], type=["csv"], accept_multiple_files=True, key="odds_multi_upload")
    pasted = st.text_area(TEXT["paste"], height=120, key="odds_paste_text")
    frames: list[pd.DataFrame] = []
    names: list[str] = []
    if uploads:
        for upload in uploads:
            try:
                frame = pd.read_csv(upload)
                frame["source_file"] = upload.name
                frames.append(frame)
                names.append(upload.name)
            except Exception as exc:
                st.warning(f"Could not read {upload.name}: {exc}")
    if pasted.strip():
        try:
            frame = pd.read_csv(io.StringIO(pasted.strip()))
            frame["source_file"] = "pasted_csv"
            frames.append(frame)
            names.append("pasted_csv")
        except Exception as exc:
            st.warning(f"Could not read pasted CSV: {exc}")
    if not frames:
        return "", None
    return ", ".join(names), pd.concat(frames, ignore_index=True, sort=False)


def filter_main(df: pd.DataFrame, min_quality: int, candidates_only: bool, query: str) -> pd.DataFrame:
    out = df.copy()
    if "odds_quality_score" in out.columns:
        out = out[out["odds_quality_score"].map(to_float).fillna(0) >= min_quality]
    if candidates_only and "decision" in out.columns:
        out = out[out["decision"].astype(str).isin(["candidate", "strong_candidate"])]
    if query.strip():
        query_l = query.strip().lower()
        cols = [col for col in ["event", "prediction", "sport", "market_type"] if col in out.columns]
        if cols:
            out = out[out[cols].astype(str).agg(" ".join, axis=1).str.lower().str.contains(query_l, regex=False, na=False)]
    return out


def best_value(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "decision" not in df.columns:
        return pd.DataFrame()
    out = df[df["decision"].astype(str).isin(["strong_candidate", "candidate"])].copy()
    if out.empty:
        return out
    out["_ev"] = out.get("computed_ev_decimal", "").map(to_float).fillna(-999)
    out["_q"] = out.get("odds_quality_score", "").map(to_float).fillna(0)
    out = out.sort_values(["_ev", "_q"], ascending=[False, False]).drop(columns=["_ev", "_q"])
    cols = ["event", "sport", "prediction", "model_probability", "market_probability", "best_price", "computed_ev_decimal", "model_minus_implied", "odds_quality_score", "decision", "estimated_score"]
    return out[[col for col in cols if col in out.columns]].head(15)


def column_health(diag: pd.DataFrame) -> pd.DataFrame:
    if diag.empty:
        return diag
    row = diag.iloc[0].to_dict()
    fields = ["event_col", "pick_col", "probability_col", "market_probability_col", "price_col", "sport_col", "market_col", "confidence_col", "books_col", "api_col", "warning_col"]
    return pd.DataFrame([{"field": field, "detected_column": row.get(field, "missing"), "status": "ok" if str(row.get(field, "missing")) not in {"missing", ""} else "missing"} for field in fields])


def analyzed_view(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any], int]:
    enriched = enrich_prediction_frame(df) if not df.empty else pd.DataFrame()
    issues = rejection_summary(enriched)
    compact = compact_report_frame(enriched)
    actionable = enriched[enriched["confidence_tier"].isin(ACTIONABLE_TIERS)] if "confidence_tier" in enriched.columns else pd.DataFrame()
    metrics = audit_dashboard_metrics(enriched)
    missing_odds = int(issues.loc[issues["Issue"] == "Missing odds / price", "Count"].sum()) if not issues.empty else 0
    return enriched, issues, compact, actionable, metrics, missing_odds


st.title(TEXT["title"])
st.caption(TEXT["caption"])
source, raw_df = read_inputs()

if raw_df is None:
    st.info(TEXT["waiting"])
    st.stop()

st.caption(f"{TEXT['source']}: {source}")
st.metric(TEXT["input_rows"], len(raw_df))
auto = st.checkbox(TEXT["auto"], value=True, key="odds_auto_analyze")
manual = st.button(TEXT["refresh"], type="primary", use_container_width=True, key="odds_refresh")
signature = f"{source}|{len(raw_df)}|{list(raw_df.columns)}"
if manual or (auto and st.session_state.get("odds_signature") != signature):
    main_df, props_df, diag_df = build_odds_breakdown(raw_df)
    st.session_state["odds_main_df"] = main_df
    st.session_state["odds_props_df"] = props_df
    st.session_state["odds_diag_df"] = diag_df
    st.session_state["odds_signature"] = signature

main_df = st.session_state.get("odds_main_df")
props_df = st.session_state.get("odds_props_df")
diag_df = st.session_state.get("odds_diag_df")
if not isinstance(main_df, pd.DataFrame):
    st.stop()
if not isinstance(props_df, pd.DataFrame):
    props_df = pd.DataFrame()
if not isinstance(diag_df, pd.DataFrame):
    diag_df = pd.DataFrame()

candidate_count = int(main_df.get("decision", pd.Series(dtype=str)).astype(str).isin(["candidate", "strong_candidate"]).sum()) if not main_df.empty else 0
score_count = int((props_df.get("prop_type", pd.Series(dtype=str)).astype(str) == "estimated_score").sum()) if not props_df.empty else 0
csv_prop_count = int(props_df.get("source", pd.Series(dtype=str)).astype(str).str.contains("csv", case=False, na=False).sum()) if not props_df.empty else 0
odds_only_count = int(main_df.get("decision", pd.Series(dtype=str)).astype(str).eq("odds_only").sum()) if not main_df.empty else 0

min_quality = st.slider(TEXT["quality"], 0, 100, 0, 5, key="odds_min_quality")
candidates_only = st.checkbox(TEXT["candidate_only"], value=False, key="odds_candidates_only")
query = st.text_input(TEXT["search"], value="", key="odds_search")
filtered = filter_main(main_df, min_quality, candidates_only, query)
enriched, issues, compact, actionable, metrics, missing_odds = analyzed_view(filtered)

c1, c2, c3, c4 = st.columns(4)
c1.metric(TEXT["main_rows"], len(filtered))
c2.metric(TEXT["candidates"], candidate_count)
c3.metric(TEXT["actionable"], len(actionable))
c4.metric(TEXT["missing_odds"], missing_odds)

if odds_only_count:
    st.info(TEXT["odds_only"])
if missing_odds:
    st.warning(TEXT["missing_odds_warning"])

with st.expander("Extra counts" if not IS_ES else "Conteos extra", expanded=False):
    ec1, ec2, ec3, ec4 = st.columns(4)
    ec1.metric(TEXT["scores"], score_count)
    ec2.metric(TEXT["props"], csv_prop_count)
    ec3.metric("Official graded", metrics.get("official_graded", 0))
    ec4.metric("ROI", "" if metrics.get("roi_percent") is None else f"{metrics['roi_percent']:.2f}%")

tabs = st.tabs([TEXT["summary"], TEXT["best"], TEXT["main"], TEXT["extras"], TEXT["diag"]])
with tabs[0]:
    st.subheader(TEXT["best_first"])
    render_pick_cards(actionable)
    st.subheader(TEXT["why_rejected"])
    st.dataframe(issues, use_container_width=True, hide_index=True)
    with st.expander(TEXT["compact"], expanded=True):
        st.dataframe(compact, use_container_width=True, hide_index=True)
with tabs[1]:
    best = best_value(main_df)
    if best.empty:
        st.info(TEXT["no_candidates"])
    else:
        st.dataframe(compact_report_frame(enrich_prediction_frame(best)), use_container_width=True, hide_index=True)
with tabs[2]:
    st.dataframe(compact, use_container_width=True, hide_index=True)
    with st.expander(TEXT["technical"], expanded=False):
        st.dataframe(enriched, use_container_width=True, hide_index=True)
    st.download_button(TEXT["download_main"], data=enriched.to_csv(index=False), file_name="what_are_the_odds_breakdown.csv", mime="text/csv", key="odds_main_download")
with tabs[3]:
    if props_df.empty:
        st.info("No score or prop rows found." if not IS_ES else "No se encontraron filas de marcador o props.")
    else:
        st.dataframe(props_df, use_container_width=True, hide_index=True)
        st.download_button(TEXT["download_props"], data=props_df.to_csv(index=False), file_name="what_are_the_odds_scores_props.csv", mime="text/csv", key="odds_props_download")
with tabs[4]:
    st.write(TEXT["health"])
    st.dataframe(column_health(diag_df), use_container_width=True, hide_index=True)
    st.dataframe(diag_df, use_container_width=True, hide_index=True)
