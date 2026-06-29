import ast
from pathlib import Path

PAGE = Path("pages/restart_regression_package.py")
SOURCE = PAGE.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def _assignment_value(name: str):
    for node in TREE.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"Missing assignment for {name}")


def test_restart_page_imports_services():
    for token in (
        "build_restart_regression_package_from_text",
        "export_restart_regression_json",
        "export_restart_checks_csv",
        "export_restart_manifest_json",
    ):
        assert token in SOURCE


def test_restart_page_exposes_controls():
    for token in (
        "restart_regression_workspace_id",
        "restart_regression_proof_csv",
        "restart_regression_history_csv",
        "restart_regression_decision_csv",
        "restart_regression_dashboard_json",
        "restart_regression_checklist_json",
        "restart_regression_run",
        "st.download_button",
    ):
        assert token in SOURCE


def test_restart_page_displays_required_fields():
    for token in (
        "schema_version",
        "workspace_id",
        "restart_regression_id",
        "restart_regression_hash",
        "mode",
        "restart_status",
        "proof_row_count",
        "history_row_count",
        "decision_row_count",
        "pass_count",
        "warn_count",
        "fail_count",
        "dashboard_original_fingerprint",
        "dashboard_rebuilt_fingerprint",
        "checklist_original_fingerprint",
        "checklist_rebuilt_fingerprint",
        "check_rows",
        "rebuilt_dashboard_manifest",
        "rebuilt_checklist_summary",
        "safety_gates",
        "preview_only",
        "files_written",
        "live_changes",
    ):
        assert token in SOURCE


def test_restart_page_text_keys_exist():
    text = _assignment_value("TEXT")
    required = {
        "title",
        "caption",
        "workspace_id",
        "proof_csv",
        "history_csv",
        "decision_csv",
        "dashboard_json",
        "checklist_json",
        "run",
        "summary",
        "checks",
        "dashboard",
        "checklist",
        "safety",
        "download_json",
        "download_checks",
        "download_manifest",
        "preview_only",
        "no_files",
        "no_live",
        "no_report",
    }
    assert required.issubset(text["en"])
    assert required.issubset(text["es"])


def test_restart_page_has_no_external_client_paths():
    for token in ("requests" + ".", "httpx" + ".", "urllib" + "."):
        assert token not in SOURCE
