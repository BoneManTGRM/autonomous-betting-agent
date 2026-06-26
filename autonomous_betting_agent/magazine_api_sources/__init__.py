from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

_BASE_PATH = Path(__file__).resolve().parents[1] / "magazine_api_sources.py"
_SPEC = importlib.util.spec_from_file_location("_aba_base_magazine_api_sources", _BASE_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"Unable to load base magazine API source patch from {_BASE_PATH}")

_base = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_base)

for _name in dir(_base):
    if _name.startswith("__") and _name not in {"__doc__", "__all__"}:
        continue
    globals()[_name] = getattr(_base, _name)


def apply_magazine_api_patch(module: Any) -> Any:
    """Apply the base API display patch, then force sale-ready report polish.

    Report Studio is clearly reaching this API patch path because the generated
    page already shows compact `ACTIVE` / `NO LIVE` labels. Applying sale-ready
    polish here guarantees the final recommendation, VS badge, fallback text,
    evidence strip, and weather cleanup travel through the path that is actually
    active in the running app.
    """
    module = _base.apply_magazine_api_patch(module)
    try:
        from autonomous_betting_agent import magazine_sale_ready_patch as sale_ready

        module.team_items = sale_ready.sale_ready_team_items
        module.injury_items = sale_ready.sale_ready_injury_items
        module.matchup_items = sale_ready.sale_ready_matchup_items
        module._team_items = sale_ready.sale_ready_team_items
        module._injury_items = sale_ready.sale_ready_injury_items
        module._matchup_items = sale_ready.sale_ready_matchup_items
        module._items = sale_ready._items_from_context
        module.sale_ready_recommendation = sale_ready.sale_ready_recommendation
        if getattr(module, "_ABA_SALE_READY_VISUALS_FROM_API_PATCH", False) is not True:
            sale_ready._patch_visuals(module)
            module.MAGAZINE_STYLE_VERSION = f"{module.MAGAZINE_STYLE_VERSION}_sale_ready_from_api_patch_v1"
            module._ABA_SALE_READY_VISUALS_FROM_API_PATCH = True
    except Exception:
        # Never break report generation if optional visual polish has an issue.
        pass
    return module


__all__ = [name for name in globals() if not name.startswith("_")]
