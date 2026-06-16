from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.commercial_platform_tools import dashboard_metrics, load_persistent_ledger, public_dashboard_table, report_card_markdown
from autonomous_betting_agent.proof_safety_tools import client_safe_frame, enrich_safety_columns, private_beta_snapshot
from autonomous_betting_agent.tool_sidebar import render_tool_sidebar

st.set_page_config(page_title='Private Beta Sales Dashboard', layout='wide')
LANG = 'es' if st.sidebar.selectbox('Language / Idioma', ['English', 'Español'], key='private_beta_sales_language') == 'Español' else 'en'
render_tool_sidebar('monthly_license_readiness', 'Español' if LANG == 'es' else 'English')

TEXT = {
    'en': {
        'title': 'Private Beta Sales Dashboard',
        'caption': 'Client-facing beta dashboard for proof record, ROI, sample size, last picks, proof quality, pricing tier, and safe exports.',
        'brand': 'Brand name',
        'use_db': 'Use persistent proof ledger',
        'use_session': 'Use locked session rows',
        'use_demo': 'Use demo rows if empty',
        'no_rows': 'No proof rows found. Create locked proof rows first or enable demo mode for a walkthrough.',
        'demo_warning': 'Demo rows are for walkthroughs only. Do not present them as real performance.',
        'offer': 'Beta offer copy',
        'proof': 'Proof table',
        'last': 'Last 10 picks',
        'client': 'Client-safe export',
        'private': 'Private safety audit',
    },
    'es': {
        'title': 'Dashboard de Venta Beta Privada',
        'caption': 'Dashboard para cliente beta con récord, ROI, tamaño de muestra, últimos picks, calidad de prueba, precio y exports seguros.',
        'brand': 'Nombre de marca',
        'use_db': 'Usar ledger persistente',
        'use_session': 'Usar filas bloqueadas de sesión',
        'use_demo': 'Usar demo si está vacío',
        'no_rows': 'No hay filas de prueba. Crea filas bloqueadas o activa demo para walkthrough.',
        'demo_warning': 'Filas demo solo para walkthrough. No las presentes como rendimiento real.',
        'offer': 'Texto de oferta beta',
        'proof': 'Tabla de prueba',
        'last': 'Últimos 10 picks',
        'client': 'Export cliente',
        'private': 'Auditoría privada',
    },
}


def t(key: str) -> str:
    return TEXT[LANG].get(key, TEXT['en'].get(key, key))


def demo_rows() -> pd.DataFrame:
    from autonomous_betting_agent.commercial_platform_tools import demo_ledger
    return demo_ledger()


st.title(t('title'))
st.caption(t('caption'))
brand = st.text_input(t('brand'), value='Private Analytics')
frames = []
used_demo = False
if st.checkbox(t('use_db'), value=True):
    db = load_persistent_ledger()
    if not db.empty:
        frames.append(db)
if st.checkbox(t('use_session'), value=True):
    rows = st.session_state.get('odds_lock_pro_locked_rows') or []
    if rows:
        frames.append(pd.DataFrame(rows))
if not frames and st.checkbox(t('use_demo'), value=True):
    used_demo = True
    frames.append(demo_rows())
if not frames:
    st.warning(t('no_rows'))
    st.stop()
if used_demo:
    st.warning(t('demo_warning'))

ledger = pd.concat(frames, ignore_index=True, sort=False)
enriched = enrich_safety_columns(ledger)
metrics = dashboard_metrics(enriched)
snapshot = private_beta_snapshot(enriched)

cols = st.columns(8)
cols[0].metric('Locked', metrics['locked_picks'])
cols[1].metric('Resolved', metrics['resolved_picks'])
cols[2].metric('Record', f"{metrics['wins']}-{metrics['losses']}")
cols[3].metric('Hit rate', 'N/A' if metrics['hit_rate'] is None else f"{metrics['hit_rate'] * 100:.1f}%")
cols[4].metric('ROI', 'N/A' if metrics['roi'] is None else f"{metrics['roi'] * 100:.1f}%")
cols[5].metric('Proof quality', metrics['proof_quality_score'])
cols[6].metric('Eligible', snapshot['eligible'])
cols[7].metric('Warnings', snapshot['warnings'])

offer = '\n'.join([
    f'{brand} Private Beta Analytics License',
    '',
    'Includes: private dashboard access, future-only proof ledger, daily ranked reports, result tracking, proof audit, and weekly review.',
    'Positioning: sports analytics and research software only. No guaranteed wins or returns. No managed funds. No transaction execution.',
    '',
    f"Current proof: {metrics['locked_picks']} locked rows, {metrics['resolved_picks']} resolved, record {metrics['wins']}-{metrics['losses']}, proof quality {metrics['proof_quality_score']}/100.",
    'Recommended beta price: $500-$1,000/month for the first 2-3 private testers.',
])

tabs = st.tabs([t('offer'), t('proof'), t('last'), t('client'), t('private')])
with tabs[0]:
    st.text_area(t('offer'), value=offer, height=260)
    st.download_button('Download beta offer', offer, file_name='private_beta_offer.txt', mime='text/plain')
    card = report_card_markdown(enriched, title='Private Beta Proof Snapshot', brand=brand)
    st.text_area('Proof card', value=card, height=280)
with tabs[1]:
    st.dataframe(public_dashboard_table(enriched), use_container_width=True, hide_index=True)
with tabs[2]:
    sort_col = 'locked_at_utc' if 'locked_at_utc' in enriched.columns else None
    last = enriched.sort_values(sort_col, ascending=False).head(10) if sort_col else enriched.tail(10)
    st.dataframe(client_safe_frame(last, client_safe=True), use_container_width=True, hide_index=True)
with tabs[3]:
    client = client_safe_frame(enriched, client_safe=True)
    st.dataframe(client, use_container_width=True, hide_index=True)
    st.download_button('Download client-safe proof CSV', client.to_csv(index=False), file_name='private_beta_client_safe.csv', mime='text/csv')
with tabs[4]:
    st.dataframe(enriched, use_container_width=True, hide_index=True)
    st.download_button('Download private safety audit CSV', enriched.to_csv(index=False), file_name='private_beta_safety_audit.csv', mime='text/csv')
