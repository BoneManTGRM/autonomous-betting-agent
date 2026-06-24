from __future__ import annotations

import streamlit as st

from autonomous_betting_agent.explanations import build_client_safe_pick_summary
from autonomous_betting_agent.report_exports import render_html_report, render_markdown_report, render_messenger_report
from autonomous_betting_agent.sidebar_nav import render_app_sidebar
from autonomous_betting_agent.ui_i18n import tr

st.set_page_config(page_title="Buyer Demo Local", layout="wide")
LANG = render_app_sidebar("buyer_demo_local", language_key="buyer_demo_local_language")

st.title(tr(LANG, "Buyer Demo Local", "Demo Local para Comprador"))
st.caption(tr(LANG, "Sample local-first buyer walkthrough. No API keys or cloud server required.", "Recorrido de muestra local-first para compradores. No requiere API keys ni servidor en la nube."))
st.warning(tr(LANG, "Demo only. Analytics, proof tracking, reporting, and risk review only.", "Solo demo. Solo analítica, seguimiento de prueba, reportes y revisión de riesgo."))

sample_rows = [
    {"proof_id": "DEMO-001", "locked_at_utc": "2026-06-23T10:00:00+00:00", "event_start_time": "2026-06-23T12:00:00+00:00", "event_name": "Demo Team A vs Demo Team B", "prediction": "Demo Team A", "market": "moneyline", "sport": "soccer", "decimal_price": 1.82, "odds_audit_status": "pass", "pattern_points": 82, "model_probability": 0.61, "model_market_edge": 0.04, "bookmaker_count": 5, "grade": "pending", "ledger_type": "official"},
    {"proof_id": "DEMO-002", "locked_at_utc": "2026-06-23T10:30:00+00:00", "event_start_time": "2026-06-23T13:00:00+00:00", "event_name": "Demo Club C vs Demo Club D", "prediction": "Over 2.5", "market": "total", "sport": "soccer", "decimal_price": 1.95, "odds_audit_status": "pass", "pattern_points": 76, "model_probability": 0.57, "model_market_edge": 0.02, "bookmaker_count": 4, "grade": "pending", "ledger_type": "research"},
]

st.header(tr(LANG, "What this shows", "Qué muestra esto"))
st.markdown(tr(LANG, """
- Local-first proof tracking without a cloud server.
- Timestamped proof rows with proof IDs.
- Client-safe pick explanations.
- Local Report Studio output.
- Clear separation between official and research rows.
""", """
- Seguimiento de prueba local-first sin servidor en la nube.
- Filas de prueba con hora e ID de prueba.
- Explicaciones seguras para clientes.
- Salida local de Report Studio.
- Separación clara entre filas oficiales y de investigación.
"""))

st.header(tr(LANG, "Sample proof explanations", "Explicaciones de prueba de muestra"))
for row in sample_rows:
    st.info(build_client_safe_pick_summary(row))

st.header(tr(LANG, "Sample report outputs", "Salidas de reporte de muestra"))
report_title = tr(LANG, "ABA Signal Pro Buyer Demo", "Demo para Comprador ABA Signal Pro")
client_name = tr(LANG, "Demo Buyer", "Comprador Demo")
markdown_report = render_markdown_report(sample_rows, title=report_title, client_name=client_name, public_safe=False)
html_report = render_html_report(sample_rows, title=report_title, client_name=client_name, public_safe=False)
message_report = render_messenger_report(sample_rows, title=report_title)

st.text_area(tr(LANG, "Messenger-ready summary", "Resumen listo para mensaje"), message_report, height=120)
st.download_button(tr(LANG, "Download demo Markdown", "Descargar demo Markdown"), markdown_report.encode("utf-8"), file_name="aba_buyer_demo.md", mime="text/markdown")
st.download_button(tr(LANG, "Download demo HTML / print-to-PDF", "Descargar demo HTML / imprimir como PDF"), html_report.encode("utf-8"), file_name="aba_buyer_demo.html", mime="text/html")

with st.expander(tr(LANG, "Markdown preview", "Vista previa Markdown")):
    st.text(markdown_report)

st.header(tr(LANG, "Local-first buyer summary", "Resumen local-first para comprador"))
st.markdown(tr(LANG, """
ABA Signal Pro can be shown as a local-first analytics and reporting workflow:

1. Scan or upload rows.
2. Review odds, market support, and proof readiness.
3. Lock rows before event start.
4. Save rows locally to SQLite/CSV fallback.
5. Verify proof IDs.
6. Export client-ready reports.
7. Review calibration and learning safety after grading.
""", """
ABA Signal Pro se puede mostrar como un flujo local-first de analítica y reportes:

1. Escanear o subir filas.
2. Revisar cuotas, mercados y preparación de prueba.
3. Bloquear filas antes del inicio del evento.
4. Guardar filas localmente en SQLite/CSV fallback.
5. Verificar IDs de prueba.
6. Exportar reportes listos para clientes.
7. Revisar calibración y seguridad de aprendizaje después de calificar.
"""))
