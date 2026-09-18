"""Stage 2 helper — does the sender believe they attached the documents?

Why this module exists (docs/DATA_NOTES.md §5a)
-----------------------------------------------
Two emails in the inbox are both BL_COMPARISON, both carry **zero**
attachments, and have opposite correct outcomes:

    A. "Please assist to send the draft BL for MSDUL0942535439 for checking
        asap."
       -> the sender is asking US to produce a draft. There is nothing to
          compare and nothing has gone wrong. Status OK.

    B. "Please compare the SI and draft BL for MSDUL0942535439 and confirm
        (attachments appear to have been dropped)."
       -> the sender believes they attached two documents. They did not
          arrive. We cannot compare. NEEDS_REVIEW / missing_attachment.

`len(email.attachments) == 0` is true for both, so the attachment count cannot
separate them. The distinguishing fact is the direction of the request:

    "send me X"      -> we are the producer; nothing is expected in the mail
    "check X and Y"  -> we are the reviewer; two documents were expected

So we score two independent intents and compare them.

Bias, stated explicitly
-----------------------
Ambiguity resolves to `expects_attached_documents = False`. Escalating a
routine "please send me a draft" email puts an item in a human's queue that a
human can do nothing with, and every such item costs escalation precision.
A missed escalation on a genuinely ambiguous email costs recall on one case;
a stream of false escalations costs the operator's trust in the queue.

Deterministic, no network, no per-email special cases.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field as dc_field

from ..schema import EmailRecord
from .rules import body_head, clean_body, clean_subject

# A single strong phrase is worth ~3; the thresholds sit below one strong
# phrase so that one unambiguous sentence is enough to decide.
ATTACH_MIN = 1.5
DRAFT_MIN = 1.5

# Score at which an intent is considered fully evidenced (confidence scale).
FULL_SIGNAL_SCORE = 5.0


@dataclass(frozen=True)
class Signal:
    """One readable phrase-level piece of evidence for one intent."""

    name: str
    weight: float
    pattern: re.Pattern[str]
    why: str = ""
    field: str = "body"  # body | subject

    def score(self, body: str, subject: str) -> float:
        target = subject if self.field == "subject" else body
        return self.weight if target and self.pattern.search(target) else 0.0


def _s(name, weight, pattern, why, field="body"):
    return Signal(name=name, weight=weight, pattern=re.compile(pattern, re.M),
                  why=why, field=field)


# --------------------------------------------------------------------------
# "I attached documents" — the sender is the supplier, we are the reviewer.
# Patterns run against UPPER-CASED text (see rules.clean_body).
# --------------------------------------------------------------------------
ATTACHED_SIGNALS: list[Signal] = [
    _s("attach.attachments-dropped", 3.5,
       r"\bATTACHMENTS?\b[^.]{0,40}\b(?:DROPPED|MISSING|NOT COME THROUGH|DID NOT COME"
       r"|FAILED TO ATTACH|STRIPPED)\b",
       "'(attachments appear to have been dropped)' — the sender is telling us the documents "
       "SHOULD be here. This is the whole of case B, and the reason intent beats counting."),
    _s("attach.document-still-missing", 3.0,
       r"\b(?:DRAFT B/?L|B/?L|SI|SHIPPING INSTRUCTION|DOCUMENTS?|ATTACHMENTS?)\b[^.]{0,25}"
       r"\b(?:IS|ARE)? ?STILL MISSING\b",
       "'the draft BL is still missing' — the sender expects a document that is not here."),
    _s("attach.please-find-attached", 3.0,
       r"\b(?:PLEASE|KINDLY)\s+FIND\s+(?:ATTACHED|THE ATTACHED)\b[^.]{0,70}"
       r"\b(?:SI|SHIPPING INSTRUCTION|DRAFT B/?L|BILL OF LADING|PACKING LIST"
       r"|COMMERCIAL INVOICE|CERTIFICATE OF ORIGIN|DOCUMENTS?)\b",
       "'Please find attached the shipping instruction and the draft bill of lading ...'. "
       "The document noun is required: a GENERAL circular also says 'Please find attached the "
       "list of outstanding BL', and that is a spreadsheet, not a bill of lading."),
    _s("attach.attached-are", 3.0,
       r"\bATTACHED\s+(?:ARE|IS|HEREWITH|HERETO)\b",
       "'Attached are the SI and draft BL for OC 5RSG-00133 ...'"),
    _s("attach.attached-documents", 3.0,
       r"\bATTACHED\s+(?:THE\s+)?(?:SI\b|SHIPPING INSTRUCTION|DRAFT B/?L|BILL OF LADING)",
       "'Attached SI and draft BL for ... for checking (the BL file will not open).' — the "
       "documents are claimed even when one of them cannot be opened."),
    _s("attach.please-compare", 2.5,
       r"\b(?:PLEASE|PLS|KINDLY)\s+COMPARE\b",
       "You can only ask someone to compare two things you believe they have. This is what "
       "separates case B's 'please compare' from case A's 'assist to send'."),
    _s("attach.check-against", 2.0,
       r"\bCHECK\b[^.]{0,40}\bAGAINST\b",
       "'check the draft BL against the SI' — a two-document operation."),
    _s("attach.verify-matches", 2.0,
       r"\bVERIFY\b[^.]{0,25}\bMATCHES\b",
       "'Kindly verify the BL matches the SI'."),
    _s("attach.confirm-in-order", 2.0,
       r"\bCONFIRM\b[^.]{0,25}\bB/?L\b[^.]{0,20}\bIN ORDER\b",
       "'Kindly confirm the BL is in order' — we are asked to inspect, so something was sent."),
    _s("attach.enclosed", 1.5,
       r"\bENCLOSED\b|\bAS ATTACHED\b|\bIN THE ATTACHMENT\b",
       "Weaker wordings of the same claim."),
]

# --------------------------------------------------------------------------
# "Please make me a draft" — we are the producer, nothing is expected inbound.
# --------------------------------------------------------------------------
DRAFT_SIGNALS: list[Signal] = [
    _s("draft.assist-to-send", 3.5,
       r"\b(?:ASSIST|HELP)\b[^.]{0,20}\b(?:SEND|ISSUE|PREPARE|PROVIDE|RELEASE|SHARE)\b"
       r"[^.]{0,25}\bDRAFT\b",
       "'Please assist to send the draft BL for <booking> for checking asap.' — case A. Note "
       "the verb: 'assist to CHECK the draft BL against the SI' is the opposite request and "
       "deliberately does not match."),
    _s("draft.please-send-draft", 3.0,
       r"\b(?:PLEASE|PLS|KINDLY)\s+(?:SEND|ISSUE|PREPARE|PROVIDE|SHARE|FORWARD|RAISE)\b"
       r"[^.]{0,25}\bDRAFT B/?L\b",
       "Direct request for us to produce the draft."),
    _s("draft.revert-once-available", 3.0,
       r"\bREVERT WITH\b[^.]{0,20}\bDRAFT B/?L\b[^.]{0,25}\bONCE AVAILABLE\b",
       "The closing line of every SI_REQUEST body. It asks us to produce a draft LATER, so it "
       "must never be read as 'documents are attached'."),
    _s("draft.awaiting-draft", 2.0,
       r"\b(?:AWAIT(?:ING)?|PENDING|CHASING)\b[^.]{0,25}\bDRAFT B/?L\b"
       r"|\bDRAFT B/?L\b[^.]{0,20}\b(?:NOT YET (?:ISSUED|READY)|ONCE READY)\b",
       "The draft does not exist yet, so nothing can have been attached."),
    _s("draft.subject-request-bl-draft", 1.0,
       r"^REQUEST B/?L DRAFT(?![A-Z])",
       "Subject only, and deliberately weak: 'REQUEST BL DRAFT _ PO 26067' is also used as a "
       "thread title for mails that DO carry the finished pair, so the body's ask outranks it.",
       "subject"),
]


@dataclass(frozen=True)
class Intent:
    expects_attached_documents: bool
    requests_draft: bool
    confidence: float
    rationale: list[str] = dc_field(default_factory=list)


def _tally(signals: list[Signal], body: str, subject: str) -> tuple[float, list[tuple[float, str]]]:
    total = 0.0
    fired: list[tuple[float, str]] = []
    for sig in signals:
        gained = sig.score(body, subject)
        if gained:
            total += gained
            fired.append((gained, sig.name))
    return total, fired


def _merge_tail(
    signals: list[Signal],
    head_score: float,
    head_fired: list[tuple[float, str]],
    body: str,
    subject: str,
) -> tuple[float, list[tuple[float, str]]]:
    """Fold in signals that appear outside the first paragraph, at half weight.

    The ask belongs in the opening paragraph, but it is not guaranteed to be
    there — an SI_REQUEST, for instance, closes with "Please revert with draft
    BL once available" pages below its opening line. Half weight keeps a
    late-paragraph claim from outvoting the sentence the sender actually led
    with.
    """
    known = {name for _, name in head_fired}
    _, tail_fired = _tally(signals, body, subject)
    extra = [(0.5 * w, name) for w, name in tail_fired if name not in known]
    return head_score + sum(w for w, _ in extra), head_fired + extra


def _confidence(lead: float, second: float) -> float:
    """How much evidence, and how one-sided.

    Both halves are needed: a body that shouts both intents at once is not
    confident however loud it is, and a single weak phrase is not confident
    however lonely it is.
    """
    if lead <= 0.0:
        return 0.0
    strength = min(1.0, lead / FULL_SIGNAL_SCORE)
    separation = (lead - second) / lead
    return round(0.5 * strength + 0.5 * separation, 4)


def detect_intent(email: EmailRecord) -> Intent:
    """Decide whether the sender believes documents are attached.

    Reads the sender's own words only: `rules.clean_body` has already removed
    the external-sender banner, the forwarded thread and the signature block,
    all three of which carry shipping vocabulary from other conversations.

    Never raises on an empty subject or an empty body — an email that says
    nothing expects nothing.
    """
    subject = clean_subject(email.subject or "")
    body = clean_body(email.body or "")
    # The ask lives in the first paragraph; a later "(Note: the second
    # attachment is a Commercial Invoice)" is commentary, not the request.
    # Scoring the head first and falling back to the whole body keeps a
    # two-paragraph email and a one-paragraph email on the same footing.
    head = body_head(body) or body

    attach_score, attach_fired = _tally(ATTACHED_SIGNALS, head, subject)
    draft_score, draft_fired = _tally(DRAFT_SIGNALS, head, subject)

    if head != body:
        # A claim made anywhere in the message still counts, at half weight:
        # the head is where the ask belongs, not where it is guaranteed to be.
        tail_attach, tail_fired = _tally(ATTACHED_SIGNALS, body, subject)
        if tail_attach > attach_score:
            attach_score = attach_score + 0.5 * (tail_attach - attach_score)
            known = {n for _, n in attach_fired}
            attach_fired += [(w * 0.5, n) for w, n in tail_fired if n not in known]

    expects = attach_score >= ATTACH_MIN and attach_score > draft_score
    requests = draft_score >= DRAFT_MIN and draft_score >= attach_score

    rationale = [n for _, n in sorted(attach_fired + draft_fired, key=lambda x: -x[0])]
    if not rationale:
        # No signal at all. Both flags stay False, which is the safe default:
        # we do not escalate an email that never claimed to carry anything.
        rationale = ["intent.no-signal"]

    lead = max(attach_score, draft_score)
    second = min(attach_score, draft_score)
    return Intent(
        expects_attached_documents=expects,
        requests_draft=requests,
        confidence=_confidence(lead, second),
        rationale=rationale,
    )


def explain(email: EmailRecord) -> list[tuple[str, str, float]]:
    """(intent, signal name, score) for every signal that fired — for the UI."""
    subject = clean_subject(email.subject or "")
    body = clean_body(email.body or "")
    head = body_head(body) or body
    out: list[tuple[str, str, float]] = []
    for kind, table in (("expects_attached", ATTACHED_SIGNALS), ("requests_draft", DRAFT_SIGNALS)):
        for sig in table:
            gained = sig.score(head, subject) or sig.score(body, subject)
            if gained:
                out.append((kind, sig.name, gained))
    return sorted(out, key=lambda t: -t[2])


SIGNALS: dict[str, list[Signal]] = {
    "expects_attached_documents": ATTACHED_SIGNALS,
    "requests_draft": DRAFT_SIGNALS,
}

__all__ = [
    "Intent",
    "detect_intent",
    "explain",
    "ATTACHED_SIGNALS",
    "DRAFT_SIGNALS",
    "SIGNALS",
    "Signal",
    "ATTACH_MIN",
    "DRAFT_MIN",
]
