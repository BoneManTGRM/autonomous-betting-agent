from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.commercial_platform_tools import (
    filter_locked_proof_rows,
    load_persistent_ledger,
    normalize_workspace_id,
    persistent_ledger_path,
)

st.set_page_config(page_title='Reset Lock File', layout='wide')
LANG = 'es' if st.sidebar.selectbox('Language / Idioma', ['English', 'Español'], key='reset_lock_file_language') == 'Español' else 'en'

TEXT = {
    'en': {
        'title': 'Reset Lock File',
        'caption': 'Clear one no-login test window proof ledger without touching other test windows.',
        'warning': 'Download a backup before clearing. This deletes only the persistent lock file for the active Test Window ID.',
        'test_window': 'Test Window ID',
        'test_window_help': 'Use the same ID used in Odds Lock Pro and Public Proof Dashboard, such as test_01 or test_10.',
        'active_file': 'Active lock file',
        'current_rows': 'Current locked rows',
        'download_backup': 'Download backup before reset',
        'confirm': 'Type CLEAR to enable reset',
        'clear': 'Reset this lock file',
        'done': 'Lock file reset complete.',
        'missing': 'No persistent lock file exists for this Test Window ID.',
        'session_only': 'Clear session locked rows too',
        'session_help': 'Also clears temporary locked rows from the current browser session for this test window.',
        'not_clear': 'This cannot clear uploaded CSVs or files you already downloaded. It only clears the app ledger file and optional session rows.',
    },
    'es': {
        'title': 'Reiniciar Archivo de Bloqueo',
        'caption': 'Borra el ledger de prueba de una ventana sin contraseña sin tocar otras ventanas.',
        'warning': 'Descarga un respaldo antes de borrar. Esto elimina solo el archivo persistente del Test Window ID activo.',
        'test_window': 'ID de ventana de prueba',
        'test_window_help': 'Usa el mismo ID de Odds Lock Pro y Dashboard Público, como test_01 o test_10.',
        'active_file': 'Archivo de bloqueo activo',
        'current_rows': 'Filas bloqueadas actuales',
        'download_backup': 'Descargar respaldo antes de borrar',
        'confirm': 'Escribe CLEAR para activar el reset',
        'clear': 'Reiniciar este archivo de bloqueo',
        'done': 'Archivo de bloqueo reiniciado.',
        'missing': 'No existe archivo persistente para este Test Window ID.',
        'session_only': 'Borrar también filas bloqueadas de sesión',
        'session_help': 'También borra filas bloqueadas temporales de esta sesión del navegador para esta ventana de prueba.',
        'not_clear': 'Esto no borra CSVs descargados o subidos. Solo borra el ledger de la app y opcionalmente filas de sesión.',
    },
}


def t(key: str) -> str:
    return TEXT[LANG].get(key, TEXT['en'].get(key, key))


st.title(t('title'))
st.caption(t('caption'))
st.warning(t('warning'))
st.info(t('not_clear'))

workspace_input = st.text_input(
    t('test_window'),
    value=st.session_state.get('aba_test_window_id', 'test_01'),
    help=t('test_window_help'),
)
workspace_id = normalize_workspace_id(workspace_input)
st.session_state['aba_test_window_id'] = workspace_id
ledger_path = persistent_ledger_path(workspace_id=workspace_id)
st.caption(f"{t('active_file')}: `{ledger_path}`")

ledger = load_persistent_ledger(workspace_id=workspace_id)
locked = filter_locked_proof_rows(ledger)
st.metric(t('current_rows'), int(len(locked)))

if locked.empty:
    st.caption(t('missing'))
else:
    st.download_button(
        t('download_backup'),
        locked.to_csv(index=False),
        file_name=f'odds_lock_pro_ledger_backup_{workspace_id}.csv',
        mime='text/csv',
        use_container_width=True,
    )

clear_session = st.checkbox(t('session_only'), value=True, help=t('session_help'))
confirm = st.text_input(t('confirm'), value='', key='reset_lock_file_confirm')
if st.button(t('clear'), type='primary', use_container_width=True, disabled=confirm.strip() != 'CLEAR'):
    try:
        if ledger_path.exists():
            ledger_path.unlink()
    except Exception as exc:
        st.error(str(exc))
        st.stop()
    if clear_session:
        for key in ['odds_lock_pro_locked_rows', 'daily_workflow_locked_rows', 'public_proof_dashboard_latest_rows']:
            st.session_state.pop(key, None)
        source = st.session_state.get('ara_latest_predictions_source', '')
        if isinstance(source, str) and ('Odds Lock Pro' in source or 'Simulation Lab survivor' in source):
            st.session_state.pop('ara_latest_predictions', None)
            st.session_state.pop('ara_latest_predictions_source', None)
    st.success(f"{t('done')} {workspace_id}")
