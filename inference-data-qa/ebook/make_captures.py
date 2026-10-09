"""Cut verbatim excerpts from the real run logs in outputs/logs/ and render each as a terminal-style image.

    python ebook/make_captures.py   -> ebook/captures/*.txt (the excerpt) and ebook/img/term_*.png (its image)

Each excerpt is copied line for line from the log (nothing retyped), headed by the command that produced it.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOGS = ROOT / "outputs" / "logs"
CAP = ROOT / "ebook" / "captures"
IMG = ROOT / "ebook" / "img"
CAP.mkdir(parents=True, exist_ok=True)
IMG.mkdir(parents=True, exist_ok=True)


def lines(name):
    return (LOGS / name).read_text(encoding="utf-8").splitlines()


def between(ls, start, end, include_end=True, nth=1):
    """Lines from the nth line starting with `start` up to the next line starting with `end`."""
    hits = [i for i, l in enumerate(ls) if l.startswith(start)]
    i = hits[nth - 1]
    j = next(k for k in range(i + 1, len(ls)) if ls[k].startswith(end))
    return ls[i:j + (1 if include_end else 0)]


def table_after(ls, title_prefix):
    """A titled result table: the title line and the table under it."""
    i = next(k for k, l in enumerate(ls) if l.startswith(title_prefix))
    out, borders = [ls[i]], 0
    for l in ls[i + 1:]:
        out.append(l)
        if l.startswith("+-"):
            borders += 1
            if borders == 3:
                break
    return out


local = lines("run_local.log")
inc = lines("run_incremental_local.log")
check = lines("check_expected.log")

captures = {
    "term_checks": ("$ python run_local.py   (data-quality checks: affected employee IDs)",
                    table_after(local, "check_failures")),
    "term_counts": ("$ python run_local.py   (reconciliation: counts agree, key sets do not)",
                    table_after(local, "R2.") + [""] + table_after(local, "R4.")),
    "term_release": ("$ python run_local.py   (release decision)",
                     [l for l in local if l.startswith("Release decision")]),
    "term_independent": ("$ python tests/check_expected.py", check),
    "term_incremental": ("$ python run_incremental_local.py   (three deliveries)",
                         between(inc, "RUN 1", "employees with a change") + [""] +
                         between(inc, "RUN 2", "No source changed") + [""] +
                         between(inc, "RUN 3", "employees with a change") + [""] +
                         between(inc, "New issues this run", "{'changed_employees'")),
}
for name, (command, body) in captures.items():
    text = "\n".join([command, ""] + body) + "\n"
    (CAP / f"{name}.txt").write_text(text, encoding="utf-8")
    width = max(len(l) for l in text.splitlines()) + 2
    subprocess.run([sys.executable, str(ROOT / "ebook" / "make_screenshot.py"), str(CAP / f"{name}.txt"),
                    str(IMG / f"{name}.png"), command.split("   ")[0].lstrip("$ "), "80", str(max(width, 60))], check=True)
print("wrote", sorted(p.name for p in IMG.glob("term_*.png")))
