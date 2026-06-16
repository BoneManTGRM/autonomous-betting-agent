from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from autonomous_betting_agent.ui_language import render_language_selector

REPO_ROOT = Path(__file__).resolve().parents[1]
PERSISTENT_LEDGER_PATH = REPO_ROOT / 'data' / 'odds_lock_pro_ledger.csv'
LEARNING_BANK_PATH = REPO_ROOT / 'data' / 'learning_memory_bank.json'
ARA_MEMORY_PATH = REPO_ROOT / 'data' / 'ara_learning_memory.csv'
LEARNED_STATE_PATH = REPO_ROOT / 'learned_state.json'

SESSION_KEYS = [
    'scanner_pro_latest_rows',
    'pro_predictor_all_rows',
    'pro_predictor_high_confidence_rows',
    'pro_predictor_latest_rows',
    'what_are_the_odds_latest_rows',
    'game_intelligence_latest_rows',
    'command_center_latest_rows',
    'odds_lock_pro_locked_rows',
    'ara_latest_predictions',
    'ara_latest_predictions_source',
    'ara_latest_predictions_saved_at',
    'buyer_demo_rows',
    'daily_workflow_locked_rows',
    'public_proof_dashboard_latest_rows',
]

st.set_page_config(page_title='Reset Data', layout='wide')
LANG = render_language_selector(key='reset_data_language')

TEXT = {
    'en': {
        'title': 'Reset Data',
        'caption': 'Clear old session rows, proof ledger rows, or learning memory before starting a cleaner forward test.',
        'warning': 'Use this when the system has changed enough that older rows should not be mixed with the new validation period. Download backups before clearing anything important.',
        'session': 'Clear session rows',
        'session_help': 'Removes temporary rows from Scanner Pro, Pro Predictor, What Are the Odds, Game Intelligence, Command Center, Odds Lock Pro, and handoff state. It does not delete downloaded CSV files.',
        'clear_session': 'Clear current session rows',
        'session_done': 'Session rows cleared.',
        'ledger': 'Clear persistent proof ledger',
        'ledger_help': 'This resets the local proof dashboard ledger used by the deployed app. It does not delete CSV files you already downloaded.',
        'download_ledger': 'Download current ledger backup',
        'confirm_ledger': 'Type CLEAR to enable ledger reset',
        'clear_ledger': 'Clear persistent proof ledger',
        'ledger_done': 'Persistent proof ledger cleared.',
        'memory': 'Clear learning memory',
        'memory_help': 'This removes saved calibration/memory files so future training starts from a clean memory state.',
        'download_memory': 'Download learning memory backup',
        'confirm_memory': 'Type RESET MEMORY to enable learning reset',
        'clear_memory': 'Clear learning memory files',
        'memory_done': 'Learning memory files cleared.',
        'rows': 'Rows',
        'missing': 'No saved file found.',
    },
    'es': {
        'title': 'Reiniciar Datos',
        'caption': 'Borra filas viejas de sesión, ledger de prueba o memoria de aprendizaje antes de empezar una validación limpia.',
        'warning': 'Úsalo cuando el sistema cambió bastante y no quieres mezclar filas viejas con el nuevo periodo de validación. Descarga respaldos antes de borrar algo importante.',
        'session': 'Borrar filas de sesión',
        'session_help': 'Quita filas temporales de Scanner Pro, Predictor Pro, What Are the Odds, Game Intelligence, Command Center, Odds Lock Pro y handoff. No borra CSVs descargados.',
        'clear_session': 'Borrar filas actuales de sesión',
        'session_done': 'Filas de sesión borradas.',
        'ledger': 'Borrar ledger persistente de prueba',
        'ledger_help': 'Reinicia el ledger local del dashboard público usado por la app desplegada. No borra CSVs que ya descargaste.',
        'download_ledger': 'Descargar respaldo del ledger actual',
        'confirm_ledger': 'Escribe CLEAR para activar reinicio del ledger',
        'clear_ledger': 'Borrar ledger persistente',
        'ledger_done': 'Ledger persistente borrado.',
        'memory': 'Borrar memoria de aprendizaje',
        'memory_help': 'Quita archivos de calibración/memoria para que el próximo entrenamiento empiece limpio.',
        'download_memory': 'Descargar respaldo de memoria',
        'confirm_memory': 'Escribe RESET MEMORY para activar reinicio de memoria',
        'clear_memory': 'Borrar archivos de memoria',
        'memory_done': 'Archivos de memoria borrados.',
        'rows': 'Filas',
        'missing': 'No existe archivo guardado.',
    },
}


def t(key: str) -> str:
    return TEXT[LANG].get(key, TEXT['en'].get(key, key))


def read_csv_if_exists(path: Path) -> pd.DataFrame:
    try:
        if path.exists():
            return pd.read_csv(path)
    except Exception:
        pass
    return pd.DataFrame()


def session_item_count() -> int:
    total = 0
    for key in SESSION_KEYS:
        value = st.session_state.get(key)
        if isinstance(value, list):
            total += len(value)
        elif isinstance(value, pd.DataFrame):
            total += len(value)
        elif value:
            total += 1
    return total


st.title(t('title'))
st.caption(t('caption'))
st.warning(t('warning'))

st.subheader(t('session'))
st.info(t('session_help'))
st.metric(t('rows'), session_item_count())
if st.button(t('clear_session'), use_container_width=True):
    for key in SESSION_KEYS:
        st.session_state.pop(key, None)
    st.success(t('session_done'))

st.divider()
st.subheader(t('ledger'))
st.info(t('ledger_help'))
ledger = read_csv_if_exists(PERSISTENT_LEDGER_PATH)
if ledger.empty:
    st.caption(t('missing'))
else:
    st.metric(t('rows'), len(ledger))
    st.download_button(t('download_ledger'), ledger.to_csv(index=False), file_name='odds_lock_pro_ledger_backup.csv', mime='text/csv')
ledger_confirm = st.text_input(t('confirm_ledger'), value='', key='ledger_reset_confirm')
if st.button(t('clear_ledger'), use_container_width=True, disabled=ledger_confirm.strip() != 'CLEAR'):
    PERSISTENT_LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    if PERSISTENT_LEDGER_PATH.exists():
        PERSISTENT_LEDGER_PATH.unlink()
    for key in ['odds_lock_pro_locked_rows', 'daily_workflow_locked_rows', 'public_proof_dashboard_latest_rows']:
        st.session_state.pop(key, None)
    st.success(t('ledger_done'))

st.divider()
st.subheader(t('memory'))
st.info(t('memory_help'))
backup_parts = []
for path in [LEARNED_STATE_PATH, LEARNING_BANK_PATH, ARA_MEMORY_PATH]:
    if path.exists():
        backup_parts.append(f'--- {path.name} ---\n' + path.read_text(encoding='utf-8', errors='replace'))
if backup_parts:
    st.download_button(t('download_memory'), '\n\n'.join(backup_parts), file_name='learning_memory_backup.txt', mime='text/plain')
else:
    st.caption(t('missing'))
memory_confirm = st.text_input(t('confirm_memory'), value='', key='memory_reset_confirm')
if st.button(t('clear_memory'), use_container_width=True, disabled=memory_confirm.strip() != 'RESET MEMORY'):
    for path in [LEARNED_STATE_PATH, LEARNING_BANK_PATH, ARA_MEMORY_PATH]:
        if path.exists():
            path.unlink()
    st.success(t('memory_done'))
