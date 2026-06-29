import ast
from pathlib import Path

PAGE = Path("pages/adaptive_learning_intake_router.py")
SOURCE = PAGE.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def _assignment_value(name: str):
    for node in TREE.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"Missing assignment for {name}")


def test_adaptive_intake_page_imports_services():
    for token in ("build_adaptive_learning_intake_from_text", "export_intake_manifest_json", "lane_csv"):
        assert token in SOURCE


def test_adaptive_intake_page_exposes_controls():
    for token in (
        "adaptive_intake_workspace_id",
        "adaptive_verified_confidence",
        "adaptive_review_confidence",
        "adaptive_package_json",
        "adaptive_shadow_csv",
        "adaptive_review_json",
        "adaptive_intake_run",
        "st.download_button",
    ):
        assert token in SOURCE


def test_adaptive_intake_page_displays_required_fields():
    for token in (
        "schema_version",
        "workspace_id",
        "intake_id",
        "intake_hash",
        "status",
        "total_rows",
        "verified_count",
        "review_count",
        "shadow_count",
        "quarantine_count",
        "official_metrics_row_count",
        "shadow_learning_row_count",
        "preview_only",
        "files_written",
        "lane_rows",
    ):
        assert token in SOURCE


def test_adaptive_intake_page_has_lane_language():
    for token in ("VERIFIED LANE", "REVIEW LANE", "SHADOW LANE", "QUARANTINE LANE", "INTAKE READY", "NO ROWS", "PREVIEW ONLY", "NO FILES WRITTEN"):
        assert token in SOURCE


def test_adaptive_intake_page_text_keys_exist():
    text = _assignment_value("TEXT")
    required = {
        "title",
        "caption",
        "workspace_id",
        "package_json",
        "shadow_csv",
        "review_json",
        "verified_confidence",
        "review_confidence",
        "run",
        "ready",
        "review",
        "empty",
        "preview_only",
        "no_files",
        "summary",
        "verified",
        "review_lane",
        "shadow",
        "quarantine",
        "manifest",
        "lane_download",
        "no_report",
    }
    assert required.issubset(text["en"])
    assert required.issubset(text["es"])


def test_adaptive_intake_page_has_all_downloads():
    for token in (
        "aba_adaptive_intake_",
        "aba_adaptive_intake_manifest_",
        "text/csv",
        "application/json",
    ):
        assert token in SOURCE


def test_adaptive_intake_page_has_no_external_client_paths():
    for token in ("requests" + ".", "httpx" + ".", "urllib" + "."):
        assert token not in SOURCE
