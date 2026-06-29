import ast
from pathlib import Path

PAGE = Path("pages/odds_reparodynamics_upgrade_layer.py")
SOURCE = PAGE.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def _assignment_value(name: str):
    for node in TREE.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"Missing assignment for {name}")


def test_upgrade_page_imports_services():
    for token in (
        "build_phase3e38_upgrade_report_from_text",
        "export_phase3e38_json",
        "export_upgraded_odds_csv",
        "export_market_groups_csv",
        "export_drift_csv",
        "export_repair_candidates_csv",
    ):
        assert token in SOURCE


def test_upgrade_page_exposes_controls():
    for token in (
        "phase3e38_workspace_id",
        "phase3e38_ev_buffer",
        "phase3e38_safety_margin",
        "phase3e38_max_age",
        "phase3e38_min_segment",
        "phase3e38_drift_threshold",
        "phase3e38_odds_csv",
        "phase3e38_history_csv",
        "phase3e38_run",
        "st.download_button",
    ):
        assert token in SOURCE


def test_upgrade_page_displays_required_fields():
    for token in (
        "schema_version",
        "workspace_id",
        "upgrade_id",
        "upgrade_hash",
        "mode",
        "odds_row_count",
        "history_row_count",
        "playable_count",
        "blocked_count",
        "market_group_count",
        "best_book_count",
        "drift_count",
        "repair_candidate_count",
        "upgraded_odds_rows",
        "market_groups",
        "best_book_rows",
        "segment_drift",
        "repair_candidates",
        "shadow_scoring",
        "safety_gates",
        "preview_only",
        "files_written",
        "live_changes",
    ):
        assert token in SOURCE


def test_upgrade_page_text_keys_exist():
    text = _assignment_value("TEXT")
    required = {
        "title",
        "caption",
        "workspace_id",
        "odds_csv",
        "history_csv",
        "ev_buffer",
        "safety_margin",
        "max_age",
        "min_segment",
        "drift_threshold",
        "run",
        "summary",
        "odds_rows",
        "market_groups",
        "best_books",
        "drift",
        "repairs",
        "shadow",
        "safety",
        "download_json",
        "download_odds",
        "download_groups",
        "download_drift",
        "download_repairs",
        "preview_only",
        "no_files",
        "no_live",
        "no_report",
    }
    assert required.issubset(text["en"])
    assert required.issubset(text["es"])


def test_upgrade_page_has_no_external_client_paths():
    for token in ("requests" + ".", "httpx" + ".", "urllib" + "."):
        assert token not in SOURCE
