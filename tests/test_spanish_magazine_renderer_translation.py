import importlib

import autonomous_betting_agent.magazine_book_export as magazine_book_export
from autonomous_betting_agent.magazine_live_api_enrichment import enrich_row_with_live_api_data, enrich_rows_with_live_api_data


def test_spanish_report_enrichment_translates_dynamic_text_fields():
    row = {
        "report_language": "es",
        "event": "Iraq at France",
        "prediction": "TOTAL DEL PARTIDO: MÁS DE 2.5",
        "model_probability": 0.71,
        "market_probability": 0.73,
        "model_market_edge": -0.021,
        "expected_value_per_unit": -0.029,
        "final_decision": "WATCHLIST",
        "bookmaker": "consensus average",
        "news_injury_summary": "No lineup/injury headline returned.",
        "api_football_summary": "API-FB: no fixture match.",
        "why_lose": "Negative edge at current price.\nDo not play unless price improves.\nRecheck odds and key news.",
        "chain_notes": "Do not chain negative-EV picks.\nAvoid parlays unless edge turns positive.\nRecheck price before including.",
    }

    enriched = enrich_row_with_live_api_data(row)
    combined = "\n".join(str(enriched.get(key, "")) for key in ("why_bullets", "why_lose", "risk_reason", "chain_notes", "parlay_notes", "final_explanation"))

    assert enriched["final_decision"] == "LISTA DE SEGUIMIENTO"
    assert enriched["bookmaker"] == "promedio consenso"
    assert enriched["news_injury_summary"] == "Sin titular de lesiones/alineación."
    assert enriched["api_football_summary"] == "API-FB: sin coincidencia de partido."
    assert "El modelo proyecta" in combined
    assert "La probabilidad implícita" in combined
    assert "Ventaja negativa con la cuota actual" in combined
    assert "No jugar salvo que la cuota mejore" in combined
    assert "Revisar cuotas y noticias clave" in combined
    assert "No encadenar señales" in combined
    assert "Evitar parlays" in combined
    assert "Revisar la cuota antes de incluir" in combined
    assert "No jugar con la cuota listada" in combined
    assert "Negative edge" not in combined
    assert "Do not chain" not in combined


def test_spanish_renderer_translation_is_installed_after_row_enrichment():
    module = importlib.reload(magazine_book_export)
    enrich_rows_with_live_api_data([{"report_language": "es", "event": "Iraq at France"}])

    assert module._tr("PAGE 1 OF 75", "es") == "PÁGINA 1 DE 75"
    assert module._tr("WATCHLIST", "es") == "LISTA DE SEGUIMIENTO"
    assert module._tr("No SDIO event ID.", "es") == "Sin ID de evento SDIO."
    assert module._tr("API-FB: no fixture match.", "es") == "API-FB: sin coincidencia de partido."
