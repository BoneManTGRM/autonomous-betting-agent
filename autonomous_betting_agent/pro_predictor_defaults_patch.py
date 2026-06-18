from __future__ import annotations

from typing import Any


NUMBER_DEFAULTS = {
    'Max sports': 50,
    'Máximo de deportes': 50,
    'Max events per sport': 500,
    'Máximo de eventos por deporte': 500,
}

MULTI_DEFAULTS = {
    'Bookmaker regions': ['us', 'us2', 'eu', 'uk'],
    'Regiones de casas': ['us', 'us2', 'eu', 'uk'],
    'Markets': ['h2h'],
    'Mercados': ['h2h'],
}

PROFILE_VALUES = {
    'baseline_accuracy_min_books': 1,
    'baseline_accuracy_min_model_prob': 0.58,
    'baseline_accuracy_min_edge': -0.03,
    'baseline_accuracy_strong_edge': 0.04,
    'baseline_accuracy_min_strength': 38.0,
    'baseline_accuracy_max_high_conf': 250,
    'baseline_accuracy_min_high_prob': 0.60,
    'baseline_accuracy_min_high_edge': -0.03,
    'baseline_accuracy_min_high_strength': 40.0,
    'baseline_accuracy_min_high_agent': 40.0,
}


def _label(args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
    if args:
        return str(args[0])
    return str(kwargs.get('label', ''))


def install_pro_predictor_defaults_patch() -> None:
    try:
        import streamlit as st
        from streamlit.delta_generator import DeltaGenerator
    except Exception:
        return

    for key, value in PROFILE_VALUES.items():
        st.session_state[key] = value

    if getattr(st, '_aba_pro_predictor_defaults_patch_v2', False):
        return

    real_number = st.number_input
    real_multi = st.multiselect
    real_dg_number = DeltaGenerator.number_input
    real_dg_multi = DeltaGenerator.multiselect

    def patch_number_call(args: tuple[Any, ...], kwargs: dict[str, Any]) -> tuple[tuple[Any, ...], dict[str, Any]]:
        label = _label(args, kwargs)
        if label not in NUMBER_DEFAULTS:
            return args, kwargs
        value = NUMBER_DEFAULTS[label]
        patched_args = list(args)
        patched_kwargs = dict(kwargs)
        if len(patched_args) >= 4:
            patched_args[3] = value
        else:
            patched_kwargs['value'] = value
        return tuple(patched_args), patched_kwargs

    def patch_multi_call(args: tuple[Any, ...], kwargs: dict[str, Any]) -> tuple[tuple[Any, ...], dict[str, Any]]:
        label = _label(args, kwargs)
        if label not in MULTI_DEFAULTS:
            return args, kwargs
        default = MULTI_DEFAULTS[label]
        patched_args = list(args)
        patched_kwargs = dict(kwargs)
        if len(patched_args) >= 3:
            patched_args[2] = default
        else:
            patched_kwargs['default'] = default
        return tuple(patched_args), patched_kwargs

    def number_input(*args: Any, **kwargs: Any) -> Any:
        patched_args, patched_kwargs = patch_number_call(args, kwargs)
        return real_number(*patched_args, **patched_kwargs)

    def multiselect(*args: Any, **kwargs: Any) -> Any:
        patched_args, patched_kwargs = patch_multi_call(args, kwargs)
        return real_multi(*patched_args, **patched_kwargs)

    def dg_number_input(self: Any, *args: Any, **kwargs: Any) -> Any:
        patched_args, patched_kwargs = patch_number_call(args, kwargs)
        return real_dg_number(self, *patched_args, **patched_kwargs)

    def dg_multiselect(self: Any, *args: Any, **kwargs: Any) -> Any:
        patched_args, patched_kwargs = patch_multi_call(args, kwargs)
        return real_dg_multi(self, *patched_args, **patched_kwargs)

    st.number_input = number_input
    st.multiselect = multiselect
    DeltaGenerator.number_input = dg_number_input
    DeltaGenerator.multiselect = dg_multiselect
    st._aba_pro_predictor_defaults_patch_v2 = True
