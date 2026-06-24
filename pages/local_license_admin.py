from __future__ import annotations

from dataclasses import asdict

import pandas as pd
import streamlit as st

from autonomous_betting_agent.license_status import load_license_records, make_license_record, upsert_license_record
from autonomous_betting_agent.local_access import require_streamlit_access
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title="Local License Admin", layout="wide")
LANG = render_app_sidebar("local_license_admin", language_key="local_license_admin_language")
require_streamlit_access(st, allow_roles={"admin"})
ES = LANG == "es"


def tr(en: str, es: str) -> str:
    return es if ES else en


st.title(tr("Local License Admin", "Admin de Licencia Local"))
st.caption(tr("Manual local license tracking only. No payment processing.", "Solo seguimiento manual de licencias locales. No procesa pagos."))

with st.form("license_form"):
    client_name = st.text_input(tr("Client name", "Nombre del cliente"))
    client_status = st.selectbox(tr("Client status", "Estado del cliente"), ["trial", "active", "inactive", "expired"])
    subscription_tier = st.text_input(tr("Subscription tier", "Nivel de suscripción"), "private_beta")
    manual_payment_status = st.text_input(tr("Manual payment status", "Estado de pago manual"), "manual")
    renewal_date = st.text_input(tr("Renewal date", "Fecha de renovación"), "")
    notes = st.text_area(tr("Notes", "Notas"), "")
    future_stripe_ready = st.checkbox(tr("Future payment placeholder", "Marcador futuro de pago"), value=False)
    submitted = st.form_submit_button(tr("Save local license record", "Guardar licencia local"))

if submitted:
    if not client_name.strip():
        st.error(tr("Client name is required.", "El nombre del cliente es obligatorio."))
    else:
        record = make_license_record(client_name, client_status, subscription_tier, manual_payment_status, renewal_date, notes, future_stripe_ready)
        upsert_license_record(record)
        st.success(tr("Manual local license record saved.", "Licencia local guardada."))

records = load_license_records()
if records:
    df = pd.DataFrame([asdict(record) for record in records])
    st.dataframe(df, use_container_width=True)
    st.download_button(tr("Download local license CSV", "Descargar CSV local de licencias"), df.to_csv(index=False).encode("utf-8"), file_name="local_license_status.csv", mime="text/csv")
else:
    st.info(tr("No local license records found yet.", "Todavía no hay licencias locales."))

st.warning(tr("Manual license tracking only.", "Solo seguimiento manual de licencias."))
