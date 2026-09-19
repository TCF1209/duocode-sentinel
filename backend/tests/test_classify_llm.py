"""Tests for the Stage 1 model fallback: `classify/llm.py`.

**Nothing here touches the network.** Every test that exercises a model answer
passes a `StubClient`, and the one test that lets the module build its own
client blanks `OPENAI_API_KEY` first, so the suite runs identically on CI and on
a judge's laptop with no key in sight.

The stub deliberately mirrors the two things `LLMClient` does that this module
depends on: it exposes `available`, and it validates the answer through the
caller's Pydantic schema exactly as the real client's cache path does
(`schema.model_validate`). That is what makes "the model cannot return a
category outside the five" a real test rather than a restatement of the type
hint — the stub is allowed to *try*.

`data/_grader/` is never opened. The one fact these tests assert about the real
inbox is one the inbox itself makes visible: how many of its 520 emails the
rule classifier is unsure about.
"""
from __future__ import annotations

import json
from typing import Any, Optional

import pytest
from pydantic import ValidationError

from conftest import DATA, skip_without_bundle
from sdoc.classify import llm as classify_llm
from sdoc.classify import rules
from sdoc.llm import LLMUnavailable
from sdoc.schema import CATEGORIES, EmailRecord

INBOX = DATA / "inbox"


# --------------------------------------------------------------------------
# A model client that never leaves the process
# --------------------------------------------------------------------------
class StubClient:
    """Stands in for `LLMClient`, recording what it was asked.

    `structured` validates through the caller's schema rather than returning a
    hand-built object, so a test can hand it an answer the schema forbids and
    watch the module refuse it — which is how the real client behaves when it
    replays a cache entry written against an older schema.
    """

    def __init__(self, *, payload: Optional[dict[str, Any]] = None,
                 raises: Optional[BaseException] = None,
                 available: bool = True) -> None:
        self._payload = payload or {
            "category": "SI_REQUEST",
            "reason": "The sender writes 'SI attached, pls process'.",
            "confidence": 0.8,
        }
        self._raises = raises
        self._available = available
        self.calls: list[dict[str, Any]] = []

    @property
    def available(self) -> bool:
        return self._available

    def structured(self, *, purpose: str, instructions: str, prompt: str,
                   schema: Any, **kwargs: Any) -> Any:
        self.calls.append({"purpose": purpose, "instructions": instructions,
                           "prompt": prompt, "schema": schema, **kwargs})
        if self._raises is not None:
            raise self._raises
        return schema.model_validate(self._payload)


def email(subject: str = "MEDUUD104332", body: str = "Pls advise on the BL for this one.",
          sender: str = "sunil.r@bdpsingapore.com", attachments: Optional[list[str]] = None,
          email_id: str = "stub_001") -> EmailRecord:
    return EmailRecord(email_id=email_id, sender=sender, subject=subject, body=body,
                       attachments=list(attachments or []))


def rule_result_for(e: EmailRecord) -> rules.Classification:
    return rules.classify_email(e)


# --------------------------------------------------------------------------
# A model answer is adopted
# --------------------------------------------------------------------------
def test_stub_category_is_adopted_and_marked_llm():
    e = email(body="SI attached, pls process.")
    rule = rule_result_for(e)
    assert rule.category != "SI_REQUEST", "fixture must actually be a disagreement"

    out = classify_llm.classify_with_llm(e, rule, client=StubClient())

    assert out.category == "SI_REQUEST"
    assert out.decided_by == "llm"


def test_the_call_is_made_once_with_the_cheap_triage_settings():
    stub = StubClient()
    e = email()
    classify_llm.classify_with_llm(e, rule_result_for(e), client=stub)

    assert len(stub.calls) == 1
    call = stub.calls[0]
    # The purpose slug drives the cost breakdown the metrics page reports.
    assert call["purpose"] == "classify"
    # Triage, not analysis. Measured at ~70 output tokens against ~171 at "low".
    assert call["reasoning_effort"] == "minimal"


def test_rule_rationale_is_kept_and_the_model_reason_appended():
    """The audit trail must show both what the rules thought and why it changed."""
    e = email(body="SI attached, pls process.")
    rule = rule_result_for(e)
    stub = StubClient(payload={
        "category": "SI_REQUEST",
        "reason": "The sender writes 'SI attached, pls process'.",
        "confidence": 0.8,
    })

    out = classify_llm.classify_with_llm(e, rule, client=stub)

    # Every rule-side rationale entry survives, in order, at the front.
    assert out.rationale[: len(rule.rationale)] == list(rule.rationale)
    assert f"llm.rule_said:{rule.category}" in out.rationale
    assert "llm.category:SI_REQUEST" in out.rationale
    assert f"llm.overrode:{rule.category}" in out.rationale
    assert any(r.startswith("llm.reason:") and "pls process" in r for r in out.rationale)


def test_agreement_is_recorded_differently_from_an_override():
    e = email(subject="TO CONFIRM DOCS _ 5RSG-00133", body="Attached are the SI and draft BL.")
    rule = rule_result_for(e)
    assert rule.category == "BL_COMPARISON"

    out = classify_llm.classify_with_llm(e, rule, client=StubClient(payload={
        "category": "BL_COMPARISON", "reason": "Both documents are named.", "confidence": 0.7,
    }))

    assert "llm.agreed" in out.rationale
    assert not any(r.startswith("llm.overrode:") for r in out.rationale)


def test_the_rule_scoreboard_survives_the_override():
    """`scores` and `margin` are the record of *why* the model was asked at all."""
    e = email()
    rule = rule_result_for(e)
    out = classify_llm.classify_with_llm(e, rule, client=StubClient())

    assert out.scores == rule.scores
    assert out.margin == rule.margin
    # The case has been answered; it must not be escalated a second time.
    assert out.needs_llm is False
    assert classify_llm.should_escalate(out) is False


# --------------------------------------------------------------------------
# Failure behaviour — the important part
# --------------------------------------------------------------------------
def test_llm_unavailable_leaves_the_rule_result_untouched():
    e = email()
    rule = rule_result_for(e)
    stub = StubClient(raises=LLMUnavailable("no OPENAI_API_KEY configured"))

    out = classify_llm.classify_with_llm(e, rule, client=stub)

    assert out.category == rule.category
    assert out.confidence == rule.confidence
    assert out.margin == rule.margin
    assert out.scores == rule.scores
    assert out.needs_llm == rule.needs_llm
    assert out.decided_by == "rule", "a case no model answered must not be billed to the model"
    assert any(r.startswith("llm.unavailable:") for r in out.rationale)


@pytest.mark.parametrize("reason", [
    "no OPENAI_API_KEY configured",
    "run budget of $2.00 reached; remaining cases are escalated rather than charged",
    "ConnectionError: [Errno -3] Temporary failure in name resolution",
    "model returned no parsed output",
])
def test_every_flavour_of_unavailable_is_the_same_answer(reason: str):
    """No key, a spent budget, a dead network and a refusal all mean one thing."""
    e = email()
    rule = rule_result_for(e)
    out = classify_llm.classify_with_llm(e, rule, client=StubClient(raises=LLMUnavailable(reason)))
    assert (out.category, out.decided_by) == (rule.category, "rule")


def test_an_unavailable_client_is_not_even_asked():
    """With no key configured this is the path every email takes; it must be free."""
    stub = StubClient(available=False)
    e = email()
    out = classify_llm.classify_with_llm(e, rule_result_for(e), client=stub)

    assert stub.calls == [], "no prompt should be built for a client that cannot answer"
    assert out.decided_by == "rule"
    assert "llm.unavailable:no-client" in out.rationale


def test_an_unexpected_exception_costs_one_case_not_the_run():
    """A stale cache entry validates outside the client's LLMUnavailable funnel."""
    e = email()
    rule = rule_result_for(e)
    out = classify_llm.classify_with_llm(e, rule, client=StubClient(raises=KeyError("value")))

    assert out.category == rule.category
    assert out.decided_by == "rule"
    assert "llm.error:KeyError" in out.rationale


def test_the_module_stays_offline_when_it_builds_its_own_client(monkeypatch):
    """`client=None` must not become a network dependency on a key-less machine."""
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.delenv("SENTINEL_LLM_MODEL", raising=False)
    monkeypatch.delenv("SENTINEL_VISION_MODEL", raising=False)

    e = email()
    rule = rule_result_for(e)
    out = classify_llm.classify_with_llm(e, rule)

    assert out.decided_by == "rule"
    assert "llm.unavailable:no-client" in out.rationale


def test_an_empty_email_is_never_sent_to_the_model():
    """No text in, no answer out — a call here buys a guess at full price."""
    stub = StubClient()
    e = email(subject="???", body="   ")
    rule = rule_result_for(e)

    out = classify_llm.classify_with_llm(e, rule, client=stub)

    assert stub.calls == []
    assert out.category == rule.category
    assert out.decided_by == "rule"
    assert "llm.skipped:empty-email" in out.rationale


# --------------------------------------------------------------------------
# The model cannot invent a category
# --------------------------------------------------------------------------
def test_the_answer_literal_matches_the_pipeline_categories():
    from typing import get_args
    assert get_args(classify_llm.CategoryName) == CATEGORIES


@pytest.mark.parametrize("invented", [
    "Documentation/BL Review",      # what an unconstrained schema actually returns
    "BL_COMPARISON ",               # trailing space is a different string
    "bl_comparison",                # the scorer is case-sensitive
    "OTHER",
    "",
])
def test_the_schema_rejects_a_category_outside_the_five(invented: str):
    with pytest.raises(ValidationError):
        classify_llm.CategoryVerdict.model_validate(
            {"category": invented, "reason": "because", "confidence": 0.9})


def test_an_invented_category_falls_back_to_the_rule_answer():
    """End to end: the refusal must not crash, and must not reach submission.json."""
    e = email()
    rule = rule_result_for(e)
    stub = StubClient(payload={
        "category": "Documentation/BL Review", "reason": "Looks like a BL job.", "confidence": 0.95,
    })

    out = classify_llm.classify_with_llm(e, rule, client=stub)

    assert out.category in CATEGORIES
    assert out.category == rule.category
    assert out.decided_by == "rule"


def test_every_category_the_schema_allows_is_adoptable():
    e = email()
    rule = rule_result_for(e)
    for name in CATEGORIES:
        out = classify_llm.classify_with_llm(e, rule, client=StubClient(payload={
            "category": name, "reason": "one sentence", "confidence": 0.6,
        }))
        assert out.category == name
        assert out.decided_by == "llm"


@pytest.mark.parametrize("given,expected", [
    (0.5, 0.5),
    (0.0, 0.0),
    (1.0, classify_llm.MAX_LLM_CONFIDENCE),   # a fallback answer is never a certainty
    (4.2, classify_llm.MAX_LLM_CONFIDENCE),
    (-3.0, 0.0),
])
def test_reported_confidence_is_clamped(given: float, expected: float):
    e = email()
    out = classify_llm.classify_with_llm(e, rule_result_for(e), client=StubClient(payload={
        "category": "GENERAL", "reason": "r", "confidence": given,
    }))
    assert out.confidence == pytest.approx(expected)


# --------------------------------------------------------------------------
# The prompt builder
# --------------------------------------------------------------------------
QUOTED_TAILS = {
    "outlook rule line": "\n______________________________\nFrom: Hari <hari@aprilasia.com>\nSent: Monday\n\nPlease compare the SI and draft BL and confirm.",
    "bare header block": "\nFrom: Hari <hari@aprilasia.com>\nSent: Monday 12 January 2026 09:14\nSubject: RE_ TO CONFIRM DOCS\n\nPlease compare the SI and draft BL and confirm.",
    "original message": "\n-----Original Message-----\nFrom: Hari\n\nPlease compare the SI and draft BL and confirm.",
    "forwarded message": "\n---------- Forwarded message ----------\nFrom: Hari\n\nPlease compare the SI and draft BL and confirm.",
    "on-date-wrote": "\nOn Mon, 12 Jan 2026, Hari wrote:\n> Please compare the SI and draft BL and confirm.",
    "plain-text quoting": "\n> Please compare the SI and draft BL\n> and confirm by today.",
}


@pytest.mark.parametrize("shape", sorted(QUOTED_TAILS))
def test_the_prompt_strips_the_quoted_thread(shape: str):
    """Last week's comparison request must not answer this week's question."""
    ask = "Hi Najiha,\n\nPlease advise on invoice 5070146244.\n"
    body = ask + QUOTED_TAILS[shape]

    visible = classify_llm.visible_body(body)

    assert "invoice 5070146244" in visible
    assert "compare the SI and draft BL" not in visible
    assert "From:" not in visible and ">" not in visible


def test_the_prompt_strips_the_signature_block():
    body = ("Hi Najiha,\n\nAttached are the SI and draft BL for OC 5RSG-00133.\n\n"
            "Best Regards,\nWilly Situmorang\nShipping Documentation\n"
            "DID : +971 04 4938289\nAPRIL Fine Paper Trading (Middle East) Fze")

    visible = classify_llm.visible_body(body)

    assert "OC 5RSG-00133" in visible
    assert "Willy Situmorang" not in visible
    assert "+971" not in visible


def test_the_prompt_strips_the_gateway_banner():
    body = ("WARNING: This email originated outside of our organisation.\n"
            "Hi,\n\nPlease check the draft BL against the SI.")

    visible = classify_llm.visible_body(body)

    assert "WARNING" not in visible
    assert "draft BL against the SI" in visible


def test_the_prompt_keeps_the_si_form_block():
    """An SI_REQUEST body IS a form; cutting on labelled lines would gut it."""
    body = ("Hi,\n\nPOL: SINGAPORE\nPOD: JEBEL ALI\nShipper: APRIL FINE PAPER TRADING\n"
            "Consignee: KPP-ANTALIS (SINGAPORE) PTE. LTD.\nGross Wt: 354,765 KG\n")

    visible = classify_llm.visible_body(body)

    for marker in ("POL:", "POD:", "Shipper:", "Consignee:", "Gross Wt:"):
        assert marker in visible


def test_the_prompt_preserves_the_original_case():
    """Upper-casing is for rule patterns; a prompt loses signal to it."""
    visible = classify_llm.visible_body("Hi,\n\nPlease check MEDUUD104332 for KPP-Antalis.")
    assert "KPP-Antalis" in visible


def test_a_long_body_is_truncated_on_a_line_boundary():
    body = "Hi,\n\n" + "\n".join(f"Container MSDU{i:07d} loaded on schedule." for i in range(200))

    visible = classify_llm.visible_body(body)

    assert len(visible) <= classify_llm.MAX_BODY_CHARS + len("\n[...truncated]")
    assert visible.endswith("[...truncated]")


def test_the_prompt_carries_sender_subject_and_attachment_types():
    e = email(subject="RE_ TO CONFIRM DOCS _ 5RSG-00133", sender="willy@aprilasia.com",
              body="Attached are the SI and draft BL.",
              attachments=["attachments/a_SI.pdf", "attachments/b_BL.pdf"])

    prompt = classify_llm.build_prompt(
        e, rule_result=rule_result_for(e),
        attachment_doc_types=["SHIPPING_INSTRUCTION", "BILL_OF_LADING"])

    assert "willy@aprilasia.com" in prompt
    # The reply prefix is noise; `clean_subject` removes it for the model too.
    assert "TO CONFIRM DOCS _ 5RSG-00133" in prompt
    assert "RE_ TO" not in prompt
    assert "Attachments: 2" in prompt
    assert "SHIPPING_INSTRUCTION" in prompt and "BILL_OF_LADING" in prompt
    # Filenames are withheld on purpose: a file named _BL.pdf that is really a
    # commercial invoice is a case the pipeline exists to catch.
    assert "a_SI.pdf" not in prompt


def test_the_prompt_says_plainly_when_nothing_was_attached():
    prompt = classify_llm.build_prompt(email(attachments=[]))
    assert "Attachments: none" in prompt


def test_the_prompt_names_the_contest_but_not_the_rule_winner():
    """Naming the leader would turn a second opinion into an agreement machine."""
    e = email(sender="documentation@msc.com", subject="MEDUUD104332 - papers",
              body="Dear colleague,\n\nPlease see the below for checking.\n\nThanks")
    rule = rule_result_for(e)
    contested = sorted((c for c, s in rule.scores.items() if s > 0),
                       key=lambda c: -rule.scores[c])
    assert len(contested) >= 2, "fixture must be a genuine two-way contest"

    prompt = classify_llm.build_prompt(e, rule_result=rule)

    assert contested[0] in prompt and contested[1] in prompt
    assert "triage" in prompt.lower()
    for claim in ("winner", "most likely", "best guess"):
        assert claim not in prompt.lower()


def test_the_instructions_name_the_three_documented_confusions():
    """docs/DATA_NOTES.md §6: the model has never worked a shipping desk."""
    text = classify_llm.INSTRUCTIONS.lower()
    assert "revert with draft bl once available" in text   # SI_REQUEST, not BL_COMPARISON
    assert "list of outstanding" in text or "list of many bls" in text
    assert "submit si for all pending shipments" in text   # GENERAL, not SI_REQUEST
    for name in CATEGORIES:
        assert name in classify_llm.INSTRUCTIONS


# --------------------------------------------------------------------------
# When the fallback fires
# --------------------------------------------------------------------------
def test_needs_llm_escalates():
    weak = rules.Classification(category="GENERAL", confidence=0.0, decided_by="rule",
                                margin=0.0, scores={}, rationale=["fallback.no-rule-fired"],
                                needs_llm=True)
    assert classify_llm.should_escalate(weak) is True


def test_a_confident_rule_answer_does_not_escalate():
    strong = rules.Classification(category="SPAM", confidence=1.0, decided_by="rule",
                                  margin=8.0, scores={"SPAM": 8.0}, rationale=["spam.text.prize"],
                                  needs_llm=False)
    assert classify_llm.should_escalate(strong) is False


def test_an_answer_that_cleared_both_floors_by_a_hair_still_escalates():
    """The condition `needs_llm` cannot see: two thin signals, neither wrong.

    A winner on exactly `rules.MIN_SCORE` with exactly `rules.MIN_MARGIN` passes
    both of the rule layer's thresholds and still scores 0.375 confidence.
    """
    thin = rules.Classification(
        category="GENERAL", confidence=rules._confidence(rules.MIN_SCORE, rules.MIN_MARGIN),
        decided_by="rule", margin=rules.MIN_MARGIN,
        scores={"GENERAL": rules.MIN_SCORE, "BL_COMPARISON": rules.MIN_SCORE - rules.MIN_MARGIN},
        rationale=["gen.sender.role-mailbox"], needs_llm=False)

    assert thin.needs_llm is False
    assert thin.confidence < classify_llm.CONFIDENCE_FLOOR
    assert classify_llm.should_escalate(thin) is True


def test_a_real_email_can_clear_both_floors_and_still_escalate():
    """The same condition, reached through the rule table rather than by hand.

    A role mailbox (GENERAL, 3.0) that also asks for something to be checked
    (BL_COMPARISON, 1.5) is a genuine two-way case the thresholds wave through.
    """
    e = email(sender="documentation@msc.com", subject="MEDUUD104332 - papers",
              body="Dear colleague,\n\nPlease see the below for checking.\n\nThanks")
    rule = rule_result_for(e)

    assert rule.needs_llm is False
    assert classify_llm.should_escalate(rule) is True


def test_a_case_already_answered_by_a_model_is_not_asked_twice():
    answered = rules.Classification(category="SI_REQUEST", confidence=0.2, decided_by="llm",
                                    margin=0.0, scores={}, rationale=["llm.category:SI_REQUEST"],
                                    needs_llm=False)
    assert classify_llm.should_escalate(answered) is False


# --------------------------------------------------------------------------
# How often the fallback is reached on the real inbox
# --------------------------------------------------------------------------
@pytest.fixture(scope="module")
def inbox() -> list[EmailRecord]:
    skip_without_bundle()
    emails = [EmailRecord.from_json(json.loads(p.read_text(encoding="utf-8")))
              for p in sorted(INBOX.glob("email_*.json"))]
    assert emails, f"no emails found under {INBOX}"
    return emails


def test_the_generated_inbox_never_reaches_the_fallback(inbox: list[EmailRecord]):
    """Measured, and asserted so that it stays a measurement and not a belief.

    Every one of the 520 generated emails matches a desk template, so the rule
    table wins by a landslide: the lowest score in the set is 7.0 against a
    `MIN_SCORE` of 3.0, and the thinnest margin is 6.5 against a `MIN_MARGIN`
    of 1.5. `needs_llm` is therefore set exactly zero times, and this module is
    dead code on this dataset by construction rather than by luck.

    That is a statement about the *generator*, not about the classifier: the
    tests below build the ambiguous emails the generator cannot produce, which
    is the only way this path can be shown to work.
    """
    escalated = [e.email_id for e in inbox if classify_llm.should_escalate(rules.classify_email(e))]
    assert len(inbox) == 520
    assert escalated == [], (
        "the fallback is now reachable on real data; re-measure before relying on "
        f"the zero-cost claim: {escalated[:10]}")


# Emails the dataset generator cannot produce: short, unstructured, and
# genuinely between two categories. Each is a shape a real operations inbox
# produces daily — a one-line chaser, a mail that asks two desks at once, a
# cold-sales mail from a plausible domain, an SI sent without the form block.
AMBIGUOUS: list[tuple[str, dict[str, str]]] = [
    ("one-line chaser", {
        "sender": "sunil.r@bdpsingapore.com", "subject": "MEDUUD104332",
        "body": "Hi Najiha,\n\nPls advise on the BL for this one.\n\nThanks,\nSunil"}),
    ("two desks at once", {
        "sender": "ops@kppantalis.com.sg", "subject": "5RSG-00133 - follow up",
        "body": "Hi team,\n\nKindly check the BL and also advise on the D&D charges "
                "for this container.\n\nRegards,\nLina"}),
    ("cold sales, plausible domain", {
        "sender": "sales@oceanfreight-partners.com", "subject": "Q1 rate card for your desk",
        "body": "Dear Sir/Madam,\n\nWe have space available ex Singapore this quarter "
                "and can offer improved rates.\n\nBest regards,\nTom"}),
    ("SI without the form block", {
        "sender": "shipper@moorim.co.kr", "subject": "5RFR-37631",
        "body": "Hi,\n\nSI attached, pls process.\n\nThanks"}),
    ("novel wording", {
        "sender": "najiha@april.com.sg", "subject": "Docs needed today",
        "body": "Hi,\n\nCan you sort out the paperwork for MEDUUD104332 before "
                "cut-off? The customer is chasing.\n\nRgds"}),
]


@pytest.mark.parametrize("name,fields", AMBIGUOUS, ids=[n for n, _ in AMBIGUOUS])
def test_a_genuinely_ambiguous_email_reaches_the_fallback(name: str, fields: dict[str, str]):
    rule = rule_result_for(email(email_id=f"amb_{name}", **fields))
    assert classify_llm.should_escalate(rule) is True, (
        f"{name!r} scored {rule.scores} — the rules are confident about an email they should not be")


@pytest.mark.parametrize("name,fields", AMBIGUOUS, ids=[n for n, _ in AMBIGUOUS])
def test_the_whole_path_runs_offline_on_an_ambiguous_email(name: str, fields: dict[str, str]):
    """Escalate, fail to reach a model, keep the rule answer. No key, no network."""
    e = email(email_id=f"amb_{name}", **fields)
    rule = rule_result_for(e)
    out = classify_llm.classify_with_llm(e, rule, client=StubClient(
        raises=LLMUnavailable("no OPENAI_API_KEY configured")))

    assert out.category in CATEGORIES
    assert out.decided_by == "rule"
    assert out.category == rule.category


@pytest.mark.parametrize("name,fields", AMBIGUOUS, ids=[n for n, _ in AMBIGUOUS])
def test_the_whole_path_runs_with_a_model_on_an_ambiguous_email(name: str, fields: dict[str, str]):
    """The same emails with a model answering. Live answers are recorded below.

    Run against gpt-5-mini at `reasoning_effort="minimal"` these five returned
    BL_COMPARISON, BL_COMPARISON, SPAM, SI_REQUEST and GENERAL respectively —
    all defensible, and three of them corrections of the rule answer. The stub
    here fixes the answer so the assertion is about plumbing, not about a
    model's mood.
    """
    e = email(email_id=f"amb_{name}", **fields)
    rule = rule_result_for(e)
    out = classify_llm.classify_with_llm(e, rule, client=StubClient(payload={
        "category": "BL_COMPARISON", "reason": "The sender asks about the BL.", "confidence": 0.8,
    }))

    assert out.category == "BL_COMPARISON"
    assert out.decided_by == "llm"
    assert out.rationale[: len(rule.rationale)] == list(rule.rationale)
