import ast
from pathlib import Path

PAGE = Path("pages/odds_math_completion.py")
SOURCE = PAGE.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def _assignment_value(name: str):
    for node in TREE.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"Missing assignment for {name}")


def test_odds_math_page_imports_services():
    for token in ("build_odds_math_completion_report_from_text", "export_odds_math_json", "export_odds_rows_csv"):
        assert token in SOURCE


def test_odds_math_page_exposes_controls():
    for token in (
        "odds_math_workspace_id",
        "odds_math_ev_buffer",
        "odds_math_safety_margin",
        "odds_math_kelly_fraction",
        "odds_math_max_stake",
        "odds_math_odds_csv",
        "odds_math_market_csv",
        "odds_math_run",
        "st.download_button",
    ):
        assert token in SOURCE


def test_odds_math_page_displays_required_fields():
    for token in (
        "schema_version",
        "workspace_id",
        "odds_math_id",
        "odds_math_hash",
        "row_count",
        "playable_count",
        "blocked_count",
        "market_no_vig",
        "odds_rows",
        "preview_only",
        "files_written",
        "live_changes",
    ):
        assert token in SOURCE


def test_odds_math_page_text_keys_exist():
    text = _assignment_value("TEXT")
    required = {
        "title",
        "caption",
        "workspace_id",
        "odds_csv",
        "market_csv",
        "ev_buffer",
        "safety_margin",
        "kelly_fraction",
        "max_stake",
        "run",
        "summary",
        "rows",
        "market",
        "download_json",
        "download_csv",
        "preview_only",
        "no_files",
        "no_live",
        "no_report",
    }
    assert required.issubset(text["en"])
    assert required.issubset(text["es"])


def test_odds_math_page_has_no_external_client_paths():
    for token in ("requests" + ".", "httpx" + ".", "urllib" + "."):
        assert token not in SOURCE
