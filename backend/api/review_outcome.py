"""What a case is after a reviewer's corrections -- computed here, once, when
the review is saved (main.py's review route), never in the browser.

The case page lets a reviewer change a value on a field card ("the shipper
confirmed the BL should read EAST BRIGHT FZ-LLC") and make one-click
choices ("not a mismatch"). Whether a corrected pair now agrees is decided
by the same comparison the pipeline ran -- `sdoc.compare.compare_field`,
with the same canonicalisation and the same OCR-confusable veto -- so a
value typed by a person is judged exactly as one read from a document, and
the browser never has to guess what "SDN BHD" against "SDN. BHD." means.

Sentinel's own comparison is never touched: `CaseResult.comparisons` stays
what the run produced, and the outcome here lives on the review beside it
(store.py's `effective_outcome`).
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Optional

from sdoc.compare import compare_field
from sdoc.schema import MATCH, MISMATCH, UNCOMPARABLE, CaseResult, FieldValue

#: The two sides of a comparison, as the review body names them.
SIDES: tuple[str, ...] = ("si", "bl")
#: The three one-click choices a reviewer can make on a field.
FIELD_DECISIONS: tuple[str, ...] = ("cleared", "flagged", "fine")


@dataclass
class ReviewOutcome:
    status: str
    defect_fields: list[str]
    #: Per field: the verdict the corrected pair gets (`verdict`, `reason`),
    #: what stands once the reviewer's choice is applied on top (`stands`),
    #: and each side as compared, with `corrected` marking a value the
    #: reviewer typed rather than one read from the document.
    field_verdicts: dict[str, dict]


def _corrected(value: FieldValue, field: str, text: Optional[str]) -> FieldValue:
    """The side as the reviewer says it reads. A copy: the run's own value
    is the audit trail and stays where it was."""
    if text is None:
        return value
    return replace(
        value,
        field=field,
        raw=text,
        normalised=None,
        number=None,
        present=True,
        blank=False,
        extractor="reviewer",
        evidence=None,
    )


def derive(
    result: CaseResult,
    *,
    decisions: dict[str, str],
    corrections: dict[str, dict[str, str]],
    cant_tell: bool,
) -> ReviewOutcome:
    """The outcome that stands after the reviewer's corrections and choices.

    Same rule the case page used to apply on its own: any field that still
    differs is a defect and the case is MISMATCH; none, with a field still
    uncomparable, is NEEDS_REVIEW; none at all is OK; "I can't tell" is
    NEEDS_REVIEW whatever the fields say.
    """
    verdicts: dict[str, dict] = {}
    defect_fields: list[str] = []
    undecided = False
    for c in result.comparisons:
        corr = corrections.get(c.field) or {}
        if corr:
            fc = compare_field(
                c.field,
                _corrected(c.si, c.field, corr.get("si")),
                _corrected(c.bl, c.field, corr.get("bl")),
            )
        else:
            fc = c
        decision = decisions.get(c.field)
        if decision in ("cleared", "fine"):
            stands = MATCH
        elif decision == "flagged":
            stands = MISMATCH
        else:
            stands = fc.verdict
        if stands == MISMATCH:
            defect_fields.append(c.field)
        elif stands == UNCOMPARABLE:
            undecided = True
        verdicts[c.field] = {
            "verdict": fc.verdict,
            "reason": fc.reason,
            "stands": stands,
            "si": {"raw": fc.si.raw, "normalised": fc.si.normalised, "corrected": "si" in corr},
            "bl": {"raw": fc.bl.raw, "normalised": fc.bl.normalised, "corrected": "bl" in corr},
        }

    if not result.comparisons:
        # Nothing comparable (a missing or unreadable document): there is
        # no field to correct, so the run's own outcome stands unless the
        # reviewer says they cannot tell.
        status = "NEEDS_REVIEW" if cant_tell else result.status
        return ReviewOutcome(status=status, defect_fields=sorted(result.defect_fields) if status == "MISMATCH" else [], field_verdicts={})

    if cant_tell:
        status = "NEEDS_REVIEW"
    elif defect_fields:
        status = "MISMATCH"
    elif undecided:
        status = "NEEDS_REVIEW"
    else:
        status = "OK"
    return ReviewOutcome(status=status, defect_fields=sorted(defect_fields), field_verdicts=verdicts)
