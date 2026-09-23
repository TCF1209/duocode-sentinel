"""Domain types shared by every stage of the pipeline.

Plain dataclasses on purpose: the core pipeline must run with no web framework,
no database and no network, so it can be unit-tested and executed as a CLI.
Pydantic models live only at the API boundary (backend/api).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

# --------------------------------------------------------------------------
# Constants fixed by the problem statement. Do not rename — the submission
# format and the official scorer key off these exact strings.
# --------------------------------------------------------------------------
COMPARE_FIELDS: tuple[str, ...] = (
    "shipper",
    "consignee",
    "notify_party",
    "port_of_loading",
    "port_of_discharge",
    "container_count",
    "gross_weight_kg",
)

CATEGORIES: tuple[str, ...] = (
    "BL_COMPARISON",
    "SI_REQUEST",
    "INVOICE_QUERY",
    "GENERAL",
    "SPAM",
)

STATUSES: tuple[str, ...] = ("OK", "MISMATCH", "NEEDS_REVIEW")

REVIEW_REASONS: tuple[str, ...] = (
    "wrong_doc_type",
    "missing_attachment",
    "unreadable",
    "missing_value",
)

# Document kinds we can tell apart. Only SI + BL form a comparable pair.
DOC_SI = "SHIPPING_INSTRUCTION"
DOC_BL = "BILL_OF_LADING"
DOC_INVOICE = "COMMERCIAL_INVOICE"
DOC_PACKING_LIST = "PACKING_LIST"
DOC_COO = "CERTIFICATE_OF_ORIGIN"
DOC_UNKNOWN = "UNKNOWN"

# Which numeric fields are compared as numbers rather than as text.
NUMERIC_FIELDS: tuple[str, ...] = ("container_count", "gross_weight_kg")
PARTY_FIELDS: tuple[str, ...] = ("shipper", "consignee", "notify_party")
PORT_FIELDS: tuple[str, ...] = ("port_of_loading", "port_of_discharge")


# --------------------------------------------------------------------------
# Input
# --------------------------------------------------------------------------
@dataclass
class EmailRecord:
    """One inbox record, exactly as it arrives in inbox/email_XXX.json."""

    email_id: str
    sender: str
    subject: str
    body: str
    attachments: list[str] = field(default_factory=list)

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> "EmailRecord":
        return cls(
            email_id=d["email_id"],
            sender=d.get("from", "") or "",
            subject=d.get("subject", "") or "",
            body=d.get("body", "") or "",
            attachments=list(d.get("attachments") or []),
        )

    @property
    def text(self) -> str:
        return f"{self.subject}\n\n{self.body}"


# --------------------------------------------------------------------------
# Reading a document
# --------------------------------------------------------------------------
@dataclass
class Chunk:
    """A label/value pair recovered from a document, with provenance.

    Every reader (txt / pdf / docx / xlsx) normalises down to a list of these,
    so the field extractor is format-agnostic and every extracted value can be
    traced back to a spot in the source document.
    """

    label: str
    value: str
    locator: str          # "line 7" | "cell B5" | "p1 r3" — shown to reviewers
    order: int = 0        # position in the document, for ordinal fallback


@dataclass
class ParsedDoc:
    """The result of reading one attachment."""

    path: str
    ext: str
    role_hint: str = "?"                      # "SI" | "BL" | "?" from filename
    readable: bool = True
    unreadable_reason: Optional[str] = None   # empty_file|corrupt|no_text_layer|unsupported
    doc_type: str = DOC_UNKNOWN
    doc_type_confidence: float = 0.0
    text: str = ""
    chunks: list[Chunk] = field(default_factory=list)
    n_bytes: int = 0
    notes: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------
# Extraction
# --------------------------------------------------------------------------
@dataclass
class Evidence:
    """Where a value came from — this is what a human reviewer looks at."""

    doc_role: str        # "SI" | "BL"
    locator: str         # "line 7" / "cell B5"
    label: str           # the label as it literally appeared in the document
    snippet: str         # the raw text we parsed


@dataclass
class FieldValue:
    """One of the 7 compared fields, as read from one document."""

    field: str
    raw: Optional[str] = None            # verbatim text from the document
    normalised: Optional[str] = None     # canonical form used for comparison
    number: Optional[float] = None       # for container_count / gross_weight_kg
    present: bool = False                # found a usable value
    blank: bool = False                  # label found, value is ??? / ____ / TBA
    evidence: Optional[Evidence] = None
    extractor: str = "rule"              # rule | llm | ocr


@dataclass
class DocFields:
    """All 7 fields from one document."""

    doc: ParsedDoc
    fields: dict[str, FieldValue] = field(default_factory=dict)

    def get(self, name: str) -> FieldValue:
        return self.fields.get(name) or FieldValue(field=name)


# --------------------------------------------------------------------------
# Comparison
# --------------------------------------------------------------------------
MATCH = "MATCH"
MISMATCH = "MISMATCH"
UNCOMPARABLE = "UNCOMPARABLE"


@dataclass
class FieldComparison:
    field: str
    verdict: str                     # MATCH | MISMATCH | UNCOMPARABLE
    si: FieldValue = field(default_factory=lambda: FieldValue(field=""))
    bl: FieldValue = field(default_factory=lambda: FieldValue(field=""))
    reason: Optional[str] = None     # why UNCOMPARABLE


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------
@dataclass
class CaseResult:
    """Everything the pipeline decided about one email."""

    email_id: str
    category: str
    # The inbox record's own "from" address. Carried through for the API/
    # dashboard layer only (a mailto: link, never an auto-send) -- never
    # read by anything under backend/sdoc/ itself, and not part of
    # to_submission()'s shape, so it cannot touch what the scorer sees.
    sender: str = ""
    category_confidence: float = 0.0
    decided_by: str = "rule"                 # rule | llm  (scorer reads this)
    category_rationale: list[str] = field(default_factory=list)

    status: str = "OK"                       # OK | MISMATCH | NEEDS_REVIEW
    review_reason: Optional[str] = None
    has_defect: bool = False
    defect_fields: list[str] = field(default_factory=list)

    comparisons: list[FieldComparison] = field(default_factory=list)
    si_doc: Optional[ParsedDoc] = None
    bl_doc: Optional[ParsedDoc] = None
    notes: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    duration_ms: float = 0.0
    llm_calls: int = 0

    # ---- output shapes ---------------------------------------------------
    def to_submission(self) -> dict[str, Any]:
        """The exact shape the official self-evaluation expects.

        `decided_by` is an extra key the organisers' scorer reads to report what
        fraction of the inbox was resolved by cheap rules instead of an LLM
        call — we emit it deliberately.
        """
        return {
            "category": self.category,
            "status": self.status,
            "review_reason": self.review_reason,
            "defect_fields": sorted(self.defect_fields),
            "has_defect": self.has_defect,
            "decided_by": self.decided_by,
        }

    def to_report(self) -> dict[str, Any]:
        """Rich record for the dashboard / audit trail."""
        return {
            "email_id": self.email_id,
            "sender": self.sender,
            "category": self.category,
            "category_confidence": round(self.category_confidence, 3),
            "decided_by": self.decided_by,
            "category_rationale": self.category_rationale,
            "status": self.status,
            "review_reason": self.review_reason,
            "has_defect": self.has_defect,
            "defect_fields": sorted(self.defect_fields),
            "fields": [
                {
                    "field": c.field,
                    "verdict": c.verdict,
                    "reason": c.reason,
                    "si": _fv(c.si),
                    "bl": _fv(c.bl),
                }
                for c in self.comparisons
            ],
            "documents": {"si": _doc(self.si_doc), "bl": _doc(self.bl_doc)},
            "notes": self.notes,
            "errors": self.errors,
            "duration_ms": round(self.duration_ms, 1),
            "llm_calls": self.llm_calls,
        }


def _fv(v: FieldValue) -> dict[str, Any]:
    return {
        "raw": v.raw,
        "normalised": v.normalised,
        "present": v.present,
        "blank": v.blank,
        "extractor": v.extractor,
        "evidence": _ev(v.evidence),
    }


def _ev(e: Optional[Evidence]) -> Optional[dict[str, str]]:
    if e is None:
        return None
    return {
        "doc": e.doc_role,
        "locator": e.locator,
        "label": e.label,
        "snippet": e.snippet,
    }


def _doc(d: Optional[ParsedDoc]) -> Optional[dict[str, Any]]:
    if d is None:
        return None
    return {
        "path": d.path,
        "ext": d.ext,
        "doc_type": d.doc_type,
        "readable": d.readable,
        "unreadable_reason": d.unreadable_reason,
        "n_bytes": d.n_bytes,
        "notes": d.notes,
    }
