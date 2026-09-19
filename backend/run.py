#!/usr/bin/env python3
"""Run Sentinel over an inbox and write a submission plus a full audit trail.

    python backend/run.py --data data/bundle --out runs/latest
    python backend/run.py --data data/bundle --out runs/quick --limit 40

Outputs, under --out:

    submission.json   the shape the official self-evaluation expects
    report.json       every field, verdict, evidence span and gate decision
    metrics.json      counts, timings, and the share resolved without an LLM

The submission is the only file with a fixed shape. report.json is ours: it is
what the dashboard renders and what a reviewer reads, and it is deliberately
verbose — an operations team cannot act on a verdict it cannot trace.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sdoc.pipeline import Pipeline, PipelineConfig, build_client   # noqa: E402
from sdoc.schema import EmailRecord                                # noqa: E402


def load_emails(data_root: Path, limit: int | None = None) -> list[EmailRecord]:
    inbox = data_root / "inbox"
    if not inbox.is_dir():
        raise SystemExit(
            f"No inbox at {inbox}.\n"
            f"Extract the participant bundle so that {data_root}/inbox and "
            f"{data_root}/attachments exist."
        )
    paths = sorted(inbox.glob("email_*.json"))
    if limit:
        paths = paths[:limit]
    out: list[EmailRecord] = []
    for p in paths:
        out.append(EmailRecord.from_json(json.loads(p.read_text(encoding="utf-8"))))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default="data/bundle", help="folder holding inbox/ and attachments/")
    ap.add_argument("--out", default="runs/latest", help="where to write the three output files")
    ap.add_argument("--limit", type=int, default=None, help="process only the first N emails")
    ap.add_argument("--no-llm", action="store_true",
                    help="deterministic path only — no model calls, no network")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    data_root = Path(args.data).resolve()
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    emails = load_emails(data_root, args.limit)
    client = build_client(enabled=not args.no_llm)
    if not args.quiet:
        mode = "rules + model fallback" if client else "rules only"
        print(f"Processing {len(emails)} emails from {data_root}  [{mode}]")

    pipeline = Pipeline(PipelineConfig(data_root=data_root, llm=client))
    submission: dict[str, dict] = {}
    report: dict[str, dict] = {}

    for i, email in enumerate(emails, start=1):
        result = pipeline.process(email)
        submission[email.email_id] = result.to_submission()
        report[email.email_id] = result.to_report()
        if not args.quiet and i % 100 == 0:
            print(f"  {i}/{len(emails)}")

    (out_dir / "submission.json").write_text(
        json.dumps(submission, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    metrics = pipeline.stats.to_dict()
    # What the model layer actually did and cost, at the pinned rates. Recorded
    # even when it did nothing, so "0 model calls" is an evidenced claim.
    metrics["llm"] = client.stats() if client else {"available": False}
    (out_dir / "metrics.json").write_text(
        json.dumps(metrics, indent=2), encoding="utf-8")

    if not args.quiet:
        _print_summary(metrics, report, out_dir)
    return 0


def _print_summary(metrics: dict, report: dict, out_dir: Path) -> None:
    print("\n" + "=" * 64)
    print(f"  {metrics['emails']} emails  ·  {metrics['mean_ms_per_email']} ms each"
          f"  ·  {metrics['rule_share']:.0%} resolved by rules")
    print("=" * 64)

    print("\nCategories")
    for name, n in metrics["by_category"].items():
        print(f"  {name:<16} {n:>4}")

    print("\nOutcomes")
    for name, n in metrics["by_status"].items():
        print(f"  {name:<16} {n:>4}")

    if metrics["by_review_reason"]:
        print("\nEscalated for review")
        for name, n in metrics["by_review_reason"].items():
            print(f"  {name:<20} {n:>4}")

    errors = [eid for eid, r in report.items() if r["errors"]]
    if errors:
        print(f"\n{len(errors)} emails raised an error: {', '.join(errors[:8])}"
              f"{' ...' if len(errors) > 8 else ''}")

    unreadable = metrics["documents_unreadable"]
    print(f"\nDocuments read {metrics['documents_read']}"
          f"  ·  unreadable {unreadable}")

    llm = metrics.get("llm") or {}
    if llm.get("available"):
        usage = llm["usage"]
        cache = llm["cache"]
        print(f"\nModel fallback ({llm['model']})")
        print(f"  {usage['live_calls']} live calls, {usage['cached_calls']} from cache"
              f"  ·  ${usage['cost_usd']:.4f}  ·  {llm['pricing_snapshot']}")
        for purpose, d in usage["by_purpose"].items():
            print(f"    {purpose:<14} {d['calls']:>4} calls   ${d['cost_usd']:.4f}")
        if cache["hits"] or cache["misses"]:
            print(f"  cache hit rate {cache['hit_rate']:.0%}")
        if llm.get("budget_exhausted"):
            print("  BUDGET REACHED — remaining cases were escalated, not charged")
    else:
        print("\nModel fallback: not configured (deterministic path only)")
    print(f"\nWrote {out_dir / 'submission.json'}")
    print(f"      {out_dir / 'report.json'}")
    print(f"      {out_dir / 'metrics.json'}")


if __name__ == "__main__":
    raise SystemExit(main())
