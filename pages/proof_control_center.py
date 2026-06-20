from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from autonomous_betting_agent.commercial_platform_tools import (
    filter_locked_proof_rows,
    load_persistent_ledger,
    save_persistent_ledger,
)
from autonomous_betting_agent.market_rules import (
    PROOF_STORE_KEYS,
    market_support_summary,
    mark_market_support,
    supported_only,
    unsupported_only,
)
from autonomous_betting_agent.pick_hold_store import (
    HELD_KEYS,
    github_store_enabled,
    load_held_rows,
    normalize_workspace_id,
    save_held_rows,
    store_snapshot,
    verify_held_rows,
)
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title='Proof Control Center', layout='wide')
LANG = render_app_sidebar('proof_control_center', language_key='proof_control_center_language')

TEXT = {
    'en': {
        'title': 'Proof Control Center',
        'caption': 'Clean unsupported markets, consolidate proof storage, and run save/reload tests before selling the record.',
        'workspace': 'Workspace ID',
        'storage': 'Storage status',
        'loaded': 'Loaded rows',
        'github': 'GitHub rows',
        'proof': 'Valid proof rows',
        'unsupported': 'Unsupported rows',
        'supported': 'Supported proof rows',
        'consolidate': 'Clean + consolidate supported proof rows',
        'test': 'Run save/reload tests',
        'download': 'Download cleaned official proof CSV',
        'no_rows': 'No proof rows found. Create locks in Odds Lock Pro first.',
        'cleaned': 'Cleaned and saved supported proof rows to durable proof stores.',
        'tests': 'Storage test results',
        'warning': 'Tennis is excluded from official proof because your odds API does not support it for this workflow.',
    },
    'es': {
        'title': 'Centro de Control de Prueba',
        'caption': 'Limpia mercados no compatibles, consolida almacenamiento y prueba guardado/recarga antes de vender el récord.',
        'workspace': 'ID del espacio de trabajo',
        'storage': 'Estado de almacenamiento',
        'loaded': 'Filas cargadas',
        'github': 'Filas GitHub',
        'proof': 'Filas válidas de prueba',
        'unsupported': 'Filas no compatibles',
        'supported': 'Filas compatibles',
        'consolidate': 'Limpiar + consolidar filas compatibles',
        'test': 'Ejecutar pruebas guardar/recargar',
        'download': 'Descargar CSV oficial limpio',
        'no_rows': 'No hay filas de prueba. Primero crea bloqueos en Odds Lock Pro.',
        'cleaned': 'Filas compatibles guardadas en almacenamiento duradero.',
        'tests': 'Resultados de prueba de almacenamiento',
        'warning': 'Tenis queda excluido de la prueba oficial porque tu API de cuotas no lo soporta para este flujo.',
    },
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT['en']).get(key, TEXT['en'].get(key, key))


def _frame_from_rows(rows: list[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame([dict(row) for row in rows if isinstance(row, dict)])


def load_all_rows(workspace_id: str) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    persistent = load_persistent_ledger(workspace_id=workspace_id)
    if not persistent.empty:
        persistent['source_store_key'] = 'persistent_ledger'
        frames.append(persistent)
    for key in sorted(HELD_KEYS):
        rows = load_held_rows(key, workspace_id)
        if rows:
            frame = _frame_from_rows(rows)
            frame['source_store_key'] = key
            frames.append(frame)
    if not frames:
        return pd.DataFrame()
    merged = pd.concat(frames, ignore_index=True, sort=False)
    locked = filter_locked_proof_rows(merged)
    if locked.empty:
        return mark_market_support(merged)
    return mark_market_support(locked)


def save_cleaned(cleaned: pd.DataFrame, workspace_id: str) -> dict[str, Any]:
    if cleaned.empty:
        return {'saved_rows': 0, 'keys': 0}
    cleaned = cleaned.copy()
    cleaned['test_window_id'] = workspace_id
    saved = save_persistent_ledger(cleaned, workspace_id=workspace_id)
    records = saved.to_dict('records') if not saved.empty else cleaned.to_dict('records')
    keys = 0
    total = 0
    for key in PROOF_STORE_KEYS:
        total += save_held_rows(key, records, workspace_id)
        st.session_state[key] = records
        keys += 1
    return {'saved_rows': len(records), 'keys': keys, 'row_writes': total}


def run_storage_tests(cleaned: pd.DataFrame, workspace_id: str) -> pd.DataFrame:
    rows = cleaned.to_dict('records') if not cleaned.empty else []
    results = []
    for key in PROOF_STORE_KEYS:
        results.append(verify_held_rows(key, rows, workspace_id))
    return pd.DataFrame(results)


st.title(t('title'))
st.caption(t('caption'))
st.warning(t('warning'))

workspace_input = st.text_input(t('workspace'), value=st.session_state.get('aba_test_window_id', 'test_01'))
workspace_id = normalize_workspace_id(workspace_input)
st.session_state['aba_test_window_id'] = workspace_id

snapshot = store_snapshot(workspace_id)
raw = load_all_rows(workspace_id)
proof = filter_locked_proof_rows(raw)
cleaned = supported_only(proof)
rejected = unsupported_only(proof)
summary = market_support_summary(proof)

st.subheader(t('storage'))
cols = st.columns(6)
cols[0].metric('Workspace', workspace_id)
cols[1].metric('GitHub durable', 'enabled' if github_store_enabled() else 'off')
cols[2].metric(t('loaded'), int(snapshot['loaded_rows'].sum()) if not snapshot.empty else 0)
cols[3].metric(t('github'), int(snapshot['github_rows'].sum()) if not snapshot.empty and 'github_rows' in snapshot.columns else 0)
cols[4].metric(t('proof'), len(proof))
cols[5].metric(t('unsupported'), summary['unsupported'])

cols2 = st.columns(4)
cols2[0].metric(t('supported'), len(cleaned))
cols2[1].metric('Unsupported tennis', summary['unsupported_tennis'])
cols2[2].metric('Raw/proof source rows', len(raw))
cols2[3].metric('Proof quality target', '100/100' if not cleaned.empty else 'N/A')

button_cols = st.columns(2)
if button_cols[0].button(t('consolidate'), type='primary', use_container_width=True, disabled=cleaned.empty):
    result = save_cleaned(cleaned, workspace_id)
    st.success(f"{t('cleaned')} Rows: {result['saved_rows']} / keys: {result['keys']}")

if button_cols[1].button(t('test'), use_container_width=True, disabled=cleaned.empty):
    test_frame = run_storage_tests(cleaned, workspace_id)
    st.subheader(t('tests'))
    st.dataframe(test_frame, use_container_width=True, hide_index=True)
    if not test_frame.empty and bool(test_frame['ok'].all()):
        st.success('All proof store save/reload tests passed.')
    else:
        st.error('One or more proof store tests failed.')

if cleaned.empty:
    st.warning(t('no_rows'))
else:
    st.download_button(t('download'), cleaned.to_csv(index=False), file_name=f'clean_official_proof_{workspace_id}.csv', mime='text/csv')

with st.expander('Cleaned official proof rows', expanded=True):
    show_cols = [col for col in ['proof_id', 'event', 'sport', 'market_type', 'prediction', 'decimal_price', 'model_probability', 'result_status', 'profit_units', 'market_supported_for_proof', 'unsupported_market_reason', 'source_store_key'] if col in cleaned.columns]
    st.dataframe(cleaned[show_cols] if show_cols else cleaned, use_container_width=True, hide_index=True)

with st.expander('Rejected unsupported rows', expanded=False):
    show_cols = [col for col in ['proof_id', 'event', 'sport', 'market_type', 'prediction', 'unsupported_market_reason', 'source_store_key'] if col in rejected.columns]
    st.dataframe(rejected[show_cols] if show_cols else rejected, use_container_width=True, hide_index=True)

with st.expander('Storage snapshot', expanded=False):
    st.dataframe(snapshot, use_container_width=True, hide_index=True)
