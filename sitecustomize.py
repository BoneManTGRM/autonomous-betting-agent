from __future__ import annotations

import builtins
import importlib
import os
import sys
from types import ModuleType
from typing import Any

_TARGET = "autonomous_betting_agent.magazine_book_export"
_ORIGINAL_IMPORT = builtins.__import__
_ORIGINAL_RELOAD = importlib.reload


def get_secret(*names: str) -> str:
    """Read a secret from Streamlit secrets first, then environment variables.

    This file intentionally does not monkey-patch Streamlit widgets. Uploaders,
    buttons, forms, text inputs, radios, and selectboxes must stay native so the
    app remains stable on mobile and desktop.
    """
    try:
        import streamlit as st
    except Exception:
        st = None
    for name in names:
        if not name:
            continue
        if st is not None:
            try:
                raw = st.secrets.get(name, '')
                value = str(raw.strip()) if hasattr(raw, 'strip') else str(raw).strip()
                if value:
                    return value
            except Exception:
                pass
        value = os.getenv(name, '').strip()
        if value:
            return value
    return ''


def _patch_live_enrichment_final_rows() -> None:
    """Make Report Studio receive final_enriched_picks_df rows, not raw rows.

    pages/report_studio imports enrich_rows_with_live_api_data by name before it
    renders the magazine preview. Patching the module here makes that imported
    function return canonical rows with run ids, hashes, provenance, explicit
    fallback reasons, and recalculated odds math.
    """
    try:
        from autonomous_betting_agent import magazine_live_api_enrichment as live
    except Exception:
        return
    if getattr(live, "_aba_final_enriched_rows_wrapped", False):
        return
    original = live.enrich_rows_with_live_api_data

    def wrapped_enrich_rows_with_live_api_data(rows, *args, **kwargs):
        enriched = original(rows, *args, **kwargs)
        try:
            from autonomous_betting_agent.magazine_pipeline_runtime import build_final_enriched_picks_df
            return build_final_enriched_picks_df(enriched, force_refresh=True).to_dict("records")
        except Exception:
            return enriched

    live.enrich_rows_with_live_api_data = wrapped_enrich_rows_with_live_api_data
    live._aba_final_enriched_rows_wrapped = True


def _patch_commercial_pending_proof_mask() -> None:
    """Keep raw pending rows from qualifying as proof solely by pending status."""
    try:
        import pandas as pd
        from autonomous_betting_agent import commercial_platform_tools as cpt
    except Exception:
        return
    if getattr(cpt, "_aba_pending_proof_mask_runtime_v2", False):
        return

    def guarded_lock_ready_mask(frame):
        if frame.empty:
            return pd.Series(dtype=bool)
        mask = pd.Series(False, index=frame.index)
        for field in ['lock_ready', 'official_lock_ready', 'research_lock_ready', 'profit_volume_safe']:
            if field in frame.columns:
                mask = mask | frame[field].map(cpt._truthy).fillna(False)
        if 'verified_grade' in frame.columns:
            grade = frame['verified_grade'].map(cpt.safe_text).str.lower()
            mask = mask | grade.isin(['win', 'loss', 'void', 'push', 'needs_review'])
        if 'result_status' in frame.columns:
            status = frame['result_status'].map(cpt.safe_text).str.lower()
            mask = mask | status.isin(['win', 'loss', 'void', 'push', 'needs_review'])
        return mask

    cpt._lock_ready_mask = guarded_lock_ready_mask
    cpt._aba_pending_proof_mask_runtime_v2 = True


def _apply_if_target(module: ModuleType | None) -> ModuleType | None:
    if module is None or getattr(module, "__name__", "") != _TARGET:
        return module
    try:
        from autonomous_betting_agent.magazine_api_sources import apply_magazine_api_patch
        from autonomous_betting_agent.magazine_auto_sizer import apply_magazine_auto_sizer
        from autonomous_betting_agent.magazine_combo_section_patch import install as install_combo_section
        from autonomous_betting_agent.magazine_footer_cleanup import install as install_footer_cleanup
        from autonomous_betting_agent.magazine_headline_safety import install as install_headline_safety
        from autonomous_betting_agent.magazine_live_api_enrichment import install as install_live_api_enrichment
        from autonomous_betting_agent.magazine_parlay_footer_override import install as install_parlay_footer_override
        from autonomous_betting_agent.magazine_sale_ready_patch import apply_magazine_sale_ready_patch
        from autonomous_betting_agent.spanish_magazine_fixes import install as install_spanish_magazine_fixes

        module = apply_magazine_api_patch(module)
        module = install_live_api_enrichment(module)
        module = apply_magazine_auto_sizer(module)
        module = install_headline_safety(module)
        module = apply_magazine_sale_ready_patch(module)
        try:
            from autonomous_betting_agent.magazine_pipeline_runtime import install as install_final_enriched_pipeline
            install_final_enriched_pipeline()
        except Exception:
            pass
        module = install_footer_cleanup(module)
        module = install_combo_section(module)
        module = install_parlay_footer_override(module)
        install_spanish_magazine_fixes()
        return module
    except Exception:
        return module


def _patched_import(name: str, globals: dict[str, Any] | None = None, locals: dict[str, Any] | None = None, fromlist: tuple[str, ...] = (), level: int = 0) -> Any:
    imported = _ORIGINAL_IMPORT(name, globals, locals, fromlist, level)
    if name == _TARGET or name.startswith(f"{_TARGET}.") or (name == "autonomous_betting_agent" and "magazine_book_export" in fromlist):
        _apply_if_target(sys.modules.get(_TARGET))
    if name == "autonomous_betting_agent.magazine_live_api_enrichment" or (name == "autonomous_betting_agent" and "magazine_live_api_enrichment" in fromlist):
        _patch_live_enrichment_final_rows()
    if name == "autonomous_betting_agent.commercial_platform_tools" or (name == "autonomous_betting_agent" and "commercial_platform_tools" in fromlist):
        _patch_commercial_pending_proof_mask()
    return imported


def _patched_reload(module: ModuleType) -> ModuleType:
    reloaded = _ORIGINAL_RELOAD(module)
    name = getattr(reloaded, "__name__", "")
    if name == _TARGET:
        reloaded = _apply_if_target(reloaded) or reloaded
    if name == "autonomous_betting_agent.magazine_live_api_enrichment":
        _patch_live_enrichment_final_rows()
    if name == "autonomous_betting_agent.commercial_platform_tools":
        _patch_commercial_pending_proof_mask()
    return reloaded


builtins.get_secret = get_secret
if getattr(builtins, "_ABA_MAGAZINE_IMPORT_AND_RELOAD_PATCHED", False) is not True:
    builtins.__import__ = _patched_import
    importlib.reload = _patched_reload
    builtins._ABA_MAGAZINE_IMPORT_AND_RELOAD_PATCHED = True

_patch_live_enrichment_final_rows()
_patch_commercial_pending_proof_mask()
