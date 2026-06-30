import ast
from pathlib import Path

PAGE = Path("pages/market_dashboard_bridge.py")
SOURCE = PAGE.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def _assignment_value(name: str):
    for node in TREE.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"Missing assignment for {name}")


def test_market_dashboard_bridge_page_imports_services():
    for token in (
        "build_market_dashboard_bridge_from_text",
        "export_market_bridge_json",
        "export_dashboard_cards_json",
        "export_tracking_schema_csv",
        "export_segment_summary_csv",
        "export_proof_handoff_csv",
        "export_market_bridge_checks_csv",
        "export_market_bridge_manifest_json",
    ):
        assert token in SOURCE


def test_market_dashboard_bridge_page_exposes_controls():
    for token in (
        "market_bridge_workspace_id",
        "market_bridge_optimizer_json",
        "market_bridge_market_csv",
        "market_bridge_chain_csv",
        "market_bridge_avoid_csv",
        "market_bridge_run",
        "st.download_button",
    ):
        assert token in SOURCE


def test_market_dashboard_bridge_page_displays_required_fields():
    for token in (
        "schema_version",
        "tracking_schema_version",
        "workspace_id",
        "bridge_id",
        "bridge_hash",
        "mode",
        "bridge_status",
        "tracking_row_count",
        "market_row_count",
        "chain_row_count",
        "avoid_row_count",
        "dashboard_cards",
        "tracking_rows",
        "segment_summary_rows",
        "proof_handoff_rows",
        "bridge_checks",
        "safety_gates",
        "preview_only",
        "files_written",
        "live_changes",
    ):
        assert token in SOURCE


def test_market_dashboard_bridge_page_text_keys_exist():
    text = _assignment_value("TEXT")
    required = {
        "title",
        "caption",
        "workspace_id",
        "optimizer_json",
        "market_csv",
        "chain_csv",
        "avoid_csv",
        "run",
        "summary",
        "cards",
        "tracking",
        "segments",
        "handoff",
        "checks",
        "safety",
        "download_json",
        "download_cards",
        "download_tracking",
        "download_segments",
        "download_handoff",
        "download_checks",
        "download_manifest",
        "preview_only",
        "no_files",
        "no_live",
        "no_report",
    }
    assert required.issubset(text["en"])
    assert required.issubset(text["es"])


def test_market_dashboard_bridge_page_has_no_external_client_paths():
    for token in ("requests" + ".", "httpx" + ".", "urllib" + "."):
        assert token not in SOURCE
