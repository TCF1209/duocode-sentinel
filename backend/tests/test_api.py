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

        case_detail = client.get(f"/cases/{run_id}:email_002").json()
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
