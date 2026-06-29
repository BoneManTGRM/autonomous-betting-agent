import ast
from pathlib import Path

PAGE = Path("pages/local_review_checklist.py")
SOURCE = PAGE.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def _assignment_value(name: str):
    for node in TREE.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"Missing assignment for {name}")


def test_local_review_page_imports_services():
    for token in (
        "build_local_review_checklist_from_text",
        "export_local_review_json",
        "export_local_review_checklist_csv",
        "export_local_review_next_actions_csv",
        "export_local_review_manifest_json",
    ):
        assert token in SOURCE


def test_local_review_page_exposes_controls():
    for token in (
        "local_review_workspace_id",
        "local_review_proof_csv",
        "local_review_history_csv",
        "local_review_decision_csv",
        "local_review_dashboard_json",
        "local_review_decision_json",
        "local_review_ack_json",
        "local_review_run",
        "st.download_button",
    ):
        assert token in SOURCE


def test_local_review_page_displays_required_fields():
    for token in (
        "schema_version",
        "workspace_id",
        "local_review_id",
        "local_review_hash",
        "mode",
        "readiness_status",
        "proof_row_count",
        "history_row_count",
        "decision_row_count",
        "dashboard_status",
        "pass_count",
        "warn_count",
        "fail_count",
        "required_failure_count",
        "checklist_rows",
        "next_actions",
        "safety_gates",
        "preview_only",
        "files_written",
        "live_changes",
    ):
        assert token in SOURCE


def test_local_review_page_text_keys_exist():
    text = _assignment_value("TEXT")
    required = {
        "title",
        "caption",
        "workspace_id",
        "proof_csv",
        "history_csv",
        "decision_csv",
        "dashboard_json",
        "decision_json",
        "ack_json",
        "run",
        "summary",
        "checks",
        "actions",
        "manifest",
        "safety",
        "download_json",
        "download_checks",
        "download_actions",
        "download_manifest",
        "preview_only",
        "no_files",
        "no_live",
        "no_report",
    }
    assert required.issubset(text["en"])
    assert required.issubset(text["es"])


def test_local_review_page_has_no_external_client_paths():
    for token in ("requests" + ".", "httpx" + ".", "urllib" + "."):
        assert token not in SOURCE
