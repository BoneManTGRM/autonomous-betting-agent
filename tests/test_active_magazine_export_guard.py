from autonomous_betting_agent.active_magazine_export_guard import normalize_row


def test_guard_cleans_total_label_and_status():
    row = {
        "market_type": "game total",
        "prediction": "Game Total: Over",
        "line_point": "171.5",
        "decimal_price": 1.70,
        "model_probability": 0.57,
        "model_market_edge": -0.022,
        "expected_value_per_unit": -0.038,
        "odds_status": "UPLOADED_ROW",
        "weather_summary": "Weather: Weather: Sunny.",
    }
    out = normalize_row(row)
    assert out["prediction"] == "Game Total: Over 171.5"
    assert out["risk"] == "PRICE REJECTED"
    assert "Weather: Weather" not in out["weather_summary"]


def test_guard_cleans_spread_label():
    out = normalize_row({"sport": "WNBA", "market_type": "spread", "prediction": "Point Spread: Phoenix Mercury -1.5"})
    assert out["prediction"] == "Spread: Phoenix Mercury -1.5"
