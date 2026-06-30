from __future__ import annotations

# Compatibility shim only. The magazine truth/enrichment behavior now lives directly
# in autonomous_betting_agent.magazine_live_api_enrichment. Keeping this module as a
# no-op prevents older startup hooks from applying a second renderer monkey patch.

_PATCH_VERSION = 'legacy_magazine_truth_patch_retired_v1'


def apply() -> None:
    return None


apply()
