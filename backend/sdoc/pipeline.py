"""The orchestrator: one email in, one decision out.

Everything here is sequencing and bookkeeping. The judgement lives in the
modules this calls — which is the point: each stage can be tested, replaced or
explained on its own, and this file stays readable enough that an operations
lead can follow what the system did to their email.

    read attachments -> what documents are these -> what is this email
                     -> extract -> compare -> evidence gate -> decide
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from . import compare as compare_mod
from . import doctype, evidence_gate
from .classify import llm as classify_llm
from .classify import intent as intent_mod
from .classify import rules as rules_mod
from .extract import fields as extract_mod
from .extract import llm as extract_llm
from .llm import LLMClient
from .readers import read_attachment
from .readers import scan as scan_mod
from .schema import (
    DOC_BL,
    DOC_SI,
    CaseResult,
    DocFields,
    EmailRecord,
    ParsedDoc,
)


@dataclass
class PipelineConfig:
    """Knobs the CLI and the API share."""

    data_root: Path
    # A shared client, so one budget and one cache cover the whole run. None
    # means the deterministic path only — which is a supported mode, not a
    # degraded one: every stage falls back to its rule answer or escalates.
    llm: Optional[LLMClient] = None


@dataclass
class PipelineStats:
    """Aggregates for the metrics page and the cost story."""

    emails: int = 0
    by_category: dict[str, int] = field(default_factory=dict)
    by_status: dict[str, int] = field(default_factory=dict)
    by_review_reason: dict[str, int] = field(default_factory=dict)
    decided_by_rule: int = 0
    decided_by_llm: int = 0
    documents_read: int = 0
    documents_unreadable: int = 0
    llm_calls: int = 0
    total_ms: float = 0.0

    def observe(self, result: CaseResult) -> None:
        self.emails += 1
        _bump(self.by_category, result.category)
        _bump(self.by_status, result.status)
        if result.review_reason:
            _bump(self.by_review_reason, result.review_reason)
        if result.decided_by == "llm":
            self.decided_by_llm += 1
        else:
            self.decided_by_rule += 1
        self.llm_calls += result.llm_calls
        self.total_ms += result.duration_ms
        for doc in (result.si_doc, result.bl_doc):
            if doc is not None:
                self.documents_read += 1
                if not doc.readable:
                    self.documents_unreadable += 1

    def to_dict(self) -> dict:
        rule_pct = self.decided_by_rule / self.emails if self.emails else 0.0
        return {
            "emails": self.emails,
            "by_category": dict(sorted(self.by_category.items())),
            "by_status": dict(sorted(self.by_status.items())),
            "by_review_reason": dict(sorted(self.by_review_reason.items())),
            "decided_by_rule": self.decided_by_rule,
            "decided_by_llm": self.decided_by_llm,
            "rule_share": round(rule_pct, 4),
            "documents_read": self.documents_read,
            "documents_unreadable": self.documents_unreadable,
            "llm_calls": self.llm_calls,
            "total_ms": round(self.total_ms, 1),
            "mean_ms_per_email": round(self.total_ms / self.emails, 2) if self.emails else 0.0,
        }


def _bump(counter: dict[str, int], key: str) -> None:
    counter[key] = counter.get(key, 0) + 1


class Pipeline:
    def __init__(self, config: PipelineConfig) -> None:
        self.config = config
        self.stats = PipelineStats()

    # -- the whole job, for one email ------------------------------------
    def process(self, email: EmailRecord) -> CaseResult:
        started = time.perf_counter()
        result = CaseResult(email_id=email.email_id, category="GENERAL")
        try:
            self._process(email, result)
        except Exception as exc:                    # never lose an email
            # A crash is a processing failure, not a clean pass. Surfacing it as
            # a review case keeps it visible and retryable instead of silently
            # reporting "no mismatch detected" on an email we never looked at.
            result.status = "NEEDS_REVIEW"
            result.review_reason = "unreadable"
            result.has_defect = False
            result.defect_fields = []
            result.errors.append(f"{type(exc).__name__}: {exc}")
            result.notes.append("Processing failed; case queued for retry.")
        result.duration_ms = (time.perf_counter() - started) * 1000
        self.stats.observe(result)
        return result

    # -- stages ----------------------------------------------------------
    def _process(self, email: EmailRecord, result: CaseResult) -> None:
        docs = self._read_documents(email, result)
        for doc in docs:
            doctype.classify_document(doc)

        doc_types = [d.doc_type for d in docs] or None
        classification = rules_mod.classify_email(email, attachment_doc_types=doc_types)

        # A second opinion only where the rules admit they are unsure. With no
        # client this is a no-op and the rule answer stands, still reported as
        # "rule" — so the cost figure never overstates what the model did.
        if self.config.llm is not None and classify_llm.should_escalate(classification):
            classification = classify_llm.classify_with_llm(
                email, classification, client=self.config.llm,
                attachment_doc_types=doc_types,
            )

        result.category = classification.category
        result.category_confidence = classification.confidence
        result.decided_by = classification.decided_by
        result.category_rationale = list(classification.rationale)

        # Everything that is not a document-check request only needs a label.
        if result.category != "BL_COMPARISON":
            result.status = "OK"
            return

        si_doc, bl_doc = self._assign_roles(docs, result)
        result.si_doc = si_doc
        result.bl_doc = bl_doc

        intent = intent_mod.detect_intent(email)
        result.notes.extend(intent.rationale)

        # Settle the document-type question before extraction, because it can
        # make the model fallback pointless. When the "BL" is really a
        # Commercial Invoice the case escalates whatever we read off it, so
        # paying a model to hunt for a port of discharge in an invoice buys
        # nothing. Rule extraction still runs and still gives the reviewer
        # whatever the document does contain.
        pair_problem = doctype.pair_problem(si_doc, bl_doc) if (si_doc and bl_doc) else None
        assisted = pair_problem is None

        si_fields = self._extract(si_doc, "SI", assisted=assisted)
        bl_fields = self._extract(bl_doc, "BL", assisted=assisted)

        comparisons: list = []
        if si_fields is not None and bl_fields is not None:
            comparisons = compare_mod.compare_documents(si_fields, bl_fields)
        result.comparisons = comparisons

        decision = evidence_gate.evaluate(
            si_doc=si_doc,
            bl_doc=bl_doc,
            si_fields=si_fields,
            bl_fields=bl_fields,
            comparisons=comparisons,
            intent=intent,
            pair_problem=pair_problem,
        )
        self._apply(decision, comparisons, result)

    def _read_documents(self, email: EmailRecord, result: CaseResult) -> list[ParsedDoc]:
        docs: list[ParsedDoc] = []
        for rel_path in email.attachments:
            doc = read_attachment(self.config.data_root, rel_path)
            if not doc.readable:
                result.notes.append(f"{rel_path}: {doc.unreadable_reason}")
                self._transcribe_scan(doc, rel_path)
            docs.append(doc)
        return docs

    def _transcribe_scan(self, doc: ParsedDoc, rel_path: str) -> None:
        """Read a scan for the reviewer — without letting it decide anything.

        A page with no text layer still escalates; that is the correct outcome
        and the transcript does not change it. What it changes is what the
        reviewer receives: the document already read, instead of a note saying
        it could not be. `scan.transcribe` deliberately does not write
        `doc.text`, so the transcript can never be traced by the evidence gate
        as if it were the document itself.
        """
        if self.config.llm is None or doc.unreadable_reason != "no_text_layer":
            return
        try:
            data = (Path(self.config.data_root) / rel_path).read_bytes()
        except OSError:
            return
        scan_mod.transcribe(doc, data, client=self.config.llm)

    def _extract(self, doc: Optional[ParsedDoc], role: str, *,
                 assisted: bool = True) -> Optional[DocFields]:
        """Rule extraction, then the model only for labels the rules missed.

        `assisted=False` turns the model off for this document because its
        outcome is already settled — see the caller. `fill_missing_fields`
        returns its input untouched when there is nothing missing, nobody to
        ask, or the model is unavailable, so a run with no key behaves exactly
        as it did before this layer existed.
        """
        if doc is None:
            return None
        fields = extract_mod.extract_fields(doc, role)
        if not assisted or self.config.llm is None:
            return fields
        return extract_llm.fill_missing_fields(doc, fields, role, client=self.config.llm)

    @staticmethod
    def _assign_roles(
        docs: list[ParsedDoc], result: CaseResult
    ) -> tuple[Optional[ParsedDoc], Optional[ParsedDoc]]:
        """Decide which attachment is the reference and which is under test.

        Content wins over filename. The filename is only a tie-breaker, because
        a file called "..._BL.pdf" that is really a Commercial Invoice is a case
        we are specifically meant to catch — trusting the name would hide it.
        An unreadable document has no detectable type, so there the hint is all
        we have left.
        """
        if not docs:
            return None, None

        si = next((d for d in docs if d.doc_type == DOC_SI), None)
        bl = next((d for d in docs if d.doc_type == DOC_BL and d is not si), None)

        remaining = [d for d in docs if d is not si and d is not bl]
        if si is None:
            si = next((d for d in remaining if d.role_hint == "SI"), None)
            remaining = [d for d in remaining if d is not si]
        if bl is None:
            bl = next((d for d in remaining if d.role_hint == "BL"), None)
            remaining = [d for d in remaining if d is not bl]

        # Still unassigned: fall back to document order, which matches how the
        # inbox lists them (SI first, then the draft BL).
        for doc in remaining:
            if si is None:
                si = doc
            elif bl is None:
                bl = doc

        if si is not None and bl is not None and si.doc_type == bl.doc_type:
            result.notes.append(
                f"Both attachments look like the same document type ({si.doc_type})."
            )
        return si, bl

    @staticmethod
    def _apply(decision, comparisons: list, result: CaseResult) -> None:
        """Turn a gate decision plus the comparison into the reported outcome."""
        result.notes.append(decision.reason)
        if decision.recovery:
            result.notes.append(f"Suggested action: {decision.recovery}")
        result.notes.extend(decision.blocked_signals)

        if decision.status in ("grounded", "no_comparison_needed"):
            defects = compare_mod.defect_fields(comparisons) if comparisons else []
            if defects:
                result.status = "MISMATCH"
                result.has_defect = True
                result.defect_fields = defects
            else:
                result.status = "OK"
                result.has_defect = False
                result.defect_fields = []
            return

        # The gate vetoed an automatic answer. Whatever the comparison thought,
        # this case goes to a person: a value we could not read is not a defect.
        result.status = "NEEDS_REVIEW"
        result.review_reason = decision.review_reason
        result.has_defect = False
        result.defect_fields = []


def build_client(enabled: bool = True) -> Optional[LLMClient]:
    """A shared client for a run, or None when the model layer is off.

    Returns None rather than an unusable client when no key is configured, so
    every `if self.config.llm is not None` reads as "is the fallback layer
    available" and the deterministic path is the plain, untouched default.
    """
    if not enabled:
        return None
    from .llm import load_dotenv_if_present

    load_dotenv_if_present()
    client = LLMClient()
    return client if client.available else None


def run_inbox(emails: list[EmailRecord],
              config: PipelineConfig) -> tuple[list[CaseResult], PipelineStats]:
    pipeline = Pipeline(config)
    return [pipeline.process(e) for e in emails], pipeline.stats
