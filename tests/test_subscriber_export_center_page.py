import ast
from pathlib import Path

PAGE = Path("pages/subscriber_export_center.py")
SOURCE = PAGE.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def _assignment_value(name: str):
    for node in TREE.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"Missing assignment for {name}")


def test_subscriber_export_page_imports_services():
    for token in (
        "build_subscriber_export_center_from_text",
        "export_subscriber_export_center_json",
        "export_admin_dashboard_json",
        "export_package_index_csv",
        "export_client_safe_rows_csv",
        "export_partner_summary_csv",
        "export_plan_distribution_csv",
        "export_risk_distribution_csv",
        "export_export_checks_csv",
        "export_export_manifest_json",
    ):
        assert token in SOURCE


def test_subscriber_export_page_exposes_controls():
    for token in (
        "subscriber_export_workspace_id",
        "subscriber_export_intelligence_json",
        "subscriber_export_ledger_json",
        "subscriber_export_profiles_csv",
        "subscriber_export_run",
        "st.download_button",
    ):
        assert token in SOURCE


def test_subscriber_export_page_displays_required_fields():
    for token in (
        "schema_version",
        "workspace_id",
        "export_run_id",
        "export_hash",
        "mode",
        "export_status",
        "package_count",
        "admin_dashboard_summary",
        "export_packages",
        "package_index_rows",
        "partner_summary_rows",
        "plan_distribution_rows",
        "risk_distribution_rows",
        "export_checks",
        "safety_gates",
        "preview_only",
        "files_written",
        "live_changes",
    ):
        assert token in SOURCE


def test_subscriber_export_page_text_keys_exist():
    text = _assignment_value("TEXT")
    required = {
        "title",
        "caption",
        "workspace_id",
        "intelligence_json",
        "ledger_json",
        "profiles_csv",
        "run",
        "summary",
        "admin",
        "packages",
        "index",
        "partners",
        "plans",
        "risks",
        "checks",
        "safety",
        "download_json",
        "download_admin",
        "download_index",
        "download_client",
        "download_partner",
        "download_plan",
        "download_risk",
        "download_checks",
        "download_manifest",
        "preview_only",
        "no_files",
        "no_live",
        "no_report",
    }
    assert required.issubset(text["en"])
    assert required.issubset(text["es"])


def test_subscriber_export_page_has_no_external_client_paths():
    for token in ("requests" + ".", "httpx" + ".", "urllib" + "."):
        assert token not in SOURCE
