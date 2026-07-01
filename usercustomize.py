from __future__ import annotations

import os


def _skip_runtime_patches() -> bool:
    return os.getenv("GITHUB_ACTIONS", "").lower() in {"1", "true", "yes"}


if not _skip_runtime_patches():
    try:
        import sitecustomize as _aba_sitecustomize
        # Streamlit Cloud can expose CI=true. That must not disable runtime magazine rendering repairs.
        if hasattr(_aba_sitecustomize, "_ci_enabled"):
            _aba_sitecustomize._ci_enabled = lambda: False  # type: ignore[attr-defined]
        if hasattr(_aba_sitecustomize, "_apply_magazine_display_bridge"):
            _aba_sitecustomize._apply_magazine_display_bridge()  # type: ignore[attr-defined]
    except Exception:
        pass

    try:
        from autonomous_betting_agent.proof_persistence_patch import install_proof_persistence_patch
        install_proof_persistence_patch()
    except Exception:
        pass

    try:
        from autonomous_betting_agent.magazine_report_cleanup_patch import install as install_magazine_report_cleanup
        install_magazine_report_cleanup()
    except Exception:
        pass

    try:
        from autonomous_betting_agent.magazine_provider_usage_patch import install as install_magazine_provider_usage
        install_magazine_provider_usage()
    except Exception:
        pass

    try:
        from autonomous_betting_agent.magazine_report_polish_patch import install as install_magazine_report_polish
        install_magazine_report_polish()
    except Exception:
        pass

    try:
        import sitecustomize as _aba_sitecustomize
        if hasattr(_aba_sitecustomize, "_apply_magazine_display_bridge"):
            _aba_sitecustomize._apply_magazine_display_bridge()  # type: ignore[attr-defined]
    except Exception:
        pass

    try:
        from autonomous_betting_agent.sidebar_tools import install_sidebar_tools
        install_sidebar_tools()
    except Exception:
        pass

    try:
        from autonomous_betting_agent.odds_input_normalizer import install_odds_breakdown_normalizer
        install_odds_breakdown_normalizer()
    except Exception:
        pass

    try:
        from autonomous_betting_agent.proof_dashboard_patch import install_proof_dashboard_patch
        install_proof_dashboard_patch()
    except Exception:
        pass

    try:
        from autonomous_betting_agent.local_users import install_streamlit_local_user_selector
        install_streamlit_local_user_selector()
    except Exception:
        pass
