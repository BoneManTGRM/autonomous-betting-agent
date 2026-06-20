from pathlib import Path

import streamlit as st

_original_number_input = st.number_input


def volume_number_input(label, *args, **kwargs):
    if str(label).startswith('Max large-list'):
        kwargs['max_value'] = 700
        kwargs['value'] = 700
    return _original_number_input(label, *args, **kwargs)


st.number_input = volume_number_input
code = Path(__file__).with_name('pro_predictor.py').read_text(encoding='utf-8')
exec(code, globals())
