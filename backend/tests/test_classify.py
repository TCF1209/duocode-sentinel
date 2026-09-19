"""Tests for Stage 1: `classify/rules.py` and `classify/intent.py`.

Everything here runs against the real inbox in `data/bundle/inbox/`. Emails are
located by the *shape* of their subject or body — never by a hard-coded id
alone — so that a test says what property it is protecting, and so that the
suite keeps working if the sample is regenerated.

`data/_grader/` is never opened. The reference facts these tests assert are the
ones documented in `docs/DATA_NOTES.md` (the per-category counts) plus
invariants that the inbox itself makes visible (a role mailbox broadcasts; a
throwaway domain sends bait).
"""
from __future__ import annotations

import collections
import json
from typing import Callable, Optional

import pytest

from conftest import DATA
from sdoc.classify import intent as intent_mod
from sdoc.classify import rules
from sdoc.schema import CATEGORIES, DOC_BL, DOC_COO, DOC_INVOICE, DOC_SI, EmailRecord

INBOX = DATA / "inbox"


# --------------------------------------------------------------------------
# Fixtures / helpers
# --------------------------------------------------------------------------
@pytest.fixture(scope="module")
def inbox() -> list[EmailRecord]:
    emails = [
        EmailRecord.from_json(json.loads(p.read_text(encoding="utf-8")))
        for p in sorted(INBOX.glob("email_*.json"))
    ]
    assert emails, f"no emails found under {INBOX}"
    return emails


def pick(
    inbox: list[EmailRecord],
    predicate: Callable[[EmailRecord], bool],
    *,
    limit: Optional[int] = None,
) -> list[EmailRecord]:
    hits = [e for e in inbox if predicate(e)]
    assert hits, "no email in the bundle matches this shape"
    return hits[:limit] if limit else hits


def one(inbox, predicate) -> EmailRecord:
    return pick(inbox, predicate, limit=1)[0]


def subject_starts(prefix: str):
    return lambda e: rules.clean_subject(e.subject).startswith(prefix)


def body_has(fragment: str):
    return lambda e: fragment.upper() in (e.body or "").upper()


def category_of(email: EmailRecord, **kw) -> str:
    return rules.classify_email(email, **kw).category


# --------------------------------------------------------------------------
# The rule table itself is a deliverable — it must stay readable and sane.
# --------------------------------------------------------------------------
def test_rule_table_is_well_formed():
    names = [r.name for r in rules.RULES]
    assert len(names) == len(set(names)), "rule names must be unique — the UI keys off them"
    for r in rules.RULES:
        assert r.category in CATEGORIES, r.name
        assert r.field in {"subject", "body", "body_head", "sender", "any"}, r.name
        assert r.weight > 0, r.name
        assert r.why.strip(), f"{r.name} has no explanation; an operator must be able to read it"
        assert (r.pattern is not None) ^ (r.counter is not None), r.name


def test_every_category_has_rules():
    covered = {r.category for r in rules.RULES}
    assert covered == set(CATEGORIES)


# --------------------------------------------------------------------------
# One representative real email per category
# --------------------------------------------------------------------------
def test_bl_comparison_representative(inbox):
    email = one(inbox, lambda e: rules.clean_subject(e.subject).startswith("TO CONFIRM DOCS"))
    result = rules.classify_email(email)
    assert result.category == "BL_COMPARISON"
    assert result.decided_by == "rule"
    assert not result.needs_llm
    assert result.rationale


def test_si_request_representative(inbox):
    email = one(inbox, body_has("Please find Shipping instruction for"))
    assert category_of(email) == "SI_REQUEST"


def test_invoice_query_representative(inbox):
    email = one(inbox, body_has("is the THC / local charge included"))
    assert category_of(email) == "INVOICE_QUERY"


def test_general_representative(inbox):
    email = one(inbox, body_has("This is an automated notification"))
    assert category_of(email) == "GENERAL"


def test_spam_representative(inbox):
    email = one(inbox, body_has("gift card"))
    assert category_of(email) == "SPAM"


# --------------------------------------------------------------------------
# The confusions named in docs/DATA_NOTES.md §6. One test each, on purpose.
# --------------------------------------------------------------------------
def test_reminder_submit_si_is_general_not_si_request(inbox):
    """'_Reminder_Paper - Submit SI & AED_18-01-2026' says 'Submit SI' and is GENERAL.

    Nobody is sending or asking for one shipment's SI; it is a standing
    reminder to the whole desk.
    """
    emails = pick(inbox, subject_starts("_REMINDER_"))
    for email in emails:
        result = rules.classify_email(email)
        assert result.category == "GENERAL", (email.email_id, email.subject, result.scores)
        assert result.scores["SI_REQUEST"] < result.scores["GENERAL"]


def test_reminder_body_is_general_even_under_a_neutral_subject(inbox):
    """The body half of the same trap: 'Please submit SI & AED for all pending
    shipments by end of day' must not read as a shipping instruction."""
    emails = pick(inbox, body_has("submit SI & AED for all pending shipments"))
    for email in emails:
        assert category_of(email) == "GENERAL", email.email_id


def test_outstanding_bl_list_is_general_not_bl_comparison(inbox):
    """'APRIL PAPER - List of Outstanding BL (BDP SG)' — many BLs, no draft to check."""
    emails = pick(inbox, lambda e: "OUTSTANDING BL" in rules.clean_subject(e.subject))
    for email in emails:
        result = rules.classify_email(email)
        assert result.category == "GENERAL", (email.email_id, email.subject, result.scores)
        assert result.scores["BL_COMPARISON"] < result.scores["GENERAL"]


def test_pending_bl_release_is_general_not_bl_comparison(inbox):
    emails = pick(inbox, subject_starts("PENDING BL RELEASE"))
    for email in emails:
        result = rules.classify_email(email)
        assert result.category == "GENERAL", (email.email_id, email.subject, result.scores)
        assert result.scores["BL_COMPARISON"] < result.scores["GENERAL"]


def test_circular_body_mentioning_attached_bl_is_general(inbox):
    """'Please find attached the list of outstanding BL (BDP SG)' has the words
    'attached' and 'BL' next to each other and is still GENERAL."""
    emails = pick(inbox, body_has("attached the list of outstanding BL"))
    for email in emails:
        assert category_of(email) == "GENERAL", email.email_id


def test_bare_draft_bl_in_an_si_body_does_not_become_bl_comparison(inbox):
    """Every SI_REQUEST body closes with 'Please revert with draft BL once
    available'. The bare phrase must not route the email to BL_COMPARISON."""
    emails = pick(inbox, body_has("revert with draft BL once available"))
    assert len(emails) > 50, "this closing line should be on every SI_REQUEST body"
    for email in emails:
        result = rules.classify_email(email)
        assert result.category == "SI_REQUEST", (email.email_id, result.scores)
        assert result.scores["SI_REQUEST"] > result.scores["BL_COMPARISON"]


def test_leading_token_separates_coded_si_from_coded_bl_subject(inbox):
    """'SI - <blno> - DIRECT(MSC) - ...' is SI_REQUEST;
    'AIE - <port> - MSC(<blno>) - ...' is BL_COMPARISON. Only the first token
    differs in kind, and that is what the rules key off."""
    coded_si = pick(inbox, subject_starts("SI - "))
    coded_bl = pick(inbox, lambda e: rules.clean_subject(e.subject).split(" - ")[0]
                    in {"AIE", "AFPTME", "AFRT", "AFEMY"})
    for email in coded_si:
        assert category_of(email) == "SI_REQUEST", (email.email_id, email.subject)
    for email in coded_bl:
        assert category_of(email) == "BL_COMPARISON", (email.email_id, email.subject)


def test_desk_code_shape_rule_does_not_claim_a_coded_si_subject():
    """The generalised '<DESK> - <PORT> - <CARRIER>(<blno>)' rule must not fire
    on 'SI - <blno> - DIRECT(MSC)': the second field there carries digits."""
    rule = next(r for r in rules.RULES if r.name == "bl.subject.desk-code-shape")
    assert rule.pattern.search("AIE - JEBEL_ALI - MSC(MEDUUD123456) - 5RAE-00543 - X")
    assert rule.pattern.search("XYZ - LONG BEACH_US - EVER(EGLV433335384951) - 5RSG-19787")
    assert not rule.pattern.search("SI - MEDUUD104332 - DIRECT(MSC) - 5ALT-12567 - KOPER")


def test_boilerplate_does_not_decide_the_category(inbox):
    """Bodies carry an 'external sender' banner, a signature block with a phone
    number, and a forwarded thread. None of it may outvote the real ask."""
    banner = one(inbox, body_has("WARNING: This email originated outside"))
    cleaned = rules.clean_body(banner.body)
    assert "ORIGINATED OUTSIDE" not in cleaned

    quoted = one(inbox, body_has("\n______________________________\nFrom:"))
    cleaned = rules.clean_body(quoted.body)
    assert "FROM:" not in cleaned
    assert "PLEASE FOLLOW THE PREVIOUS INSTRUCTION" not in cleaned

    signed = one(inbox, body_has("DID : +971"))
    cleaned = rules.clean_body(signed.body)
    assert "DID :" not in cleaned
    assert "WWW.APRILASIA.COM" not in cleaned


def test_invoice_query_survives_a_quoted_shipping_thread(inbox):
    """A one-line money question whose quoted tail is another conversation."""
    emails = pick(inbox, lambda e: body_has("Query on invoice")(e)
                  and "From:" in (e.body or ""))
    for email in emails:
        assert category_of(email) == "INVOICE_QUERY", email.email_id


def test_spam_from_a_no_reply_address_is_not_general(inbox):
    """'no-reply@parcel-track.co' matches the role-mailbox shape that marks
    GENERAL. The suspicious domain plus the bait language must outweigh it."""
    emails = pick(inbox, lambda e: e.sender.lower().startswith("no-reply@")
                  and not e.sender.lower().endswith("aprilasia.com"))
    for email in emails:
        result = rules.classify_email(email)
        assert result.category == "SPAM", (email.email_id, email.sender, result.scores)
        assert result.scores["SPAM"] > result.scores["GENERAL"]


def test_phishing_about_an_invoice_is_spam_not_invoice_query(inbox):
    """'Re: Invoice payment - kindly confirm your bank details' contains the
    word 'invoice'; it is still advance-fee fraud."""
    emails = pick(inbox, body_has("reply with your bank details"))
    for email in emails:
        result = rules.classify_email(email)
        assert result.category == "SPAM", (email.email_id, result.scores)


# --------------------------------------------------------------------------
# Small-class protection — Stage 1 is macro-F1, so SPAM and GENERAL matter as
# much as BL_COMPARISON. These invariants are visible in the inbox itself.
# --------------------------------------------------------------------------
ROLE_MAILBOXES = {
    "hr@aprilasia.com",
    "noreply@aprilasia.com",
    "operations@aprilasia.com",
    "rpa.bot@aprilasia.com",
    "documentation@aprilasia.com",
}
THROWAWAY_DOMAINS = {
    "prize-claims.info",
    "parcel-track.co",
    "webmail-verify.co",
    "logistics-deals.biz",
    "crypto-invest.net",
    "secure-mailbox.org",
}


def test_every_role_mailbox_broadcast_is_general(inbox):
    emails = pick(inbox, lambda e: e.sender.lower() in ROLE_MAILBOXES)
    for email in emails:
        assert category_of(email) == "GENERAL", (email.email_id, email.subject)


def test_every_throwaway_domain_email_is_spam(inbox):
    emails = pick(inbox, lambda e: e.sender.lower().split("@")[-1] in THROWAWAY_DOMAINS)
    for email in emails:
        assert category_of(email) == "SPAM", (email.email_id, email.subject)


def test_unseen_spam_domain_is_still_caught():
    """The literal domain list plus the shape rules: a domain nobody has
    registered yet must still score as SPAM on 'suspicious domain + hype'."""
    email = EmailRecord(
        email_id="synthetic",
        sender="winner@prize-vault-2027.click",
        subject="CONGRATULATIONS!!! You have WON a $1,000 Gift Card - CLAIM NOW",
        body="Dear Valued Customer, click here within 24 hours to claim your prize.",
    )
    result = rules.classify_email(email)
    assert result.category == "SPAM", result.scores
    assert not result.needs_llm


def test_category_distribution_matches_data_notes(inbox):
    """docs/DATA_NOTES.md §1 documents the shape of the inbox. If the
    classifier's own distribution drifts from it, a class is being absorbed by
    a bigger neighbour — the exact failure macro-F1 punishes."""
    counts = collections.Counter(category_of(e) for e in inbox)
    assert counts == {
        "BL_COMPARISON": 220,
        "SI_REQUEST": 125,
        "INVOICE_QUERY": 75,
        "GENERAL": 60,
        "SPAM": 40,
    }


def test_whole_inbox_is_decided_by_rules(inbox):
    """No network, no API key: the rule layer alone must settle this inbox."""
    for email in inbox:
        result = rules.classify_email(email)
        assert result.category in CATEGORIES
        assert result.decided_by == "rule"
        assert 0.0 <= result.confidence <= 1.0
        assert result.margin >= 0.0
        assert not result.needs_llm, (email.email_id, result.scores)


# --------------------------------------------------------------------------
# Attachments are one more signal, never an override
# --------------------------------------------------------------------------
def test_attachment_pair_adds_evidence_without_changing_a_clear_answer(inbox):
    email = one(inbox, body_has("Attached are the SI and draft BL"))
    plain = rules.classify_email(email)
    with_docs = rules.classify_email(email, attachment_doc_types=[DOC_SI, DOC_BL])
    assert plain.category == with_docs.category == "BL_COMPARISON"
    assert with_docs.scores["BL_COMPARISON"] > plain.scores["BL_COMPARISON"]
    assert "attachments.si-bl-pair" in with_docs.rationale


def test_wrong_document_pair_does_not_flip_the_category(inbox):
    """'Please find attached the SI and the Commercial Invoice ... kindly
    confirm the BL is in order' is still BL_COMPARISON — it has to be, because
    `wrong_doc_type` is a BL_COMPARISON escalation reason."""
    emails = pick(inbox, body_has("Kindly confirm the BL is in order"))
    for email in emails:
        for pair in ([DOC_SI, DOC_INVOICE], [DOC_SI, DOC_COO], []):
            result = rules.classify_email(email, attachment_doc_types=pair)
            assert result.category == "BL_COMPARISON", (email.email_id, pair, result.scores)


def test_emails_with_no_attachments_still_classify(inbox):
    """96 of the 220 BL_COMPARISON emails carry nothing at all."""
    emails = pick(inbox, lambda e: not e.attachments and body_has("assist to send the draft BL")(e))
    for email in emails:
        assert category_of(email, attachment_doc_types=None) == "BL_COMPARISON"


# --------------------------------------------------------------------------
# Robustness — a classifier that raises takes the whole batch down
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "subject,body,sender",
    [
        ("", "", ""),
        ("", "Attached are the SI and draft BL for OC 5RSG-00133.", "a@b.com"),
        ("TO CONFIRM DOCS _ 5RSG-00133", "", "a@b.com"),
        ("   ", "\n\n\n", "   "),
        ("RE_ RE_ FW_ ", "Best Regards,\nSomebody", "a@b.com"),
        ("???", "???", "?"),
        ("Gross Weight毛重(KGS)", "中文内容", "x@y.z"),
        ("A" * 5000, "B " * 5000, "c@d.e"),
    ],
)
def test_classifier_never_raises(subject, body, sender):
    email = EmailRecord(email_id="edge", sender=sender, subject=subject, body=body)
    result = rules.classify_email(email)
    assert result.category in CATEGORIES
    assert 0.0 <= result.confidence <= 1.0
    assert set(result.scores) == set(CATEGORIES)
    detected = intent_mod.detect_intent(email)
    assert isinstance(detected.expects_attached_documents, bool)
    assert isinstance(detected.requests_draft, bool)


def test_empty_email_is_flagged_for_the_llm_rather_than_guessed():
    email = EmailRecord(email_id="edge", sender="", subject="", body="")
    result = rules.classify_email(email)
    assert result.needs_llm
    assert result.confidence == 0.0
    assert rules.is_empty(email)


def test_reply_prefixes_do_not_change_the_answer(inbox):
    email = one(inbox, subject_starts("TO CONFIRM DOCS"))
    for prefix in ("RE_ ", "RE: ", "FW_ ", "FWD: ", "RE_ FW_ "):
        echoed = EmailRecord(
            email_id=email.email_id, sender=email.sender,
            subject=prefix + email.subject, body=email.body,
        )
        assert category_of(echoed) == category_of(email)


# --------------------------------------------------------------------------
# The structured-SI-block signal reuses labels.py
# --------------------------------------------------------------------------
def test_si_block_marker_count_uses_label_resolution(inbox):
    email = one(inbox, body_has("Please find Shipping instruction for"))
    body = rules.clean_body(email.body)
    assert rules.count_si_block_markers(body) >= 5, body[:400]
    # A body with no form in it scores zero, which is what makes the count a
    # signal rather than noise.
    invoice = one(inbox, body_has("is the THC / local charge included"))
    assert rules.count_si_block_markers(rules.clean_body(invoice.body)) == 0


def test_si_block_ignores_labels_labels_py_excludes():
    """'Description of Goods:' and 'H.S.CODE:' sit inside the same block but are
    not one of the 7 compared fields, so they must not inflate the count."""
    block = "DESCRIPTION OF GOODS:\nPAPERBOARD\nH.S.CODE: 48109200\nVESSEL: MMSS 2507\n"
    assert rules.count_si_block_markers(block) == 0


# ==========================================================================
# intent.py — the zero-attachment disambiguation (DATA_NOTES §5a)
# ==========================================================================
def _variant_a(inbox) -> list[EmailRecord]:
    """A: 'Please assist to send the draft BL for <booking> for checking asap.'
    with nothing attached — we are asked to PRODUCE a draft."""
    return pick(inbox, lambda e: not e.attachments
                and "ASSIST TO SEND THE DRAFT BL" in (e.body or "").upper())


def _variant_b(inbox) -> list[EmailRecord]:
    """B: 'Please compare the SI and draft BL ... (attachments appear to have
    been dropped)' with nothing attached — the sender believes they attached."""
    return pick(inbox, lambda e: not e.attachments
                and "ATTACHMENTS APPEAR TO HAVE BEEN DROPPED" in (e.body or "").upper())


def test_variant_a_and_b_are_indistinguishable_by_attachment_count(inbox):
    """The premise of the whole module: counting cannot separate these."""
    a, b = _variant_a(inbox), _variant_b(inbox)
    assert all(len(e.attachments) == 0 for e in a + b)
    assert {rules.classify_email(e).category for e in a + b} == {"BL_COMPARISON"}


def test_variant_a_asks_us_to_produce_a_draft(inbox):
    for email in _variant_a(inbox):
        detected = intent_mod.detect_intent(email)
        assert detected.requests_draft is True, email.email_id
        assert detected.expects_attached_documents is False, (email.email_id, detected.rationale)
        assert detected.confidence > 0.5


def test_variant_b_believes_documents_were_attached(inbox):
    for email in _variant_b(inbox):
        detected = intent_mod.detect_intent(email)
        assert detected.expects_attached_documents is True, (email.email_id, detected.rationale)
        assert detected.requests_draft is False, email.email_id
        assert "attach.attachments-dropped" in detected.rationale


def test_draft_bl_still_missing_also_expects_documents(inbox):
    """The one-attachment sibling of B: 'the draft BL is still missing'."""
    emails = pick(inbox, body_has("the draft BL is still missing"))
    for email in emails:
        detected = intent_mod.detect_intent(email)
        assert detected.expects_attached_documents is True, (email.email_id, detected.rationale)


def test_assist_to_check_is_not_assist_to_send(inbox):
    """'Pls assist to check the draft BL against the SI' shares four words with
    variant A and means the opposite."""
    emails = pick(inbox, body_has("assist to check the draft BL against the SI"))
    for email in emails:
        detected = intent_mod.detect_intent(email)
        assert detected.expects_attached_documents is True, (email.email_id, detected.rationale)
        assert detected.requests_draft is False, email.email_id


def test_attached_pair_bodies_expect_documents(inbox):
    for email in pick(inbox, body_has("Attached are the SI and draft BL"), limit=15):
        assert intent_mod.detect_intent(email).expects_attached_documents is True


def test_circular_attachment_is_not_a_document_claim(inbox):
    """'Please find attached the list of outstanding BL' says 'attached' and
    'BL' and claims no shipping document — the noun after 'attached' is what
    makes the difference."""
    for email in pick(inbox, body_has("attached the list of outstanding BL"), limit=10):
        assert intent_mod.detect_intent(email).expects_attached_documents is False, email.email_id


def test_ambiguity_resolves_to_not_expecting_documents():
    """Stated bias: escalating a routine 'please send me a draft' wastes an
    operator's time, so a tie must not claim documents were attached."""
    email = EmailRecord(
        email_id="synthetic",
        sender="a@b.com",
        subject="Draft BL MMSS 2507 V.257087E NHAVA SHEVA - amend BL 058",
        body="Please assist to send the draft BL for PSGSE9638346; attached are the SI and "
             "draft BL from the previous round.",
    )
    detected = intent_mod.detect_intent(email)
    assert detected.requests_draft is True
    # Both intents are evidenced; the safe reading wins and the confidence says so.
    assert detected.confidence < 0.8


def test_intent_on_a_silent_body_claims_nothing():
    email = EmailRecord(email_id="edge", sender="a@b.com", subject="FYI", body="")
    detected = intent_mod.detect_intent(email)
    assert detected.expects_attached_documents is False
    assert detected.requests_draft is False
    assert detected.confidence == 0.0
    assert detected.rationale == ["intent.no-signal"]


def test_intent_signal_tables_are_well_formed():
    names = [s.name for table in intent_mod.SIGNALS.values() for s in table]
    assert len(names) == len(set(names))
    for table in intent_mod.SIGNALS.values():
        for signal in table:
            assert signal.weight > 0
            assert signal.field in {"body", "subject"}
            assert signal.why.strip()
