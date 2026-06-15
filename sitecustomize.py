from __future__ import annotations

import builtins
import os


def get_secret(*names: str) -> str:
    """Read a Streamlit secret or environment variable by one of several names.

    Some older pages call get_secret directly. Registering this helper in
    builtins keeps those pages working without duplicating the same function in
    every Streamlit page.
    """
    try:
        import streamlit as st
    except Exception:
        st = None  # type: ignore[assignment]
    for name in names:
        if not name:
            continue
        if st is not None:
            try:
                value = str(st.secrets.get(name, "")).strip()
                if value:
                    return value
            except Exception:
                pass
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


builtins.get_secret = get_secret

# Python imports sitecustomize automatically at interpreter startup when this
# repository is on sys.path. Importing the package installs the global Streamlit
# language/sidebar/report translator before any page renders.
try:
    import autonomous_betting_agent  # noqa: F401
except Exception:
    # Keep app startup safe even if a non-Streamlit command imports Python with a
    # partially installed environment.
    pass
