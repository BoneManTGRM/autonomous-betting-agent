import pandas as pd

from autonomous_betting_agent.row_normalizer import normalize_frame


def test_normalize_frame_dedupes_uploaded_and_saved_same_prediction():
    row = {
        "event_id": "evt-1",
        "event": "Away at Home",
        "event_start_utc": "2099-01-01T00:00:00Z",
        "sport": "NBA",
        "market_type": "spreads",
        "line_point": -3.5,
        "prediction": "Home",
        "bookmaker": "Book A",
        "decimal_price": 1.91,
        "model_probability": 0.62,
    }
    frame = pd.DataFrame([row, {**row, "source_file": "upload.csv"}])

    normalized = normalize_frame(frame)

    assert len(normalized) == 1


def test_normalize_frame_keeps_different_market_lines():
    base = {
        "event_id": "evt-1",
        "event": "Away at Home",
        "event_start_utc": "2099-01-01T00:00:00Z",
        "sport": "NBA",
        "market_type": "spreads",
        "prediction": "Home",
        "bookmaker": "Book A",
        "decimal_price": 1.91,
        "model_probability": 0.62,
    }
    frame = pd.DataFrame([{**base, "line_point": -3.5}, {**base, "line_point": -4.5}])

    normalized = normalize_frame(frame)

    assert len(normalized) == 2
