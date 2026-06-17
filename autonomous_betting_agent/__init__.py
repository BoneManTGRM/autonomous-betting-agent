"""Autonomous Betting Agent package."""

from __future__ import annotations

try:
    from .sidebar_tools import install_sidebar_tools
    install_sidebar_tools()
except Exception:
    pass

APP_NAME = 'ABA Signal Pro'
APP_TAGLINE = 'Powered by Reparodynamics'
PREDICTOR_TOOL_NAME = 'Pro Predictor'
