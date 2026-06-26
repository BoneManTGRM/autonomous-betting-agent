from __future__ import annotations

from autonomous_betting_agent.magazine_sale_ready_patch import apply_magazine_sale_ready_patch


def install(module):
    return apply_magazine_sale_ready_patch(module)
