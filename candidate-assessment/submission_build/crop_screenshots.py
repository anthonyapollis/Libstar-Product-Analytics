"""Crop the outer framing (other apps, browser chrome, desktop, taskbar) off the genuine captures.

Pixel crops only: no resize, no retouch. Each crop is checked to be byte-for-byte the same pixels as
that region of the original, and the original and new SHA-256 are written to
evidence/screenshot_crops.md. Runs once: an image already at its cropped size is left alone.
"""
import hashlib
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
TASKBAR = (0, 0, 1366, 728)              # Windows taskbar starts at y = 728 on a 1366 x 768 screen
CMD_WINDOW = (59, 52, 1038, 564)         # the cmd.exe window, border included, on the Claude app
BROWSER_PAGE = (0, 80, 1366, 728)        # below Edge's tab strip and address bar, above the taskbar

CROPS = {
    "local_load/screenshots/00_windows_xampp_step1_load.png": (CMD_WINDOW, "cmd.exe window only; Claude app, desktop and taskbar removed"),
    "local_load/screenshots/01_windows_xampp_dbt_debug.png": (CMD_WINDOW, "cmd.exe window only; Claude app, desktop and taskbar removed"),
    "local_load/screenshots/02_windows_xampp_dbt_staging.png": (CMD_WINDOW, "cmd.exe window only; Claude app, desktop and taskbar removed"),
    "local_load/screenshots/03_windows_xampp_dbt_marts.png": (CMD_WINDOW, "cmd.exe window only; Claude app, desktop and taskbar removed"),
    "local_load/screenshots/04_windows_workbench_jsb_assessment.png": (TASKBAR, "taskbar removed"),
    "local_load/screenshots/05_windows_workbench_jsb_platform.png": (TASKBAR, "taskbar removed"),
    "local_load/screenshots/06_windows_xampp_proof_queries.png": (TASKBAR, "taskbar removed"),
    "local_load/screenshots/07_windows_xampp_dbt_test.png": (TASKBAR, "taskbar removed"),
    "local_load/screenshots/07_windows_xampp_dbt_test_pass.png": (TASKBAR, "taskbar removed"),
    "powerbi/screenshots/01_page1_ngr_overview.png": (TASKBAR, "taskbar removed"),
    "powerbi/screenshots/02_page2_player_balances.png": (TASKBAR, "taskbar removed"),
    "powerbi/screenshots/03_page3_reconciliation.png": (TASKBAR, "taskbar removed"),
    "powerbi/screenshots/04_page4_ingestion_monitoring.png": (TASKBAR, "taskbar removed"),
    "powerbi/screenshots/05_model_view.png": (TASKBAR, "taskbar removed"),
    "exercise2-ingestion/screenshots/09_postman_runner_clean_summary.png": (TASKBAR, "taskbar removed"),
    "exercise2-ingestion/screenshots/09_postman_runner_all_tests_pass.png": (TASKBAR, "taskbar removed"),
    "exercise2-ingestion/screenshots/10_postman_runner_clean_count_1027.png": (TASKBAR, "taskbar removed"),
    "exercise2-ingestion/screenshots/10_postman_runner_pagination_complete.png": (TASKBAR, "taskbar removed"),
    "databricks/screenshots/02_serverless_job_success.png": (BROWSER_PAGE, "browser tabs, address bar and taskbar removed; run ID is in evidence/databricks_run.md"),
}

# Genuine captures that already show only the producing application.
UNCHANGED = [
    "exercise2-ingestion/screenshots/03_postman_runner_config.png",
    "exercise2-ingestion/screenshots/04_postman_request0_200ok.png",
    "exercise2-ingestion/screenshots/05_postman_runner_pages_1_to_4.png",
    "exercise2-ingestion/screenshots/06_postman_runner_total_1027.png",
    "exercise2-ingestion/screenshots/07_pycharm_mock_api_running.png",
]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    rows = []
    for rel, (box, what) in CROPS.items():
        p = ROOT / rel
        before = sha(p)
        src = Image.open(p)
        src.load()
        w, h = box[2] - box[0], box[3] - box[1]
        if src.size == (w, h):
            print(f"already cropped: {rel}")
            continue
        assert src.size == (1366, 768), (rel, src.size)
        out = src.crop(box)
        assert out.tobytes() == src.crop(box).tobytes() and out.size == (w, h)
        out.save(p, optimize=True)
        check = Image.open(p)
        assert check.mode == src.mode and check.tobytes() == src.crop(box).tobytes(), rel
        rows.append((rel, f"{box}", f"1366×768 → {w}×{h}", what, before, sha(p)))
        print(f"cropped {rel}: {w}x{h}")
    if rows:
        doc = ROOT / "evidence" / "screenshot_crops.md"
        lines = [
            "# Screenshot crops (QA-19)",
            "",
            "The genuine Windows captures below were cropped to the producing application: other apps (the Claude",
            "desktop app), browser chrome, desktop and taskbar were removed. **Pixel crop only**: no resize, retouch",
            "or other edit. `submission_build/crop_screenshots.py` checks every output pixel against the same",
            "region of the original. The originals remain in git history at the listed SHA-256.",
            "",
            "| Image | Crop box (left, top, right, bottom) | Size | What was removed | Original SHA-256 | Cropped SHA-256 |",
            "|---|---|---|---|---|---|",
        ]
        lines += [f"| `{r[0]}` | {r[1]} | {r[2]} | {r[3]} | `{r[4]}` | `{r[5]}` |" for r in rows]
        lines += ["", "Already app-only, unchanged: " + ", ".join(f"`{u}`" for u in UNCHANGED) + ".",
                  "Rendered logs (terminal-style images drawn from text files) have no framing and are unchanged.", ""]
        doc.write_text("\n".join(lines))


if __name__ == "__main__":
    main()
