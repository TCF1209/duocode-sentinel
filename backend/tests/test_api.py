"""Tests for backend/api — the FastAPI surface added in Phase 3a (docs/ROADMAP.md).

Everything here uses small synthetic fixtures built in this file, never
`data/bundle`: the organisers' dataset (and the answer key beside it) is
git-ignored and stays out of reach of this suite on purpose
(CLAUDE.md rule 1 / docs/COLLABORATION.md "Non-negotiables").
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from fastapi.testclient import TestClient  # noqa: E402

from api import main as api_main  # noqa: E402
from sdoc.readers import scan  # noqa: E402
from sdoc.schema import COMPARE_FIELDS, CaseResult, ParsedDoc  # noqa: E402

_SI_TEXT = (
    "Shipper: TEST EXPORT COMPANY LTD\n"
    "Consignee: TEST IMPORT COMPANY LTD\n"
    "Notify Party: TEST NOTIFY AGENT LTD\n"
    "Port of Loading: PORT KLANG\n"
    "Port of Discharge: SINGAPORE\n"
    "Container Count: 2\n"
    "Gross Weight (KG): 15000\n"
)
_BL_TEXT_MATCH = _SI_TEXT
_BL_TEXT_MISMATCH = _SI_TEXT.replace(
    "Consignee: TEST IMPORT COMPANY LTD", "Consignee: DIFFERENT IMPORT COMPANY LTD"
)
_COMPARE_BODY = "Please compare the SI and draft BL for booking {ref} and confirm all fields match."


@pytest.fixture()
def client() -> TestClient:
    return TestClient(api_main.app)


def _write_email(data_root: Path, email_id: str, subject: str, body: str, attachments: list[str]) -> None:
    inbox = data_root / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    (inbox / f"{email_id}.json").write_text(
        json.dumps(
            {
                "email_id": email_id,
                "from": "ops@example.com",
                "subject": subject,
                "body": body,
                "attachments": attachments,
            }
        ),
        encoding="utf-8",
    )


def _write_attachment(data_root: Path, rel_path: str, text: str) -> None:
    full = data_root / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(text, encoding="utf-8")


@pytest.fixture()
def synthetic_inbox(tmp_path: Path) -> Path:
    """Three emails: a clean match, a planted mismatch, and a missing pair."""
    data_root = tmp_path / "bundle"

    _write_email(
        data_root, "email_001", "TO CONFIRM DOCS - TEST0001", _COMPARE_BODY.format(ref="TEST0001"),
        ["attachments/test0001_SI.txt", "attachments/test0001_BL.txt"],
    )
    _write_attachment(data_root, "attachments/test0001_SI.txt", _SI_TEXT)
    _write_attachment(data_root, "attachments/test0001_BL.txt", _BL_TEXT_MATCH)

    _write_email(
        data_root, "email_002", "TO CONFIRM DOCS - TEST0002", _COMPARE_BODY.format(ref="TEST0002"),
        ["attachments/test0002_SI.txt", "attachments/test0002_BL.txt"],
    )
    _write_attachment(data_root, "attachments/test0002_SI.txt", _SI_TEXT)
    _write_attachment(data_root, "attachments/test0002_BL.txt", _BL_TEXT_MISMATCH)

    _write_email(
        data_root, "email_003", "TO CONFIRM DOCS - TEST0003", _COMPARE_BODY.format(ref="TEST0003"),
        ["attachments/test0003_SI.txt"],
    )
    _write_attachment(data_root, "attachments/test0003_SI.txt", _SI_TEXT)

    return data_root


class TestCompareUpload:
    def test_matching_documents_are_ok(self, client: TestClient) -> None:
        resp = client.post(
            "/compare",
            files={
                "si": ("si.txt", _SI_TEXT.encode(), "text/plain"),
                "bl": ("bl.txt", _BL_TEXT_MATCH.encode(), "text/plain"),
            },
        )
        assert resp.status_code == 200, resp.text
        report = resp.json()
        assert report["status"] == "OK"
        assert report["defect_fields"] == []
        assert report["decided_by"] == "rule"

    def test_mismatched_consignee_is_flagged_with_evidence(self, client: TestClient) -> None:
        resp = client.post(
            "/compare",
            files={
                "si": ("si.txt", _SI_TEXT.encode(), "text/plain"),
                "bl": ("bl.txt", _BL_TEXT_MISMATCH.encode(), "text/plain"),
            },
        )
        assert resp.status_code == 200, resp.text
        report = resp.json()
        assert report["status"] == "MISMATCH"
        assert report["defect_fields"] == ["consignee"]
        consignee = next(f for f in report["fields"] if f["field"] == "consignee")
        assert consignee["si"]["evidence"]["snippet"]
        assert consignee["bl"]["evidence"]["snippet"]

    def test_empty_upload_is_needs_review_not_a_crash(self, client: TestClient) -> None:
        resp = client.post(
            "/compare",
            files={
                "si": ("si.txt", b"", "text/plain"),
                "bl": ("bl.txt", _BL_TEXT_MATCH.encode(), "text/plain"),
            },
        )
        assert resp.status_code == 200, resp.text
        report = resp.json()
        assert report["status"] == "NEEDS_REVIEW"


class TestRunLifecycle:
    def test_full_lifecycle(
        self, client: TestClient, synthetic_inbox: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(api_main, "DEFAULT_DATA_ROOT", synthetic_inbox)

        created = client.post("/runs", json={"use_llm": False})
        assert created.status_code == 200, created.text
        run_id = created.json()["run_id"]

        status = {}
        for _ in range(100):
            status = client.get(f"/runs/{run_id}").json()
            if status["status"] != "running":
                break
            time.sleep(0.05)
        assert status["status"] == "done", status
        assert status["processed"] == 3

        cases = client.get(f"/runs/{run_id}/cases").json()
        assert cases["count"] == 3, cases

        by_status = {c["email_id"]: c["status"] for c in cases["cases"]}
        assert by_status == {
            "email_001": "OK",
            "email_002": "MISMATCH",
            "email_003": "NEEDS_REVIEW",
        }, by_status
        assert all(0.0 <= c["category_confidence"] <= 1.0 for c in cases["cases"])

        # The case-list summary carries the shipper's name too, read off the
        # same comparison the pipeline already produced -- no extra request
        # per case, so the dashboard's pattern view can group by counterparty
        # without doing an N+1 fetch over the whole run.
        by_shipper = {c["email_id"]: c["shipper"] for c in cases["cases"]}
        assert by_shipper["email_001"] == "TEST EXPORT COMPANY LTD"
        assert by_shipper["email_002"] == "TEST EXPORT COMPANY LTD"

        # The inbox record's own "from" address, carried through for a
        # mailto: link -- never read by backend/sdoc/ itself, never sent
        # anywhere by Sentinel. _write_email's fixture puts the same address
        # on every email, which is realistic: one contact often sends a
        # whole thread of comparison requests.
        by_sender = {c["email_id"]: c["sender"] for c in cases["cases"]}
        assert by_sender["email_001"] == "ops@example.com"
        assert by_sender["email_002"] == "ops@example.com"

        # The email as it arrived -- subject line and attachment *names* --
        # for the dashboard's "Before Sentinel" view. Names, not the
        # data-root paths the inbox JSON lists: a person reading their mail
        # sees "test0001_BL.txt", not "attachments/test0001_BL.txt".
        by_subject = {c["email_id"]: c["subject"] for c in cases["cases"]}
        assert by_subject["email_001"] == "TO CONFIRM DOCS - TEST0001"
        by_attachments = {c["email_id"]: c["attachments"] for c in cases["cases"]}
        assert by_attachments["email_001"] == ["test0001_SI.txt", "test0001_BL.txt"]
        assert by_attachments["email_003"] == ["test0003_SI.txt"]

        # No document here is an image-only scan, so none was read out
        # either -- TestScanState covers the cases where one is.
        assert all(c["scanned"] is False and c["scan_transcribed"] is False for c in cases["cases"])

        case_detail = client.get(f"/cases/{run_id}:email_002").json()
        assert case_detail["sender"] == "ops@example.com"
        assert case_detail["inbox"] == {
            "subject": "TO CONFIRM DOCS - TEST0002",
            "attachments": ["test0002_SI.txt", "test0002_BL.txt"],
        }
        assert case_detail["defect_fields"] == ["consignee"]
        assert case_detail["review"] is None

        review = client.post(
            f"/cases/{run_id}:email_002/review",
            json={"decision": "confirm", "reviewer": "test-operator"},
        )
        assert review.status_code == 200, review.text
        assert review.json()["status"] == "MISMATCH"

        case_after_review = client.get(f"/cases/{run_id}:email_002").json()
        assert case_after_review["review"]["decision"] == "confirm"

        run_list = client.get("/runs").json()
        assert any(r["run_id"] == run_id for r in run_list)

        metrics = client.get("/metrics", params={"run_id": run_id}).json()
        assert metrics["emails"] == 3

        submission = client.get("/submission", params={"run_id": run_id}).json()
        assert set(submission) == {"email_001", "email_002", "email_003"}
        assert submission["email_001"]["status"] == "OK"

    def test_case_attachment_serves_the_real_file_a_run_read(
        self, client: TestClient, synthetic_inbox: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The document itself, not just the evidence snippet cut from it.

        Reads back exactly the bytes _write_attachment put on disk for
        email_001's SI side -- the point is this is the real file the
        pipeline actually read, not a reconstruction from report.json.
        """
        monkeypatch.setattr(api_main, "DEFAULT_DATA_ROOT", synthetic_inbox)
        run_id = client.post("/runs", json={"use_llm": False}).json()["run_id"]
        for _ in range(100):
            if client.get(f"/runs/{run_id}").json()["status"] != "running":
                break
            time.sleep(0.05)

        # Normalises \r\n: Path.write_text (_write_attachment, above) writes
        # the platform's own newline translation, CRLF on Windows, while
        # _SI_TEXT is a plain-\n literal -- a fact about this fixture on
        # this OS, not something the endpoint should paper over by
        # rewriting bytes it reads off disk. It exists to serve the file
        # verbatim; asserting on content should not care which newline a
        # given OS happened to write.
        si = client.get(f"/cases/{run_id}:email_001/attachments/si")
        assert si.status_code == 200, si.text
        assert si.text.replace("\r\n", "\n") == _SI_TEXT
        assert si.headers["content-type"].startswith("text/")
        # "inline", not FileResponse's own "attachment" default -- a reviewer
        # clicking this from the report should see the document in the tab,
        # not get a save-as dialog. See main.py's comment on this route.
        assert si.headers["content-disposition"].startswith("inline")
        # Not cacheable -- a stale cached copy of this exact route reproducibly
        # broke live browser testing during this session (main.py's own
        # comment on this route has the full story); this pins the fix.
        assert si.headers["cache-control"] == "no-store"

        bl = client.get(f"/cases/{run_id}:email_001/attachments/bl")
        assert bl.status_code == 200, bl.text
        assert bl.text.replace("\r\n", "\n") == _BL_TEXT_MATCH

        # email_003 has only an SI attached (see synthetic_inbox) -- the
        # missing BL side must 404, not serve a stale or empty file.
        assert client.get(f"/cases/{run_id}:email_003/attachments/bl").status_code == 404
        assert client.get(f"/cases/{run_id}:email_001/attachments/upside-down").status_code == 404
        assert client.get(f"/cases/{run_id}:email_999/attachments/si").status_code == 404

    def test_unknown_run_is_404(self, client: TestClient) -> None:
        assert client.get("/runs/does-not-exist").status_code == 404

    def test_unknown_case_id_shape_is_400(self, client: TestClient) -> None:
        assert client.get("/cases/not-a-valid-id").status_code == 400

    def test_missing_data_root_is_400_not_a_crash(
        self, client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(api_main, "DEFAULT_DATA_ROOT", tmp_path / "nowhere")
        resp = client.post("/runs", json={})
        assert resp.status_code == 400


class TestScanState:
    """The case list's `scanned` / `scan_transcribed` (api/main.py _scan_state)."""

    def test_a_scan_is_told_apart_from_a_corrupt_file_and_from_one_read_out(self) -> None:
        # All three escalate as review_reason "unreadable"; only a scan has
        # anything to read out, and only a run made with the model read it.
        def doc(role: str, reason: str) -> ParsedDoc:
            return ParsedDoc(path=f"attachments/x_{role}.pdf", ext=".pdf", role_hint=role,
                             readable=False, unreadable_reason=reason)

        def state(si: ParsedDoc, bl: ParsedDoc) -> tuple[bool, bool]:
            case = CaseResult(email_id="email_x", category="BL_COMPARISON", status="NEEDS_REVIEW",
                              review_reason="unreadable", si_doc=si, bl_doc=bl)
            return api_main._scan_state(case)

        read_out = doc("SI", "no_text_layer")
        scan.attach(read_out, scan.ScanTranscript(
            fields=[scan.ScanField(field=f, value="", legible=False) for f in COMPARE_FIELDS],
            overall_legible=False, confidence=0.0, model="gpt-5-mini", pages_read=1, note="",
        ))

        assert state(read_out, doc("BL", "no_text_layer")) == (True, True)
        assert state(doc("SI", "no_text_layer"), doc("BL", "no_text_layer")) == (True, False)
        assert state(doc("SI", "corrupt"), doc("BL", "corrupt")) == (False, False)


def _finished_run(client: TestClient, data_root: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    """Start a deterministic run over `data_root` and wait for it to finish."""
    monkeypatch.setattr(api_main, "DEFAULT_DATA_ROOT", data_root)
    run_id = client.post("/runs", json={"use_llm": False}).json()["run_id"]
    for _ in range(100):
        if client.get(f"/runs/{run_id}").json()["status"] != "running":
            break
        time.sleep(0.05)
    assert client.get(f"/runs/{run_id}").json()["status"] == "done"
    return run_id


# A third SI, differing from _SI_TEXT on container count only -- so a re-check
# that re-sends the SI against a BL identical to _SI_TEXT must flag exactly
# that field, and a re-check that wrongly fell back to the disk BL (which
# differs on consignee) would flag two.
_SI_TEXT_THREE_BOXES = _SI_TEXT.replace("Container Count: 2", "Container Count: 3")


class TestRecheck:
    """POST /cases/{id}/recheck -- the same check, run again on re-sent documents."""

    def test_resent_bl_replaces_the_answer_and_keeps_the_old_one(
        self, client: TestClient, synthetic_inbox: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        run_id = _finished_run(client, synthetic_inbox, monkeypatch)
        case = f"{run_id}:email_002"

        # A reviewer has already confirmed the mismatch against the first BL.
        confirmed = client.post(f"/cases/{case}/review", json={"decision": "confirm", "note": "asked shipper"})
        assert confirmed.status_code == 200, confirmed.text
        before = client.get(f"/cases/{case}").json()
        assert before["status"] == "MISMATCH"
        assert before["recheck"] is None
        assert before["history"] == []

        # The shipper re-sends a BL that matches. SI is not re-sent.
        resp = client.post(
            f"/cases/{case}/recheck",
            files={"bl": ("test0002_BL_rev2.txt", _BL_TEXT_MATCH.encode(), "text/plain")},
        )
        assert resp.status_code == 200, resp.text
        after = resp.json()
        assert after["status"] == "OK"
        assert after["defect_fields"] == []
        # The email is still the email: identity and classification are the
        # run's, only the comparison is new.
        assert after["email_id"] == "email_002"
        assert after["sender"] == "ops@example.com"
        assert after["category"] == "BL_COMPARISON"
        assert after["category_confidence"] == before["category_confidence"]
        # The re-sent file is the BL now; the SI is still the run's own.
        assert after["documents"]["bl"]["path"] == "test0002_BL_rev2.txt"
        assert after["documents"]["si"]["path"] == "attachments/test0002_SI.txt"
        # The old review was about the old BL -- reset, not carried over.
        assert after["review"] is None
        assert after["effective"]["status"] == "OK"
        assert after["effective"]["reviewed"] is False
        assert after["recheck"]["count"] == 1
        assert after["recheck"]["last_resubmitted"] == ["bl"]
        assert after["recheck"]["sources"] == {"si": "original", "bl": "resent"}
        # ...and the superseded answer is kept, review and all.
        assert len(after["history"]) == 1
        old = after["history"][0]
        assert old["version"] == 1
        assert old["resubmitted"] == ["bl"]
        assert old["uploaded"] == {"bl": "test0002_BL_rev2.txt"}
        assert old["report"]["status"] == "MISMATCH"
        assert old["report"]["defect_fields"] == ["consignee"]
        assert old["review"]["decision"] == "confirm"
        assert old["review"]["note"] == "asked shipper"
        assert old["effective"]["status"] == "MISMATCH"
        assert old["effective"]["reviewed"] is True

        # GET /cases/{id} says the same thing the POST answered with.
        assert client.get(f"/cases/{case}").json() == after

        # Everything downstream follows the new answer: the list, the graded
        # submission, the review counts (the reset review is not counted).
        rows = {c["email_id"]: c for c in client.get(f"/runs/{run_id}/cases").json()["cases"]}
        assert rows["email_002"]["status"] == "OK"
        assert rows["email_002"]["reviewed"] is False
        assert rows["email_002"]["recheck_count"] == 1
        assert rows["email_001"]["recheck_count"] == 0
        assert client.get("/submission", params={"run_id": run_id}).json()["email_002"]["status"] == "OK"
        metrics = client.get("/metrics", params={"run_id": run_id}).json()
        assert metrics["review"] == {"reviewed": 0, "confirmed": 0, "corrected": 0, "unresolved": 0}
        assert metrics["recheck"] == {"cases": 1, "rechecks": 1}

    def test_attachments_serve_the_resent_file_and_the_superseded_one(
        self, client: TestClient, synthetic_inbox: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        run_id = _finished_run(client, synthetic_inbox, monkeypatch)
        case = f"{run_id}:email_002"
        resent = _BL_TEXT_MATCH.encode()
        assert client.post(
            f"/cases/{case}/recheck", files={"bl": ("BL rev 2.txt", resent, "text/plain")},
        ).status_code == 200

        # The BL is now the re-sent one, served from memory with the same
        # headers the disk route uses; the SI is still the disk original.
        bl = client.get(f"/cases/{case}/attachments/bl")
        assert bl.status_code == 200, bl.text
        assert bl.content == resent
        assert bl.headers["content-type"].startswith("text/plain")
        assert bl.headers["content-disposition"].startswith("inline")
        assert "BL%20rev%202.txt" in bl.headers["content-disposition"]
        assert bl.headers["cache-control"] == "no-store"
        si = client.get(f"/cases/{case}/attachments/si")
        assert si.status_code == 200
        assert si.text.replace("\r\n", "\n") == _SI_TEXT

        # Version 1 is what the run originally read: the mismatching BL.
        old_bl = client.get(f"/cases/{case}/attachments/bl", params={"version": 1})
        assert old_bl.status_code == 200, old_bl.text
        assert old_bl.text.replace("\r\n", "\n") == _BL_TEXT_MISMATCH
        assert old_bl.headers["cache-control"] == "no-store"
        assert client.get(f"/cases/{case}/attachments/bl", params={"version": 2}).status_code == 404
        assert client.get(f"/cases/{case}/attachments/bl", params={"version": 0}).status_code == 404

    def test_second_recheck_keeps_the_earlier_resent_side(
        self, client: TestClient, synthetic_inbox: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        run_id = _finished_run(client, synthetic_inbox, monkeypatch)
        case = f"{run_id}:email_002"
        first = client.post(
            f"/cases/{case}/recheck", files={"bl": ("bl2.txt", _BL_TEXT_MATCH.encode(), "text/plain")},
        ).json()
        assert first["status"] == "OK"

        # Now only the SI is re-sent. It must be compared against the BL
        # from the first re-check, not the disk BL the desk has moved past.
        second = client.post(
            f"/cases/{case}/recheck", files={"si": ("si2.txt", _SI_TEXT_THREE_BOXES.encode(), "text/plain")},
        ).json()
        assert second["status"] == "MISMATCH"
        assert second["defect_fields"] == ["container_count"]
        assert second["recheck"]["count"] == 2
        assert second["recheck"]["sources"] == {"si": "resent", "bl": "resent"}
        assert [h["version"] for h in second["history"]] == [1, 2]
        assert [h["report"]["status"] for h in second["history"]] == ["MISMATCH", "OK"]
        assert second["history"][1]["resubmitted"] == ["si"]

        # Version 2's BL was the first re-sent copy; version 1's the disk one.
        v2 = client.get(f"/cases/{case}/attachments/bl", params={"version": 2})
        assert v2.content == _BL_TEXT_MATCH.encode()
        v1 = client.get(f"/cases/{case}/attachments/bl", params={"version": 1})
        assert v1.text.replace("\r\n", "\n") == _BL_TEXT_MISMATCH

    def test_missing_side_can_be_supplied_but_not_skipped(
        self, client: TestClient, synthetic_inbox: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        run_id = _finished_run(client, synthetic_inbox, monkeypatch)
        case = f"{run_id}:email_003"          # SI only; the BL never arrived
        assert client.get(f"/cases/{case}").json()["status"] == "NEEDS_REVIEW"

        # Re-sending only the SI leaves nothing to compare it against.
        no_bl = client.post(
            f"/cases/{case}/recheck", files={"si": ("si.txt", _SI_TEXT.encode(), "text/plain")},
        )
        assert no_bl.status_code == 422, no_bl.text
        assert "no BL on file" in no_bl.json()["detail"]
        assert client.get(f"/cases/{case}").json()["recheck"] is None

        # The BL arriving is the whole scenario: the case resolves.
        resp = client.post(
            f"/cases/{case}/recheck", files={"bl": ("bl.txt", _BL_TEXT_MATCH.encode(), "text/plain")},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "OK"
        assert resp.json()["recheck"]["sources"] == {"si": "original", "bl": "resent"}
        assert resp.json()["history"][0]["report"]["status"] == "NEEDS_REVIEW"

    def test_refusals(
        self, client: TestClient, synthetic_inbox: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        run_id = _finished_run(client, synthetic_inbox, monkeypatch)
        case = f"{run_id}:email_002"
        bl_ok = {"bl": ("bl.txt", _BL_TEXT_MATCH.encode(), "text/plain")}

        assert client.post(f"/cases/{case}/recheck").status_code == 422             # nothing attached
        empty = client.post(f"/cases/{case}/recheck", files={"bl": ("bl.txt", b"", "text/plain")})
        assert empty.status_code == 422, empty.text                                  # a slip, not a document
        assert client.post(f"/cases/{run_id}:email_999/recheck", files=bl_ok).status_code == 404
        assert client.post("/cases/not-a-valid-id/recheck", files=bl_ok).status_code == 400
        # None of those touched the case.
        assert client.get(f"/cases/{case}").json()["recheck"] is None

        # A case that is not a comparison request has no SI/BL pair to
        # re-check. The classifier's verdict on a synthetic body is not what
        # this test is about, so the stored category is set directly.
        api_main.store.get_case(run_id, "email_001").category = "GENERAL"
        not_a_comparison = client.post(f"/cases/{run_id}:email_001/recheck", files=bl_ok)
        assert not_a_comparison.status_code == 409, not_a_comparison.text
        assert "GENERAL" in not_a_comparison.json()["detail"]

    def test_retry_is_refused_once_a_case_was_rechecked(
        self, client: TestClient, synthetic_inbox: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        run_id = _finished_run(client, synthetic_inbox, monkeypatch)
        case = f"{run_id}:email_002"
        assert client.post(f"/cases/{case}/retry").status_code == 200        # fine before
        assert client.post(
            f"/cases/{case}/recheck", files={"bl": ("bl.txt", _BL_TEXT_MATCH.encode(), "text/plain")},
        ).status_code == 200
        # A retry would re-read the disk BL over the re-sent one, silently.
        refused = client.post(f"/cases/{case}/retry")
        assert refused.status_code == 409, refused.text
        assert client.get(f"/cases/{case}").json()["status"] == "OK"        # untouched


class TestReviewInPlace:
    """The case page's in-place review: each choice on a field card is saved
    as it is made (POST, with the per-field choices behind the outcome), and
    taking the last one back withdraws the review (DELETE)."""

    def test_per_field_choices_are_kept_and_returned(
        self, client: TestClient, synthetic_inbox: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        run_id = _finished_run(client, synthetic_inbox, monkeypatch)
        case = f"{run_id}:email_002"                      # MISMATCH on consignee
        # No status sent: in place, the outcome is derived from the choices.
        saved = client.post(
            f"/cases/{case}/review",
            json={
                "decision": "correct",
                "decisions": {"consignee": "cleared"},
                "corrections": {"shipper": {"si": "   "}},          # blank: no correction
                "note": "typo on the draft",
            },
        )
        assert saved.status_code == 200, saved.text
        review = saved.json()
        assert review["decisions"] == {"consignee": "cleared"}
        assert review["cant_tell"] is False
        assert review["corrections"] == {}
        assert review["status"] == "OK"
        assert review["defect_fields"] == []
        # Sentinel's verdict on the field is kept; what stands is the choice.
        assert review["field_verdicts"]["consignee"]["verdict"] == "MISMATCH"
        assert review["field_verdicts"]["consignee"]["stands"] == "MATCH"
        assert review["field_verdicts"]["shipper"]["si"]["corrected"] is False

        detail = client.get(f"/cases/{case}").json()
        assert detail["review"]["decisions"] == {"consignee": "cleared"}
        assert detail["effective"] == {
            "status": "OK", "review_reason": None, "has_defect": False, "defect_fields": [],
            "source": "review", "reviewed": True, "review_decision": "correct",
        }
        # The system's own answer is untouched underneath.
        assert detail["status"] == "MISMATCH"
        assert detail["defect_fields"] == ["consignee"]

        # A review recorded the old way -- no per-field choices -- still reads
        # back with empty ones, so a client never has to special-case it.
        plain = client.post(f"/cases/{case}/review", json={"decision": "confirm"})
        assert plain.status_code == 200, plain.text
        assert plain.json()["decisions"] == {}
        assert plain.json()["cant_tell"] is False
        assert plain.json()["corrections"] == {}
        assert plain.json()["field_verdicts"] == {}
        # The whole-case form still has to say what it corrects to.
        no_status = client.post(f"/cases/{case}/review", json={"decision": "correct"})
        assert no_status.status_code == 422, no_status.text

    def test_a_corrected_value_is_compared_by_the_pipeline_itself(
        self, client: TestClient, synthetic_inbox: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The reviewer types what a side should read; the pair is compared
        again with the same canonicalisation the run used."""
        run_id = _finished_run(client, synthetic_inbox, monkeypatch)
        case = f"{run_id}:email_002"                      # BL consignee differs from the SI

        # Written the way a person types it, not the way the document prints
        # it -- case and spacing are the canonicaliser's job, as in the run.
        agreed = client.post(
            f"/cases/{case}/review",
            json={"decision": "correct", "corrections": {"consignee": {"bl": "  test import company ltd "}}},
        )
        assert agreed.status_code == 200, agreed.text
        review = agreed.json()
        assert review["corrections"] == {"consignee": {"bl": "test import company ltd"}}
        assert review["status"] == "OK"
        assert review["defect_fields"] == []
        consignee = review["field_verdicts"]["consignee"]
        assert consignee["verdict"] == "MATCH"
        assert consignee["bl"] == {"raw": "test import company ltd", "normalised": consignee["si"]["normalised"], "corrected": True}
        assert consignee["si"]["corrected"] is False
        rows = {c["email_id"]: c for c in client.get(f"/runs/{run_id}/cases").json()["cases"]}
        assert rows["email_002"]["status"] == "OK"
        assert rows["email_002"]["outcome_source"] == "review"
        assert client.get("/submission", params={"run_id": run_id}).json()["email_002"]["status"] == "OK"

        # A value that still differs keeps the field on the list.
        still = client.post(
            f"/cases/{case}/review",
            json={"decision": "correct", "corrections": {"consignee": {"bl": "ANOTHER IMPORT COMPANY LTD"}}},
        )
        assert still.status_code == 200, still.text
        assert still.json()["status"] == "MISMATCH"
        assert still.json()["defect_fields"] == ["consignee"]
        assert still.json()["field_verdicts"]["consignee"]["verdict"] == "MISMATCH"

        # A placeholder is a blank, not a discrepancy (CLAUDE.md rule 4):
        # the field becomes uncomparable and the case goes to a person.
        blank = client.post(
            f"/cases/{case}/review",
            json={"decision": "correct", "corrections": {"consignee": {"bl": "???"}}},
        )
        assert blank.status_code == 200, blank.text
        assert blank.json()["status"] == "NEEDS_REVIEW"
        assert blank.json()["defect_fields"] == []
        assert blank.json()["field_verdicts"]["consignee"]["verdict"] == "UNCOMPARABLE"
        assert blank.json()["field_verdicts"]["consignee"]["reason"] == "bl_blank"

        # Sentinel's own comparison never moved.
        detail = client.get(f"/cases/{case}").json()
        assert detail["status"] == "MISMATCH"
        assert [f for f in detail["fields"] if f["field"] == "consignee"][0]["bl"]["raw"] == "DIFFERENT IMPORT COMPANY LTD"

    def test_numeric_correction_must_be_a_value_the_field_actually_parses(
        self, client: TestClient, synthetic_inbox: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """container_count() and gross_weight_kg() only ever look at the
        first number in a string (sdoc/normalize.py's own module docstring on
        this). Found live on the pitch10 demo, 25 Sep: a reviewer's BL
        correction of "6 x 40' FUCK" against an SI of "6 x 40'HC" was
        accepted and read MATCH, because nothing checked what came after the
        6. This is that gap, closed: the same correction must now be
        refused outright, not silently accepted and shown as "Consistent"."""
        run_id = _finished_run(client, synthetic_inbox, monkeypatch)
        case = f"{run_id}:email_002"           # container_count is "2" on both sides

        garbage = client.post(
            f"/cases/{case}/review",
            json={"decision": "correct", "corrections": {"container_count": {"bl": "2 x 40' FUCK"}}},
        )
        assert garbage.status_code == 422, garbage.text
        assert "container_count.bl" in garbage.json()["detail"]
        # Nothing was recorded.
        assert client.get(f"/cases/{case}").json()["review"] is None

        garbage_weight = client.post(
            f"/cases/{case}/review",
            json={"decision": "correct", "corrections": {"gross_weight_kg": {"bl": "15,000FUCK"}}},
        )
        assert garbage_weight.status_code == 422, garbage_weight.text
        assert "gross_weight_kg.bl" in garbage_weight.json()["detail"]

        # A real, well-formed correction still goes through exactly as before
        # (email_002's planted defect is in consignee, not this field, so
        # container_count on its own reads MATCH regardless of overall status).
        fine = client.post(
            f"/cases/{case}/review",
            json={"decision": "correct", "corrections": {"container_count": {"bl": "2 x 40'HC"}}},
        )
        assert fine.status_code == 200, fine.text
        assert fine.json()["field_verdicts"]["container_count"]["verdict"] == "MATCH"

    def test_choices_must_name_real_fields_and_real_choices(
        self, client: TestClient, synthetic_inbox: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        run_id = _finished_run(client, synthetic_inbox, monkeypatch)
        case = f"{run_id}:email_002"
        unknown_field = client.post(
            f"/cases/{case}/review",
            json={"decision": "correct", "status": "OK", "decisions": {"vessel": "cleared"}},
        )
        assert unknown_field.status_code == 422, unknown_field.text
        assert "vessel" in unknown_field.json()["detail"]
        unknown_choice = client.post(
            f"/cases/{case}/review",
            json={"decision": "correct", "status": "OK", "decisions": {"consignee": "maybe"}},
        )
        assert unknown_choice.status_code == 422, unknown_choice.text
        assert "maybe" in unknown_choice.json()["detail"]
        unknown_corrected_field = client.post(
            f"/cases/{case}/review",
            json={"decision": "correct", "corrections": {"vessel": {"bl": "X"}}},
        )
        assert unknown_corrected_field.status_code == 422, unknown_corrected_field.text
        unknown_side = client.post(
            f"/cases/{case}/review",
            json={"decision": "correct", "corrections": {"consignee": {"invoice": "X"}}},
        )
        assert unknown_side.status_code == 422, unknown_side.text
        assert "si or bl" in unknown_side.json()["detail"]
        # Nothing was recorded by any of them.
        assert client.get(f"/cases/{case}").json()["review"] is None

    def test_withdrawing_a_review_puts_the_case_back_unreviewed(
        self, client: TestClient, synthetic_inbox: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        run_id = _finished_run(client, synthetic_inbox, monkeypatch)
        case = f"{run_id}:email_002"
        assert client.post(
            f"/cases/{case}/review",
            json={"decision": "correct", "decisions": {"consignee": "cleared"}},
        ).status_code == 200
        rows = {c["email_id"]: c for c in client.get(f"/runs/{run_id}/cases").json()["cases"]}
        assert rows["email_002"]["status"] == "OK"
        assert rows["email_002"]["outcome_source"] == "review"

        gone = client.delete(f"/cases/{case}/review")
        assert gone.status_code == 200, gone.text
        # The fresh case report comes back, review-less, Sentinel's answer standing.
        assert gone.json()["review"] is None
        assert gone.json()["effective"]["status"] == "MISMATCH"
        assert gone.json()["effective"]["reviewed"] is False
        assert gone.json()["effective"]["source"] == "system"
        rows = {c["email_id"]: c for c in client.get(f"/runs/{run_id}/cases").json()["cases"]}
        assert rows["email_002"]["status"] == "MISMATCH"
        assert rows["email_002"]["reviewed"] is False
        assert client.get("/metrics", params={"run_id": run_id}).json()["review"] == {
            "reviewed": 0, "confirmed": 0, "corrected": 0, "unresolved": 0,
        }
        submission = client.get("/submission", params={"run_id": run_id}).json()
        assert submission["email_002"]["status"] == "MISMATCH"

        # Nothing left to withdraw; and an unknown case is an unknown case.
        assert client.delete(f"/cases/{case}/review").status_code == 404
        assert client.delete(f"/cases/{run_id}:email_999/review").status_code == 404
        assert client.delete("/cases/not-a-valid-id/review").status_code == 400

    def test_review_counts_keep_unresolved_apart_from_overridden(
        self, client: TestClient, synthetic_inbox: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The metrics page's "Reviewer decisions": a reviewer who could not
        decide leaves the case escalated, which is not an override of the
        Sentinel result and is not counted as one. A review is counted by the
        outcome it left, whichever button was pressed."""
        run_id = _finished_run(client, synthetic_inbox, monkeypatch)

        # Could not decide on email_002 (MISMATCH on consignee): no per-field
        # choice, and the case stays NEEDS_REVIEW.
        undecided = client.post(
            f"/cases/{run_id}:email_002/review",
            json={"decision": "correct", "decisions": {}, "corrections": {}, "cant_tell": True},
        )
        assert undecided.status_code == 200, undecided.text
        assert undecided.json()["status"] == "NEEDS_REVIEW"

        # Overrode email_001 (OK): a field Sentinel found consistent is flagged.
        overridden = client.post(
            f"/cases/{run_id}:email_001/review",
            json={"decision": "correct", "decisions": {"consignee": "flagged"}},
        )
        assert overridden.status_code == 200, overridden.text
        assert overridden.json()["status"] == "MISMATCH"

        assert client.get("/metrics", params={"run_id": run_id}).json()["review"] == {
            "reviewed": 2, "confirmed": 0, "corrected": 1, "unresolved": 1,
        }

        # email_002 re-reviewed, "corrected" to exactly Sentinel's answer: this
        # replaces the undecided review and counts as Confirmed.
        same = client.post(
            f"/cases/{run_id}:email_002/review",
            json={"decision": "correct", "status": "MISMATCH", "defect_fields": ["consignee"]},
        )
        assert same.status_code == 200, same.text
        # email_003 (NEEDS_REVIEW) confirmed as it stands: still escalated.
        still_escalated = client.post(f"/cases/{run_id}:email_003/review", json={"decision": "confirm"})
        assert still_escalated.status_code == 200, still_escalated.text

        assert client.get("/metrics", params={"run_id": run_id}).json()["review"] == {
            "reviewed": 3, "confirmed": 1, "corrected": 1, "unresolved": 1,
        }
