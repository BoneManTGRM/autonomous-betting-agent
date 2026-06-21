from pathlib import Path

import streamlit as st

_original_number_input = st.number_input


def volume_number_input(label, *args, **kwargs):
    text = str(label)
    if text.startswith('Max large-list') or text.startswith('Máximo de filas'):
        kwargs['max_value'] = 1000
        kwargs['value'] = 700
    elif text.startswith('Minimum model probability') or text.startswith('Probabilidad mínima'):
        kwargs['value'] = 0.50
    elif text.startswith('Large-list min learned score') or text.startswith('Puntaje aprendido mínimo'):
        kwargs['value'] = 45.0
    return _original_number_input(label, *args, **kwargs)


st.number_input = volume_number_input
code = Path(__file__).with_name('pro_predictor.py').read_text(encoding='utf-8')
exec(code, globals())
