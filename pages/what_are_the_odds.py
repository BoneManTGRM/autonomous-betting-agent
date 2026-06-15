from __future__ import annotations

import io
import math
from typing import Any

import pandas as pd
import streamlit as st

import autonomous_betting_agent  # noqa: F401  # installs global sidebar/report translator

st.set_page_config(page_title="What Are the Odds", layout="wide")

language = st.sidebar.selectbox("Language / Idioma", ["English", "Español"], key="what_are_the_odds_language")
IS_ES = language == "Español"

TEXT = {
    "title": {"English": "What Are the Odds", "Español": "Qué dicen las cuotas"},
    "caption": {
        "English": "Upload any predictor/report CSV and this page will extract every market it can safely read: winner, score estimate, spread, total, round/method, home run, props, EV, and warnings.",
        "Español": "Sube cualquier CSV del predictor/reporte y esta página extrae cada mercado que pueda leer con seguridad: ganador, marcador estimado, spread, total, round/método, home run, props, EV y advertencias.",
    },
    "upload": {"English": "Upload report CSV", "Español": "Subir CSV del reporte"},
    "paste": {"English": "Or paste CSV text", "Español": "O pega texto CSV"},
    "detail": {"English": "Report depth", "Español": "Profundidad del reporte"},
    "simple": {"English": "Simple", "Español": "Simple"},
    "detailed": {"English": "Detailed", "Español": "Detallado"},
    "full": {"English": "Full ARA", "Español": "ARA completo"},
    "button": {"English": "Analyze odds", "Español": "Analizar cuotas"},
    "empty": {"English": "Upload or paste a CSV first.", "Español": "Primero sube o pega un CSV."},
    "loaded": {"English": "Rows loaded", "Español": "Filas cargadas"},
    "detected": {"English": "Detected columns", "Español": "Columnas detectadas"},
    "main": {"English": "Main odds report", "Español": "Reporte principal de cuotas"},
    "props": {"English": "Props and extras", "Español": "Props y extras"},
    "diagnostics": {"English": "Diagnostics", "Español": "Diagnóstico"},
    "download_main": {"English": "Download main odds report", "Español": "Descargar reporte principal"},
    "download_props": {"English": "Download props/extras report", "Español": "Descargar reporte de props/extras"},
    "no_props": {"English": "No score, round, home run, or prop fields were detected. The page still produced a winner/market odds report from the available columns.", "Español": "No se detectaron campos de marcador, round, home run o props. La página aún produjo un reporte de ganador/mercado con las columnas disponibles."},
    "note": {
        "English": "Official sportsbook props are used when the CSV contains those markets. Otherwise, score/round/home-run sections are model estimates only and are clearly labeled as estimates.",
        "Español": "Los props oficiales de casa de apuesta se usan cuando el CSV contiene esos mercados. Si no, marcador/round/home-run son solo estimaciones del modelo y se etiquetan como estimaciones.",
    },
}


def t(key: str) -> str:
    item = TEXT.get(key, {})
    return item.get(language) or item.get("English") or key


def clean_key(value: Any) -> str:
    return str(value or "").strip().lower().replace(" ", "_").replace("-", "_").replace("/", "_")


def find_col(df: pd.DataFrame, names: tuple[str, ...]) -> str | None:
    lookup = {clean_key(col): col for col in df.columns}
    for name in names:
        key = clean_key(name)
        if key in lookup:
            return lookup[key]
    for col in df.columns:
        col_key = clean_key(col)
        if any(clean_key(name) in col_key for name in names):
            return col
    return None


def parse_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    text = str(value).strip().replace(",", "").replace("%", "")
    if not text or text.lower() in {"nan", "none", "null", "unknown", "n/a"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_probability(value: Any) -> float | None:
    number = parse_float(value)
    if number is None:
        return None
    if number > 1.0 and number <= 100.0:
        number /= 100.0
    if 0.0 <= number <= 1.0:
        return number
    return None


def implied_prob_from_price(value: Any) -> float | None:
    price = parse_float(value)
    if price is None:
        return None
    if price > 1.01:
        return 1.0 / price
    if price >= 100:
        return 100.0 / (price + 100.0)
    if price <= -100:
        return abs(price) / (abs(price) + 100.0)
    return None


def pct(value: float | None) -> str:
    return "" if value is None else f"{value * 100:.1f}%"


def sport_family(sport: str) -> str:
    text = clean_key(sport)
    if any(token in text for token in ("mma", "ufc", "boxing", "combat", "pfl", "bellator")):
        return "combat"
    if any(token in text for token in ("mlb", "baseball")):
        return "baseball"
    if any(token in text for token in ("nba", "wnba", "basketball", "ncaab")):
        return "basketball"
    if any(token in text for token in ("nfl", "ncaaf", "football")) and "soccer" not in text:
        return "football"
    if any(token in text for token in ("soccer", "fifa", "uefa", "liga", "premier", "mls")):
        return "soccer"
    if "tennis" in text:
        return "tennis"
    if "hockey" in text or "nhl" in text:
        return "hockey"
    return "general"


def typical_total(family: str) -> float:
    return {
        "soccer": 2.6,
        "basketball": 221.0,
        "football": 45.0,
        "baseball": 8.5,
        "hockey": 6.0,
        "tennis": 23.0,
        "combat": 1.0,
    }.get(family, 3.0)


def estimate_score(event: str, pick: str, sport: str, probability: float | None, line_total: float | None = None, spread: float | None = None) -> tuple[str, str, str]:
    family = sport_family(sport)
    if family == "combat":
        return "", "", "not_applicable"
    total = line_total if line_total is not None and line_total > 0 else typical_total(family)
    p = probability if probability is not None else 0.55
    edge = max(-0.45, min(0.45, p - 0.50))
    margin = spread if spread is not None else edge * {"soccer": 2.2, "basketball": 22, "football": 16, "baseball": 3.2, "hockey": 2.5, "tennis": 6}.get(family, 3)
    winner_score = max(0.0, (total + abs(margin)) / 2)
    loser_score = max(0.0, total - winner_score)
    if family in {"soccer", "baseball", "hockey"}:
        ws, ls = round(winner_score), round(loser_score)
    elif family == "tennis":
        ws, ls = max(2, round(winner_score / 7)), max(0, round(loser_score / 7))
    else:
        ws, ls = round(winner_score), round(loser_score)
    score = f"{pick} {ws} - Opponent {ls}" if pick else f"{ws}-{ls}"
    return score, "model_estimate", "Estimated from probability, sport type, and any total/spread fields found."


def estimate_combat_round(row: pd.Series, pick: str, probability: float | None) -> tuple[str, str, str]:
    round_col_value = first_existing_value(row, ("round", "predicted_round", "method_round", "finish_round"))
    method_col_value = first_existing_value(row, ("method", "predicted_method", "finish_method", "win_method"))
    if round_col_value or method_col_value:
        label = " / ".join(str(x) for x in (method_col_value, round_col_value) if x not in (None, ""))
        return label, "csv_market_or_field", "Round/method came from a detected CSV field."
    p = probability or 0.55
    if p >= 0.72:
        return f"{pick} by decision or late finish", "model_estimate", "No official round prop found; estimated from strong favorite probability."
    if p >= 0.60:
        return f"{pick} by decision", "model_estimate", "No official round prop found; estimated from moderate favorite probability."
    return "close fight / decision most likely", "model_estimate", "No official round prop found; estimated from near-even probability."


def first_existing_value(row: pd.Series, names: tuple[str, ...]) -> Any:
    lookup = {clean_key(col): col for col in row.index}
    for name in names:
        col = lookup.get(clean_key(name))
        if col is not None and row.get(col) not in (None, ""):
            return row.get(col)
    for col in row.index:
        key = clean_key(col)
        if any(clean_key(name) in key for name in names) and row.get(col) not in (None, ""):
            return row.get(col)
    return ""


def home_run_value(row: pd.Series) -> tuple[str, str, str]:
    value = first_existing_value(row, ("home_run", "homerun", "hr", "to_hit_a_home_run", "home_run_probability"))
    if value not in (None, ""):
        return str(value), "csv_market_or_field", "Home-run market/field was detected in the CSV."
    text = " ".join(str(row.get(col, "")) for col in row.index).lower()
    if "home run" in text or "homerun" in text or " hr" in text:
        return "detected in row text", "csv_market_or_field", "Home-run wording was detected in the row."
    return "", "", ""


def collect_prop_fields(row: pd.Series) -> list[dict[str, Any]]:
    prop_keywords = ("score", "correct_score", "round", "method", "home_run", "homerun", "hr", "td", "touchdown", "goal", "assist", "strikeout", "player", "prop", "over_under", "total", "spread")
    props: list[dict[str, Any]] = []
    for col in row.index:
        key = clean_key(col)
        if any(word in key for word in prop_keywords):
            value = row.get(col)
            if value not in (None, "", "nan") and not (isinstance(value, float) and math.isnan(value)):
                props.append({"prop_field": col, "prop_value": value})
    return props


def analyze(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    event_col = find_col(df, ("event", "event_name", "game", "match", "fixture"))
    sport_col = find_col(df, ("sport", "sport_title", "league", "competition"))
    pick_col = find_col(df, ("prediction", "pick", "predicted_side", "predicted_winner", "favorite", "selection"))
    prob_col = find_col(df, ("final_probability_value", "calibrated_probability", "predicted_probability", "market_probability_value", "probability", "market_probability"))
    price_col = find_col(df, ("best_price", "decimal_odds", "average_price", "avg_price", "odds", "price"))
    market_col = find_col(df, ("market_type", "market", "bet_type", "prop_type"))
    confidence_col = find_col(df, ("confidence", "read", "classification"))
    total_col = find_col(df, ("total", "line_total", "over_under", "points_total"))
    spread_col = find_col(df, ("spread", "line_spread", "handicap"))
    ev_col = find_col(df, ("estimated_ev_decimal", "estimated_ev_value", "ev", "edge"))

    main_rows: list[dict[str, Any]] = []
    prop_rows: list[dict[str, Any]] = []
    for i, row in df.iterrows():
        event = str(row.get(event_col, f"row {i + 1}")) if event_col else f"row {i + 1}"
        sport = str(row.get(sport_col, "unknown")) if sport_col else "unknown"
        pick = str(row.get(pick_col, "")) if pick_col else ""
        probability = parse_probability(row.get(prob_col)) if prob_col else None
        price = row.get(price_col, "") if price_col else ""
        implied = implied_prob_from_price(price)
        market = str(row.get(market_col, "moneyline/winner")) if market_col else "moneyline/winner"
        confidence = str(row.get(confidence_col, "")) if confidence_col else ""
        total = parse_float(row.get(total_col)) if total_col else None
        spread = parse_float(row.get(spread_col)) if spread_col else None
        ev = row.get(ev_col, "") if ev_col else ""
        score, score_source, score_note = estimate_score(event, pick, sport, probability, total, spread)
        main_rows.append({
            "event": event,
            "sport": sport,
            "market_type": market,
            "prediction": pick,
            "model_probability": pct(probability),
            "best_price": price,
            "implied_probability": pct(implied),
            "estimated_ev": ev,
            "confidence": confidence,
            "estimated_score": score,
            "score_source": score_source,
            "score_note": score_note,
        })
        family = sport_family(sport)
        round_value, round_source, round_note = estimate_combat_round(row, pick, probability) if family == "combat" else ("", "", "")
        hr_value, hr_source, hr_note = home_run_value(row) if family == "baseball" or any("home" in clean_key(c) or "hr" == clean_key(c) for c in row.index) else ("", "", "")
        if round_value:
            prop_rows.append({"event": event, "sport": sport, "prediction": pick, "prop_type": "round/method", "prop_estimate": round_value, "source": round_source, "note": round_note})
        if hr_value:
            prop_rows.append({"event": event, "sport": sport, "prediction": pick, "prop_type": "home_run", "prop_estimate": hr_value, "source": hr_source, "note": hr_note})
        for prop in collect_prop_fields(row):
            prop_rows.append({"event": event, "sport": sport, "prediction": pick, "prop_type": str(prop["prop_field"]), "prop_estimate": prop["prop_value"], "source": "csv_field", "note": "Detected from uploaded CSV column."})
    diagnostics = pd.DataFrame([{
        "event_col": event_col or "missing",
        "sport_col": sport_col or "missing",
        "pick_col": pick_col or "missing",
        "probability_col": prob_col or "missing",
        "price_col": price_col or "missing",
        "market_col": market_col or "missing",
        "confidence_col": confidence_col or "missing",
        "total_col": total_col or "missing",
        "spread_col": spread_col or "missing",
        "ev_col": ev_col or "missing",
        "rows_analyzed": len(df),
    }])
    return pd.DataFrame(main_rows), pd.DataFrame(prop_rows).drop_duplicates(), diagnostics


def read_uploaded_csv() -> pd.DataFrame | None:
    uploaded = st.file_uploader(t("upload"), type=["csv"])
    pasted = st.text_area(t("paste"), height=120)
    if uploaded is not None:
        return pd.read_csv(uploaded)
    if pasted.strip():
        return pd.read_csv(io.StringIO(pasted.strip()))
    return None


st.title(t("title"))
st.caption(t("caption"))
st.info(t("note"))

detail_options = [t("simple"), t("detailed"), t("full")]
detail = st.selectbox(t("detail"), detail_options, index=1)
raw_df = read_uploaded_csv()

if raw_df is None:
    st.info(t("empty"))
    st.stop()

st.metric(t("loaded"), len(raw_df))
if st.button(t("button"), type="primary", use_container_width=True):
    main_df, props_df, diagnostics_df = analyze(raw_df)
    st.session_state["what_are_the_odds_main"] = main_df
    st.session_state["what_are_the_odds_props"] = props_df
    st.session_state["what_are_the_odds_diagnostics"] = diagnostics_df

main_df = st.session_state.get("what_are_the_odds_main")
props_df = st.session_state.get("what_are_the_odds_props")
diagnostics_df = st.session_state.get("what_are_the_odds_diagnostics")

if main_df is not None:
    if detail == t("simple"):
        display_main = main_df[["event", "sport", "prediction", "model_probability", "best_price", "confidence", "estimated_score"]].copy()
    else:
        display_main = main_df.copy()
    st.subheader(t("main"))
    st.dataframe(display_main, use_container_width=True, hide_index=True)
    st.download_button(t("download_main"), data=main_df.to_csv(index=False), file_name="what_are_the_odds_report.csv", mime="text/csv")

if props_df is not None:
    st.subheader(t("props"))
    if props_df.empty:
        st.info(t("no_props"))
    else:
        st.dataframe(props_df, use_container_width=True, hide_index=True)
        st.download_button(t("download_props"), data=props_df.to_csv(index=False), file_name="what_are_the_odds_props.csv", mime="text/csv")

if diagnostics_df is not None and detail == t("full"):
    st.subheader(t("diagnostics"))
    st.dataframe(diagnostics_df, use_container_width=True, hide_index=True)
    st.write(t("detected"))
    st.write(list(raw_df.columns))
