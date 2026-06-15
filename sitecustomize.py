from __future__ import annotations

# Python imports sitecustomize automatically at interpreter startup when this
# repository is on sys.path. Importing the package installs the global Streamlit
# language/sidebar/report translator before any page renders.
try:
    import autonomous_betting_agent  # noqa: F401
except Exception:
    # Keep app startup safe even if a non-Streamlit command imports Python with a
    # partially installed environment.
    pass
