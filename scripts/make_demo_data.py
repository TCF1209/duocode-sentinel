#!/usr/bin/env python3
"""make_demo_data.py — curate the small inbox the deployed demo serves.

    python scripts/make_demo_data.py
    python scripts/make_demo_data.py --report runs/postmerge/report.json
    python scripts/make_demo_data.py --out demo_data --quiet

Why this exists
---------------
`data/` is git-ignored (3.3 MB, 520 emails, 251 attachments) and Render builds
the container from git, so a deployed API has no inbox at all and `POST /runs`
fails on an empty directory. `docs/ROADMAP.md` §3 chose a curated subset
committed as `demo_data/` over committing the whole bundle: small enough to
load instantly, complete enough to tell the entire story on stage.

What "the entire story" means is spelled out as slots below — one slot per
thing a judge must be able to see happen. Every slot carries the reason it is
in the set. If a slot cannot be filled the script fails rather than quietly
shipping a demo with a hole in it, and the coverage it promises is re-checked
against the finished selection (`_verify_selection`) before anything is
written, not assumed.

Selection is deterministic
--------------------------
Candidates are always scanned in `email_id` order and the first one that fits a
slot wins. No sampling, no shuffling, no seed. Two consequences, both wanted:
the subset is reproducible on a teammate's machine, and it is reviewable — a
slot's pick can be argued with, which a random draw cannot.

Where the labels come from: they do not
---------------------------------------
Selection reads the pipeline's own `report.json`, never `data/_grader/`.
CLAUDE.md rule 1 forbids the answer key to any code that decides anything, and
this script decides what ships. Using our own verdicts is also the honest
construction: the subset is "cases the pipeline says are interesting", and the
claim that they are the *right* verdicts rests on the full 520-email score in
`docs/SCORING.md`, not on anything asserted here.

Nothing labelled is written either. The output is inbox JSON plus attachments —
exactly the participant-bundle shape, which the organisers confirmed may be
published — and `_verify_written` re-reads every emitted record to prove no
verdict, reason or defect field leaked into it.
"""
from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]

# The seven compared fields, in the order docs/DATA_NOTES.md §2 lists them.
FIELDS = ("shipper", "consignee", "notify_party", "port_of_loading",
          "port_of_discharge", "container_count", "gross_weight_kg")

# The participant record's exact key set. Emitting anything else would mean we
# had started shipping our own annotations alongside the data.
EMAIL_KEYS = {"email_id", "from", "subject", "body", "attachments"}

CATEGORIES = ("BL_COMPARISON", "SI_REQUEST", "INVOICE_QUERY", "GENERAL", "SPAM")
REVIEW_REASONS = ("wrong_doc_type", "missing_attachment", "unreadable", "missing_value")

# The four ways a pair arrives in the real bundle, measured over its 46 defect
# emails: 33 txt-only, 6 docx+xlsx, 3 xlsx-only, 4 pdf-only. Each group is a
# different reader, so a defect in each is what proves each reader works.
FORMAT_GROUPS = {
    (".txt", ".txt"): "txt-only",
    (".pdf", ".pdf"): "pdf-only",
    (".xlsx", ".xlsx"): "xlsx-only",
    (".docx", ".xlsx"): "docx+xlsx",
}


# --------------------------------------------------------------------------
#  A candidate: one email, joined to what the pipeline decided about it
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Case:
    email_id: str
    subject: str
    category: str
    status: str
    review_reason: Optional[str]
    defect_fields: tuple[str, ...]
    attachments: tuple[str, ...]
    exts: tuple[str, ...]
    doc_types: tuple[str, ...]
    unreadable_reasons: tuple[str, ...]
    notes: tuple[str, ...]

    @property
    def format_group(self) -> str:
        """One of the four groups above where the pair is one of them, and a
        derived name otherwise — an unreadable case can pair a readable .txt SI
        with a broken .pdf, which is a real shape but never a defect's shape."""
        if not self.exts:
            return "none"
        return FORMAT_GROUPS.get(self.exts,
                                 "+".join(e.lstrip(".") for e in self.exts))

    @property
    def intent(self) -> str:
        """`classify/intent.py` records its verdict as a note. It is the only
        thing separating the two halves of the DATA_NOTES §5a pair, so the
        selector reads it rather than re-deriving it from the body text."""
        for note in self.notes:
            if note.startswith("intent:"):
                return note[len("intent:"):]
        return ""

    def has_unreadable(self, reason: str) -> bool:
        return reason in self.unreadable_reasons


def load_cases(data_root: Path, report_path: Path) -> list[Case]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    cases: list[Case] = []
    for path in sorted((data_root / "inbox").glob("email_*.json")):
        email = json.loads(path.read_text(encoding="utf-8"))
        eid = email["email_id"]
        rec = report.get(eid)
        if rec is None:
            raise SystemExit(
                f"{report_path} has no record for {eid}. It was produced from a "
                f"different inbox, or with --limit; re-run backend/run.py over "
                f"{data_root} in full."
            )
        docs = [d for d in (rec.get("documents") or {}).values() if d]
        atts = tuple(email["attachments"])
        cases.append(Case(
            email_id=eid,
            subject=email["subject"],
            category=rec["category"],
            status=rec["status"],
            review_reason=rec["review_reason"],
            defect_fields=tuple(rec["defect_fields"]),
            attachments=atts,
            exts=tuple(sorted(Path(a).suffix.lower() for a in atts)),
            doc_types=tuple(d["doc_type"] for d in docs),
            unreadable_reasons=tuple(d["unreadable_reason"] for d in docs
                                     if d["unreadable_reason"]),
            notes=tuple(rec.get("notes") or ()),
        ))
    return cases


# --------------------------------------------------------------------------
#  Slots — each one is a sentence in the demo, in the order it earns its place
# --------------------------------------------------------------------------
Want = Callable[[Case, Sequence[Case]], bool]


@dataclass(frozen=True)
class Slot:
    key: str
    story: str          # printed, and written into demo_data/README.md
    want: Want
    required: bool = True


def _is_comparison(c: Case) -> bool:
    return c.category == "BL_COMPARISON"


def _defect_fields_seen(picked: Sequence[Case]) -> set[str]:
    return {f for c in picked for f in c.defect_fields}


def _subjects_seen(picked: Sequence[Case], category: str) -> set[str]:
    return {c.subject for c in picked if c.category == category}


def _slots() -> list[Slot]:
    """Ordered deliberately: the scarce, structural cases choose first, because
    a clean txt pair can be filled by 51 candidates and a corrupt PDF by two."""
    slots: list[Slot] = [
        # -- DATA_NOTES §5a, the single most instructive pair in the set. Two
        # -- emails, both BL_COMPARISON, both with zero attachments, opposite
        # -- correct outcomes. Nothing separates them but what the sender is
        # -- asking for, which is why counting attachments is not enough and
        # -- why classify/intent.py exists. A judge who sees only these two
        # -- has seen the thesis of the project.
        Slot("pair.draft_requested",
             "Zero attachments, asking us to PRODUCE a draft BL — correctly OK, "
             "nothing to compare yet (DATA_NOTES §5a, case A).",
             lambda c, p: (_is_comparison(c) and not c.attachments
                           and c.status == "OK" and c.intent == "requests_draft")),
        Slot("pair.attachments_dropped",
             "Zero attachments, asking us to CHECK documents the sender believes "
             "they attached — correctly NEEDS_REVIEW (DATA_NOTES §5a, case B).",
             lambda c, p: (_is_comparison(c) and not c.attachments
                           and c.review_reason == "missing_attachment")),

        # -- The four escalation reasons (DATA_NOTES §5). The review queue is
        # -- half the product: a case the system declines to decide, with a
        # -- reason an operator can act on, is a success, not a gap.
        Slot("escalate.wrong_doc_type",
             "The attached 'BL' is really another document entirely — the "
             "doc-type classifier catches it before any field is compared.",
             lambda c, p: c.review_reason == "wrong_doc_type"),
        Slot("escalate.unreadable_scan",
             "An image-only scanned PDF pair: no text layer, so nothing can be "
             "read deterministically. This is the one case the vision path "
             "transcribes — and it still escalates, because a transcript is "
             "reviewer evidence, not an extracted value.",
             lambda c, p: (c.review_reason == "unreadable"
                           and c.has_unreadable("no_text_layer"))),
        Slot("escalate.unreadable_corrupt",
             "A different failure mode in the same reason: a PDF that will not "
             "open at all, next to a perfectly readable SI. Half a readable "
             "pair is still not a comparison.",
             lambda c, p: (c.review_reason == "unreadable"
                           and c.has_unreadable("corrupt"))),
        Slot("escalate.missing_value",
             "A required field left as ??? / TBA. CLAUDE.md rule 4: a blank is "
             "NEEDS_REVIEW, never a MISMATCH — reporting a discrepancy on an "
             "empty field is a false alarm that costs precision.",
             lambda c, p: c.review_reason == "missing_value"),
        Slot("escalate.half_a_pair",
             "A comparison request carrying exactly ONE document. Distinct from "
             "the zero-attachment case above and worth showing beside it: you "
             "cannot compare a pair with half a pair.",
             lambda c, p: (c.review_reason == "missing_attachment"
                           and len(c.attachments) == 1)),

        # -- One planted defect per format group. These are the reader-coverage
        # -- slots: the PDF defect is the only thing that proves the coordinate
        # -- reader of DATA_NOTES §3 works on a real two-column form, and the
        # -- docx+xlsx defect is the only thing that proves the office readers
        # -- survive Chinese labels (Trap 2b) and numeric cells.
        Slot("defect.pdf",
             "A real discrepancy found inside a two-column PDF form — the "
             "coordinate-based reader, on the layout that defeats a "
             "line-oriented parser (DATA_NOTES §3).",
             lambda c, p: c.status == "MISMATCH" and c.format_group == "pdf-only"),
        Slot("defect.docx_xlsx",
             "A discrepancy across a .docx SI and an .xlsx BL — different "
             "readers on each side, Chinese label text on one of them.",
             lambda c, p: c.status == "MISMATCH" and c.format_group == "docx+xlsx"),
        Slot("defect.xlsx",
             "A discrepancy between two spreadsheets, where the weight is stored "
             "as a bare number rather than '131,058 KG' (DATA_NOTES §4).",
             lambda c, p: c.status == "MISMATCH" and c.format_group == "xlsx-only"),
        Slot("defect.txt_one_field",
             "The smallest real defect: one field out of seven differs. 20 of "
             "the bundle's 46 defects are this size.",
             lambda c, p: (c.status == "MISMATCH" and c.format_group == "txt-only"
                           and len(c.defect_fields) == 1)),
        Slot("defect.txt_two_fields",
             "A two-field defect, the other 26. Picking a party-name defect here "
             "also shows the address-block trap: the generator swaps the name and "
             "leaves the old address behind, so only the entity name is compared.",
             lambda c, p: (c.status == "MISMATCH" and c.format_group == "txt-only"
                           and len(c.defect_fields) == 2)),
    ]

    # -- One slot per compared field, so the discrepancy screen can show every
    # -- one of the seven at least once. Most are already satisfied by the
    # -- format slots above and cost nothing; `required=False` means "skip if
    # -- this field is already on screen", not "shrug if it is missing" — the
    # -- final check below is what makes the promise binding.
    for field in FIELDS:
        slots.append(Slot(
            f"defect.field.{field}",
            f"Puts `{field}` on the discrepancy screen — no compared field "
            f"should be one the demo never shows failing.",
            (lambda f: lambda c, p: (c.status == "MISMATCH"
                                     and f in c.defect_fields
                                     and f not in _defect_fields_seen(p)))(field),
            required=False,
        ))

    slots += [
        # -- Clean comparisons, one per format group plus two more. A demo in
        # -- which every case is broken is not a credible operations tool: the
        # -- everyday outcome is "seven fields agree, nothing to do", and the
        # -- triage screen needs enough of those rows to look like an inbox.
        # -- These also prove the readers on each format do not invent
        # -- discrepancies, which is the expensive failure (ADVERSARIAL.md).
        Slot("clean.pdf",
             "A PDF pair that matches on all seven fields — the coordinate "
             "reader producing a clean bill of health, not just catching faults.",
             lambda c, p: (_is_comparison(c) and c.status == "OK"
                           and c.format_group == "pdf-only")),
        Slot("clean.xlsx",
             "A clean spreadsheet pair.",
             lambda c, p: (_is_comparison(c) and c.status == "OK"
                           and c.format_group == "xlsx-only")),
        Slot("clean.docx_xlsx",
             "A clean .docx/.xlsx pair — the office readers agreeing across "
             "two different label vocabularies.",
             lambda c, p: (_is_comparison(c) and c.status == "OK"
                           and c.format_group == "docx+xlsx")),
        Slot("clean.txt.1",
             "The everyday case: a plain-text pair, all seven fields matched, "
             "no action needed.",
             lambda c, p: (_is_comparison(c) and c.status == "OK"
                           and c.format_group == "txt-only")),
        Slot("clean.txt.2",
             "A second one, because one clean case reads as an anecdote.",
             lambda c, p: (_is_comparison(c) and c.status == "OK"
                           and c.format_group == "txt-only")),
    ]

    # -- The other four categories. Stage 1 is scored with macro-F1, so the
    # -- small classes matter as much as BL_COMPARISON (DATA_NOTES §6); the
    # -- triage screen has to show five categories or it shows a classifier
    # -- with nothing to do. Distinct subjects, because three copies of the
    # -- same template demonstrate the classifier once, not three times.
    first_story = {
        "SI_REQUEST": "An SI request. Every one of these ends with 'revert with "
                      "draft BL once available' — the phrase 'draft BL' alone "
                      "must not route an email to BL_COMPARISON (DATA_NOTES §6).",
        "INVOICE_QUERY": "A billing query: charges, freight, credit notes. "
                         "Nothing to compare, and nothing to escalate.",
    }
    for i in range(1, 4):
        for category in ("SI_REQUEST", "INVOICE_QUERY"):
            slots.append(Slot(
                f"category.{category.lower()}.{i}",
                first_story[category] if i == 1
                else f"A second/third {category}, on a different subject template.",
                (lambda cat: lambda c, p: (c.category == cat
                                           and c.subject not in _subjects_seen(p, cat)))(category),
            ))

    slots += [
        # -- The two classification traps DATA_NOTES §6 names by hand. They are
        # -- the emails a keyword classifier gets wrong, so they are the ones
        # -- worth putting in front of a judge.
        Slot("general.si_trap",
             "GENERAL, not SI_REQUEST — a bulk reminder whose subject says "
             "'Submit SI'. The classifier keys off the real signal, not the "
             "keyword (DATA_NOTES §6).",
             lambda c, p: c.category == "GENERAL" and "si" in _subject_words(c)),
        Slot("general.bl_trap",
             "GENERAL, not BL_COMPARISON — an operational notice about BLs with "
             "nothing attached and nothing to check.",
             lambda c, p: c.category == "GENERAL" and "bl" in _subject_words(c)),
        Slot("general.routine",
             "Ordinary operational traffic: a schedule update or planning note.",
             lambda c, p: (c.category == "GENERAL"
                           and c.subject not in _subjects_seen(p, "GENERAL"))),
    ]

    for i in range(1, 4):
        slots.append(Slot(
            f"category.spam.{i}",
            "Spam. The smallest class and the most separable one — and under "
            "macro-F1 one spam error costs as much as five BL_COMPARISON "
            "errors, so it is never the class to leave out." if i == 1
            else "Another spam archetype — phishing, crypto, storage-full. "
                 "Three templates, not three copies of one.",
            lambda c, p: (c.category == "SPAM"
                          and c.subject not in _subjects_seen(p, "SPAM")),
        ))

    return slots


def _subject_words(c: Case) -> set[str]:
    """Subject tokens, lowercased. Word-level on purpose: substring matching
    finds 'si' inside 'business' and 'bl' inside 'available', which is exactly
    the mistake the classifier itself is built to avoid."""
    cleaned = "".join(ch if ch.isalnum() else " " for ch in c.subject.lower())
    return set(cleaned.split())


def select(cases: Sequence[Case], slots: Sequence[Slot]) -> list[tuple[Slot, Case]]:
    ordered = sorted(cases, key=lambda c: c.email_id)
    picked: list[Case] = []
    chosen: list[tuple[Slot, Case]] = []
    taken: set[str] = set()
    for slot in slots:
        hit = next((c for c in ordered
                    if c.email_id not in taken and slot.want(c, picked)), None)
        if hit is None:
            if slot.required:
                raise SystemExit(
                    f"No email fits the required slot '{slot.key}'.\n"
                    f"  {slot.story}\n"
                    f"The bundle or the pipeline's verdicts changed; fix the slot "
                    f"or the pipeline, do not delete the slot."
                )
            continue
        taken.add(hit.email_id)
        picked.append(hit)
        chosen.append((slot, hit))
    return chosen


# --------------------------------------------------------------------------
#  Writing the subset
# --------------------------------------------------------------------------
def write_subset(data_root: Path, out_dir: Path, picked: Sequence[Case]) -> int:
    """Copy the selected emails and their attachments verbatim. Returns bytes
    written. Files are copied byte-for-byte rather than re-serialised so the
    subset is provably the same data the pipeline was measured on, and so a
    future change to our JSON formatting cannot silently rewrite it."""
    inbox_dir = out_dir / "inbox"
    att_dir = out_dir / "attachments"
    # Idempotency: a stale file from an earlier selection would otherwise
    # survive and the API would serve an email no slot justifies.
    for d in (inbox_dir, att_dir):
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)

    total = 0
    for case in sorted(picked, key=lambda c: c.email_id):
        src = data_root / "inbox" / f"{case.email_id}.json"
        blob = src.read_bytes()
        (inbox_dir / src.name).write_bytes(blob)
        total += len(blob)
        for rel in case.attachments:
            att = (data_root / rel)
            blob = att.read_bytes()
            (att_dir / att.name).write_bytes(blob)
            total += len(blob)
    return total


def _counts(picked: Sequence[Case]) -> dict[str, dict[str, int]]:
    out = {"category": {}, "status": {}, "review_reason": {}, "format_group": {}}
    for c in picked:
        out["category"][c.category] = out["category"].get(c.category, 0) + 1
        out["status"][c.status] = out["status"].get(c.status, 0) + 1
        if c.review_reason:
            out["review_reason"][c.review_reason] = out["review_reason"].get(c.review_reason, 0) + 1
        if c.attachments:
            g = c.format_group
            out["format_group"][g] = out["format_group"].get(g, 0) + 1
    return {k: dict(sorted(v.items())) for k, v in out.items()}


# --------------------------------------------------------------------------
#  Verification — the promises this script makes, re-checked against the result
# --------------------------------------------------------------------------
class _Checks:
    """Collects the assertions so all failures are reported at once — being
    told one missing category at a time, re-running, and being told the next is
    a waste of the only evening left before the deadline.

    Written as explicit raises rather than `assert` statements: `assert`
    vanishes under `python -O`, and a guarantee that can be switched off from
    the command line is not a guarantee."""

    def __init__(self, headline: str) -> None:
        self.headline = headline
        self.results: list[tuple[str, bool]] = []
        self.failures: list[str] = []

    def __call__(self, label: str, ok: bool, detail: str) -> None:
        self.results.append((label, ok))
        if not ok:
            self.failures.append(detail)

    def done(self) -> list[tuple[str, bool]]:
        if self.failures:
            raise SystemExit(f"{self.headline}\n  " + "\n  ".join(self.failures))
        return self.results


def _verify_selection(picked: Sequence[Case]) -> list[tuple[str, bool]]:
    """The coverage the demo exists for, checked before a single file is
    written, so a selection with a hole in it never reaches disk where someone
    could commit it."""
    check = _Checks("Coverage check FAILED — nothing written:")

    cats = {c.category for c in picked}
    check("all 5 categories", cats == set(CATEGORIES),
          f"categories missing: {sorted(set(CATEGORIES) - cats)}")

    reasons = {c.review_reason for c in picked if c.review_reason}
    check("all 4 escalation reasons", reasons == set(REVIEW_REASONS),
          f"escalation reasons missing: {sorted(set(REVIEW_REASONS) - reasons)}")

    defects = [c for c in picked if c.status == "MISMATCH"]
    sizes = {len(c.defect_fields) for c in defects}
    check("defect of 1 field", 1 in sizes, "no single-field defect selected")
    check("defect of 2 fields", 2 in sizes, "no two-field defect selected")

    groups = {c.format_group for c in defects}
    for group in FORMAT_GROUPS.values():
        check(f"defect in {group}", group in groups,
              f"no defect selected in the {group} format group — the reader "
              f"behind it would go undemonstrated")

    fields = _defect_fields_seen(defects)
    check("all 7 fields shown failing", set(FIELDS) <= fields,
          f"fields never shown as a discrepancy: {sorted(set(FIELDS) - fields)}")

    clean = [c for c in picked
             if c.category == "BL_COMPARISON" and c.status == "OK" and c.attachments]
    check("clean comparisons >= 3", len(clean) >= 3,
          f"only {len(clean)} clean comparisons — a demo where everything is "
          f"broken is not credible")

    zero = [c for c in picked if c.category == "BL_COMPARISON" and not c.attachments]
    pair_ok = any(c.status == "OK" for c in zero)
    pair_review = any(c.review_reason == "missing_attachment" for c in zero)
    check("the DATA_NOTES §5a pair", pair_ok and pair_review,
          "the zero-attachment pair is incomplete — both halves are needed or "
          "the intent distinction is invisible")

    n = len(picked)
    check("size within 30-40", 30 <= n <= 40,
          f"{n} emails selected; ROADMAP §3 sized this at roughly 30-40 and a "
          f"drift this large means the slots changed meaning")

    return check.done()


def _verify_written(picked: Sequence[Case], out_dir: Path) -> list[tuple[str, bool]]:
    """The data boundary, checked on what actually reached disk rather than on
    what we meant to write. The subset carries no labels: a verdict that got
    into an emitted record would be published the moment the repo goes public,
    and the organisers' package may never be."""
    check = _Checks("Data-boundary check FAILED — do not commit this output:")

    written = sorted((out_dir / "inbox").glob("email_*.json"))
    check("emitted file count", len(written) == len(picked),
          f"{len(written)} files written for {len(picked)} selected emails")

    stray = set()
    for path in written:
        stray |= set(json.loads(path.read_text(encoding="utf-8"))) - EMAIL_KEYS
    check("no labels in the output", not stray,
          f"emitted records carry non-participant keys: {sorted(stray)}")

    wanted = {Path(a).name for c in picked for a in c.attachments}
    present = {p.name for p in (out_dir / "attachments").iterdir()}
    check("attachments complete and exact", wanted == present,
          f"attachment mismatch: missing {sorted(wanted - present)}, "
          f"unexpected {sorted(present - wanted)}")

    return check.done()


# --------------------------------------------------------------------------
#  README — the subset has to explain itself to whoever finds it in the repo
# --------------------------------------------------------------------------
def render_readme(chosen: Sequence[tuple[Slot, Case]], counts: dict,
                  n_bytes: int, n_source: int) -> str:
    """No timestamp anywhere in here on purpose: a generated file that changes
    every time it is generated cannot be diffed, and `git status` would nag
    about a demo nobody edited."""
    picked = [c for _, c in chosen]
    n_att = sum(len(c.attachments) for c in picked)
    lines = [
        "# demo_data — the curated inbox the live demo serves",
        "",
        "**Generated. Do not edit by hand.** Re-create it with:",
        "",
        "```bash",
        ".venv/Scripts/python.exe scripts/make_demo_data.py",
        "```",
        "",
        f"{len(picked)} emails and {n_att} attachments — {n_bytes / 1024:.0f} KB of "
        f"inbox JSON and attachments, drawn from the {n_source}-email participant bundle.",
        "",
        "## Why this exists",
        "",
        "`data/` is git-ignored and Render builds from git, so a deployed",
        "container has no inbox and `POST /runs` has nothing to run over. This",
        "is the smallest subset that still tells the whole story: every",
        "category, every escalation reason, a real defect in every attachment",
        "format, and enough clean cases that the demo looks like an operations",
        "inbox rather than a fault museum.",
        "",
        "## What it is not",
        "",
        "It carries **no labels** — inbox JSON and attachments only, exactly the",
        "participant-bundle shape the organisers confirmed may be published.",
        "Nothing from the organisers' package is here, and nothing from it ever",
        "may be (`docs/SCORING.md` §3).",
        "",
        "It is also **deliberately not representative**: defects and escalations",
        "are over-sampled so a five-minute demo can show them. Counting statuses",
        "here tells you nothing about the pipeline's accuracy — that claim lives",
        "in `docs/SCORING.md`, measured over all 520 emails.",
        "",
        "## How it was chosen",
        "",
        "`scripts/make_demo_data.py` joins the bundle to a pipeline run's",
        "`report.json` and fills one slot at a time, scanning candidates in",
        "`email_id` order and taking the first that fits. No randomness: the",
        "same inputs give a byte-identical subset, and every pick can be argued",
        "with. The script asserts the coverage below before it writes, and never",
        "opens `data/_grader/`.",
        "",
        "## The slots, and what each one is here to show",
        "",
        "| email | slot | why it is in the set |",
        "|---|---|---|",
    ]
    for slot, case in chosen:
        lines.append(f"| `{case.email_id}` | `{slot.key}` | {slot.story} |")

    lines += ["", "## What is in it", ""]
    for heading, key in (("Category", "category"), ("Status", "status"),
                         ("Escalation reason", "review_reason"),
                         ("Attachment shape", "format_group")):
        lines.append(f"**{heading}**")
        lines.append("")
        for name, n in counts[key].items():
            lines.append(f"- `{name}` — {n}")
        lines.append("")

    lines += [
        "## Running it",
        "",
        "```bash",
        ".venv/Scripts/python.exe backend/run.py --data demo_data --out runs/demo",
        "```",
        "",
        "The API serves it by pointing `SENTINEL_DATA_ROOT` at this folder;",
        "`backend/api/main.py` falls back to `data/bundle` for local work.",
        "",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    # Relative paths resolve against the repo root, not the shell's directory,
    # so the same command works from anywhere and the output cannot land in a
    # stray demo_data/ next to wherever someone happened to be standing.
    ap.add_argument("--data", default="data/bundle",
                    help="the participant bundle to draw from (relative to the repo root)")
    ap.add_argument("--report", default="runs/latest/report.json",
                    help="a full pipeline run over --data; supplies the verdicts")
    ap.add_argument("--out", default="demo_data", help="where to write the subset")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    data_root = (ROOT / args.data).resolve() if not Path(args.data).is_absolute() else Path(args.data)
    report_path = (ROOT / args.report).resolve() if not Path(args.report).is_absolute() else Path(args.report)
    out_dir = (ROOT / args.out).resolve() if not Path(args.out).is_absolute() else Path(args.out)

    # CLAUDE.md rule 1, enforced rather than trusted: the answer key is one
    # `--data data/_grader` away and a typo must not be the thing that stops it.
    for path in (data_root, report_path):
        if "_grader" in path.parts:
            raise SystemExit(f"Refusing to read {path}: the organisers' package is "
                             f"off limits to everything that decides what ships.")
    if not (data_root / "inbox").is_dir():
        raise SystemExit(f"No inbox at {data_root / 'inbox'}.")
    if not report_path.is_file():
        raise SystemExit(
            f"No report at {report_path}. Produce one first:\n"
            f"  .venv/Scripts/python.exe backend/run.py --data {args.data} --out runs/latest"
        )

    cases = load_cases(data_root, report_path)
    chosen = select(cases, _slots())
    picked = [c for _, c in chosen]

    results = _verify_selection(picked)
    n_bytes = write_subset(data_root, out_dir, picked)
    results += _verify_written(picked, out_dir)

    counts = _counts(picked)
    readme = render_readme(chosen, counts, n_bytes, n_source=len(cases))
    # Bytes, not write_text: on Windows the default newline translation would
    # emit CRLF and the "running it twice is byte-identical" promise would hold
    # only per platform.
    readme_bytes = readme.encode("utf-8")
    (out_dir / "README.md").write_bytes(readme_bytes)
    n_bytes += len(readme_bytes)

    if not args.quiet:
        _print_summary(chosen, counts, results, n_bytes, out_dir)
    return 0


def _print_summary(chosen: Sequence[tuple[Slot, Case]], counts: dict,
                   results: Sequence[tuple[str, bool]], n_bytes: int,
                   out_dir: Path) -> None:
    picked = [c for _, c in chosen]
    n_att = sum(len(c.attachments) for c in picked)
    print("=" * 72)
    print(f"  demo_data  ·  {len(picked)} emails  ·  {n_att} attachments  "
          f"·  {n_bytes / 1024:.0f} KB")
    print("=" * 72)

    print("\nSelection")
    for slot, case in chosen:
        detail = case.status
        if case.review_reason:
            detail += f"/{case.review_reason}"
        if case.defect_fields:
            detail += f" {list(case.defect_fields)}"
        print(f"  {case.email_id}  {slot.key:<28} {case.category:<14} {detail}")

    for heading, key in (("Categories", "category"), ("Statuses", "status"),
                         ("Escalation reasons", "review_reason"),
                         ("Attachment shapes", "format_group")):
        print(f"\n{heading}")
        for name, n in counts[key].items():
            print(f"  {name:<20} {n:>3}")

    print("\nCoverage asserted")
    for label, ok in results:
        print(f"  [{'x' if ok else ' '}] {label}")

    print(f"\nWrote {out_dir}")


if __name__ == "__main__":
    raise SystemExit(main())
