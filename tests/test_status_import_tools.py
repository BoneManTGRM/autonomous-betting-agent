from autonomous_betting_agent import status_import_tools as tools


def test_parse_status_csv_text_returns_rows():
    rows = tools.parse_status_csv_text("id,name\n1,Alpha\n2,Beta\n")

    assert rows == [{"id": "1", "name": "Alpha"}, {"id": "2", "name": "Beta"}]


def test_coerce_status_records_maps_common_fields():
    records = tools.coerce_status_records([
        {"proof_id": "p1", "sport": "tennis", "event": "A vs B", "event_start_utc": "2026-06-29"},
    ])

    assert records == [{"record_id": "p1", "category": "tennis", "name": "A vs B", "time": "2026-06-29"}]


def test_coerce_status_markers_maps_generic_values():
    markers = tools.coerce_status_markers([
        {"sport": "tennis", "event": "A vs B", "event_start_utc": "2026-06-29", "provider": "source_a", "primary_value": 2, "secondary_value": 0, "confidence": 0.9},
    ])

    assert markers[0]["category"] == "tennis"
    assert markers[0]["name"] == "A vs B"
    assert markers[0]["source"] == "source_a"
    assert markers[0]["primary"] == 2
    assert markers[0]["secondary"] == 0
    assert markers[0]["confidence"] == 0.9


def test_coerce_status_snapshots_maps_generic_values():
    snapshots = tools.coerce_status_snapshots([
        {"sport": "tennis", "event": "A vs B", "event_start_utc": "2026-06-29", "provider": "source_b", "original_value": 2.0, "current_value": 1.9},
    ])

    assert snapshots[0]["category"] == "tennis"
    assert snapshots[0]["source"] == "source_b"
    assert snapshots[0]["start_value"] == 2.0
    assert snapshots[0]["latest_value"] == 1.9


def test_build_status_preview_from_sources_reconciles_clean_inputs():
    row = {"proof_id": "p1", "sport": "tennis", "event": "A vs B", "event_start_utc": "2026-06-29"}
    marker = {**row, "primary": 2, "secondary": 0, "confidence": 0.95}
    snapshot = {**row, "start_value": 2.0, "latest_value": 1.9}

    report = tools.build_status_preview_from_sources("test_01", [row], [marker], [snapshot])

    assert report["overall_passed"] is True
    assert report["ready_count"] == 1
    assert report["review_count"] == 0
    assert report["record_count"] == 1


def test_build_status_preview_from_csv_text_accepts_three_csv_inputs():
    record_csv = "proof_id,sport,event,event_start_utc\np1,tennis,A vs B,2026-06-29\n"
    marker_csv = "sport,event,event_start_utc,primary,secondary,confidence\ntennis,A vs B,2026-06-29,2,0,0.9\n"
    snapshot_csv = "sport,event,event_start_utc,start_value,latest_value\ntennis,A vs B,2026-06-29,2.0,1.9\n"

    report = tools.build_status_preview_from_csv_text("test_01", record_csv, marker_csv, snapshot_csv)

    assert report["overall_passed"] is True
    assert report["ready_count"] == 1


def test_status_import_tools_has_no_network_write_or_mutation_paths():
    source = open("autonomous_betting_agent/status_import_tools.py", encoding="utf-8").read()
    for token in ("requests.", "httpx.", "urllib.", "approve_ledger_import", "append_performance_rows", "sync_rows_by_source", "update_result", "delete_proof", "write_text", "write_bytes"):
        assert token not in source
