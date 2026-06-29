import json

from autonomous_betting_agent import odds_reparodynamics_upgrade_layer as upgrade


def _odds_rows():
    return [
        {"event_id": "e1", "sport": "tennis", "league": "atp", "market_type": "moneyline", "sportsbook": "book_a", "selection": "A", "decimal_odds": "2.20", "model_probability": "55%", "closing_decimal_odds": "2.00"},
        {"event_id": "e1", "sport": "tennis", "league": "atp", "market_type": "moneyline", "sportsbook": "book_a", "selection": "B", "decimal_odds": "1.80", "model_probability": "45%", "closing_decimal_odds": "1.85"},
        {"event_id": "e1", "sport": "tennis", "league": "atp", "market_type": "moneyline", "sportsbook": "book_b", "selection": "A", "decimal_odds": "2.35", "model_probability": "55%", "closing_decimal_odds": "2.10"},
    ]


def _history_rows():
    rows = []
    for index in range(20):
        rows.append({
            "event_id": f"base_{index}",
            "sport": "tennis",
            "league": "atp",
            "market_type": "moneyline",
            "sportsbook": "book_a",
            "decimal_odds": "1.80",
            "result": "win" if index < 14 else "loss",
            "locked_at_utc": f"2026-01-{index + 1:02d}T00:00:00Z",
        })
    for index in range(10):
        rows.append({
            "event_id": f"recent_{index}",
            "sport": "tennis",
            "league": "atp",
            "market_type": "moneyline",
            "sportsbook": "book_a",
            "decimal_odds": "1.80",
            "result": "win" if index < 2 else "loss",
            "locked_at_utc": f"2026-02-{index + 1:02d}T00:00:00Z",
        })
    return rows


def test_group_keys_are_stable():
    row = _odds_rows()[0]

    assert upgrade.event_key(row) == "e1"
    assert upgrade.market_type(row) == "moneyline"
    assert upgrade.sportsbook(row) == "book_a"
    assert upgrade.selection_key(row) == "a"
    assert "e1|book_a|moneyline" == upgrade.group_key(row)


def test_no_vig_by_market_group_supports_two_way_market():
    report = upgrade.no_vig_by_market_group(_odds_rows()[:2])

    assert len(report["groups"]) == 1
    assert report["groups"][0]["market_shape"] == "2-way"
    assert report["groups"][0]["overround"] > 1
    assert report["row_values"][0]["group_no_vig_probability"] is not None


def test_best_book_by_selection_chooses_highest_decimal_odds():
    best = upgrade.best_book_by_selection(_odds_rows())
    key = "e1|moneyline|a"

    assert best[key]["best_sportsbook"] == "book_b"
    assert best[key]["best_decimal_odds"] == 2.35


def test_clv_metrics_detect_positive_clv():
    clv = upgrade.clv_metrics(_odds_rows()[0])

    assert clv["CLV_status"] == "positive_CLV"
    assert clv["CLV_decimal_delta"] == 0.2


def test_upgraded_odds_rows_adds_blockers_and_price_quality():
    rows = upgrade.upgraded_odds_rows(_odds_rows(), ev_buffer=0.0, safety_margin=0.02)

    assert rows[0]["market_shape"] == "2-way"
    assert rows[0]["price_quality"] in {"premium_price", "playable_price", "fair_but_thin_price", "bad_price"}
    assert "not_best_available_book" in rows[0]["blockers"]
    assert rows[2]["best_sportsbook"] == "book_b"


def test_wilson_interval_has_bounds():
    interval = upgrade.wilson_interval(6, 10)

    assert 0 <= interval["low"] <= interval["center"] <= interval["high"] <= 1


def test_segment_drift_report_flags_underperformance():
    drift = upgrade.segment_drift_report(_history_rows(), min_segment_rows=10, drift_threshold=0.08)

    assert drift["drift_count"] >= 1
    assert any(row["drift_detected"] for row in drift["segments"])


def test_repair_candidates_from_drift_creates_shadow_candidates():
    odds_rows = upgrade.upgraded_odds_rows(_odds_rows())
    drift = upgrade.segment_drift_report(_history_rows(), min_segment_rows=10, drift_threshold=0.08)
    candidates = upgrade.repair_candidates_from_drift(drift, odds_rows)

    assert candidates
    assert all(candidate["live_mutation"] == "FORBIDDEN" for candidate in candidates)
    assert all(candidate["shadow_only"] is True for candidate in candidates)


def test_build_phase3e38_upgrade_report_from_text_exports():
    odds_csv = "event_id,sport,league,market_type,sportsbook,selection,decimal_odds,model_probability,closing_decimal_odds\ne1,tennis,atp,moneyline,book_a,A,2.20,55%,2.00\ne1,tennis,atp,moneyline,book_a,B,1.80,45%,1.85\n"
    history_csv = upgrade.csv_from_rows(_history_rows())
    report = upgrade.build_phase3e38_upgrade_report_from_text("test_01", odds_csv, history_csv, min_segment_rows=10)
    payload = json.loads(upgrade.export_phase3e38_json(report))

    assert payload["schema_version"] == "odds_reparodynamics_upgrade_v1"
    assert payload["odds_row_count"] == 2
    assert payload["market_group_count"] == 1
    assert payload["preview_only"] is True
    assert payload["files_written"] == 0
    assert payload["live_changes"] == 0
    assert "CLV_status" in upgrade.export_upgraded_odds_csv(report)
    assert "market_group_key" in upgrade.export_market_groups_csv(report)
    assert "segment_group" in upgrade.export_drift_csv(report)
    assert "repair_category" in upgrade.export_repair_candidates_csv(report)


def test_upgrade_layer_has_no_external_client_paths():
    source = open("autonomous_betting_agent/odds_reparodynamics_upgrade_layer.py", encoding="utf-8").read()
    for token in ("requests" + ".", "httpx" + ".", "urllib" + "."):
        assert token not in source
