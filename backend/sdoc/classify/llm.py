"""Stage 1 fallback — the classifier of last resort.

`classify/rules.py` scores a table of domain signals and sets `needs_llm` when
the winner is weak or the runner-up is close. This module is what consumes that
flag: it asks a model the same question a human triager would be asked, and
returns a `Classification` carrying `decided_by="llm"`.

Four decisions shape this file.

**The model is asked a triage question, not handed an email dump.** What goes
into the prompt is what a person on a documentation desk would actually look
at: who sent it, the subject line, the sender's own words with the forwarded
thread and the signature block removed, and whether documents came with it and
what they turned out to be. The forwarded tail below a one-line invoice query is
frequently a document-comparison request from last week — it is precisely the
thing that misleads a reader, human or otherwise, so `rules.clean_body`'s
definition of boilerplate is reused rather than re-invented here.

**The five categories are spelled out in business terms.** A model that has
never worked a shipping desk does not know that "please send the draft BL" is a
document request rather than small talk, that a *list* of outstanding BLs is a
circular and not a comparison, or that a blanket "submit SI for all pending
shipments" is a standing reminder to the team. Those three confusions are the
ones `docs/DATA_NOTES.md` §6 names, and they are stated in the instructions.

**The answer shape is closed, not open.** The category is a `Literal` of the
five exact strings. Asked without that constraint a model happily returns
"Documentation/BL Review", which is a plausible-looking label that no downstream
stage can act on and no scorer recognises. The SDK validates the shape, so this
module never parses text.

**Unavailable is a normal answer.** No key, no network, a refusal, a spent
budget, or a cache entry from an older schema all end the same way: the rule
classification is returned untouched, still marked `decided_by="rule"`, with a
note saying the second opinion could not be obtained. The inbox is fully
classified either way — that is the whole reason the rules go first.
"""
from __future__ import annotations

import re
from dataclasses import replace
from typing import Literal, Optional, get_args

from pydantic import BaseModel

from ..llm import LLMClient, LLMUnavailable
from ..schema import CATEGORIES, EmailRecord
from .rules import (
    Classification,
    clean_subject,
    is_empty,
    # The one definition of "this is boilerplate, not the ask". Copying these
    # patterns into this module would let the two drift, and then the model
    # would be reading a different email than the rules scored — which makes
    # the audit trail ("the rules thought X, the model thought Y") a lie.
    _BANNER_RE,
    _QUOTE_START_RE,
    _SIGNOFF_RE,
)

# --------------------------------------------------------------------------
# The closed answer shape
# --------------------------------------------------------------------------
CategoryName = Literal[
    "BL_COMPARISON",
    "SI_REQUEST",
    "INVOICE_QUERY",
    "GENERAL",
    "SPAM",
]

# Spelled out above because a Literal needs static members, and checked here
# because a silent divergence from `schema.CATEGORIES` would mean the model is
# allowed to return a category the rest of the pipeline cannot handle. Raised
# rather than asserted so it survives `python -O`.
if get_args(CategoryName) != CATEGORIES:        # pragma: no cover - guards an edit
    raise RuntimeError(
        "classify.llm.CategoryName has drifted from schema.CATEGORIES: "
        f"{get_args(CategoryName)} != {CATEGORIES}"
    )


class CategoryVerdict(BaseModel):
    """What the model is allowed to say.

    No `Field(ge=..., le=...)` on `confidence` on purpose: numeric bounds are
    not part of the strict structured-output subset, so a bounded schema is
    rejected by the provider before the model ever sees it. The value is
    clamped on arrival instead (`_clamp`), which is where an out-of-range
    answer would have to be handled anyway.
    """

    category: CategoryName
    reason: str
    confidence: float


# --------------------------------------------------------------------------
# When to spend a call
# --------------------------------------------------------------------------
# Matches `pipeline.PipelineConfig.classification_confidence_floor`. Kept as a
# constant here rather than imported, because `classify` must not depend on the
# orchestrator (docs/ARCHITECTURE.md §3: the dependency direction is one-way).
CONFIDENCE_FLOOR = 0.45

# How much of the sender's own text the model sees. The ask lives in the first
# paragraph or two; past that a shipping email is addresses and reference
# numbers, which cost input tokens and decide nothing.
MAX_BODY_CHARS = 1200

# A justification longer than this is not a justification. Truncated rather
# than rejected: the category is the answer, the sentence is the audit trail.
MAX_REASON_CHARS = 300

# A fallback answer on a case that was ambiguous by construction is not a
# certainty, whatever the model says about itself. The review queue is sorted
# by confidence, and an LLM-decided email must not outrank an email the rules
# settled cleanly.
MAX_LLM_CONFIDENCE = 0.9

_WHITESPACE_RUN = re.compile(r"\n{3,}")

# --------------------------------------------------------------------------
# Quoted-thread markers this module cuts on *in addition* to `rules`'.
#
# `rules._QUOTE_START_RE` cuts on the horizontal rule that Outlook writes above
# a forwarded header, which is how all 195 threaded emails in this inbox are
# shaped. A client that omits the rule line — or writes
# "-----Original Message-----" instead — leaks the whole thread past it.
#
# Stage 1 survives that, because the tail is scored on the low-weight `body`
# view and the ask still outweighs it. A prompt does not: the model is handed
# one blob, and last week's "please compare the SI and draft BL" sitting under
# today's one-line invoice query is the single most effective way to get a
# wrong category back. So the prompt cuts earlier than the scorer does, which
# is the right asymmetry — losing a paragraph of context costs a little,
# quoting someone else's request costs the answer.
# --------------------------------------------------------------------------
_FORWARDED_TAIL_RE = re.compile(
    # "-----Original Message-----", "---------- Forwarded message ----------"
    r"^[ \t]*-{2,}[ \t]*(?:Original Message|Forwarded message)\b"
    # A mail header block: "From: ..." with a second header within three lines.
    # Two headers are demanded because one "Subject:" line on its own is prose,
    # and because an SI form block in the body is full of single labelled lines.
    r"|^[ \t]*From[ \t]*:[ \t]*\S[^\n]*\n(?:[^\n]*\n){0,2}?"
    r"[ \t]*(?:Sent|Date|To|Cc|Subject)[ \t]*:[ \t]*\S"
    # Two consecutive ">"-quoted lines: the plain-text client's forwarded tail.
    r"|^[ \t]*>[^\n]*\n[ \t]*>",
    re.I | re.M,
)


def should_escalate(rule_result: Classification) -> bool:
    """Is this a case worth a second opinion?

    Three conditions, in the order they matter:

    * `needs_llm` — the rule layer's own verdict: the winning score was below
      `rules.MIN_SCORE`, the margin below `rules.MIN_MARGIN`, or nothing fired
      at all. This is the flag the module exists to consume.
    * `confidence < CONFIDENCE_FLOOR` — the case that clears both thresholds by
      a hair. `rules._confidence` mixes score and margin, so a winner on 3.5
      points with a margin of 1.6 passes both floors and still scores 0.42: two
      thin signals, neither of which is wrong on its own, which together are
      not a decision. `needs_llm` cannot see that combination; this can.
    * already decided by a model — do not pay twice for the same answer, and do
      not let a re-run of the pipeline turn one call into two.
    """
    if rule_result.decided_by == "llm":
        return False
    return bool(rule_result.needs_llm) or rule_result.confidence < CONFIDENCE_FLOOR


# --------------------------------------------------------------------------
# What the model is shown
# --------------------------------------------------------------------------
def visible_body(body: str) -> str:
    """The sender's own words, in their original case.

    `rules.clean_body` does the same three removals — the mail gateway's
    "external sender" banner, the forwarded/quoted tail, the signature block —
    but upper-cases its output so the rule patterns can be written the way a
    subject line reads. A prompt wants the original casing back: proper nouns,
    carrier acronyms and a SHOUTED phishing line all carry signal that
    upper-casing destroys.

    Removes at least what `clean_body` removes, and cuts on the forwarded-tail
    shapes `_FORWARDED_TAIL_RE` adds on top.
    """
    text = _BANNER_RE.sub("", body or "", count=1)
    cut = len(text)
    for pattern in (_QUOTE_START_RE, _FORWARDED_TAIL_RE):
        m = pattern.search(text)
        if m:
            cut = min(cut, m.start())
    text = text[:cut]
    m = _SIGNOFF_RE.search(text)
    if m:
        text = text[: m.start()]
    text = _WHITESPACE_RUN.sub("\n\n", text).strip()
    if len(text) > MAX_BODY_CHARS:
        # Cut on a line boundary so the model is not handed half a sentence.
        cut = text.rfind("\n", 0, MAX_BODY_CHARS)
        text = text[: cut if cut > MAX_BODY_CHARS // 2 else MAX_BODY_CHARS].rstrip()
        text += "\n[...truncated]"
    return text


def _attachment_line(email: EmailRecord,
                     attachment_doc_types: Optional[list[str]]) -> str:
    """What came with the email, as evidence rather than as a filename.

    Deliberately no filenames: `_BL.pdf` is exactly the hint the pipeline
    distrusts (a file named for a bill of lading that is really a commercial
    invoice is a case we are meant to catch), and a model shown the name will
    believe it. The detected type is a read of the content, so it is the
    honest signal.
    """
    n = len(email.attachments or [])
    if n == 0:
        return "Attachments: none"
    kinds = [str(t) for t in (attachment_doc_types or []) if t]
    if not kinds:
        return f"Attachments: {n} (document type not determined)"
    return f"Attachments: {n}, detected as {', '.join(kinds)}"


def _contest_line(rule_result: Optional[Classification]) -> str:
    """Name the categories the rules could not separate — never the winner.

    Telling the model which side the rules leaned towards would turn an
    independent second opinion into an agreement machine, and agreement is
    worth nothing on a case that was escalated precisely because the rules were
    not sure. Naming the *contest* focuses the question without answering it.
    """
    if rule_result is None or not rule_result.scores:
        return ""
    contested = sorted(
        (name for name, score in rule_result.scores.items() if score > 0),
        key=lambda name: -rule_result.scores[name],
    )[:2]
    if len(contested) < 2:
        return ""
    return ("Automated triage found evidence for two of these and could not "
            f"separate them: {contested[0]} and {contested[1]}.")


def build_prompt(
    email: EmailRecord,
    *,
    rule_result: Optional[Classification] = None,
    attachment_doc_types: Optional[list[str]] = None,
) -> str:
    """The case, as a triager would see it on screen."""
    parts = [
        f"Sender: {(email.sender or '').strip() or '(unknown)'}",
        f"Subject: {clean_subject(email.subject or '') or '(no subject)'}",
        _attachment_line(email, attachment_doc_types),
        "",
        "Body (forwarded thread, signature block and gateway banner removed):",
        "---",
        visible_body(email.body or "") or "(empty)",
        "---",
    ]
    contest = _contest_line(rule_result)
    if contest:
        parts += ["", contest]
    return "\n".join(parts)


INSTRUCTIONS = (
    "You are a documentation clerk on an ocean-freight export desk. File one "
    "incoming email into exactly one of five categories. Decide only from the "
    "email in front of you.\n"
    "\n"
    "BL_COMPARISON - about the draft Bill of Lading for ONE shipment: check a "
    "draft BL against the Shipping Instruction, amend a draft, or produce and "
    "send one. 'Please assist to send the draft BL for checking' is "
    "BL_COMPARISON even with nothing attached.\n"
    "SI_REQUEST - a Shipping Instruction for ONE shipment is being supplied to "
    "us or asked for. These bodies are often a form (POL:, POD:, Shipper:, "
    "Consignee:, Gross Wt:) and usually close with 'please revert with draft "
    "BL once available' - that closing line does NOT make it BL_COMPARISON.\n"
    "INVOICE_QUERY - money: invoices, freight amounts, local or terminal "
    "charges, detention and demurrage, telex-release fees, missing goods "
    "receipts, payment and billing blocks.\n"
    "GENERAL - desk traffic that is neither one shipment's documents nor "
    "money: circulars and daily reports, a LIST of outstanding or pending BLs, "
    "automated or RPA notices, HR and office announcements, and standing "
    "reminders addressed to the whole team (a blanket 'submit SI for all "
    "pending shipments' is GENERAL, not SI_REQUEST).\n"
    "SPAM - unsolicited bait or fraud: prize and lottery claims, parcel-fee "
    "scams, mailbox or credential phishing, crypto and advance-fee offers, "
    "cold marketing blasts.\n"
    "\n"
    "The word 'BL' alone decides nothing: one shipment's draft is "
    "BL_COMPARISON, a list of many BLs is GENERAL. Pick the category that "
    "describes what the sender wants done. Give one sentence quoting the words "
    "that decided it, and a confidence between 0 and 1."
)


# --------------------------------------------------------------------------
# The fallback itself
# --------------------------------------------------------------------------
def _clamp(value: object) -> float:
    try:
        n = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0
    if n != n:                                  # NaN
        return 0.0
    return max(0.0, min(MAX_LLM_CONFIDENCE, n))


def _unchanged(rule_result: Classification, note: str) -> Classification:
    """The rule answer, kept whole, with the failure recorded against it.

    `decided_by` stays "rule" because that is the truth: no model contributed
    to this category, and the cost breakdown the organisers' scorer reads must
    not claim otherwise.
    """
    return replace(
        rule_result,
        decided_by="rule",
        rationale=list(rule_result.rationale) + [note],
    )


def _resolve_client(client: Optional[LLMClient]) -> Optional[LLMClient]:
    """Use the caller's client, or build a default one for standalone use.

    A default client is built so this function works from a notebook or a unit
    test without ceremony; the pipeline passes its own so that usage and cost
    accumulate in one place. Construction itself can fail (an unpriced model in
    the environment), and that is just another flavour of unavailable.
    """
    if client is not None:
        return client
    try:
        return LLMClient()
    except Exception:                           # pragma: no cover - env-dependent
        return None


def classify_with_llm(
    email: EmailRecord,
    rule_result: Classification,
    *,
    client: Optional[LLMClient] = None,
    attachment_doc_types: Optional[list[str]] = None,
) -> Classification:
    """Ask a model to settle a case the rules could not, or keep the rule answer.

    Returns a `Classification` with `decided_by="llm"` when a model answered,
    and the original `rule_result` (still `decided_by="rule"`) when it could
    not. Never raises: every failure mode of the model layer is a reason to
    keep the deterministic answer, not a reason to lose the email.
    """
    # An email with neither a subject nor a body gives a model nothing to read,
    # so a call on it buys a guess at full price. `rules.is_empty` is reused
    # because it is the project's one definition of "present but says nothing":
    # a subject of `???` counts as empty here exactly as a document field does.
    if is_empty(email):
        return _unchanged(rule_result, "llm.skipped:empty-email")

    resolved = _resolve_client(client)
    if resolved is None or not resolved.available:
        # Checked before building the prompt: with no key configured this is
        # the path every email takes, and it must cost nothing at all.
        return _unchanged(rule_result, "llm.unavailable:no-client")

    prompt = build_prompt(
        email,
        rule_result=rule_result,
        attachment_doc_types=attachment_doc_types,
    )

    try:
        verdict = resolved.structured(
            purpose="classify",
            instructions=INSTRUCTIONS,
            prompt=prompt,
            schema=CategoryVerdict,
            # Triage, not analysis: the answer is one of five labels and the
            # evidence is a phrase in the subject line. Measured at ~89 output
            # tokens against ~437 unset, for the same answers on this inbox.
            reasoning_effort="minimal",
        )
    except LLMUnavailable as exc:
        # No key, no network, a refusal, or the run budget spent. All of them
        # mean the same thing to this caller.
        return _unchanged(rule_result, f"llm.unavailable:{_short(exc)}")
    except Exception as exc:
        # Nothing should reach here — the client funnels provider failures into
        # LLMUnavailable — but a stale cache entry written against an older
        # answer schema validates outside that funnel. One malformed answer
        # must cost one second opinion, not the run.
        return _unchanged(rule_result, f"llm.error:{type(exc).__name__}")

    category = getattr(verdict, "category", None)
    if category not in CATEGORIES:
        # Unreachable through `CategoryVerdict`, which is the point of the
        # Literal. Kept because a future edit that widens the schema would
        # otherwise put an unhandled label into `submission.json`.
        return _unchanged(rule_result, f"llm.rejected:unknown-category:{category}")

    reason = " ".join(str(getattr(verdict, "reason", "") or "").split())[:MAX_REASON_CHARS]
    agreement = ("llm.agreed" if category == rule_result.category
                 else f"llm.overrode:{rule_result.category}")

    return replace(
        rule_result,
        category=category,
        confidence=_clamp(getattr(verdict, "confidence", 0.0)),
        decided_by="llm",
        # `margin` and `scores` are the rule layer's own scoreboard and are kept
        # verbatim: they are the record of *why* this case was escalated, and
        # overwriting them would erase the reason the model was asked at all.
        rationale=list(rule_result.rationale) + [
            f"llm.rule_said:{rule_result.category}",
            f"llm.category:{category}",
            agreement,
            f"llm.reason:{reason}" if reason else "llm.reason:(none given)",
        ],
        needs_llm=False,
    )


def _short(exc: BaseException, limit: int = 80) -> str:
    """A one-line cause for the audit trail, never the provider's full trace."""
    text = " ".join(str(exc).split())
    return (text[:limit] + "...") if len(text) > limit else (text or type(exc).__name__)


__all__ = [
    "CategoryName",
    "CategoryVerdict",
    "CONFIDENCE_FLOOR",
    "INSTRUCTIONS",
    "MAX_LLM_CONFIDENCE",
    "build_prompt",
    "classify_with_llm",
    "should_escalate",
    "visible_body",
]
