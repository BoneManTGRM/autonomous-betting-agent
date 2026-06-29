import ast
from pathlib import Path

PAGE = Path("pages/reparodynamics_shadow_scoring.py")
SOURCE = PAGE.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def _assignment_value(name: str):
    for node in TREE.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"Missing assignment for {name}")


def test_reparodynamics_page_imports_services():
    for token in ("build_reparodynamics_shadow_scoring_report_from_text", "export_shadow_scoring_json", "export_scored_candidates_csv"):
        assert token in SOURCE


def test_reparodynamics_page_exposes_controls():
    for token in (
        "shadow_scoring_workspace_id",
        "shadow_scoring_dynamic_report",
        "shadow_scoring_odds_report",
        "shadow_scoring_operator_csv",
        "shadow_scoring_run",
        "st.download_button",
    ):
        assert token in SOURCE


def test_reparodynamics_page_displays_required_fields():
    for token in (
        "schema_version",
        "workspace_id",
        "shadow_scoring_id",
        "shadow_scoring_hash",
        "status",
        "mode",
        "candidate_count",
        "manual_review_count",
        "rejected_count",
        "data_blocked_count",
        "keep_testing_count",
        "average_RYE_score",
        "safety_gates",
        "scored_candidates",
        "preview_only",
        "files_written",
        "live_changes",
    ):
        assert token in SOURCE


def test_reparodynamics_page_text_keys_exist():
    text = _assignment_value("TEXT")
    required = {
        "title",
        "caption",
        "workspace_id",
        "dynamic_report",
        "odds_report",
        "operator_csv",
        "run",
        "summary",
        "candidates",
        "safety",
        "download_json",
        "download_csv",
        "preview_only",
        "no_files",
        "no_live",
        "no_report",
    }
    assert required.issubset(text["en"])
    assert required.issubset(text["es"])


def test_reparodynamics_page_has_no_external_client_paths():
    for token in ("requests" + ".", "httpx" + ".", "urllib" + "."):
        assert token not in SOURCE
