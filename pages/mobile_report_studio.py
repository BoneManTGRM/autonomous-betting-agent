from __future__ import annotations

from dataclasses import asdict

import pandas as pd
import streamlit as st

from autonomous_betting_agent.commercial_platform_tools import load_persistent_ledger, normalize_workspace_id
from autonomous_betting_agent.mobile_png_layout import render_mobile_png
from autonomous_betting_agent.pick_hold_store import load_first_available
from autonomous_betting_agent.report_product_layer import MagazineBrand, safe_text
from autonomous_betting_agent.row_normalizer import normalize_frame
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title='Mobile Report Studio', layout='wide')
LANG = render_app_sidebar('mobile_report_studio', language_key='report_studio_language', selector='radio')

TEXT = {
    'en': {
        'title': 'Mobile Report Studio',
        'caption': 'Large-text PNG reports designed for iPhone screenshots and client sharing.',
        'workspace': 'Client / Workspace ID',
        'use_saved': 'Use saved workspace rows',
        'upload': 'Upload CSV rows',
        'brand': 'Brand / tipster name',
        'report_title': 'Report title',
        'background': 'Optional background image',
        'preview': 'Large mobile PNG preview',
        'download': 'Download large mobile PNG',
        'empty': 'No rows found. Use saved rows or upload a CSV.',
    },
    'es': {
        'title': 'Estudio móvil de reportes',
        'caption': 'Reportes PNG con texto grande para iPhone y clientes.',
        'workspace': 'ID de cliente / workspace',
        'use_saved': 'Usar filas guardadas',
        'upload': 'Subir CSV',
        'brand': 'Marca / tipster',
        'report_title': 'Título del reporte',
        'background': 'Imagen de fondo opcional',
        'preview': 'Vista previa PNG móvil grande',
        'download': 'Descargar PNG móvil grande',
        'empty': 'No hay filas. Usa filas guardadas o sube un CSV.',
    },
}

HANDOFF_KEYS = (
    'odds_lock_pro_locked_rows',
    'public_proof_dashboard_refresh_rows',
    'pro_predictor_high_confidence_rows',
    'pro_predictor_latest_rows',
    'what_are_the_odds_latest_rows',
    'ara_latest_predictions',
)


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT['en']).get(key, key)


def saved_rows(workspace_id: str) -> pd.DataFrame:
    persistent = load_persistent_ledger(workspace_id=workspace_id, active_only=False)
    if persistent is not None and not persistent.empty:
        return persistent
    for key in HANDOFF_KEYS:
        rows = st.session_state.get(key) or []
        if rows:
            return pd.DataFrame(rows)
    _, rows = load_first_available(HANDOFF_KEYS, workspace_id)
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def safe_workspace_name(value: str) -> str:
    return ''.join(ch if ch.isalnum() or ch in {'_', '-'} else '_' for ch in str(value or 'report'))


st.title(t('title'))
st.caption(t('caption'))

with st.expander('Input', expanded=True):
    workspace_input = st.text_input(t('workspace'), value=st.session_state.get('aba_test_window_id', 'test_01'))
    workspace_id = normalize_workspace_id(workspace_input)
    st.session_state['aba_test_window_id'] = workspace_id
    frames: list[pd.DataFrame] = []
    if st.checkbox(t('use_saved'), value=True):
        stored = saved_rows(workspace_id)
        if not stored.empty:
            frames.append(stored)
    uploads = st.file_uploader(t('upload'), type=['csv'], accept_multiple_files=True)
    for upload in uploads or []:
        frame = pd.read_csv(upload)
        frame['source_file'] = upload.name
        frames.append(frame)

if not frames:
    st.warning(t('empty'))
    st.stop()

raw = pd.concat(frames, ignore_index=True, sort=False)
cards = normalize_frame(raw).head(3)

brand_name = st.text_input(t('brand'), value='ABA Signal Pro')
report_title = st.text_input(t('report_title'), value='Daily Sports Analysis')
background_upload = st.file_uploader(t('background'), type=['png', 'jpg', 'jpeg'], key='mobile_report_background')
background_bytes = background_upload.getvalue() if background_upload is not None else None
brand = MagazineBrand(brand_name=brand_name, report_title=report_title, workspace_id=workspace_id, language=LANG)

png = render_mobile_png(cards, brand, background_bytes=background_bytes, top_n=3)
st.download_button(t('download'), data=png, file_name=f'mobile_report_{safe_workspace_name(workspace_id)}.png', mime='image/png')
st.image(png, caption=t('preview'), use_container_width=True)

show_cols = [col for col in ['event', 'sport', 'market_type', 'prediction', 'decimal_price', 'model_probability', 'model_market_edge', 'consumer_action', 'recommended_action'] if col in cards.columns]
st.dataframe(cards[show_cols] if show_cols else cards, use_container_width=True, hide_index=True)
