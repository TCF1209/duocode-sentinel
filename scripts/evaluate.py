#!/usr/bin/env python3
"""Run the pipeline over the inbox, then score it with the organisers' scorer.

    python scripts/evaluate.py
    python scripts/evaluate.py --limit 50          # quick loop while developing
    python scripts/evaluate.py --data data/holdout --out runs/holdout

Prints a compact scoreboard and the exact Markdown row to paste into
docs/SCORING.md. The row is printed rather than written: a score belongs in the
log only once a human has decided the run was a fair one.

The grader lives in data/_grader/, which is git-ignored — see docs/SCORING.md
for why. Without it this script still runs the pipeline and reports what the
pipeline itself measured; it just cannot tell you whether the answers are right.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GRADER = ROOT / "data" / "_grader"


def venv_python() -> str:
    for candidate in (ROOT / ".venv" / "Scripts" / "python.exe",
                      ROOT / ".venv" / "bin" / "python"):
        if candidate.exists():
            return str(candidate)
    return sys.executable


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/bundle")
    ap.add_argument("--out", default="runs/latest")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--label", default="", help="note for the score-log row")
    args = ap.parse_args()

    py = venv_python()

    # ---- 1. produce a submission -------------------------------------
    cmd = [py, "backend/run.py", "--data", args.data, "--out", args.out]
    if args.limit:
        cmd += ["--limit", str(args.limit)]
    proc = run(cmd)
    print(proc.stdout, end="")
    if proc.returncode != 0:
        print(proc.stderr, file=sys.stderr)
        return proc.returncode

    submission = ROOT / args.out / "submission.json"
    metrics = json.loads((ROOT / args.out / "metrics.json").read_text(encoding="utf-8"))

    # ---- 2. score it --------------------------------------------------
    score_cli = GRADER / "score_cli.py"
    truth = GRADER / "ground_truth.json"
    if not (score_cli.exists() and truth.exists()):
        print("\nNo local grader found — skipping scoring.")
        print("See docs/SCORING.md for how self-evaluation works.")
        return 0

    if args.limit:
        print("\n--limit produces a partial submission; the scorer counts every "
              "missing email as wrong. Treat the numbers below as a smoke test only.")

    proc = run([py, str(score_cli), str(submission),
                "--ground-truth", str(truth), "--json"])
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr, file=sys.stderr)
        return proc.returncode

    r = json.loads(proc.stdout)
    _print_board(r, metrics)
    _print_log_row(r, metrics, args.label)
    return 0


def _bar(x: float, width: int = 28) -> str:
    n = int(round(max(0.0, min(1.0, x)) * width))
    return "#" * n + "." * (width - n)


def _print_board(r: dict, metrics: dict) -> None:
    s1, s3, rel, e2e = r["stage1"], r["stage3"], r["reliability"], r["end_to_end"]
    print("\n" + "=" * 66)
    print(f"  SCORE   final {r['final_score']:.4f}    ({r['n_emails']} emails)")
    print("=" * 66)
    print(f"  end-to-end   {e2e['rate']:.3f}  {_bar(e2e['rate'])}"
          f"   {e2e['success']}/{e2e['total']} defect emails  (50%)")
    print(f"  stage1 F1    {s1['macro_f1']:.3f}  {_bar(s1['macro_f1'])}"
          f"   accuracy {s1['accuracy']:.3f}            (30%)")
    print(f"  stage3 F1    {s3['defect_f1']:.3f}  {_bar(s3['defect_f1'])}"
          f"   P {s3['defect_precision']:.2f} / R {s3['defect_recall']:.2f}  (20%)")
    print(f"  escalation   {rel['escalation_f1']:.3f}  {_bar(rel['escalation_f1'])}"
          f"   {rel['pred_review']} flagged / {rel['gold_review']} real  (diagnostic)")

    print("\n  per category   precision / recall / f1")
    for cat, d in s1["per"].items():
        tp, fp, fn = d["tp"], d["fp"], d["fn"]
        p = tp / (tp + fp) if (tp + fp) else 0.0
        rc = tp / (tp + fn) if (tp + fn) else 0.0
        f = 2 * p * rc / (p + rc) if (p + rc) else 0.0
        flag = "  <-- weakest" if f < 0.9 else ""
        print(f"    {cat:<15} {p:.2f} / {rc:.2f} / {f:.2f}{flag}")

    print("\n  escalation by reason")
    for reason, d in rel["per_reason"].items():
        print(f"    {reason:<20} {d['caught']}/{d['total']}")

    print(f"\n  resolved by rules {metrics['rule_share']:.0%}"
          f"   ·   {metrics['mean_ms_per_email']} ms per email"
          f"   ·   {metrics['llm_calls']} model calls")

    conf = s1.get("confusion", {})
    wrong = [(a, p, n) for a, row in conf.items() for p, n in row.items() if a != p]
    if wrong:
        print("\n  biggest classification confusions")
        for actual, pred, n in sorted(wrong, key=lambda x: -x[2])[:6]:
            print(f"    {n:>3}  {actual} -> {pred}")


def _print_log_row(r: dict, metrics: dict, label: str) -> None:
    row = (f"| (today) | (commit) | {r['stage1']['macro_f1']:.3f} "
           f"| {r['stage3']['defect_f1']:.3f} | {r['end_to_end']['rate']:.3f} "
           f"| {r['final_score']:.4f} | {metrics['rule_share']:.0%} "
           f"| {label or '...'} |")
    print("\n  row for docs/SCORING.md:\n  " + row + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
