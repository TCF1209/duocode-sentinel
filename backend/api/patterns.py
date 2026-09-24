"""Read one run sideways — what is wrong across the inbox, not in one case.

The dashboard shows 520 cases one at a time, which is the right shape for the
person checking a bill of lading and the wrong shape for the person deciding
where the desk should look. Twelve emails from one carrier all failing on port
of discharge is one operational fact, not twelve reports, and nothing in the
per-case view can show it.

Everything here is an aggregation of results the pipeline already produced.
Nothing under `backend/sdoc/` is touched, no case is re-processed, and the
graded `submission.json` is unaffected — this module only counts.

**The honesty problem, and why there is a statistics import in a hackathon
project.** A per-sender defect rate is the most tempting thing on this page and
the easiest to overstate: on the dev inbox one sender shows 5 defects in 11
comparisons, 45% against a 21% baseline, and a panel that prints "2.2x worse"
beside a red badge would be asserting something eleven emails cannot support.
That is the same failure the evidence gate exists to prevent, one level up — a
confident claim with nothing behind it — so the same discipline applies.

So a rate is only ever called *above baseline* when the lower bound of its 95%
Wilson score interval clears the run's own baseline. Otherwise the sender is
still listed, with its numbers, marked as too small to tell. The interval is
Wilson rather than the textbook normal approximation for exactly the case that
matters here: at n=11 the normal approximation is badly wrong and would happily
declare a signal.
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from typing import Any

from sdoc.schema import COMPARE_FIELDS

#: 95%, two-sided. Not configurable on purpose — a threshold a caller can move
#: is a threshold that gets moved until the answer is the desired one.
_Z = 1.959963984540054


def wilson_interval(successes: int, trials: int, z: float = _Z) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion.

    >>> lo, hi = wilson_interval(5, 11)
    >>> round(lo, 3), round(hi, 3)
    (0.213, 0.72)

    Returns (0.0, 1.0) for no trials: no observations, no constraint on the
    rate, which is the honest answer rather than a divide-by-zero.
    """
    if trials <= 0:
        return 0.0, 1.0
    p = successes / trials
    z2 = z * z
    denom = 1.0 + z2 / trials
    centre = (p + z2 / (2 * trials)) / denom
    margin = (z / denom) * math.sqrt(p * (1 - p) / trials + z2 / (4 * trials * trials))
    return max(0.0, centre - margin), min(1.0, centre + margin)


def _domain(sender: str) -> str:
    """The part worth grouping by. `docs@vitalsolutions.sg` -> `vitalsolutions.sg`.

    Grouping by full address would split one carrier's desk across every mailbox
    it sends from; grouping by domain is what "this carrier's drafts" means.
    """
    s = (sender or "").strip().strip("<>")
    return s.rsplit("@", 1)[-1].lower() if "@" in s else (s.lower() or "unknown")


def summarise(cases: list, senders: dict[str, str]) -> dict[str, Any]:
    """Aggregate one run's cases. `senders` maps email_id -> raw sender string."""
    totals = {"emails": 0, "comparisons": 0, "with_defect": 0, "escalated": 0}
    field_counts: Counter[str] = Counter()
    reasons: Counter[str] = Counter()
    by_domain: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"comparisons": 0, "defects": 0, "escalated": 0, "emails": 0,
                 "fields": Counter()}
    )

    for c in cases:
        totals["emails"] += 1
        d = by_domain[_domain(senders.get(c.email_id, ""))]
        d["emails"] += 1

        if c.category == "BL_COMPARISON":
            totals["comparisons"] += 1
            d["comparisons"] += 1
        if c.status == "MISMATCH":
            totals["with_defect"] += 1
            d["defects"] += 1
            for f in c.defect_fields:
                field_counts[f] += 1
                d["fields"][f] += 1
        elif c.status == "NEEDS_REVIEW":
            totals["escalated"] += 1
            d["escalated"] += 1
            if c.review_reason:
                reasons[c.review_reason] += 1

    # The baseline every sender is judged against is this run's own rate, not a
    # number carried in from anywhere else. A different inbox has a different
    # normal, and a "worse than average" claim has to mean worse than *this*
    # average or it means nothing.
    baseline = totals["with_defect"] / totals["comparisons"] if totals["comparisons"] else 0.0

    senders_out = []
    for domain, d in by_domain.items():
        n, k = d["comparisons"], d["defects"]
        lo, hi = wilson_interval(k, n)
        senders_out.append({
            "sender": domain,
            "emails": d["emails"],
            "comparisons": n,
            "defects": k,
            "escalated": d["escalated"],
            "rate": (k / n) if n else None,
            "ci_low": lo if n else None,
            "ci_high": hi if n else None,
            # The whole point of the module: a rate is only *called* elevated
            # when the interval clears the baseline. Everything else is listed
            # with its numbers and explicitly not claimed.
            "above_baseline": bool(n and lo > baseline),
            "conclusive": bool(n and (lo > baseline or hi < baseline)),
            "top_fields": [{"field": f, "count": c} for f, c in d["fields"].most_common(3)],
        })
    senders_out.sort(key=lambda s: (-(s["rate"] or 0), -s["comparisons"]))

    total_defect_fields = sum(field_counts.values())
    fields_out = [
        {
            "field": f,
            "count": field_counts.get(f, 0),
            "share": (field_counts.get(f, 0) / total_defect_fields) if total_defect_fields else 0.0,
        }
        for f in COMPARE_FIELDS
    ]
    fields_out.sort(key=lambda x: -x["count"])

    return {
        "totals": totals,
        "baseline_defect_rate": baseline,
        "defect_fields_total": total_defect_fields,
        "fields": fields_out,
        "senders": senders_out,
        "escalation_reasons": [
            {"reason": r, "count": c} for r, c in reasons.most_common()
        ],
    }
