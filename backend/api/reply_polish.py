"""Let a model reword the courtesy of a reply draft, and nothing else.

A reply draft (web/lib/reply-draft.ts) is assembled from six parts: a
greeting, the context, the facts, the action, a closing, and the fixed
"Hello," / "Regards,". Everything that says something about the case is
chosen by rules and locked:

  * the context says what happened ("We could not open one of the
    attachments, so the check is on hold");
  * the facts are quoted from the case's evidence ("Gross Weight (kg): left
    blank on the Shipping Instruction; the draft Bill of Lading shows
    235,550 KG");
  * the action is the decision the reply carries ("please check with the
    customer and confirm the gross weight", "there is no need to re-send").

None of that is ever sent here. Only the greeting ("Thank you for your
email.") and the closing ("Thank you for your patience.") reach the model,
and those hold no case value and no claim. So the first guard is structural:
the model cannot restate a value it was never shown, cannot soften a request
it never saw, and cannot turn "some fields do not match" into "everything
agrees", because it is not given the sentence to rewrite.

The second guard is a check on what comes back, because a model asked to
write a friendlier "thank you" can still *add* something ("your 5
containers", "Mr Tan", "your BL is all set", "please send the invoice"). Its
wording is refused, and the template kept, if it:

  * contains a digit, an all-capitals word of three letters or more (how
    this domain writes parties, ports and codes), a quotation, an address or
    a link;
  * capitalises a word mid-sentence that the template did not (a name the
    model made up);
  * uses a word or phrase that claims an outcome ("verified", "agrees", "all
    set", "no issues"), unless it is negated;
  * asks the customer for something (a question, or "send", "provide",
    "confirm", "pay" ...): the request is the action's job, and it is locked;
  * repeats the fixed salutation or sign-off;
  * comes back empty, or far longer than the template.

That list is a net, not a proof, worded to refuse too much rather than too
little: a refusal costs nothing but the template's own wording. What is
actually trusted is the structure, plus the person who reads the draft in
their own mail client and presses send (Sentinel never sends).
"""
from __future__ import annotations

import json
import re
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from sdoc.llm.client import LLMUnavailable

Situation = Literal[
    "no_discrepancy",
    "discrepancy",
    "attachments_missing",
    "document_missing",
    "file_unopenable",
    "scanned_copies",
    "wrong_document",
    "values_to_confirm",
    "review_generic",
]
Tone = Literal["formal", "warm", "brief"]

_TONES: dict[str, str] = {
    "formal": "formal and courteous, as a documentation desk writes to a customer",
    "warm": "warm and personable, still professional",
    "brief": "as short as it can be while staying polite",
}

# What the email is about, so the courtesy fits (a "thank you for your
# patience" suits a hold, not a clean result) without any case detail.
_SITUATIONS: dict[str, str] = {
    "no_discrepancy": "the documents were checked",
    "discrepancy": "the documents were checked and something needs the customer's attention",
    "attachments_missing": "the customer's email arrived without its attachments",
    "document_missing": "one of the two documents needed did not arrive",
    "file_unopenable": "an attachment could not be opened",
    "scanned_copies": "the documents are scans, which staff check by hand",
    "wrong_document": "an attachment is a different kind of document from the one needed",
    "values_to_confirm": "some fields need the customer's confirmation",
    "review_generic": "a person is looking at the customer's documents",
}

_INSTRUCTIONS = """\
You reword two courtesy lines of an email from a shipping documentation desk to
a customer: the GREETING (the first sentence after "Hello,") and the CLOSING
(the last line before "Regards,"). Everything between them, which says what
happened, lists the facts and makes the request, is written separately; you
will not see it.

Rules:
- Write pure courtesy: thanks, acknowledgement, patience, apology for trouble.
- Make no statement about the documents, the shipment, the fields or any
  outcome, and ask the customer for nothing.
- Never mention a company, person, place, port, number, date, reference or file
  name. Do not use quotation marks.
- No salutation or sign-off: "Hello," and "Regards," are already there.
- Write in the requested tone. Each line is one or two short sentences.
- Each time, write a fresh variation.
"""

_ALLCAPS = re.compile(r"\b[A-Z]{3,}\b")
_WORD = re.compile(r"[A-Za-z][A-Za-z'’-]*")

# Words that assert an outcome, allowed only when negated ("we could not
# verify") or when the template itself already used them.
_CLAIM_WORDS = frozenset({
    "verified", "verify", "confirmed", "approved", "approve", "released",
    "cleared", "accepted", "matched", "matches", "correct", "accurate",
    "resolved", "fixed", "finalised", "finalized", "guarantee", "guaranteed",
    "agree", "agrees", "agreed", "fine", "discrepancy", "discrepancies",
    "mismatch", "mismatches", "wrong", "issued", "shipped", "sail", "sails",
})
_CLAIM_PHRASES = tuple(re.compile(p) for p in (
    r"\bin order\b(?!\s+to\b)", r"\ball good\b", r"\bno (issues?|problems?)\b",
    r"\ball (the )?fields\b", r"\ball set\b", r"\bchecks? out\b", r"\bsigned off\b",
    r"\bgood to go\b", r"\bnothing wrong\b", r"\bno (discrepanc(y|ies)|mismatch(es)?)\b",
    r"\bon (schedule|time)\b",
))
# A claim word within three words after one of these is not a claim.
_NEGATIONS = frozenset({
    "not", "no", "nothing", "none", "never", "unable", "cannot", "can't",
    "couldn't", "wasn't", "weren't", "isn't", "aren't", "haven't", "hasn't",
    "without",
})
# "Hello," and "Regards," are fixed around the two lines; a second one reads
# as a mistake in the email a customer receives.
_SALUTATIONS = frozenset({"hello", "hi", "dear", "regards", "sincerely", "cheers"})
# The request is the action's job, and the action is locked. A courtesy line
# that asks for something is writing a second, unreviewed request.
_REQUEST_WORDS = frozenset({
    "send", "resend", "re-send", "provide", "confirm", "attach", "pay",
    "payment", "invoice", "sign", "submit", "password", "upload", "forward",
})

# Longest a rewrite may run relative to its template, in characters, plus a
# floor so a one-line template can still become a natural sentence or two.
_GROWTH = 2.0
_FLOOR = 160


class PolishRequest(BaseModel):
    """Everything the model may see. There is no field for facts, values or
    the request: that is the structural guard, and `extra="forbid"` keeps it
    one."""

    model_config = ConfigDict(extra="forbid")

    situation: Situation
    tone: Tone = "formal"
    greeting: str = Field(min_length=1, max_length=200)
    closing: str = Field(min_length=1, max_length=200)
    #: Which press of "Reword" this is. The templates are constant, so without
    #: it every press would send the identical prompt and be answered from the
    #: response cache: "Reword again" would do nothing, and one refused first
    #: answer would be refused forever. Bounded, so it cannot be used to force
    #: unbounded distinct (billed) calls from a single page.
    attempt: int = Field(default=0, ge=0, le=20)


class _Rewrite(BaseModel):
    greeting: str
    closing: str


class PolishResponse(BaseModel):
    greeting: str
    closing: str
    #: False when the rewrite was refused and the template's wording stands.
    adopted: bool
    rejected_reason: Optional[str] = None
    model: Optional[str] = None


def _capitalised_mid_sentence(text: str) -> set[str]:
    """Capitalised words that do not start a sentence ("I", "I'm" aside)."""
    out: set[str] = set()
    at_start = True
    for m in _WORD.finditer(text):
        word = m.group(0)
        if not at_start and word[0].isupper() and not re.fullmatch(r"I(['’](m|ll|d|ve))?", word):
            out.add(word)
        at_start = bool(re.match(r"\s*[.!?…]", text[m.end():m.end() + 3]))
    return out


def check_wording(text: str, template: str) -> Optional[str]:
    """None when `text` is courtesy only; otherwise why it was refused.

    `template` is the line the model was asked to reword. A capitalised word
    or an outcome word it already contains is not the model's invention.
    """
    t = " ".join(text.split())
    if not t:
        return "the rewrite was empty"
    if len(t) > max(_FLOOR, int(len(template) * _GROWTH)):
        return "the rewrite was much longer than the template"
    if re.search(r"\d", t):
        return "the rewrite contained a number"
    if _ALLCAPS.search(t):
        return "the rewrite contained an all-capitals word, which reads as a name or a code"
    if re.search(r"[\"“”«»]", t):
        return "the rewrite quoted something"
    if "@" in t or re.search(r"https?://|www\.", t, re.I):
        return "the rewrite contained an address or a link"
    new_names = _capitalised_mid_sentence(t) - set(_WORD.findall(template))
    if new_names:
        return f"the rewrite introduced a name the template did not have ({sorted(new_names)[0]})"

    low, tmpl_low = t.lower().replace("’", "'"), template.lower()
    tmpl_words = {w.lower() for w in _WORD.findall(template)}
    words = _WORD.findall(low)
    for i, w in enumerate(words):
        # "We could not verify some fields" says the template's own thing in
        # other words; "we have verified" is a claim. Only the second is refused.
        if w in _CLAIM_WORDS and w not in tmpl_words and not _NEGATIONS.intersection(words[max(0, i - 3):i]):
            return f"the rewrite claimed an outcome ({w})"
    for pat in _CLAIM_PHRASES:
        m = pat.search(low)
        if m and not pat.search(tmpl_low):
            return f"the rewrite claimed an outcome ({m.group(0)})"
    for w in words:
        if w in _SALUTATIONS and w not in tmpl_words:
            return f"the rewrite repeated the salutation or sign-off ({w})"
    if "?" in t:
        return "the rewrite asked a question, which is the locked request's job"
    for w in words:
        if w in _REQUEST_WORDS and w not in tmpl_words:
            return f"the rewrite asked the customer for something ({w}), which is the locked request's job"
    return None


def polish(req: PolishRequest, client) -> PolishResponse:
    """Ask `client` for a rewrite and keep it only if both lines pass.

    Raises `LLMUnavailable` when the model cannot be reached; the caller turns
    that into "the template stands" for the page. A refused rewrite is not an
    error: it comes back with `adopted=False` and the reason.
    """
    prompt = json.dumps(
        {
            "what_this_email_is_about": _SITUATIONS[req.situation],
            "tone": _TONES[req.tone],
            "greeting": req.greeting,
            "closing": req.closing,
            "variation": req.attempt,
        },
        ensure_ascii=False,
        indent=1,
    )
    out = client.structured(
        purpose="reply_polish",
        instructions=_INSTRUCTIONS,
        prompt=prompt,
        schema=_Rewrite,
        max_output_tokens=1500,
    )
    model = getattr(getattr(client, "settings", None), "model", None)
    greeting, closing = " ".join(out.greeting.split()), " ".join(out.closing.split())
    for part, text, template in (("greeting", greeting, req.greeting), ("closing", closing, req.closing)):
        why = check_wording(text, template)
        if why:
            return PolishResponse(
                greeting=req.greeting, closing=req.closing, adopted=False,
                rejected_reason=f"{part}: {why}", model=model,
            )
    return PolishResponse(greeting=greeting, closing=closing, adopted=True, model=model)


__all__ = ["LLMUnavailable", "PolishRequest", "PolishResponse", "check_wording", "polish"]
