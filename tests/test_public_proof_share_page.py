import ast
from pathlib import Path

PAGE = Path("pages/public_proof_share.py")
SOURCE = PAGE.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)
SIDEBAR = Path("autonomous_betting_agent/sidebar_nav.py").read_text(encoding="utf-8")


def _assignment_value(name: str):
    for node in TREE.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"Missing assignment for {name}")


def _text_dict():
    return _assignment_value("TEXT")


def test_public_proof_share_page_imports_read_only_public_package_services():
    for token in (
        "build_public_proof_package",
        "build_client_summary_package",
        "export_proof_package_json",
        "export_proof_package_markdown",
        "export_proof_package_csv_bundle",
        "package_is_proof_ready",
        "validate_public_package_redactions",
        "build_proof_package_qa_report",
    ):
        assert token in SOURCE


def test_public_proof_share_page_exposes_only_public_and_client_package_types():
    options = _assignment_value("PUBLIC_SHARE_PACKAGE_TYPES")
    assert options == ("public", "client")
    assert "build_private_audit_package" not in SOURCE
    assert "build_internal_review_package" not in SOURCE
    assert '"internal_review"' not in SOURCE.replace('"internal_review",', "")


def test_public_proof_share_uses_fingerprint_and_blocks_stale_downloads():
    assert "PUBLIC_SHARE_FINGERPRINT_KEY" in SOURCE
    assert "def public_share_fingerprint" in SOURCE
    assert "workspace_id" in SOURCE
    assert "package_type" in SOURCE
    assert "package_id" in SOURCE
    assert "package_hash" in SOURCE
    assert "stale = not _preview_matches(package, workspace_id, package_type)" in SOURCE
    assert "disabled = stale or not redaction_ok" in SOURCE
    assert "stale_preview" in SOURCE


def test_public_proof_share_download_keys_and_filenames_include_package_hash():
    assert "public_proof_share_json_{package_hash}" in SOURCE
    assert "public_proof_share_markdown_{package_hash}" in SOURCE
    assert "public_proof_share_csv_{package_hash}_{filename}" in SOURCE
    assert "aba_public_proof_share_{workspace_id}_{package_type}_{_hash_fragment(package)}" in SOURCE
    assert "_filename(package" in SOURCE


def test_public_proof_share_blocks_redaction_failed_downloads():
    assert "validate_public_package_redactions(package)" in SOURCE
    assert "redaction_ok = _redaction_passed(package)" in SOURCE
    assert "if not redaction_ok:" in SOURCE
    assert "redaction_failed" in SOURCE
    assert "disabled = stale or not redaction_ok" in SOURCE


def test_public_proof_share_shows_required_public_proof_fields():
    for token in (
        "proof_ready",
        "proof_grade",
        "ledger_backed",
        "selected_source",
        "ledger_integrity_status",
        "dashboard_ready",
        "package_id",
        "package_hash",
        "public_export_hash",
        "qa_report_hash",
        "verification_manifest",
        "redaction_status",
        "qa_status",
        "top_positive_ev_picks",
    ):
        assert token in SOURCE


def test_public_proof_share_never_exposes_private_download_fields():
    forbidden = (
        "private_export_csv",
        "private_export_json",
        "private_export_hash",
        "previous_row_hash",
        "correction_reason",
        "source_file",
        "api_key",
        "secret",
        "token",
        "bearer",
        "password",
        "/home/",
        "/mnt/",
        "data/private",
    )
    # Tokens are allowed only in the blocked-field constant, not in rendering/export code.
    render_source = SOURCE[SOURCE.find("def _package_builder") :]
    for token in forbidden:
        assert token not in render_source


def test_public_proof_share_has_no_write_or_mutation_paths():
    forbidden = (
        "append_performance_rows",
        "sync_rows_by_source",
        "approve_ledger_import",
        "preview_ledger_import",
        "create_correction",
        "update_result",
        "delete_proof",
        "write_text",
        "write_bytes",
        "open(",
    )
    for token in forbidden:
        assert token not in SOURCE


def test_public_proof_share_english_and_spanish_text_keys_exist():
    text = _text_dict()
    required = {
        "title",
        "caption",
        "workspace_id",
        "package_type",
        "build_preview",
        "proof_caption",
        "preview_ready",
        "no_preview",
        "stale_preview",
        "redaction_failed",
        "not_proof_ready",
        "proof_ready",
        "proof_grade",
        "ledger_backed",
        "selected_source",
        "package_id",
        "package_hash",
        "public_export_hash",
        "qa_report_hash",
        "top_ev",
        "no_top_ev",
        "verification_manifest",
        "redaction_status",
        "qa_status",
        "warnings_errors",
        "download_json",
        "download_markdown",
        "download_csv",
    }
    assert required.issubset(text["en"])
    assert required.issubset(text["es"])


def test_public_proof_share_is_in_sidebar_navigation_and_language_keys():
    assert "public_proof_share_language" in SIDEBAR
    assert "Public Proof Share" in SIDEBAR
    assert "Compartir Prueba Pública" in SIDEBAR
    assert "pages/public_proof_share.py" in SIDEBAR


def test_public_proof_share_has_no_fake_demo_values():
    for token in ("John Doe", "NY Liberty -120", "Aces vs Liberty", "+8.4%"):
        assert token not in SOURCE
