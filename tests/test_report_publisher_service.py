from pathlib import Path

from autonomous_betting_agent import report_publisher_service as publisher
from autonomous_betting_agent import proof_package_service as packages


def _package(package_type="public", proof_ready=True, picks=None):
    return {
        "package_id": f"pkg_test_01_{package_type}_abc123",
        "package_schema_version": packages.PACKAGE_SCHEMA_VERSION,
        "package_hash": "pkg_hash_abc123",
        "public_export_hash": "export_hash_public",
        "private_export_hash": "export_hash_private" if package_type in {"private", "internal_review"} else "",
        "generated_at_utc": "2026-06-29T12:00:00Z",
        "workspace_id": "test_01",
        "package_type": package_type,
        "proof_grade": packages.PROOF_READY_GRADE if proof_ready else packages.PROVISIONAL_GRADE,
        "proof_ready": proof_ready,
        "ledger_backed": proof_ready,
        "ledger_integrity_status": "PASS",
        "dashboard_ready": proof_ready,
        "selected_source": "ledger" if proof_ready else "uploaded",
        "total_rows": 2,
        "unique_events": 2,
        "wins": 1,
        "losses": 1,
        "pushes": 0,
        "cancels": 0,
        "win_rate_ex_push_cancel": 0.5,
        "profit_units": 0.10,
        "ROI": 0.05,
        "average_CLV": 0.015,
        "duplicate_count": 0,
        "correction_count": 0,
        "public_safe_rows": [],
        "top_positive_ev_picks": picks if picks is not None else [{"event": "Alpha vs Beta", "pick": "Alpha ML", "report_lane": "playable", "expected_value": 0.20}],
        "proof_summary": {"total_rows": 2, "unique_events": 2},
        "roi_summary": {"roi": 0.05, "profit_units": 0.10},
        "clv_summary": {"average_clv": 0.015},
        "source_disclaimer": packages.SOURCE_DISCLAIMER,
        "verification_manifest": {"package_hash": "pkg_hash_abc123", "public_export_hash": "export_hash_public", "proof_ready": proof_ready},
        "redaction_status": {"passed": True, "blocked_terms_found": [], "blocked_paths_found": [], "checked_outputs": ["json", "markdown", "csv_bundle"], "warnings": [], "errors": []},
        "warnings": [] if proof_ready else ["Package is not powered by durable ledger rows."],
        "errors": [],
        "public_export_csv": "proof_id,event\nproof-alpha,Alpha vs Beta\n",
        "public_export_json": '{"rows": []}',
    }


def test_report_publisher_payload_includes_proof_roi_clv_risk_and_manifest(monkeypatch):
    monkeypatch.setitem(publisher.PACKAGE_BUILDERS, "public", lambda workspace_id=None: _package("public", proof_ready=True))

    payload = publisher.build_report_publisher_payload("test_01", package_type="public")

    assert payload["report_id"].startswith("report_")
    assert payload["package_id"] == "pkg_test_01_public_abc123"
    assert payload["package_hash"] == "pkg_hash_abc123"
    assert payload["proof_grade"] == packages.PROOF_READY_GRADE
    assert payload["proof_ready"] is True
    assert payload["performance_summary"]["ROI"] == 0.05
    assert payload["proof_summary"]["total_rows"] == 2
    assert payload["roi_summary"]["roi"] == 0.05
    assert payload["clv_summary"]["average_clv"] == 0.015
    assert payload["risk_summary"]["ledger_integrity_status"] == "PASS"
    assert payload["verification_manifest"]["package_hash"] == "pkg_hash_abc123"
    assert payload["top_positive_ev_summary"]["count"] == 1


def test_report_publisher_payload_handles_empty_top_ev_state(monkeypatch):
    monkeypatch.setitem(publisher.PACKAGE_BUILDERS, "public", lambda workspace_id=None: _package("public", proof_ready=True, picks=[]))

    payload = publisher.build_report_publisher_payload("test_01", package_type="public")

    assert payload["top_positive_ev_summary"]["count"] == 0
    assert payload["top_positive_ev_summary"]["message"] == packages.NO_PLAYABLE_POSITIVE_EV_MESSAGE


def test_report_publisher_payload_labels_fallback_as_provisional(monkeypatch):
    monkeypatch.setitem(publisher.PACKAGE_BUILDERS, "public", lambda workspace_id=None: _package("public", proof_ready=False))

    payload = publisher.build_report_publisher_payload("test_01", package_type="public")

    assert payload["proof_ready"] is False
    assert payload["proof_grade"] == packages.PROVISIONAL_GRADE
    assert "provisional" in payload["headline_summary"].lower()
    assert "not final proof" in payload["proof_disclaimer"].lower()


def test_report_publisher_exports_json_markdown_and_csv_bundle(monkeypatch):
    monkeypatch.setitem(publisher.PACKAGE_BUILDERS, "client", lambda workspace_id=None: _package("client", proof_ready=True))

    payload = publisher.build_report_publisher_payload("test_01", package_type="client")
    export_files = payload["export_files"]

    assert export_files["json"]["filename"].endswith(".json")
    assert export_files["markdown"]["filename"].endswith(".md")
    assert isinstance(export_files["csv_bundle"], dict)
    assert "public_safe_proof_rows.csv" in export_files["csv_bundle"]
    assert "private_audit_proof_rows.csv" not in export_files["csv_bundle"]
    assert "Proof Package" in export_files["markdown"]["content"]


def test_report_publisher_private_payload_keeps_private_package(monkeypatch):
    private = _package("private", proof_ready=True)
    private["private_export_csv"] = "source_file,event\nprivate.csv,Alpha vs Beta\n"
    private["private_export_json"] = '{"rows": [{"source_file": "private.csv"}]}'
    monkeypatch.setitem(publisher.PACKAGE_BUILDERS, "private", lambda workspace_id=None: private)

    payload = publisher.build_report_publisher_payload("test_01", package_type="private")

    assert "private_package" in payload
    assert payload["private_package"]["private_export_csv"].startswith("source_file")
    assert "private_audit_proof_rows.csv" in payload["export_files"]["csv_bundle"]


def test_report_publisher_rejects_unsupported_package_type():
    try:
        publisher.build_report_publisher_payload("test_01", package_type="bad")
    except ValueError as exc:
        assert "Unsupported package_type" in str(exc)
    else:
        raise AssertionError("Unsupported package_type should raise")


def test_report_publisher_service_does_not_import_or_call_write_paths():
    source = Path("autonomous_betting_agent/report_publisher_service.py").read_text(encoding="utf-8")
    forbidden = (
        "append_performance_rows",
        "sync_rows_by_source",
        "approve_ledger_import",
        "preview_ledger_import",
        "mutate_result",
        "update_result",
        "delete_proof",
    )
    for token in forbidden:
        assert token not in source
    assert "John Doe" not in source
    assert "NY Liberty -120" not in source
