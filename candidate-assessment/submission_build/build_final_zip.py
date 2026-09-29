"""Build deliverables/JSB_Candidate_Submission_Final.zip from one git commit.

    python submission_build/build_final_zip.py [COMMIT]      (default: HEAD)

The files come from `git archive COMMIT:candidate-assessment`, so only committed content is packed,
with the repository's .gitattributes applied (setup_local.bat keeps CRLF). The EXCLUDE list below is
what START_HERE.md §5 lists as repository-only. A MANIFEST.sha256 covering every other file is added
at the root, and the ZIP is written with sorted entries and a fixed timestamp, so the same commit
always gives the same bytes.
"""
import hashlib
import io
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "candidate-assessment" / "deliverables" / "JSB_Candidate_Submission_Final.zip"
PREFIX = "JSB_Candidate_Submission/"
STAMP = (2026, 9, 29, 0, 0, 0)

EXCLUDE_PREFIXES = (
    "submission_build/", "deliverables/", "evidence/rejected/",
)
EXCLUDE_FILES = {
    "JSB_Candidate_Submission.docx",
    "exercise1-reconciliation/Finance_Summary.docx",
    "CODEX_REVIEW.md", "HANDOFF_CODEX.md",
    "evidence/POWERBI_PACKAGE.md", "evidence/LOCAL_SETUP_PACKAGE.md",
    "evidence/powerbi_v7_files.sha256", "evidence/local_setup_v5_files.sha256",
    "exercise2-ingestion/screenshots/03_postman_runner_config.png",
    "exercise2-ingestion/screenshots/05_postman_runner_pages_1_to_4.png",
    "exercise2-ingestion/screenshots/06_postman_runner_total_1027.png",
    "exercise2-ingestion/screenshots/09_postman_runner_all_tests_pass.png",
    "exercise2-ingestion/screenshots/10_postman_runner_pagination_complete.png",
    "local_load/screenshots/07_windows_xampp_dbt_test_pass.png",
    "powerbi/data/mart_ngr_by_product_monthly.csv",
    "powerbi/data/mart_bonus_cost_pct_of_ngr.csv",
    "local_load/00_drop_other_build_tables.sql",
}
EXCLUDE_NAMES = {".gitignore", ".gitattributes"}


def excluded(path):
    return (path in EXCLUDE_FILES or path.startswith(EXCLUDE_PREFIXES)
            or path.rsplit("/", 1)[-1] in EXCLUDE_NAMES or "__pycache__" in path)


def main():
    commit = sys.argv[1] if len(sys.argv) > 1 else "HEAD"
    sha = subprocess.check_output(["git", "rev-parse", commit], cwd=REPO, text=True).strip()
    tar_bytes = subprocess.check_output(["git", "archive", "--format=tar", f"{sha}:candidate-assessment"], cwd=REPO)
    files = {}
    with tarfile.open(fileobj=io.BytesIO(tar_bytes)) as tar:
        for m in tar.getmembers():
            if m.isfile() and not excluded(m.name):
                files[m.name] = tar.extractfile(m).read()
    for must in EXCLUDE_FILES:
        assert must not in files
    assert "START_HERE.md" in files and "JSB_Candidate_Submission.pdf" in files
    assert not any(n.endswith((".zip", ".docx")) for n in files), "nested zip or docx left in"

    manifest = "".join(f"{hashlib.sha256(files[n]).hexdigest()}  {n}\n" for n in sorted(files))
    files["MANIFEST.sha256"] = manifest.encode()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for n in sorted(files):
            info = zipfile.ZipInfo(PREFIX + n, STAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, files[n])
    digest = hashlib.sha256(OUT.read_bytes()).hexdigest()
    print(f"source commit {sha}")
    print(f"{OUT.name}: {len(files)} files ({len(files) - 1} + MANIFEST.sha256), "
          f"{OUT.stat().st_size:,} bytes, SHA-256 {digest}")


if __name__ == "__main__":
    main()
