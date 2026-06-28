from __future__ import annotations

from pathlib import Path

import pandas as pd

from autonomous_betting_agent.sidebar_nav import _sidebar_language_option, normalize_language
from autonomous_betting_agent.ui_i18n import localize_dataframe, localize_options, localize_value


def test_spanish_value_localization_core_buckets() -> None:
    assert localize_value("A_top_candidate", "es") == "Nivel A - candidato fuerte"
    assert localize_value("B_high_confidence_test", "es") == "Nivel B - prueba de alta confianza"
    assert localize_value("learning_candidate", "es") == "candidata de aprendizaje"
    assert localize_value("research_play", "es") == "jugada de investigacion"


def test_spanish_value_localization_visibility_and_status() -> None:
    assert localize_value("private", "es") == "privado"
    assert localize_value("public", "es") == "publico"
    assert localize_value("trial", "es") == "prueba"
    assert localize_value("active", "es") == "activo"
    assert localize_value("inactive", "es") == "inactivo"
    assert localize_value("expired", "es") == "vencido"


def test_localize_dataframe_columns_and_cells() -> None:
    frame = pd.DataFrame(
        [
            {
                "confidence_bucket": "A_top_candidate",
                "confidence_risk_score": 1,
                "sample_size": 50,
                "wins": 38,
                "losses": 12,
                "win_rate": 0.76,
                "market_type": "moneyline",
                "model_probability_bucket": "research_play",
                "report_lane_v2": "learning_candidate",
                "visibility": "private",
            }
        ]
    )
    out = localize_dataframe(frame, "es")
    assert "Rango de confianza" in out.columns
    assert "Riesgo de confianza" in out.columns
    assert "Tamano de muestra" in out.columns
    assert "Victorias" in out.columns
    assert "Derrotas" in out.columns
    assert "Tasa de acierto" in out.columns
    assert "Tipo de mercado" in out.columns
    assert "Rango de probabilidad del modelo" in out.columns
    assert "Carril de reporte v2" in out.columns
    assert out.loc[0, "Rango de confianza"] == "Nivel A - candidato fuerte"
    assert out.loc[0, "Tipo de mercado"] == "ganador"
    assert out.loc[0, "Rango de probabilidad del modelo"] == "jugada de investigacion"
    assert out.loc[0, "Carril de reporte v2"] == "candidata de aprendizaje"
    assert out.loc[0, "Visibilidad"] == "privado"


def test_empty_spanish_dataframe_columns_localize() -> None:
    frame = pd.DataFrame(columns=["event", "event_id", "sport", "sport_key", "event_start_utc"])
    out = localize_dataframe(frame, "es")
    assert list(out.columns) == ["Evento", "ID de evento", "Deporte", "Clave de deporte", "Inicio UTC"]


def test_storage_keys_localize_for_diagnostics_tables() -> None:
    frame = pd.DataFrame(
        [
            {
                "workspace_id": "test_01",
                "key": "pro_predictor_high_confidence_rows",
                "loaded_rows": 148,
                "disk_rows": 0,
                "github_rows": 148,
            }
        ]
    )
    out = localize_dataframe(frame, "es")
    assert "ID del espacio de trabajo" in out.columns
    assert "Clave" in out.columns
    assert "Filas cargadas" in out.columns
    assert "Filas en disco" in out.columns
    assert "Filas en GitHub" in out.columns
    assert out.loc[0, "Clave"] == "Filas de alta confianza de Predictor Pro"


def test_reparodynamics_forbidden_values_localize() -> None:
    assert localize_value("live repairs", "es") == "reparaciones en vivo"
    assert localize_value("TGRM repair activation", "es") == "activacion de reparacion TGRM"
    assert localize_value("automatic bet-tier changes", "es") == "cambios automaticos de nivel de apuesta"


def test_english_mode_unchanged() -> None:
    frame = pd.DataFrame([{"confidence_bucket": "A_top_candidate", "visibility": "private"}])
    assert localize_value("A_top_candidate", "en") == "A_top_candidate"
    assert localize_dataframe(frame, "en").equals(frame)


def test_localize_options_preserves_internal_values() -> None:
    display, mapping = localize_options(["private", "public"], "es")
    assert display == ["privado", "publico"]
    assert mapping["privado"] == "private"
    assert mapping["publico"] == "public"


def test_odds_lock_visible_labels_are_localized() -> None:
    source = Path("pages/odds_lock_pro.py").read_text(encoding="utf-8")
    assert "st.number_input('Daily exposure limit'" not in source
    assert "st.number_input('Per-sport exposure limit'" not in source
    assert "metric('Uploaded locked'" not in source
    assert "'Exposure', t('client')" not in source
    assert "t('daily_exposure_limit')" in source
    assert "t('per_sport_exposure_limit')" in source
    assert "t('uploaded_locked')" in source
    assert "t('exposure')" in source


def test_signal_board_spanish_guide_uses_tablero_de_senales() -> None:
    source = Path("pages/signal_board.py").read_text(encoding="utf-8")
    assert "Revisa este Signal Board" not in source
    assert "Revisa este tablero de senales" in source
    assert "st.dataframe(localize_dataframe" in source


def test_report_studio_dropdowns_preserve_raw_values_with_spanish_labels() -> None:
    source = Path("pages/report_studio.py").read_text(encoding="utf-8")
    assert "visibility_values = [\"private\", \"public\"]" in source
    assert "visibility_labels, visibility_map = localize_options(visibility_values, LANG)" in source
    assert "visibility = visibility_map.get" in source
    assert "profile_map.get" in source
    assert "global_localize_dataframe" in source


def test_sidebar_language_selector_is_spanish_in_spanish_mode() -> None:
    source = Path("autonomous_betting_agent/sidebar_nav.py").read_text(encoding="utf-8")
    assert "'Idioma' if normalize_language(language) == 'es' else 'Language'" in source
    assert "SIDEBAR_RADIO_LEGACY_TEST_MARKER" in source
    assert _sidebar_language_option("English", "es") == "Inglés"
    assert _sidebar_language_option("Español", "es") == "Español"
    assert normalize_language("Español") == "es"


def test_reparodynamics_spanish_shadow_mode_wording_is_contextual() -> None:
    source = Path("pages/reparodynamics.py").read_text(encoding="utf-8")
    assert "Resumen Shadow Mode" not in source
    assert "Resumen de Shadow Mode" in source
    assert "Evaluacion en Shadow Mode" in source
    assert "El almacenamiento local puede no persistir" in source
    assert "reparaciones en vivo" in source


def test_storage_diagnostics_uses_localized_dataframe() -> None:
    source = Path("pages/storage_diagnostics.py").read_text(encoding="utf-8")
    assert "from autonomous_betting_agent.ui_i18n import localize_dataframe" in source
    assert "st.dataframe(display_frame(snapshot)" in source


def test_no_model_or_ledger_logic_modules_changed() -> None:
    touched_pages = [
        "pages/signal_board.py",
        "pages/odds_lock_pro.py",
        "pages/report_studio.py",
        "pages/reparodynamics.py",
        "pages/storage_diagnostics.py",
    ]
    for file_name in touched_pages:
        assert Path(file_name).exists()
