from __future__ import annotations

import json

import streamlit as st

from autonomous_betting_agent.auto_learning_cycle import run_auto_learning_cycle
from autonomous_betting_agent.pick_hold_store import normalize_workspace_id
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title='Auto Learning Cycle', layout='wide')
LANG = render_app_sidebar('auto_learning_cycle', language_key='learning_memory_language')

TEXT = {
    'en': {
        'title': 'Auto Learning Cycle',
        'caption': 'Collects resolved proof rows, merges them into Learning Memory, rebuilds calibration, rebuilds learned patterns, and saves the updated learning files.',
        'workspace': 'Workspace ID',
        'run': 'Run auto learning update now',
        'result': 'Update result',
        'note': 'This trains only from resolved rows with usable probability/price and a win/loss result. Pending, void, cancelled, and unsupported rows are ignored.',
    },
    'es': {
        'title': 'Ciclo Automático de Aprendizaje',
        'caption': 'Recolecta filas resueltas, las combina con Memoria de Aprendizaje, recalibra probabilidades, reconstruye patrones y guarda archivos actualizados.',
        'workspace': 'ID del espacio de trabajo',
        'run': 'Ejecutar actualización automática ahora',
        'result': 'Resultado de actualización',
        'note': 'Entrena solo con filas resueltas que tengan probabilidad/cuota útil y resultado ganado/perdido. Pendientes, anuladas, canceladas y no compatibles se ignoran.',
    },
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT['en']).get(key, TEXT['en'].get(key, key))


st.title(t('title'))
st.caption(t('caption'))
st.info(t('note'))

workspace_input = st.text_input(t('workspace'), value=st.session_state.get('aba_test_window_id', 'test_01'))
workspace_id = normalize_workspace_id(workspace_input)
st.session_state['aba_test_window_id'] = workspace_id

settings = st.columns(5)
min_new_rows = settings[0].number_input('Minimum new resolved rows', min_value=1, max_value=100, value=5, step=1)
min_total_rows = settings[1].number_input('Minimum total memory rows', min_value=5, max_value=1000, value=10, step=5)
max_rows = settings[2].number_input('Max stored memory rows', min_value=100, max_value=100000, value=50000, step=1000)
min_patterns = settings[3].number_input('Min rows per pattern', min_value=2, max_value=50, value=3, step=1)
max_patterns = settings[4].number_input('Max stored patterns', min_value=20, max_value=5000, value=500, step=50)

save_to_github = st.toggle('Save updated learning files to GitHub when token is available', value=True)

if st.button(t('run'), type='primary', use_container_width=True):
    report = run_auto_learning_cycle(
        workspace_id,
        min_new_rows=int(min_new_rows),
        min_total_rows=int(min_total_rows),
        max_rows=int(max_rows),
        min_patterns=int(min_patterns),
        max_patterns=int(max_patterns),
        save_to_github=bool(save_to_github),
    )
    st.subheader(t('result'))
    if report.get('status') == 'trained':
        st.success('Learning files updated.')
    else:
        st.warning(f"Skipped: {report.get('reason')}")
    st.json(report)
    st.download_button('Download auto learning report', json.dumps(report, indent=2, sort_keys=True), file_name='auto_learning_cycle_report.json', mime='application/json')
