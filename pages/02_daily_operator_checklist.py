from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.commercial_platform_tools import load_persistent_ledger
from autonomous_betting_agent.proof_safety_tools import client_safe_frame, enrich_safety_columns, operator_checklist_frame, private_beta_snapshot
from autonomous_betting_agent.tool_sidebar import render_tool_sidebar, session_state_summary

st.set_page_config(page_title='Daily Operator Checklist', layout='wide')
LANG = 'es' if st.sidebar.selectbox('Language / Idioma', ['English', 'Español'], key='daily_operator_checklist_language') == 'Español' else 'en'
render_tool_sidebar('daily_workflow', 'Español' if LANG == 'es' else 'English')

TEXT = {
    'en': {
        'title': 'Daily Operator Checklist',
        'caption': 'Pre-lock checklist for running the system safely before creating official proof rows.',
        'use_session': 'Use current session rows',
        'use_ledger': 'Use persistent proof ledger',
        'upload': 'Upload candidate CSV',
        'no_rows': 'No rows found. Run Pro Predictor / What Are the Odds first or upload a CSV.',
        'checklist': 'Checklist',
        'warnings': 'Do-not-lock warnings',
        'client': 'Client-safe preview',
        'private': 'Private audit view',
        'snapshot': 'Readiness snapshot',
        'download_client': 'Download client-safe CSV',
        'download_private': 'Download private audit CSV',
    },
    'es': {
        'title': 'Checklist Diario del Operador',
        'caption': 'Checklist antes de bloquear para operar el sistema con seguridad antes de crear prueba oficial.',
        'use_session': 'Usar filas actuales de sesión',
        'use_ledger': 'Usar ledger persistente',
        'upload': 'Subir CSV de candidatos',
        'no_rows': 'No hay filas. Ejecuta Predictor Pro / What Are the Odds o sube un CSV.',
        'checklist': 'Checklist',
        'warnings': 'Advertencias no bloquear',
        'client': 'Vista segura cliente',
        'private': 'Vista privada auditoría',
        'snapshot': 'Resumen de preparación',
        'download_client': 'Descargar CSV cliente',
        'download_private': 'Descargar CSV privado',
    },
}


def t(key: str) -> str:
    return TEXT[LANG].get(key, TEXT['en'].get(key, key))


def session_rows() -> pd.DataFrame:
    frames = []
    for key in ['what_are_the_odds_latest_rows', 'pro_predictor_latest_rows', 'pro_predictor_high_confidence_rows', 'odds_lock_pro_locked_rows']:
        rows = st.session_state.get(key) or []
        if rows:
            frame = pd.DataFrame(rows)
            frame['session_source'] = key
            frames.append(frame)
    return pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()


st.title(t('title'))
st.caption(t('caption'))
frames = []
if st.checkbox(t('use_session'), value=True):
    s = session_rows()
    if not s.empty:
        frames.append(s)
if st.checkbox(t('use_ledger'), value=False):
    ledger = load_persistent_ledger()
    if not ledger.empty:
        frames.append(ledger)
uploads = st.file_uploader(t('upload'), type=['csv'], accept_multiple_files=True)
if uploads:
    for upload in uploads:
        frame = pd.read_csv(upload)
        frame['source_file'] = upload.name
        frames.append(frame)

st.subheader('Session handoff' if LANG == 'en' else 'Handoff de sesión')
st.dataframe(session_state_summary(), use_container_width=True, hide_index=True)

if not frames:
    st.warning(t('no_rows'))
    st.stop()

raw = pd.concat(frames, ignore_index=True, sort=False)
enriched = enrich_safety_columns(raw)
client = client_safe_frame(enriched, client_safe=True)
snapshot = private_beta_snapshot(enriched)
checklist = operator_checklist_frame(enriched)

cols = st.columns(6)
cols[0].metric('Rows' if LANG == 'en' else 'Filas', snapshot['rows'])
cols[1].metric('Eligible' if LANG == 'en' else 'Elegibles', snapshot['eligible'])
cols[2].metric('Warnings' if LANG == 'en' else 'Advertencias', snapshot['warnings'])
cols[3].metric('A+' , snapshot['a_plus'])
cols[4].metric('A', snapshot['a_tier'])
cols[5].metric('Client ready' if LANG == 'en' else 'Listo cliente', str(snapshot['client_ready']))

tabs = st.tabs([t('checklist'), t('warnings'), t('client'), t('private'), t('snapshot')])
with tabs[0]:
    st.dataframe(checklist, use_container_width=True, hide_index=True)
with tabs[1]:
    warning_cols = [col for col in ['event', 'prediction', 'confidence_tier', 'official_proof_eligible', 'proof_blockers', 'do_not_lock_warnings', 'needed_info', 'recommended_action'] if col in enriched.columns]
    st.dataframe(enriched[warning_cols] if warning_cols else enriched, use_container_width=True, hide_index=True)
with tabs[2]:
    st.dataframe(client, use_container_width=True, hide_index=True)
    st.download_button(t('download_client'), client.to_csv(index=False), file_name='client_safe_operator_preview.csv', mime='text/csv')
with tabs[3]:
    st.dataframe(enriched, use_container_width=True, hide_index=True)
    st.download_button(t('download_private'), enriched.to_csv(index=False), file_name='private_operator_audit.csv', mime='text/csv')
with tabs[4]:
    st.json(snapshot)
