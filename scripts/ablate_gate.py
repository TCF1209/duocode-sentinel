#!/usr/bin/env python3
"""Measure what the evidence gate is worth, by switching parts of it off.

    python scripts/ablate_gate.py
    python scripts/ablate_gate.py --data data/holdout

`docs/ARCHITECTURE.md` §2.2 argues that a discrepancy nobody can trace is a
discrepancy we invented. That is an argument. This turns it into a table:
re-run the graded inbox with each veto disabled and report what the system
would have said instead, scored by the organisers' own scorer.

**The gate is not one switch.** It performs several checks and only one of
them is unusual, so an on/off ablation would hide the interesting part behind
three conventional intake tests. The arms below remove one veto at a time:

    full            the shipped system
    no-untraceable  a value we cannot locate in its source is used anyway —
                    this is the distinctive check, the one that turns "we
                    misread it" into "they differ"
    no-blank        a blank, "???" or "TBA" is compared like any other value
    neither         both removed: whatever `compare.py` says is reported

Everything the gate does *before* those two — missing attachment, unreadable
file, wrong document type — is left in every arm. Those are intake checks any
system needs and removing them would measure the absence of a front door
rather than the value of the gate.

Nothing here is imported by `backend/sdoc/`. It monkeypatches a copy of the
pipeline in this process only, and it never reads the answer key — the scoring
is done by shelling out to the organisers' `score_cli.py`, exactly as
`scripts/evaluate.py` does.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from collections import Counter
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from sdoc import evidence_gate                                   # noqa: E402
from sdoc.pipeline import Pipeline, PipelineConfig               # noqa: E402
from sdoc.schema import EmailRecord                              # noqa: E402

GRADER = ROOT / "data" / "_grader"

ARMS = [
    ("full", set(), "the shipped system"),
    ("no-untraceable", {"untraceable_value"}, "use values we cannot locate"),
    ("no-blank", {"blank_value"}, "compare blanks like any other value"),
    ("neither", {"untraceable_value", "blank_value"}, "report whatever compare says"),
]


@contextmanager
def vetoes_disabled(statuses: set[str]):
    """Let the named gate verdicts through as if they had been grounded.

    Patching the decision on the way out, rather than editing the checks, keeps
    the arms honest: every check still runs and still records its signals, so
    the counts of what *would* have been vetoed remain available. Only the
    consequence is removed.
    """
    if not statuses:
        yield
        return

    original = evidence_gate.evaluate

    def patched(**kwargs):
        decision = original(**kwargs)
        if decision.status in statuses:
            from dataclasses import replace
            return replace(
                decision,
                status="grounded",
                review_reason=None,
                reason=f"[ablation] {decision.status} veto disabled",
            )
        return decision

    evidence_gate.evaluate = patched
    try:
        yield
    finally:
        evidence_gate.evaluate = original


def load_emails(data_root: Path) -> list[EmailRecord]:
    paths = sorted((data_root / "inbox").glob("email_*.json"))
    if not paths:
        raise SystemExit(f"no inbox at {data_root / 'inbox'}")
    return [EmailRecord.from_json(json.loads(p.read_text(encoding="utf-8"))) for p in paths]


def run_arm(emails: list[EmailRecord], data_root: Path, disabled: set[str]) -> dict:
    with vetoes_disabled(disabled):
        pipeline = Pipeline(PipelineConfig(data_root=data_root, llm=None))
        submission, statuses, defect_fields = {}, Counter(), 0
        for email in emails:
            result = pipeline.process(email)
            submission[email.email_id] = result.to_submission()
            statuses[result.status] += 1
            defect_fields += len(result.defect_fields)
    return {
        "submission": submission,
        "reported_defects": statuses["MISMATCH"],
        "defect_fields": defect_fields,
        "escalations": statuses["NEEDS_REVIEW"],
        "clean": statuses["OK"],
    }


def score(submission: dict, truth: Path) -> dict | None:
    if not (GRADER / "score_cli.py").is_file() or not truth.is_file():
        return None
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "submission.json"
        path.write_text(json.dumps(submission, indent=2), encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(GRADER / "score_cli.py"), str(path),
             "--ground-truth", str(truth), "--json"],
            capture_output=True, text=True, cwd=ROOT,
            env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"},
        )
    if proc.returncode != 0:
        return None
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default="data/bundle")
    ap.add_argument("--out", default=None, help="write the table as JSON here too")
    args = ap.parse_args()

    data_root = (ROOT / args.data).resolve()
    truth = data_root / "ground_truth.json"
    if not truth.is_file():
        truth = GRADER / "ground_truth.json"

    emails = load_emails(data_root)
    print(f"Ablating the evidence gate over {len(emails)} emails from {data_root}\n")

    rows = []
    for name, disabled, note in ARMS:
        arm = run_arm(emails, data_root, disabled)
        scored = score(arm["submission"], truth)
        row = {
            "arm": name,
            "note": note,
            "reported_defects": arm["reported_defects"],
            "defect_fields": arm["defect_fields"],
            "escalations": arm["escalations"],
            "clean": arm["clean"],
            "final_score": scored["final_score"] if scored else None,
            "stage3_defect_f1": scored["stage3"]["defect_f1"] if scored else None,
            "end_to_end": scored["end_to_end"]["rate"] if scored else None,
            # Where the gate actually lives. The headline score excludes gold
            # NEEDS_REVIEW emails from both its populations, so a veto that
            # stops us auto-deciding one of them cannot move `final_score` at
            # all — it moves this, the axis the organisers report separately
            # and the judges read.
            "escalation_recall": scored["reliability"]["escalation_recall"] if scored else None,
            "escalation_precision": scored["reliability"]["escalation_precision"] if scored else None,
            "per_reason": scored["reliability"].get("per_reason") if scored else None,
        }
        rows.append(row)
        print(f"  {name:16} defects {row['reported_defects']:>4}   "
              f"escalations {row['escalations']:>4}   "
              f"score {row['final_score'] if row['final_score'] is not None else 'n/a'}")

    base = rows[0]

    def fmt(v, nd=4):
        return f"{v:.{nd}f}" if isinstance(v, (int, float)) else "n/a"

    print()
    print("  arm             | defects | escal | esc.recall | esc.prec |  final")
    print("  ----------------|--------:|------:|-----------:|---------:|-------")
    for r in rows:
        delta = r["reported_defects"] - base["reported_defects"]
        mark = f" ({delta:+d})" if delta else ""
        print(f"  {r['arm']:15} | {r['reported_defects']:>7}{mark:<5} | "
              f"{r['escalations']:>5} | {fmt(r['escalation_recall'], 3):>10} | "
              f"{fmt(r['escalation_precision'], 3):>8} | {fmt(r['final_score'])}")

    print()
    if all(r["final_score"] == base["final_score"] for r in rows):
        for line in [
            "READ THIS BEFORE QUOTING THE TABLE. `final_score` does not move, and",
            "that is the scorer's populations rather than a verdict on the gate.",
            "Stage 3 excludes emails whose GOLD status is NEEDS_REVIEW, and",
            "end-to-end counts only gold defect emails, so a veto that stops us",
            "auto-deciding an uncertain case cannot change either number. The",
            "effect lands on escalation recall, which the organisers report and",
            "deliberately do not weight.",
            "",
            "So on this inbox the honest claim is that the gate costs nothing to",
            "carry, not that it earns the score. What it is insurance against is",
            "measured in docs/ADVERSARIAL.md, on documents this generator cannot",
            "produce.",
        ]:
            print(f"  {line}" if line else "")

    if args.out:
        out = (ROOT / args.out).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"data_root": str(data_root), "emails": len(emails),
                                   "arms": rows}, indent=2), encoding="utf-8")
        print(f"\n  Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
