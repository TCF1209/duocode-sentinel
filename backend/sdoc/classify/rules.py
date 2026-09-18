"""Stage 1 — the five-way email classifier, as a table an operator can read.

Why a scored table instead of an if/elif cascade
------------------------------------------------
An operations inbox drifts: a desk is renamed, a carrier changes its subject
template, a new phishing wave arrives. When that happens someone who is not
the author has to retune the classifier. A cascade forces them to reason about
the order of twenty branches; a table lets them read one line, see what it
costs, and change a number. So every signal here is one `Rule` — a pattern, a
field, a weight and a name — and the only logic is "sum per category, take the
winner". `RULES` is exported for exactly that reason: the UI renders it.

How the scoring is arranged
---------------------------
* Category scores are summed independently; nothing vetoes anything. A rule
  that fires is evidence, never a switch, so an unusual email still lands
  somewhere sensible instead of falling off a branch.
* The *subject* and the *first paragraph* carry the real ask. Everything after
  them — the forwarded thread, the "external sender" banner, the signature
  block with a phone number — is boilerplate that repeats across every
  category, so it is stripped before scoring (see `_clean_body`) and what
  survives is scored at a lower weight than `body_head`.
* Ties break towards the *smallest* class. Stage 1 is graded with macro-F1, so
  one SPAM error (40 emails in the set) costs as much as five BL_COMPARISON
  errors (220). A coin-flip should therefore land on the class that can least
  afford the loss.

The confusions the weights are tuned against are all real emails in the set and
all listed in `docs/DATA_NOTES.md` §6:

    "_Reminder_Paper - Submit SI & AED_18-01-2026"   GENERAL, not SI_REQUEST
    "APRIL PAPER - List of Outstanding BL (BDP SG)"  GENERAL, not BL_COMPARISON
    "Pending BL Release 12_01_2026"                  GENERAL, not BL_COMPARISON
    "... Please revert with draft BL once available"  SI_REQUEST, not BL_COMPARISON
    "SI - <blno> - DIRECT(MSC) - ..."                SI_REQUEST
    "AIE - <port> - MSC(<blno>) - ..."               BL_COMPARISON

Note on reuse: `normalize.py` canonicalises *document values* and would destroy
the punctuation that carries the signal in prose (`POL:`, `D & D`, `90% OFF`),
so it is not applied to email text. `labels.py` however is reused directly and
deliberately — the structured block inside an SI_REQUEST body is made of the
same field labels a document uses, so `labels.resolve()` recognises it, and a
new wording added to `labels.SYNONYMS` improves this classifier for free.

No network, no API key, no per-email special cases.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field as dc_field
from typing import Callable, Optional

from .. import labels
from ..normalize import is_blank
from ..schema import CATEGORIES, EmailRecord

BL = "BL_COMPARISON"
SI = "SI_REQUEST"
INV = "INVOICE_QUERY"
GEN = "GENERAL"
SPAM = "SPAM"

# Ties break towards the smallest class: macro-F1 weights every category
# equally, so an error on SPAM (40 emails) costs 5.5x an error on
# BL_COMPARISON (220). Lower index wins a tie.
TIE_BREAK_ORDER: tuple[str, ...] = (SPAM, GEN, INV, SI, BL)

# A winner below this score, or a margin below this, is not a decision — it is
# a guess, and the LLM layer is asked to look at it instead.
MIN_SCORE = 3.0
MIN_MARGIN = 1.5

# Score / margin at which we call ourselves fully confident. Above these the
# confidence term saturates; they are the scale, not a threshold.
FULL_SCORE = 8.0
FULL_MARGIN = 4.0

# Attachments are extra evidence, never an override — see `classify_email`.
ATTACHMENT_PAIR_WEIGHT = 3.0
ATTACHMENT_SINGLE_WEIGHT = 1.5


# --------------------------------------------------------------------------
# Text preparation
#
# Every body in this inbox is the same three layers: the real message, then a
# signature block, then a forwarded thread. All three contain shipping
# vocabulary, but only the first one says what the sender wants. Scoring the
# whole blob makes a one-line invoice query look like a document-comparison
# request, because the quoted tail below it is a document-comparison request.
# --------------------------------------------------------------------------
_REPLY_PREFIX_RE = re.compile(r"^\s*(?:RE|FW|FWD|AW|TR)\s*[:_\-]+\s*", re.I)

# "WARNING: This email originated outside of our organisation. ..." — a banner
# the mail gateway prepends. It is on external mail of every category.
_BANNER_RE = re.compile(r"^\s*(?:WARNING|CAUTION|\[?EXTERNAL\]?)\b[^\n]*\n?", re.I)

# Start of a quoted / forwarded tail: a rule line, a mail header block, or the
# "On <date> X wrote:" form.
_QUOTE_START_RE = re.compile(
    r"^(?:\s*[_\-=]{5,}\s*"
    r"|\s*From\s*:\s*\S"
    r"|\s*Sent\s*:\s*\S"
    r"|\s*-{2,}\s*Original Message"
    r"|\s*On\b.{0,80}\bwrote\s*:\s*)$",
    re.I | re.M,
)

# A sign-off on a line of its own ends the message and starts the signature.
# Anchored to the whole line on purpose: "... Please advise. Thank you." is
# part of the ask, "Thank you." alone is the start of the boilerplate.
_SIGNOFF_RE = re.compile(
    r"^\s*(?:BEST\s+REGARDS|KIND\s+REGARDS|WARM\s+REGARDS|BEST\s+WISHES|REGARDS"
    r"|BEST|THANKS|THANK\s+YOU|SINCERELY|CHEERS|YOURS\s+\w+)\s*[,.!]?\s*$",
    re.I | re.M,
)

_SALUTATION_RE = re.compile(r"^(?:HI|HELLO|HEY|DEAR|GOOD\s+(?:MORNING|AFTERNOON|DAY))\b")


def clean_subject(subject: str) -> str:
    """Subject with reply/forward prefixes removed, upper-cased.

    `RE_ AIE - JEBEL_ALI - ...` and `AIE - JEBEL_ALI - ...` are the same desk
    line; the prefix only records that somebody hit reply.
    """
    s = subject or ""
    for _ in range(4):  # "RE_ FW_ RE: ..." happens on long threads
        stripped = _REPLY_PREFIX_RE.sub("", s, count=1)
        if stripped == s:
            break
        s = stripped
    return " ".join(s.split()).upper()


def clean_body(body: str) -> str:
    """The sender's own words: banner, forwarded tail and signature removed."""
    text = _BANNER_RE.sub("", body or "", count=1)
    m = _QUOTE_START_RE.search(text)
    if m:
        text = text[: m.start()]
    m = _SIGNOFF_RE.search(text)
    if m:
        text = text[: m.start()]
    return text.strip().upper()


def body_head(cleaned_body: str) -> str:
    """The first substantive paragraph — where the ask lives.

    Skips the salutation ("Hi Najiha,") so that a one-paragraph email and a
    three-paragraph email are scored on the same thing.
    """
    for para in (p.strip() for p in re.split(r"\n\s*\n", cleaned_body)):
        if not para:
            continue
        if _SALUTATION_RE.match(para) and len(para) <= 40:
            continue
        return para
    return ""


@dataclass(frozen=True)
class Text:
    """The five views of an email that rules match against."""

    subject: str
    body: str
    body_head: str
    sender: str

    @property
    def any(self) -> str:
        return f"{self.subject}\n{self.body}"

    def view(self, field: str) -> str:
        if field == "subject":
            return self.subject
        if field == "body":
            return self.body
        if field == "body_head":
            return self.body_head
        if field == "sender":
            return self.sender
        return self.any


def prepare(email: EmailRecord) -> Text:
    """Build the matchable views of one email. Never raises on empty input."""
    cleaned = clean_body(email.body or "")
    return Text(
        subject=clean_subject(email.subject or ""),
        body=cleaned,
        body_head=body_head(cleaned),
        sender=(email.sender or "").strip().upper(),
    )


# --------------------------------------------------------------------------
# The structured-block signal
#
# An SI_REQUEST body is not prose, it is a form:
#
#     POL: SINGAPORE
#     Shipper:
#     APRIL FINE PAPER TRADING
#     Consignee:
#     ...
#     GROSS WT: 354,765 KG
#
# Any single one of those markers is weak ("Shipper:" appears in quoted mail
# too). *How many of them appear together* is strong, and it survives a change
# of wording, which a keyword list does not. We reuse `labels.resolve()` rather
# than hard-coding the marker names, so the moment a new SI wording is added to
# `labels.SYNONYMS` this classifier recognises it as well.
# --------------------------------------------------------------------------
_LABELLED_LINE_RE = re.compile(r"^[ \t]*([A-Z][A-Z0-9 ./&()'\-]{1,40}?)[ \t]*:", re.M)


def count_si_block_markers(text: str) -> int:
    """Number of *distinct* canonical shipping fields labelled in `text`."""
    found: set[str] = set()
    for raw_label in _LABELLED_LINE_RE.findall(text):
        resolved = labels.resolve(raw_label)
        if resolved:
            found.add(resolved)
    return len(found)


# --------------------------------------------------------------------------
# The rule table
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Rule:
    """One readable piece of evidence for one category.

    `field` is which view of the email to match: subject | body_head | body |
    sender | any. `repeat_cap` > 1 means the weight is paid once per match up
    to that cap — that is how a *count* of signals (see `count_si_block_markers`)
    becomes a score without leaving the table.
    """

    name: str
    category: str
    field: str
    weight: float
    pattern: Optional[re.Pattern[str]] = None
    counter: Optional[Callable[[str], int]] = None
    repeat_cap: int = 1
    why: str = ""

    def hits(self, text: Text) -> int:
        target = text.view(self.field)
        if not target:
            return 0
        if self.counter is not None:
            n = self.counter(target)
        else:
            assert self.pattern is not None
            n = len(self.pattern.findall(target))
        return min(n, self.repeat_cap)

    def score(self, text: Text) -> float:
        return self.weight * self.hits(text)


def _r(name, category, field, weight, pattern, *, repeat_cap=1, why="", counter=None):
    return Rule(
        name=name,
        category=category,
        field=field,
        weight=weight,
        pattern=re.compile(pattern, re.M) if pattern else None,
        counter=counter,
        repeat_cap=repeat_cap,
        why=why,
    )


# Every pattern is matched against UPPER-CASED text, so the table reads the way
# a subject line reads. `B/?L` covers both "BL" and "B/L".
RULES: list[Rule] = [
    # ==================================================================
    # BL_COMPARISON — "check these two documents", or "make me a draft"
    # ==================================================================
    _r("bl.subject.to-confirm-docs", BL, "subject", 4.0,
       r"^TO CONFIRM DOCS(?![A-Z])",
       why="The desk's standing subject for 'here are the docs, please check them'."),
    _r("bl.subject.request-bl-draft", BL, "subject", 4.0,
       r"^REQUEST B/?L DRAFT(?![A-Z])",
       why="A request for us to produce a draft BL; still a BL case, just with nothing to compare yet."),
    _r("bl.subject.draft-bl-amend", BL, "subject", 4.0,
       r"^DRAFT B/?L\b.*\bAMEND\b",
       why="'Draft BL <vessel> <voyage> <port> - amend BL 057' — a correction round on a specific draft."),
    _r("bl.subject.desk-code", BL, "subject", 4.0,
       r"^(?:AIE|AFPTME|AFRT|AFEMY)\s*-\s",
       why="Known documentation desk codes. A desk-coded subject is a routing line for a shipment file."),
    _r("bl.subject.desk-code-shape", BL, "subject", 2.5,
       r"^(?!SI\b)[A-Z]{2,6}\s*-\s*[A-Z][A-Z _]{2,}\s*-\s*[A-Z]{2,}\([A-Z0-9]+\)",
       why="Generalised desk line '<DESK> - <PORT> - <CARRIER>(<blno>)'; catches a desk code we have not seen. "
           "The port field must be alphabetic, which is what excludes 'SI - <blno> - DIRECT(MSC)'."),

    _r("bl.body.attached-si-and-draft-bl", BL, "body_head", 4.0,
       r"\bSI\b\s+AND\s+(?:THE\s+)?DRAFT\s+B/?L\b",
       why="'Attached are the SI and draft BL ...' — both documents named together is the comparison ask."),
    _r("bl.body.si-and-bill-of-lading", BL, "body_head", 4.0,
       r"SHIPPING INSTRUCTION AND (?:THE )?DRAFT BILL OF LADING",
       why="The same ask spelled out in full."),
    _r("bl.body.check-draft-against-si", BL, "body_head", 4.0,
       r"\bCHECK\b[^.]{0,40}\bDRAFT\s+B/?L\b[^.]{0,20}\bAGAINST\b[^.]{0,20}\bSI\b",
       why="'check the draft BL against the SI' — names the two documents and the operation."),
    _r("bl.body.compare-si-and-bl", BL, "body_head", 4.0,
       r"\bCOMPARE\b[^.]{0,30}\bSI\b[^.]{0,20}\bB/?L\b",
       why="'Please compare the SI and draft BL ...' — explicit comparison request."),
    _r("bl.body.verify-bl-matches-si", BL, "body_head", 3.0,
       r"\bVERIFY\b[^.]{0,20}\bB/?L\b[^.]{0,20}\bMATCHES\b[^.]{0,20}\bSI\b",
       why="'Kindly verify the BL matches the SI before we release to the line.'"),
    _r("bl.body.confirm-bl-in-order", BL, "body_head", 3.0,
       r"\bCONFIRM\b[^.]{0,20}\bB/?L\b[^.]{0,20}\bIN ORDER\b",
       why="'Kindly confirm the BL is in order' — a check request even when the wrong second document was attached."),
    _r("bl.body.assist-to-send-draft", BL, "body_head", 3.5,
       r"\b(?:ASSIST|HELP)\b[^.]{0,20}\b(?:SEND|ISSUE|PREPARE|PROVIDE|RELEASE)\b[^.]{0,20}\bDRAFT\s+B/?L\b",
       why="'Please assist to send the draft BL for <booking> for checking asap.' — we are asked to produce the "
           "draft. Still a BL case; intent.py decides that there is nothing to escalate."),
    _r("bl.body.revert-with-discrepancy", BL, "body", 2.5,
       r"\bREVERT WITH ANY DISCREPANC",
       why="Asking for discrepancies back is only meaningful if we are checking one document against another."),
    _r("bl.body.draft-bl-number", BL, "body", 2.0,
       r"\bDRAFT B/?L NO\b",
       why="Quoting the draft BL's own number identifies the document under review."),
    _r("bl.body.for-checking", BL, "body_head", 1.5,
       r"\bFOR CHECKING\b",
       why="Weak on its own — supports the stronger document-naming rules."),

    # ==================================================================
    # SI_REQUEST — a shipping instruction is being sent or asked for
    # ==================================================================
    _r("si.subject.coded-line", SI, "subject", 4.0,
       r"^SI\s*-\s*",
       why="'SI - <blno> - DIRECT(MSC) - <oc> - <pod> - OBL - AIE - 12-Jan-26'. The LEADING token is what "
           "separates this from the desk-coded BL_COMPARISON line."),
    _r("si.subject.cust-si", SI, "subject", 4.0,
       r"\bCUST SI(?![A-Z])",
       why="Customer-supplied shipping instruction."),
    _r("si.subject.request-si", SI, "subject", 4.0,
       r"\bREQUEST SI(?![A-Z])",
       why="Explicit request for the SI."),
    _r("si.subject.si-needed", SI, "subject", 4.0,
       r"\bSI NEEDED(?![A-Z])",
       why="Explicit request for the SI."),
    _r("si.body.please-find-shipping-instruction", SI, "body_head", 4.0,
       r"\bFIND\b[^.]{0,20}\bSHIPPING INSTRUCTION\b",
       why="'Please find Shipping instruction for 5RFR-37631.' — the SI is in the body, not attached."),
    _r("si.body.structured-block", SI, "body", 1.0, None,
       counter=count_si_block_markers, repeat_cap=6,
       why="Counts how many of the 7 canonical shipping fields are labelled in the body (POL:, POD:, Shipper:, "
           "Consignee:, Notify Party:, GROSS WT: ...). One marker is noise; five together is a form, and a form "
           "in the body IS the shipping instruction. Resolved through labels.py so new wording is free."),
    _r("si.body.revert-with-draft-once-available", SI, "body", 2.5,
       r"\bREVERT WITH\b[^.]{0,20}\bDRAFT B/?L\b[^.]{0,20}\bONCE AVAILABLE\b",
       why="Every SI_REQUEST body closes with this line. It mentions 'draft BL', which is exactly why it is scored "
           "FOR SI_REQUEST: left unclaimed, the bare phrase would drag the email towards BL_COMPARISON."),
    _r("si.body.documents-required-list", SI, "body", 1.5,
       r"\bDOCUMENTS REQUIRED\b",
       why="The SI's closing checklist (originals, packing list, N/N copies)."),

    # ==================================================================
    # INVOICE_QUERY — money
    # ==================================================================
    _r("inv.subject.billing", INV, "subject", 3.0,
       r"\bBILLING\b",
       why="'2115 RAK BILLING 5070146244 MISSING GR' — a billing desk reference."),
    _r("inv.subject.missing-gr", INV, "subject", 3.5,
       r"\bMISSING GR(?![A-Z])",
       why="A missing goods receipt blocks invoicing; it is an accounts question, not a documents one."),
    _r("inv.subject.cancel-invoice", INV, "subject", 4.0,
       r"\bCANCEL INVOICE(?![A-Z])",
       why="Invoice cancellation request."),
    _r("inv.subject.local-charges", INV, "subject", 3.5,
       r"\bLOCAL CHARGES(?![A-Z])",
       why="THC / local charge queries are billing."),
    _r("inv.subject.dd-charges", INV, "subject", 3.5,
       r"\bD\s*&\s*D CHARGES\b|\bDETENTION\b|\bDEMURRAGE\b",
       why="Detention & demurrage are charges, whatever document they reference."),
    _r("inv.subject.telex-release-charges", INV, "subject", 3.0,
       r"\bTELEX RELEASE CHARGES(?![A-Z])",
       why="A telex release FEE is billing; a telex release instruction would not be."),
    _r("inv.subject.total-freight", INV, "subject", 3.5,
       r"\bTOTAL FREIGHT(?![A-Z])",
       why="Freight amount query."),
    _r("inv.subject.invoice-word", INV, "subject", 1.5,
       r"\bINVOICE\b|\bPAYMENT\b",
       why="Weak on its own — phishing also says 'invoice payment'."),
    _r("inv.body.invoice-number", INV, "body_head", 2.5,
       r"\bINVOICE\s*#?\s*\d{4,}",
       why="A quoted invoice number is what an accounts query is about."),
    _r("inv.body.thc-local-charge", INV, "body_head", 2.5,
       r"\bTHC\b|\bLOCAL CHARGE",
       why="Terminal handling / local charges."),
    _r("inv.body.detention-demurrage", INV, "body_head", 2.5,
       r"\bDETENTION\b|\bDEMURRAGE\b|\bD\s*&\s*D\b",
       why="Detention & demurrage."),
    _r("inv.body.reverse-pgi", INV, "body_head", 3.0,
       r"\bREVERSE THE PGI\b",
       why="Reversing a post goods issue is an ERP/billing action."),
    _r("inv.body.release-payment", INV, "body_head", 2.0,
       r"\bRELEASE PAYMENT\b|\bPOST THE GR\b|\bPROCEED WITH BILLING\b",
       why="Payment / goods-receipt posting."),
    _r("inv.body.gr-missing", INV, "body_head", 2.5,
       r"\bGR IS STILL MISSING\b|\bMISSING\b[^.]{0,20}\bGR\b",
       why="Missing goods receipt."),

    # ==================================================================
    # GENERAL — operational noise, automated notices, HR
    # ==================================================================
    _r("gen.sender.role-mailbox", GEN, "sender", 3.0,
       r"^(?:NOREPLY|NO-REPLY|DONOTREPLY|DO-NOT-REPLY|RPA\.?BOT|RPA-BOT|HR|OPERATIONS|DOCUMENTATION"
       r"|NOTIFICATIONS?|ALERTS?)@",
       why="A role mailbox broadcasts; it does not ask one person to check one shipment's documents. "
           "Deliberately weaker than the SPAM sender rules, because phishing also forges 'no-reply@'."),
    _r("gen.subject.update-summary", GEN, "subject", 4.0,
       r"\bUPDATE SUMMARY(?![A-Z])",
       why="Daily vessel update circular."),
    _r("gen.subject.berthing-report", GEN, "subject", 4.0,
       r"\bBERTHING REPORT(?![A-Z])",
       why="Daily berthing circular."),
    _r("gen.subject.reminder-tag", GEN, "subject", 4.0,
       r"_REMINDER_",
       why="'_Reminder_Paper - Submit SI & AED_18-01-2026' is a standing HR/admin reminder to the whole desk. "
           "It says 'Submit SI' and is NOT an SI_REQUEST — nobody is sending or asking for one shipment's SI."),
    _r("gen.subject.rpa-tag", GEN, "subject", 3.5,
       r"_RPA_|\bRPA BOT(?![A-Z])",
       why="Robotic-process-automation run notice."),
    _r("gen.subject.outstanding-bl-list", GEN, "subject", 4.0,
       r"\bOUTSTANDING B/?L(?![A-Z])",
       why="'APRIL PAPER - List of Outstanding BL (BDP SG)' is a status circular about many BLs. It is NOT "
           "BL_COMPARISON: there is no draft to check against an SI."),
    _r("gen.subject.pending-bl-release", GEN, "subject", 4.0,
       r"\bPENDING B/?L RELEASE(?![A-Z])",
       why="Release-queue circular — again many BLs, no comparison."),
    _r("gen.subject.hr", GEN, "subject", 4.0,
       r"\bTIME OFF REQUEST\b|\b_APPROVAL REQUIRED_\b|\bWELCOMING THE NEW YEAR\b|\bHAPPY NEW YEAR\b"
       r"|\bDELIVERY PLANNING\b|\bMISS CONNECTION\b",
       why="HR and office announcements, and the operational-notice subjects that carry no shipment reference."),
    _r("gen.body.automated-notification", GEN, "body_head", 4.0,
       r"\bAUTOMATED NOTIFICATION\b|--\s*RPA BOT\b",
       why="Machine-generated; explicitly not addressed to anyone."),
    _r("gen.body.no-action-required", GEN, "body_head", 3.5,
       r"\bNO ACTION REQUIRED\b",
       why="The message says outright that it needs nothing from us."),
    _r("gen.body.circular-attachment", GEN, "body_head", 4.0,
       r"\bLIST OF OUTSTANDING B/?L\b|\bBERTHING REPORT\b|\bUPDATE SUMMARY\b",
       why="These bodies say 'Please find attached ...' and mention BL, which is exactly the trap: the attachment "
           "is a circular, not a draft bill of lading."),
    _r("gen.body.submit-si-reminder", GEN, "body_head", 4.0,
       r"\bSUBMIT SI\b(?:\s*(?:&|AND)\s*AED\b)?[^.]{0,60}\b(?:ALL PENDING|BY END OF DAY|SHIPMENTS)\b",
       why="'Reminder: Please submit SI & AED for all pending shipments by end of day.' A blanket reminder to the "
           "desk, addressed to no shipment — the single most confusable GENERAL body in the set."),
    _r("gen.body.office-notice", GEN, "body_head", 4.0,
       r"\bWISHING EVERYONE\b|\bOFFICE RESUMES\b|\bLOADING COMPLETED, DOCUMENTS TO FOLLOW\b"
       r"|\bKINDLY ACTION THE PENDING ITEMS\b",
       why="Broadcast phrasing: addressed to the team, not to a shipment file."),
    _r("gen.body.dear-team-broadcast", GEN, "any", 0.5,
       r"^DEAR (?:TEAM|ALL)\b",
       why="Very weak. Broadcast salutation; real document requests in this inbox name a person."),

    # ==================================================================
    # SPAM
    #
    # Two layers on purpose. The literal domain list catches what we have seen;
    # the shape rules ("throwaway-looking domain" + "hype/urgency language")
    # catch the next wave from a domain nobody has registered yet. Their sum IS
    # the general signal — a suspicious domain alone is not enough to condemn a
    # new counterparty, and hype alone is not enough to condemn a marketing
    # mail from a real partner.
    # ==================================================================
    _r("spam.sender.known-throwaway-domain", SPAM, "sender", 5.0,
       r"@(?:PRIZE-CLAIMS\.INFO|PARCEL-TRACK\.CO|WEBMAIL-VERIFY\.CO|LOGISTICS-DEALS\.BIZ"
       r"|CRYPTO-INVEST\.NET|SECURE-MAILBOX\.ORG)\b",
       why="Domains observed sending nothing but phishing and bait into this inbox."),
    _r("spam.sender.throwaway-domain-shape", SPAM, "sender", 3.0,
       r"@[A-Z0-9.\-]*\b(?:PRIZE|CLAIM|WINNER|LOTTO|GIFT|VERIFY|SECURE-|CRYPTO|INVEST|DEALS|OFFERS?"
       r"|PROMO|TRACK|MAILBOX|WEBMAIL)[A-Z0-9.\-]*\.",
       why="Domain built out of the bait itself. Generalises past the literal list above."),
    _r("spam.sender.cheap-tld", SPAM, "sender", 2.0,
       r"@[A-Z0-9.\-]+\.(?:INFO|BIZ|TOP|XYZ|CLICK|LIVE|ONLINE|SHOP|CLUB|WIN|LINK|ZIP)$",
       why="TLDs a shipping counterparty does not use, and bulk senders do."),
    _r("spam.sender.bait-local-part", SPAM, "sender", 2.0,
       r"^(?:WINNER|WINNERS|OFFERS|PROMO|DEALS|PRIZES|LOTTERY)@",
       why="The mailbox name is the pitch."),
    _r("spam.text.prize", SPAM, "any", 4.0,
       r"\bYOU HAVE WON\b|\bHAS BEEN SELECTED\b|\bGIFT CARD\b|\bCLAIM NOW\b|\bMONTHLY DRAW\b"
       r"|\bCONGRATULATIONS!{2,}|\bFREE IPHONE\b|\bBRAND NEW IPHONE\b",
       why="Prize / lottery bait."),
    _r("spam.text.parcel-fee", SPAM, "any", 4.0,
       r"\bUNPAID CUSTOMS FEE\b|\bCOULD NOT BE DELIVERED\b|\bPARCEL WILL BE RETURNED\b"
       r"|\bPARCEL (?:IS )?ON HOLD\b",
       why="Parcel-on-hold-pay-a-fee scam. Note it is shipping-flavoured, which is why it needs its own rule "
           "rather than relying on 'this inbox is about shipping'."),
    _r("spam.text.mailbox-phish", SPAM, "any", 4.0,
       r"\bSTORAGE (?:LIMIT|IS FULL|FULL)\b|\bEXCEEDED ITS STORAGE\b|\bMAILBOX\b[^.]{0,30}\bFULL\b"
       r"|\bUNDELIVERED MESSAGES\b|\bVERIFY (?:YOUR )?ACCOUNT\b|\bUPDATE YOUR ACCOUNT\b",
       why="Credential phishing dressed as a mail-system notice."),
    _r("spam.text.account-threat", SPAM, "any", 3.0,
       r"\bAVOID (?:SUSPENSION|DEACTIVATION)\b|\bWITHIN \d+ HOURS?\b|\bIMMEDIATELY\b[^.]{0,20}\bACCOUNT\b"
       r"|\bACCOUNT\b[^.]{0,20}\bIMMEDIATELY\b",
       why="Manufactured urgency — the hype half of 'suspicious domain + urgency'."),
    _r("spam.text.money-scam", SPAM, "any", 4.0,
       r"\bBITCOIN\b|\bGUARANTEED\s*\d*\s*%?\s*RETURNS?\b|\bBANK OFFICER\b|\bYOUR BANK DETAILS\b"
       r"|\bBUSINESS PROPOSAL\b|\bUSD [\d.]+ MILLION\b",
       why="Advance-fee and investment fraud."),
    _r("spam.text.marketing-hype", SPAM, "any", 3.0,
       r"\b\d{2,3}\s*%\s*OFF\b|\bLIMITED TIME OFFER\b|\bEXCLUSIVE OFFER\b|\bBUY NOW\b|\bWEIRD TRICK\b"
       r"|\bTHIS WEEK ONLY\b|\bDEAL EXPIRES\b",
       why="Cold-sales blast. Not fraud, still not the desk's work."),
    _r("spam.text.adult", SPAM, "any", 5.0,
       r"\bHOT SINGLES\b|\bIN YOUR AREA WANT TO\b",
       why="Unambiguous."),
    _r("spam.text.bait-link", SPAM, "body", 2.5,
       r"HTTPS?://[A-Z0-9.\-]*(?:CLAIM|PRIZE|FREE-|VERIFY|TRACK-PARCEL|BIT\.LY)",
       why="A link whose host is the bait."),
    _r("spam.text.mass-salutation", SPAM, "any", 2.0,
       r"\bDEAR (?:VALUED CUSTOMER|USER|CUSTOMER|SIR/MADAM)\b|\bHELLO DEAR\b",
       why="Addressed to a list, not a colleague. Weak — pair it with the domain and hype rules."),
    _r("spam.text.click-here", SPAM, "any", 2.0,
       r"\bCLICK HERE\b",
       why="Weak on its own."),
]


# --------------------------------------------------------------------------
# Result
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Classification:
    category: str
    confidence: float
    decided_by: str
    margin: float
    scores: dict[str, float]
    rationale: list[str] = dc_field(default_factory=list)
    needs_llm: bool = False


def _confidence(winner: float, margin: float) -> float:
    """0..1 from how much evidence there is and how one-sided it is.

    Both halves matter. A high score with no margin means two categories are
    equally well supported (an email that is genuinely both), and a clean
    margin on almost no evidence means one weak keyword decided it.
    """
    score_term = min(1.0, max(0.0, winner) / FULL_SCORE)
    margin_term = min(1.0, max(0.0, margin) / FULL_MARGIN)
    return round(0.5 * score_term + 0.5 * margin_term, 4)


def _attachment_evidence(doc_types: list[str]) -> tuple[float, Optional[str]]:
    """Extra weight for BL_COMPARISON from what was actually attached.

    One more signal, never an override: it can only ever ADD to
    BL_COMPARISON, so an email carrying the wrong second document (an SI plus
    a Commercial Invoice) cannot be pushed out of BL_COMPARISON by it — which
    is the behaviour the escalation stage depends on, since `wrong_doc_type`
    is a BL_COMPARISON outcome. Emails with no attachments are unaffected.
    """
    from ..schema import DOC_BL, DOC_SI

    kinds = {str(t).upper() for t in doc_types}
    if DOC_SI in kinds and DOC_BL in kinds:
        return ATTACHMENT_PAIR_WEIGHT, "attachments.si-bl-pair"
    if kinds & {DOC_SI, DOC_BL}:
        return ATTACHMENT_SINGLE_WEIGHT, "attachments.shipping-document"
    return 0.0, None


def classify_email(
    email: EmailRecord,
    *,
    attachment_doc_types: Optional[list[str]] = None,
) -> Classification:
    """Score every rule, sum per category, return the winner with its evidence.

    `attachment_doc_types` is optional extra evidence (see
    `_attachment_evidence`). The classifier works without it, because 96 of the
    220 BL_COMPARISON emails in this inbox carry no attachment at all.
    """
    text = prepare(email)
    scores: dict[str, float] = {c: 0.0 for c in CATEGORIES}
    fired: list[tuple[float, str]] = []

    for rule in RULES:
        gained = rule.score(text)
        if gained:
            scores[rule.category] += gained
            fired.append((gained, rule.name))

    if attachment_doc_types:
        gained, name = _attachment_evidence(attachment_doc_types)
        if name:
            scores[BL] += gained
            fired.append((gained, name))

    ranked = sorted(
        scores.items(),
        key=lambda kv: (-kv[1], TIE_BREAK_ORDER.index(kv[0])),
    )
    winner, top = ranked[0]
    runner_up = ranked[1][1]
    margin = top - runner_up

    # Nothing fired at all. An email this inbox cannot recognise is, by
    # definition, not one of the four things the desk acts on — it is noise —
    # but it is flagged for the LLM layer rather than quietly filed.
    if top <= 0.0:
        return Classification(
            category=GEN,
            confidence=0.0,
            decided_by="rule",
            margin=0.0,
            scores=scores,
            rationale=["fallback.no-rule-fired"],
            needs_llm=True,
        )

    rationale = [name for _, name in sorted(fired, key=lambda x: -x[0])]
    return Classification(
        category=winner,
        confidence=_confidence(top, margin),
        decided_by="rule",
        margin=round(margin, 4),
        scores={k: round(v, 4) for k, v in scores.items()},
        rationale=rationale,
        needs_llm=top < MIN_SCORE or margin < MIN_MARGIN,
    )


def explain(email: EmailRecord) -> list[tuple[str, str, float]]:
    """(category, rule name, score) for every rule that fired — for the UI."""
    text = prepare(email)
    out = [(r.category, r.name, r.score(text)) for r in RULES if r.hits(text)]
    return sorted(out, key=lambda t: -t[2])


def is_empty(email: EmailRecord) -> bool:
    """True when neither the subject nor the body carries any information.

    Reuses `normalize.is_blank`, the project's single definition of "present
    but says nothing", so a subject of `???` is treated the same here as a
    field of `???` is in the comparison stage.
    """
    return is_blank(email.subject or "") and is_blank(email.body or "")
