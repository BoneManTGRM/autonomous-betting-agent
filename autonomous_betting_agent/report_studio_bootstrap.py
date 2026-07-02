from __future__ import annotations

import importlib


def install() -> None:
    try:
        renderer = importlib.import_module('autonomous_betting_agent.' + 'magazine_book_export')
        guard = importlib.import_module('autonomous_betting_agent.' + 'active_magazine_export_guard')
        guard.install(renderer)
    except Exception:
        pass
