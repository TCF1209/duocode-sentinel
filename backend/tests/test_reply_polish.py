"""The reply draft's wording pass: a model may reword courtesy, never facts.

Two guards are under test (backend/api/reply_polish.py). The structural one:
the request carries only the greeting and the closing, so the model is never
shown a case value, a claim or the request. The check on what comes back: a
rewrite that adds anything that reads as a value, a claim or a request is
refused and the template stands.

No network: every model here is a fake that returns what the test tells it to.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from fastapi.testclient import TestClient  # noqa: E402

from api import main as api_main  # noqa: E402
from api.reply_polish import PolishRequest, check_wording, polish  # noqa: E402
from sdoc.llm.client import LLMUnavailable  # noqa: E402
from sdoc.pipeline import Pipeline, PipelineConfig  # noqa: E402
from sdoc.schema import CaseResult, EmailRecord  # noqa: E402

# The greetings and closings web/lib/reply-draft.ts writes, verbatim. If the
# model hands one back unchanged it must be adopted: a guard that refuses the
# template itself would refuse everything.
TEMPLATE_LINES = ["Thank you for your email.", "Thank you.", "Thank you for your patience."]

_GREETING = "Thank you for your email."
_CLOSING = "Thank you."


class _FakeModel:
    def __init__(self, greeting: str = "", closing: str = "", error: Exception | None = None) -> None:
        self.settings = SimpleNamespace(model="fake-model")
        self.available = True
        self.greeting, self.closing, self.error = greeting, closing, error
        self.calls: list[dict] = []

    def structured(self, *, purpose, instructions, prompt, schema, **_):
        self.calls.append({"purpose": purpose, "instructions": instructions, "prompt": prompt})
        if self.error:
            raise self.error
        return schema(greeting=self.greeting, closing=self.closing)


def _request(**kw) -> PolishRequest:
    return PolishRequest(situation="values_to_confirm", greeting=_GREETING, closing=_CLOSING, **kw)


# --------------------------------------------------------------------------
# check_wording: what counts as courtesy
# --------------------------------------------------------------------------
class TestCheckWording:
    @pytest.mark.parametrize("line", TEMPLATE_LINES)
    def test_every_template_line_passes_its_own_check(self, line: str) -> None:
        assert check_wording(line, line) is None

    @pytest.mark.parametrize("text", [
        "Many thanks for getting in touch.",
        "Thank you so much for your message, and I'm sorry for the extra step.",
        "We really appreciate your patience while our team takes a look.",
        "Thanks for bearing with us… We appreciate it.",
        "Thank you, and apologies for any inconvenience.",
        "We have gone through your message in order to help as quickly as we can.",
        "We could not verify everything automatically, and we appreciate your patience.",
    ])
    def test_ordinary_courtesy_passes(self, text: str) -> None:
        assert check_wording(text, _GREETING) is None

    @pytest.mark.parametrize(
        "text, why",
        [
            ("Thanks for sending your 5 containers.", "number"),
            ("Thanks, we will check with CLIFFORD PAPER INC.", "all-capitals"),
            ("Thanks for the documents from Pecll.", "name"),
            ('Thanks for the file you called "final".', "quoted"),
            ("Thanks, please write to ops@example.com.", "address"),
            ("Thanks, see https://example.com for details.", "address or a link"),
            ("Thanks, please ask Mr Tan to call us.", "name"),
            ("Thank you. We have verified your documents.", "outcome"),
            ("Thank you. Everything is in order.", "outcome"),
            ("Thank you. Everything agrees.", "outcome"),
            ("Thank you, your documents are all set.", "outcome"),
            ("Thank you. Your shipment will sail on schedule.", "outcome"),
            ("Thank you. We found no mismatches.", "outcome"),
            ("Thank you. Could you reply today?", "question"),
            ("Thank you. Kindly send the invoice as well.", "asked the customer"),
            ("Thank you, and please confirm by return.", "asked the customer"),
            ("Hello, and thank you for getting in touch.", "salutation"),
            ("Thank you. Kind regards", "salutation"),
            ("", "empty"),
            ("Thank you. " * 30, "longer"),
        ],
    )
    def test_anything_that_reads_as_a_value_claim_or_request_is_refused(self, text: str, why: str) -> None:
        reason = check_wording(text, _GREETING)
        assert reason is not None and why in reason, reason


# --------------------------------------------------------------------------
# polish: the model is shown nothing it could copy, and is refused when it adds
# --------------------------------------------------------------------------
class TestPolish:
    def test_a_clean_rewrite_is_adopted(self) -> None:
        model = _FakeModel(greeting="Many thanks for your email.", closing="Thank you very much.")
        out = polish(_request(tone="warm"), model)
        assert out.adopted and out.rejected_reason is None
        assert (out.greeting, out.closing) == ("Many thanks for your email.", "Thank you very much.")
        assert model.calls[0]["purpose"] == "reply_polish"

    def test_one_bad_line_refuses_the_whole_rewrite(self) -> None:
        model = _FakeModel(greeting=_GREETING, closing="Thank you. Your gross weight is 235,550 KG.")
        out = polish(_request(), model)
        assert not out.adopted
        assert (out.greeting, out.closing) == (_GREETING, _CLOSING)
        assert out.rejected_reason.startswith("closing:")

    def test_the_prompt_carries_only_the_two_courtesy_lines(self) -> None:
        model = _FakeModel(greeting=_GREETING, closing=_CLOSING)
        polish(_request(attempt=3), model)
        prompt = json.loads(model.calls[0]["prompt"])
        assert set(prompt) == {"what_this_email_is_about", "tone", "greeting", "closing", "variation"}
        assert (prompt["greeting"], prompt["closing"], prompt["variation"]) == (_GREETING, _CLOSING, 3)

    def test_each_press_is_a_different_prompt_so_the_cache_cannot_pin_one_answer(self) -> None:
        model = _FakeModel(greeting=_GREETING, closing=_CLOSING)
        polish(_request(attempt=0), model)
        polish(_request(attempt=1), model)
        assert model.calls[0]["prompt"] != model.calls[1]["prompt"]

    @pytest.mark.parametrize("extra", [
        {"facts": ['Consignee: the draft Bill of Lading shows "CLIFFORD PAPER INC"']},
        {"context": "We compared the draft Bill of Lading against the Shipping Instruction."},
        {"action": "Could you please confirm the gross weight?"},
        {"attempt": 21},
    ])
    def test_the_request_has_no_room_for_anything_else(self, extra: dict) -> None:
        with pytest.raises(ValidationError):
            PolishRequest(situation="values_to_confirm", greeting=_GREETING, closing=_CLOSING, **extra)

    def test_an_unreachable_model_is_raised_for_the_caller(self) -> None:
        with pytest.raises(LLMUnavailable):
            polish(_request(), _FakeModel(error=LLMUnavailable("network down")))


# --------------------------------------------------------------------------
# the route, and the health check it now reports on
# --------------------------------------------------------------------------
class TestRoute:
    @pytest.fixture()
    def client(self) -> TestClient:
        return TestClient(api_main.app)

    def _body(self, **kw) -> dict:
        return {"situation": "values_to_confirm", "greeting": _GREETING, "closing": _CLOSING, **kw}

    def test_no_model_is_503_and_health_says_so(self, client: TestClient,
                                                monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(api_main, "_shared_compare_client", lambda: None)
        assert client.post("/reply-drafts/polish", json=self._body()).status_code == 503
        assert client.get("/").json()["model_available"] is False

    def test_bad_model_settings_never_fail_the_health_check(self, client: TestClient,
                                                           monkeypatch: pytest.MonkeyPatch) -> None:
        # GET / is Render's health check. A model with no pinned price makes
        # load_settings raise; that must read as "no model", not as a 500
        # that restarts the whole service.
        def broken():
            raise ValueError("model 'gpt-4o' has no pinned price")
        monkeypatch.setattr(api_main, "_shared_compare_client", broken)
        r = client.get("/")
        assert r.status_code == 200 and r.json()["model_available"] is False
        assert client.post("/reply-drafts/polish", json=self._body()).status_code == 503

    def test_a_model_rewrite_comes_back(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        model = _FakeModel(greeting=_GREETING, closing="Thank you kindly.")
        monkeypatch.setattr(api_main, "_shared_compare_client", lambda: model)
        r = client.post("/reply-drafts/polish", json=self._body(tone="brief"))
        assert r.status_code == 200
        assert r.json()["adopted"] is True and r.json()["closing"] == "Thank you kindly."
        assert client.get("/").json()["model_available"] is True

    def test_facts_in_the_request_are_refused_before_any_model_call(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        model = _FakeModel(greeting=_GREETING, closing=_CLOSING)
        monkeypatch.setattr(api_main, "_shared_compare_client", lambda: model)
        r = client.post("/reply-drafts/polish", json=self._body(facts=["Gross weight: 235,550 KG"]))
        assert r.status_code == 422
        assert model.calls == []

    def test_an_unreachable_model_is_503(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        model = _FakeModel(error=LLMUnavailable("timeout"))
        monkeypatch.setattr(api_main, "_shared_compare_client", lambda: model)
        assert client.post("/reply-drafts/polish", json=self._body()).status_code == 503


# --------------------------------------------------------------------------
# the subject a reply threads under
# --------------------------------------------------------------------------
def test_the_subject_reaches_the_report_and_never_the_submission(tmp_path: Path) -> None:
    email = EmailRecord(email_id="email_x", sender="ops@example.com",
                        subject="TO CONFIRM DOCS _ TEST0001", body="Hello team.")
    result = Pipeline(PipelineConfig(data_root=tmp_path)).process(email)
    assert result.subject == "TO CONFIRM DOCS _ TEST0001"
    assert result.to_report()["subject"] == "TO CONFIRM DOCS _ TEST0001"
    assert "subject" not in result.to_submission()
    assert CaseResult(email_id="upload", category="BL_COMPARISON").to_report()["subject"] == ""
