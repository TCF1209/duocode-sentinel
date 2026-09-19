"""POST /compare — upload an SI and a BL, get a comparison back.

docs/ROADMAP.md 3d calls this "the demo, not a feature": a judge's own
documents, not a replay of the graded inbox. It runs the same stages
`Pipeline._process` runs for a BL_COMPARISON email — doctype, extract,
compare, evidence gate — minus the email wrapper and the classify/intent
stages that only make sense for an inbox message, and it reuses
`Pipeline._apply` for the final decision so that rule is not duplicated.

`read_upload` duplicates `readers.read_attachment`'s dispatch table rather
than importing it, because that function is keyed on a filesystem path under
a data root and an upload has neither.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from sdoc import compare as compare_mod
from sdoc import doctype, evidence_gate
from sdoc.classify.intent import Intent
from sdoc.extract import fields as extract_mod
from sdoc.extract import llm as extract_llm
from sdoc.llm import LLMClient
from sdoc.pipeline import Pipeline
from sdoc.readers import fallback, office, pdf, plain
from sdoc.readers import role_hint
from sdoc.schema import CaseResult, ParsedDoc

MAX_BYTES = 25 * 1024 * 1024

_READERS = {
    ".txt": plain.read,
    ".text": plain.read,
    ".csv": plain.read,
    ".pdf": pdf.read,
    ".docx": office.read_docx,
    ".xlsx": office.read_xlsx,
    ".xlsm": office.read_xlsx,
}


def read_upload(filename: str, data: bytes) -> ParsedDoc:
    ext = Path(filename).suffix.lower()
    doc = ParsedDoc(path=filename, ext=ext, role_hint=role_hint(filename))

    if not data:
        doc.readable = False
        doc.unreadable_reason = "empty_file"
        return doc
    if len(data) > MAX_BYTES:
        doc.readable = False
        doc.unreadable_reason = "unsupported"
        doc.notes.append(f"file is {len(data)} bytes, above the {MAX_BYTES} limit")
        return doc

    doc.n_bytes = len(data)
    reader = _READERS.get(ext)
    if reader is None:
        reader = fallback.read
        doc.notes.append(f"no precise reader for '{ext}'; using the fallback converter")

    try:
        doc = reader(doc, data)
    except Exception as exc:                       # a reader must never escape
        doc.readable = False
        doc.unreadable_reason = "corrupt"
        doc.notes.append(f"{type(exc).__name__}: {exc}")
        return doc

    if doc.readable and not doc.text.strip():
        doc.readable = False
        doc.unreadable_reason = doc.unreadable_reason or "empty_file"
    return doc


def compare_uploads(
    si_filename: str, si_bytes: bytes,
    bl_filename: str, bl_bytes: bytes,
    *, llm: Optional[LLMClient] = None,
) -> CaseResult:
    si_doc = read_upload(si_filename, si_bytes)
    bl_doc = read_upload(bl_filename, bl_bytes)
    doctype.classify_document(si_doc)
    doctype.classify_document(bl_doc)

    result = CaseResult(email_id="upload", category="BL_COMPARISON", decided_by="rule")
    result.si_doc = si_doc
    result.bl_doc = bl_doc

    pair_problem = doctype.pair_problem(si_doc, bl_doc)
    assisted = pair_problem is None and llm is not None

    si_fields = extract_mod.extract_fields(si_doc, "SI") if si_doc.readable else None
    bl_fields = extract_mod.extract_fields(bl_doc, "BL") if bl_doc.readable else None
    if assisted:
        if si_fields is not None:
            si_fields = extract_llm.fill_missing_fields(si_doc, si_fields, "SI", client=llm)
        if bl_fields is not None:
            bl_fields = extract_llm.fill_missing_fields(bl_doc, bl_fields, "BL", client=llm)
        result.decided_by = "llm"

    comparisons = []
    if si_fields is not None and bl_fields is not None:
        comparisons = compare_mod.compare_documents(si_fields, bl_fields)
    result.comparisons = comparisons

    # Both documents were handed to us directly, so there is no "did the sender
    # mean to attach one" ambiguity for the intent check to resolve — unlike an
    # inbox email, an upload cannot be missing a pair.
    intent = Intent(
        expects_attached_documents=True,
        requests_draft=False,
        confidence=1.0,
        rationale=["both documents were uploaded directly via /compare"],
    )
    decision = evidence_gate.evaluate(
        si_doc=si_doc, bl_doc=bl_doc,
        si_fields=si_fields, bl_fields=bl_fields,
        comparisons=comparisons, intent=intent, pair_problem=pair_problem,
    )
    Pipeline._apply(decision, comparisons, result)
    return result
