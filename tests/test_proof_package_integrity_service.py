import copy
import json
from pathlib import Path

from autonomous_betting_agent import proof_package_integrity_service as integrity
from autonomous_betting_agent.proof_package_service import (
    EMPTY_GRADE,
    PROOF_READY_GRADE,
    PROVISIONAL_GRADE,
    build_export_hash,
    build_package_hash,
)

VALIDATOR_NAMES = (
    "validate_package_export_integrity",
    "validate_public_client_package_safety",
    "validate_private_internal_package_isolation",
    "validate_package_hash_stability",
    "validate_package_download_bundle",
    "validate_proof_grade_rules",
    "validate_top_positive_ev_safety",
)


def test_only_package(package_type="public", *, proof_ready=True, empty=False):
    public_csv = "proof_id,event,pick,report_lane,expected_value\nproof-alpha,Alpha vs Beta,Alpha ML,playable,0.20\n" if not empty else ""
    public_json = json.dumps({"rows": [{"proof_id": "proof-alpha", "event": "Alpha vs Beta", "pick": "Alpha ML", "report_lane": "playable", "expected_value": 0.20}] if not empty else []}, sort_keys=True)
    package = {
        "package_id": f"pkg_test_01_{package_type}_fixture",
        "package_schema_version": "test-only-fixture",
        "package_hash": "",
        "public_export_hash": build_export_hash(public_csv, public_json),
        "generated_at_utc": "2026-06-29T12:00:00Z",
        "workspace_id": "test_01",
        "package_type": package_type,
        "proof_grade": PROOF_READY_GRADE if proof_ready and not empty else (EMPTY_GRADE if empty else PROVISIONAL_GRADE),
        "proof_ready": bool(proof_ready and not empty),
        "ledger_backed": bool(proof_ready and not empty),
        "selected_source": "ledger" if proof_ready and not empty else ("empty" if empty else "uploaded"),
        "ledger_integrity_status": "PASS",
        "dashboard_ready": bool(proof_ready and not empty),
        "total_rows": 0 if empty else 1,
        "unique_events": 0 if empty else 1,
        "wins": 0 if empty else 1,
        "losses": 0,
        "pushes": 0,
        "cancels": 0,
        "win_rate_ex_push_cancel": 0.0 if empty else 1.0,
        "profit_units": 0.0 if empty else 1.10,
        "ROI": 0.0 if empty else 1.10,
        "average_CLV": None if empty else 0.02,
        "duplicate_count": 0,
        "correction_count": 0,
        "public_safe_rows": [] if empty else [{"proof_id": "proof-alpha", "event": "Alpha vs Beta", "pick": "Alpha ML", "report_lane": "playable", "expected_value": 0.20}],
        "top_positive_ev_picks": [] if empty else [{"event": "Alpha vs Beta", "pick": "Alpha ML", "report_lane": "playable", "expected_value": 0.20}],
        "top_positive_ev_message": "No playable positive-EV picks available." if empty else "",
        "proof_summary": {"total_rows": 0 if empty else 1},
        "roi_summary": {"ROI": 0.0 if empty else 1.10},
        "clv_summary": {"average_CLV": None if empty else 0.02},
        "source_disclaimer": "Ledger-backed metrics are proof-grade only when proof_ready=true.",
        "verification_manifest": {},
        "redaction_status": {"passed": True, "blocked_terms_found": [], "blocked_paths_found": [], "checked_outputs": ["json", "markdown", "csv_bundle"], "warnings": [], "errors": []},
        "warnings": [],
        "errors": [],
        "public_export_csv": public_csv,
        "public_export_json": public_json,
    }
    if package_type in {"private", "internal_review"}:
        package["private_export_csv"] = "source_file,event\n/private/audit.csv,Alpha vs Beta\n"
        package["private_export_json"] = json.dumps({"rows": [{"source_file": "/private/audit.csv", "event": "Alpha vs Beta"}]}, sort_keys=True)
        package["private_export_hash"] = build_export_hash(package["private_export_csv"], package["private_export_json"])
    package["package_hash"] = build_package_hash(package)
    return package


def assert_validator_contract(result):
    assert set(integrity.VALIDATOR_KEYS).issubset(result)
    assert isinstance(result["passed"], bool)
    assert isinstance(result["checked_outputs"], list)
    assert isinstance(result["warnings"], list)
    assert isinstance(result["errors"], list)
    assert isinstance(result["details"], dict)


def test_every_validator_returns_standard_dictionary_contract():
    package = test_only_package("public")
    for name in VALIDATOR_NAMES:
        result = getattr(integrity, name)(package)
        assert_validator_contract(result)


def test_valid_package_export_integrity_passes_for_all_package_types():
    for package_type in ("public", "client", "private", "internal_review"):
        package = test_only_package(package_type)
        result = integrity.validate_package_export_integrity(package)
        assert_validator_contract(result)
        assert result["passed"], result["errors"]


def test_valid_public_client_private_and_internal_safety_contracts_pass():
    assert integrity.validate_public_client_package_safety(test_only_package("public"))["passed"]
    assert integrity.validate_public_client_package_safety(test_only_package("client"))["passed"]
    assert integrity.validate_private_internal_package_isolation(test_only_package("private"))["passed"]
    assert integrity.validate_private_internal_package_isolation(test_only_package("internal_review"))["passed"]


def test_validators_fail_closed_on_missing_fields_and_unsupported_type():
    missing = test_only_package("public")
    missing.pop("package_hash")
    assert integrity.validate_package_export_integrity(missing)["passed"] is False
    bad_type = dict(test_only_package("public"), package_type="bad")
    for name in VALIDATOR_NAMES:
        result = getattr(integrity, name)(bad_type)
        assert_validator_contract(result)
        assert result["passed"] is False


def test_validator_fails_closed_when_json_export_cannot_be_parsed(monkeypatch):
    package = test_only_package("public")
    monkeypatch.setattr(integrity, "export_proof_package_json", lambda package: "not-json")
    result = integrity.validate_package_export_integrity(package)
    assert result["passed"] is False
    assert any("JSON export could not be parsed" in error for error in result["errors"])


def test_hash_stability_and_hash_change_rules():
    package = test_only_package("public")
    result = integrity.validate_package_hash_stability(package)
    assert result["passed"], result["errors"]

    changed_time = dict(package)
    changed_time["generated_at_utc"] = "2099-01-01T00:00:00Z"
    assert build_package_hash(package) == build_package_hash(changed_time)

    changed_rows = copy.deepcopy(package)
    changed_rows["public_safe_rows"] = package["public_safe_rows"] + [{"proof_id": "proof-new", "row_hash": "row-new"}]
    assert build_package_hash(package) != build_package_hash(changed_rows)

    changed_type = dict(package)
    changed_type["package_type"] = "client"
    assert build_package_hash(package) != build_package_hash(changed_type)


def test_export_hash_change_rules_and_private_export_hash_rules():
    package = test_only_package("public")
    changed_public_hash = build_export_hash(package["public_export_csv"] + "proof-extra,Extra,Extra,playable,0.30\n", package["public_export_json"])
    assert changed_public_hash != package["public_export_hash"]
    assert "private_export_hash" not in package

    private = test_only_package("private")
    assert private["private_export_hash"].startswith("export_hash_")
    public_with_private = dict(package, private_export_hash="export_hash_bad")
    assert integrity.validate_package_export_integrity(public_with_private)["passed"] is False


def test_public_client_outputs_block_private_fields_and_paths():
    package = test_only_package("public")
    package["source_file"] = "/home/private/audit.csv"
    package["previous_row_hash"] = "private-prev"
    package["correction_reason"] = "private correction"
    package["private_export_csv"] = "secret"
    package["private_export_json"] = "token"
    package["private_export_hash"] = "password"
    package["api_key"] = "bearer secret token"
    result = integrity.validate_public_client_package_safety(package)
    assert result["passed"] is False
    joined = "\n".join(result["errors"])
    assert "source_file" in joined
    assert "/home/" in joined


def test_proof_grade_rules_cannot_be_overstated():
    package = test_only_package("public")
    assert integrity.validate_proof_grade_rules(package)["passed"]

    fallback = test_only_package("public", proof_ready=False)
    assert fallback["proof_grade"] == PROVISIONAL_GRADE
    assert integrity.validate_proof_grade_rules(fallback)["passed"]

    empty = test_only_package("public", proof_ready=False, empty=True)
    assert empty["proof_grade"] == EMPTY_GRADE
    assert integrity.validate_proof_grade_rules(empty)["passed"]

    overstated = dict(fallback, proof_grade=PROOF_READY_GRADE, proof_ready=True)
    assert integrity.validate_proof_grade_rules(overstated)["passed"] is False

    bad_integrity = dict(package, ledger_integrity_status="FAIL", proof_ready=True)
    assert integrity.validate_proof_grade_rules(bad_integrity)["passed"] is False

    bad_redaction = dict(package, redaction_status={"passed": False}, proof_ready=True)
    assert integrity.validate_proof_grade_rules(bad_redaction)["passed"] is False


def test_top_ev_excludes_watchlist_avoid_and_empty_state_is_honest():
    package = test_only_package("public")
    assert integrity.validate_top_positive_ev_safety(package)["passed"]

    watch = dict(package, top_positive_ev_picks=[{"event": "Bad", "report_lane": "watchlist", "expected_value": 0.50}])
    assert integrity.validate_top_positive_ev_safety(watch)["passed"] is False

    avoid = dict(package, top_positive_ev_picks=[{"event": "Bad", "report_lane": "avoid", "expected_value": 0.50}])
    assert integrity.validate_top_positive_ev_safety(avoid)["passed"] is False

    no_ev = dict(package, top_positive_ev_picks=[{"event": "Bad", "report_lane": "playable", "expected_value": -0.01}])
    assert integrity.validate_top_positive_ev_safety(no_ev)["passed"] is False

    empty = test_only_package("public", proof_ready=False, empty=True)
    assert integrity.validate_top_positive_ev_safety(empty)["passed"]


def test_download_bundle_parseability_and_no_disk_writes(tmp_path):
    package = test_only_package("public")
    result = integrity.validate_package_download_bundle(package)
    assert result["passed"], result["errors"]
    assert list(Path(tmp_path).iterdir()) == []


def test_integrity_service_source_does_not_import_write_mutation_paths():
    source = Path("autonomous_betting_agent/proof_package_integrity_service.py").read_text(encoding="utf-8")
    forbidden = (
        "append_performance_rows",
        "sync_rows_by_source",
        "approve_ledger_import",
        "preview_ledger_import",
        "create_correction",
        "update_result",
        "delete_proof",
    )
    for token in forbidden:
        assert token not in source
    assert integrity._no_write_paths_detected()["passed"]
