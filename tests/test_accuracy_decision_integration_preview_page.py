import ast
from pathlib import Path

PAGE = Path("pages/accuracy_decision_integration_preview.py")
SOURCE = PAGE.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def _assignment_value(name: str):
    for node in TREE.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"Missing assignment for {name}")


def test_decision_page_imports_services():
    for token in (
        "build_accuracy_decision_integration_report_from_text",
        "export_accuracy_decision_json",
        "export_decision_preview_csv",
        "export_decision_repair_feedback_csv",
    ):
        assert token in SOURCE


def test_decision_page_exposes_controls():
    for token in (
        "accuracy_decision_workspace_id",
        "accuracy_decision_min_segment",
        "accuracy_decision_shrinkage",
        "accuracy_decision_ev_buffer",
        "accuracy_decision_safety_margin",
        "accuracy_decision_max_age",
        "accuracy_decision_kelly_fraction",
        "accuracy_decision_max_stake",
        "accuracy_decision_current_csv",
        "accuracy_decision_history_csv",
        "accuracy_decision_run",
        "st.download_button",
    ):
        assert token in SOURCE


def test_decision_page_displays_required_fields():
    for token in (
        "schema_version",
        "workspace_id",
        "decision_preview_id",
        "decision_preview_hash",
        "mode",
        "current_row_count",
        "history_row_count",
        "playable_count",
        "watch_count",
        "wait_count",
        "no_bet_count",
        "calibration_decision",
        "calibration_decision_reason",
        "brier_improvement",
        "log_loss_improvement",
        "repair_feedback_count",
        "upgrade_repair_candidate_count",
        "decision_preview_rows",
        "calibration_summary",
        "upgrade_summary",
        "repair_feedback",
        "safety_gates",
        "preview_only",
        "files_written",
        "live_changes",
    ):
        assert token in SOURCE


def test_decision_page_text_keys_exist():
    text = _assignment_value("TEXT")
    required = {
        "title",
        "caption",
        "workspace_id",
        "current_csv",
        "history_csv",
        "min_segment",
        "shrinkage",
        "ev_buffer",
        "safety_margin",
        "max_age",
        "kelly_fraction",
        "max_stake",
        "run",
        "summary",
        "rows",
        "calibration",
        "upgrade",
        "feedback",
        "safety",
        "download_json",
        "download_rows",
        "download_feedback",
        "preview_only",
        "no_files",
        "no_live",
        "no_report",
    }
    assert required.issubset(text["en"])
    assert required.issubset(text["es"])


def test_decision_page_has_no_external_client_paths():
    for token in ("requests" + ".", "httpx" + ".", "urllib" + "."):
        assert token not in SOURCE
