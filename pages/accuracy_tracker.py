import csv
import io

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Accuracy Tracker", layout="wide")

language = st.selectbox("Language / Idioma", ["English", "Español"], index=0)
IS_ES = language == "Español"

TEXT = {
    "title": {"English": "Accuracy Tracker", "Español": "Rastreador de Precisión"},
    "caption": {
        "English": "Upload a scanner CSV, mark whether picks won or lost, and track real hit rate, Brier score, and calibration over time.",
        "Español": "Sube un CSV del escáner, marca si las selecciones ganaron o perdieron, y mide acierto real, Brier score y calibración con el tiempo.",
    },
    "upload": {"English": "Upload scanner CSV", "Español": "Subir CSV del escáner"},
    "manual": {"English": "Manual prediction", "Español": "Predicción manual"},
    "event": {"English": "Event", "Español": "Evento"},
    "pick": {"English": "Pick", "Español": "Selección"},
    "prob": {"English": "Predicted probability", "Español": "Probabilidad predicha"},
    "result": {"English": "Result", "Español": "Resultado"},
    "won": {"English": "Won", "Español": "Ganó"},
    "lost": {"English": "Lost", "Español": "Perdió"},
    "add": {"English": "Add result", "Español": "Agregar resultado"},
    "records": {"English": "Tracked predictions", "Español": "Predicciones rastreadas"},
    "hit_rate": {"English": "Hit rate", "Español": "Tasa de acierto"},
    "avg_prob": {"English": "Average predicted probability", "Español": "Probabilidad predicha promedio"},
    "brier": {"English": "Brier score", "Español": "Brier score"},
    "calibration": {"English": "Calibration buckets", "Español": "Cubetas de calibración"},
    "download": {"English": "Download tracker CSV", "Español": "Descargar CSV del rastreador"},
    "clear": {"English": "Clear tracker", "Español": "Borrar rastreador"},
    "empty": {"English": "No tracked predictions yet.", "Español": "Aún no hay predicciones rastreadas."},
}


def t(key: str) -> str:
    entry = TEXT.get(key, {})
    return entry.get(language) or entry.get("English") or key


def parse_probability(value) -> float:
    if value is None:
        return 0.0
    text = str(value).strip().replace("%", "")
    try:
        number = float(text)
    except ValueError:
        return 0.0
    if number > 1:
        number = number / 100.0
    return max(0.0, min(1.0, number))


def normalize_uploaded(df: pd.DataFrame) -> pd.DataFrame:
    columns = {col.lower().strip(): col for col in df.columns}
    event_col = columns.get("event") or columns.get("game") or columns.get("match")
    pick_col = columns.get("pick") or columns.get("team pick") or columns.get("favorite")
    prob_col = columns.get("probability") or columns.get("market %") or columns.get("team win %") or columns.get("favorite %")
    rows = []
    if not event_col or not pick_col or not prob_col:
        return pd.DataFrame(columns=["event", "pick", "probability", "result"])
    for _, row in df.iterrows():
        rows.append({
            "event": str(row.get(event_col, "")),
            "pick": str(row.get(pick_col, "")),
            "probability": parse_probability(row.get(prob_col, 0)),
            "result": "unknown",
        })
    return pd.DataFrame(rows)


def tracker_df() -> pd.DataFrame:
    if "accuracy_tracker" not in st.session_state:
        st.session_state.accuracy_tracker = []
    return pd.DataFrame(st.session_state.accuracy_tracker)


def set_tracker(df: pd.DataFrame) -> None:
    st.session_state.accuracy_tracker = df.to_dict("records")


def csv_download(df: pd.DataFrame) -> str:
    output = io.StringIO()
    df.to_csv(output, index=False, quoting=csv.QUOTE_MINIMAL)
    return output.getvalue()


st.title(t("title"))
st.caption(t("caption"))

uploaded = st.file_uploader(t("upload"), type=["csv"])
if uploaded is not None:
    uploaded_df = pd.read_csv(uploaded)
    normalized = normalize_uploaded(uploaded_df)
    if len(normalized):
        current = tracker_df()
        combined = pd.concat([current, normalized], ignore_index=True).drop_duplicates(subset=["event", "pick", "probability"], keep="last")
        set_tracker(combined)
        st.success(f"Loaded {len(normalized)} predictions." if not IS_ES else f"Se cargaron {len(normalized)} predicciones.")
    else:
        st.warning("CSV must include Event, Pick, and Probability/Market % columns." if not IS_ES else "El CSV debe incluir columnas de Evento, Selección y Probabilidad/Market %." )

with st.expander(t("manual"), expanded=False):
    event = st.text_input(t("event"))
    pick = st.text_input(t("pick"))
    probability = st.number_input(t("prob"), min_value=0.0, max_value=1.0, value=0.50, step=0.01)
    result = st.selectbox(t("result"), ["unknown", t("won"), t("lost")])
    if st.button(t("add")):
        result_value = "won" if result == t("won") else "lost" if result == t("lost") else "unknown"
        current = tracker_df()
        new_row = pd.DataFrame([{"event": event, "pick": pick, "probability": probability, "result": result_value}])
        set_tracker(pd.concat([current, new_row], ignore_index=True))

current = tracker_df()
if current.empty:
    st.info(t("empty"))
    st.stop()

editable = st.data_editor(
    current,
    use_container_width=True,
    hide_index=True,
    column_config={
        "result": st.column_config.SelectboxColumn(t("result"), options=["unknown", "won", "lost"]),
        "probability": st.column_config.NumberColumn(t("prob"), min_value=0.0, max_value=1.0, step=0.01),
    },
)
set_tracker(editable)

resolved = editable[editable["result"].isin(["won", "lost"])].copy()
if resolved.empty:
    st.info("Mark some predictions as won or lost to calculate accuracy." if not IS_ES else "Marca algunas predicciones como ganadas o perdidas para calcular precisión.")
else:
    resolved["actual"] = resolved["result"].map({"won": 1.0, "lost": 0.0})
    resolved["brier"] = (resolved["probability"] - resolved["actual"]) ** 2
    hit_rate = resolved["actual"].mean()
    avg_prob = resolved["probability"].mean()
    brier = resolved["brier"].mean()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(t("records"), len(resolved))
    c2.metric(t("hit_rate"), f"{hit_rate:.1%}")
    c3.metric(t("avg_prob"), f"{avg_prob:.1%}")
    c4.metric(t("brier"), f"{brier:.3f}")

    buckets = []
    for low, high in [(0.0, 0.4), (0.4, 0.5), (0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 1.01)]:
        bucket = resolved[(resolved["probability"] >= low) & (resolved["probability"] < high)]
        if len(bucket):
            buckets.append({
                "Bucket": f"{low:.0%}-{min(high, 1.0):.0%}",
                "Predictions": len(bucket),
                "Avg predicted": f"{bucket['probability'].mean():.1%}",
                "Actual win rate": f"{bucket['actual'].mean():.1%}",
                "Brier": round(bucket["brier"].mean(), 3),
            })
    st.write(t("calibration"))
    st.dataframe(pd.DataFrame(buckets), use_container_width=True, hide_index=True)

st.download_button(t("download"), data=csv_download(editable), file_name="accuracy_tracker.csv", mime="text/csv")
if st.button(t("clear")):
    st.session_state.accuracy_tracker = []
    st.rerun()
