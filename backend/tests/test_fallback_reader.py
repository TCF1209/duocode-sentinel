"""The fallback reader: unfamiliar formats must degrade, not fail.

These tests pin the two properties the pipeline depends on — that an unknown
extension still yields readable chunks, and that an unreadable file still comes
back as a diagnosis rather than an exception.
"""
from __future__ import annotations

import csv
import io

import pytest

from sdoc.labels import resolve
from sdoc.readers import read_attachment
from sdoc.readers.fallback import _chunks_from_markdown


def test_markdown_table_becomes_labelled_chunks():
    chunks = _chunks_from_markdown(
        "# BILL OF LADING (DRAFT)\n"
        "\n"
        "| Shipper/Exporter | APRIL FAR EAST (M) SDN BHD |\n"
        "| --- | --- |\n"
        "| Port of Discharge (POD) | KARACHI, PAKISTAN |\n"
        "| Container Count | 6 x 40'HC |\n"
    )
    by_field = {resolve(c.label): c.value for c in chunks if resolve(c.label)}
    assert by_field["shipper"] == "APRIL FAR EAST (M) SDN BHD"
    assert by_field["port_of_discharge"] == "KARACHI, PAKISTAN"
    assert by_field["container_count"] == "6 x 40'HC"


def test_separator_row_is_not_a_chunk():
    chunks = _chunks_from_markdown("| --- | --- |\n| Notify Party | UAB NOVAKOPA |\n")
    assert len(chunks) == 1
    assert resolve(chunks[0].label) == "notify_party"


def test_value_split_across_markdown_columns_is_rejoined():
    # markitdown splits a value containing a literal "|" across columns.
    chunks = _chunks_from_markdown("| Consignee | ROXCEL TRADING GMBH | OPERNRING 3-5 |\n")
    assert chunks[0].value.startswith("ROXCEL TRADING GMBH")
    assert "OPERNRING 3-5" in chunks[0].value


def test_plain_label_value_lines_outside_a_table():
    chunks = _chunks_from_markdown("Load Port: NANTONG, CHINA\nGross Weight (KG): 131,058 KG\n")
    by_field = {resolve(c.label): c.value for c in chunks if resolve(c.label)}
    assert by_field["port_of_loading"] == "NANTONG, CHINA"
    assert by_field["gross_weight_kg"] == "131,058 KG"


def test_unknown_extension_routes_to_the_fallback(tmp_path):
    # .csv has no precise reader; it must still come back readable.
    path = tmp_path / "attachments"
    path.mkdir()
    with open(path / "manifest.tsv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["Shipper", "APRIL FAR EAST (M) SDN BHD"])
        w.writerow(["Total Containers", "6 x 40'HC"])

    doc = read_attachment(tmp_path, "attachments/manifest.tsv")
    assert doc.readable, doc.unreadable_reason
    assert doc.text.strip()


def test_missing_file_is_diagnosed_not_raised(tmp_path):
    doc = read_attachment(tmp_path, "attachments/nothing_here.pptx")
    assert doc.readable is False
    assert doc.unreadable_reason == "missing_file"


def test_zero_byte_file_is_diagnosed(tmp_path):
    (tmp_path / "attachments").mkdir()
    (tmp_path / "attachments" / "empty.pptx").write_bytes(b"")
    doc = read_attachment(tmp_path, "attachments/empty.pptx")
    assert doc.readable is False
    assert doc.unreadable_reason == "empty_file"


def test_garbage_bytes_in_a_known_wrapper_are_diagnosed(tmp_path):
    (tmp_path / "attachments").mkdir()
    (tmp_path / "attachments" / "broken.pptx").write_bytes(b"PK\x03\x04" + b"\x00" * 300)
    doc = read_attachment(tmp_path, "attachments/broken.pptx")
    assert doc.readable is False
    assert doc.unreadable_reason in {"corrupt", "empty_file", "no_text_layer"}
