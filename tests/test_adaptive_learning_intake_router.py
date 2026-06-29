import json

from autonomous_betting_agent import adaptive_learning_intake_router as router


def _package():
    return {
        "verified_learning_rows": [
            {
                "locked_row_id": "locked:proof_id:p1",
                "event": "A vs B",
                "selection": "A",
                "confirmation_value": "2-0",
                "latest_value": "1.9",
                "value_delta_percent": "-0.05",
                "match_confidence": 0.94,
                "learning_status": "verified_ready",
            }
        ],
        "manual_review_rows": [
            {
                "locked_row_id": "locked:proof_id:p2",
                "event": "C vs D",
                "status": "LOW CONFIDENCE",
                "best_score": 0.61,
            }
        ],
    }


def test_parse_json_helpers_accept_object_and_rows():
    obj = router.parse_json_object('{"a": 1}')
    rows = router.parse_json_rows('{"rows": [{"b": 2}]}')

    assert obj["a"] == 1
    assert rows == [{"b": 2}]


def test_route_learning_row_verified_lane():
    row = router.route_learning_row(
        {
            "event": "A vs B",
            "selection": "A",
            "confirmation_value": "2-0",
            "match_confidence": 0.95,
            "learning_status": "verified_ready",
        }
    )

    assert row["lane"] == "VERIFIED LANE"
    assert row["official_metrics_allowed"] is True
    assert row["shadow_learning_allowed"] is True


def test_route_learning_row_review_lane():
    row = router.route_learning_row({"event": "A vs C", "status": "LOW CONFIDENCE", "best_score": 0.62})

    assert row["lane"] == "REVIEW LANE"
    assert row["requires_review"] is True
    assert row["official_metrics_allowed"] is False


def test_route_learning_row_shadow_lane():
    row = router.route_learning_row({"event": "Pending Match", "selection": "A", "confidence": 0.20})

    assert row["lane"] == "SHADOW LANE"
    assert row["shadow_learning_allowed"] is True
    assert row["official_metrics_allowed"] is False


def test_route_learning_row_quarantine_lane():
    row = router.route_learning_row({"parse_error": "invalid_json"})

    assert row["lane"] == "QUARANTINE LANE"
    assert row["quarantined"] is True


def test_extract_package_rows_reads_package_lanes():
    rows = router.extract_package_rows(_package())

    assert len(rows) == 2
    assert {row["_intake_source"] for row in rows} == {"package_verified", "package_review"}


def test_build_adaptive_learning_intake_counts_lanes():
    report = router.build_adaptive_learning_intake(
        "test_01",
        _package(),
        shadow_rows=[{"event": "Future Match", "selection": "B", "confidence": 0.1}],
        review_rows=[{"event": "Needs Review", "manual_review_required": True}],
    )

    assert report["schema_version"] == "adaptive_learning_intake_v1"
    assert report["total_rows"] == 4
    assert report["verified_count"] == 1
    assert report["review_count"] == 2
    assert report["shadow_count"] == 1
    assert report["quarantine_count"] == 0
    assert report["official_metrics_row_count"] == 1
    assert report["shadow_learning_row_count"] == 4
    assert report["preview_only"] is True
    assert report["files_written"] == 0
    assert report["intake_hash"].startswith("adaptive_intake_hash_")


def test_build_adaptive_learning_intake_from_text_round_trips():
    report = router.build_adaptive_learning_intake_from_text(
        "test_01",
        json.dumps(_package()),
        "event,selection,confidence\nFuture Match,A,0.1\n",
        json.dumps([{"event": "Review Match", "manual_review_required": True}]),
    )

    assert report["total_rows"] == 4
    assert report["verified_count"] == 1


def test_lane_csv_and_manifest_export():
    report = router.build_adaptive_learning_intake("test_01", _package())
    verified_csv = router.lane_csv(report, "VERIFIED LANE")
    manifest = json.loads(router.export_intake_manifest_json(report))

    assert "intake_row_id" in verified_csv
    assert manifest["workspace_id"] == "test_01"
    assert "raw_row" not in json.dumps(manifest)


def test_intake_router_has_no_external_client_paths():
    source = open("autonomous_betting_agent/adaptive_learning_intake_router.py", encoding="utf-8").read()
    for token in ("requests" + ".", "httpx" + ".", "urllib" + "."):
        assert token not in source
