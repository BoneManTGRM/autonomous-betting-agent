from autonomous_betting_agent.magazine_live_api_enrichment import enrich_rows_with_live_api_data


def test_spanish_magazine_enrichment_generates_spanish_report_text():
    rows = [
        {
            "report_language": "es",
            "event": "Iraq at France",
            "public_event": "Irak vs Francia",
            "prediction": "TOTAL DEL PARTIDO: MÁS DE 2.5",
            "public_pick": "TOTAL DEL PARTIDO: MÁS DE 2.5",
            "sport": "FIFA World Cup",
            "model_probability": 0.71,
            "market_probability": 0.73,
            "model_market_edge": -0.021,
            "expected_value_per_unit": -0.029,
            "bookmaker": "consensus average",
            "news_injury_summary": "No lineup/injury headline returned.",
            "api_football_summary": "API-FB: no fixture match.",
        }
    ]

    enriched = enrich_rows_with_live_api_data(rows)[0]
    combined = "\n".join(
        str(enriched.get(key, ""))
        for key in (
            "why_bullets",
            "risk_reason",
            "parlay_notes",
            "final_explanation",
            "bookmaker",
            "news_injury_summary",
            "api_football_summary",
            "data_source",
        )
    )

    assert "El modelo proyecta 71%" in combined
    assert "probabilidad implícita del mercado" in combined
    assert "Ventaja medida" in combined
    assert "Valor esperado" in combined
    assert "No encadenar señales" in combined
    assert "No usar la cuota listada" in combined
    assert "promedio consenso" in combined
    assert "Sin titular de lesiones/alineación" in combined
    assert "API-FB: sin coincidencia de partido" in combined
    assert "fila cargada/en caché" in combined
