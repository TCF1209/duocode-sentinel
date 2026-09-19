"""Per-email model-call accounting.

`metrics.json` and every per-case record carry an `llm_calls` figure, and it
is the only place a reader can see *which* emails needed the model — the run
total in the usage block cannot tell three scanned attachments apart from five
hundred cheap ones. The client meters a whole run, so the per-email figure has
to be produced by differencing its counter around one email, and these tests
pin the two properties that differencing can quietly lose: that an email which
crashed is still charged for what it spent before crashing, and that the
no-key run — the default mode — reports a number instead of raising.

Nothing here touches the network or a real client: the pipeline reads only
`usage.calls`, so a stub is the whole model layer for these tests.
"""
from __future__ import annotations

from types import SimpleNamespace

from conftest import DATA

from sdoc.pipeline import Pipeline, PipelineConfig
from sdoc.schema import EmailRecord


def _email(email_id: str = "email_001") -> EmailRecord:
    return EmailRecord(
        email_id=email_id,
        sender="ops@example.com",
        subject="Please advise on the sailing schedule",
        body="No attachments, nothing to compare.",
    )


def _stub_client(calls: int = 0) -> SimpleNamespace:
    """A stand-in for `LLMClient`: the counter is all the pipeline reads."""
    return SimpleNamespace(usage=SimpleNamespace(calls=calls))


def test_an_email_is_charged_only_for_the_calls_it_made(monkeypatch):
    client = _stub_client(calls=4)           # four already spent by earlier emails
    pipeline = Pipeline(PipelineConfig(data_root=DATA, llm=client))

    def _spends_two(self, email, result):
        client.usage.calls += 2

    monkeypatch.setattr(Pipeline, "_process", _spends_two)
    assert pipeline.process(_email()).llm_calls == 2

    monkeypatch.setattr(Pipeline, "_process", lambda self, email, result: None)
    assert pipeline.process(_email("email_002")).llm_calls == 0
    assert pipeline.stats.to_dict()["llm_calls"] == 2


def test_a_call_spent_before_a_crash_is_still_charged_to_that_email(monkeypatch):
    # The transcription of a scan happens early, and a later stage can still
    # fail on the same email. That call was made and paid for, so hiding it
    # would make the cost of the cases that break hardest invisible.
    client = _stub_client()
    pipeline = Pipeline(PipelineConfig(data_root=DATA, llm=client))

    def _spends_one_then_fails(self, email, result):
        client.usage.calls += 1
        raise RuntimeError("a stage failed after the model had answered")

    monkeypatch.setattr(Pipeline, "_process", _spends_one_then_fails)
    result = pipeline.process(_email())
    assert result.status == "NEEDS_REVIEW"   # the crash is still an escalation
    assert result.llm_calls == 1


def test_a_run_with_no_client_reports_no_calls():
    # `build_client` returns None when there is no key, so the count has to be
    # answerable with no model layer present at all.
    pipeline = Pipeline(PipelineConfig(data_root=DATA, llm=None))
    result = pipeline.process(_email())
    assert result.llm_calls == 0
    assert result.to_report()["llm_calls"] == 0
    assert pipeline.stats.to_dict()["llm_calls"] == 0
