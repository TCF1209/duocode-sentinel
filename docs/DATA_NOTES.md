# Dataset notes — what we actually found in the data

> Read this before touching the extraction code. Every item here is something
> that *will* silently cost us points if the pipeline ignores it. Everything
> was verified by reading the real files in `data/bundle/`, not assumed.

---

## 1. Shape of the inbox

520 emails in `inbox/`, 250 attachment files in `attachments/`.

| Category | Count | Carries attachments? |
|---|---:|---|
| `BL_COMPARISON` | 220 | only ~124; the rest ask us to *send* a BL |
| `SI_REQUEST` | 125 | no |
| `INVOICE_QUERY` | 75 | no |
| `GENERAL` | 60 | no |
| `SPAM` | 40 | no |

Attachment formats: 192 `.txt`, 28 `.pdf`, 22 `.xlsx`, 8 `.docx`.
Format pairings seen: `txt+txt`, `pdf+pdf`, `xlsx+docx`, `xlsx+xlsx`.

Roughly 109 genuine SI+BL pairs are comparable; about half of them carry a
planted discrepancy, and a discrepancy is 1 or 2 fields.

---

## 2. The seven fields, and how they are labelled

`shipper, consignee, notify_party, port_of_loading, port_of_discharge,
container_count, gross_weight_kg`

The SI and the BL deliberately use **different labels for the same fact**.
Observed variants:

| Field | Seen as |
|---|---|
| shipper | `Shipper`, `Shipper/Exporter`, `Shipper (Principal or Seller)`, `SHIPPER` |
| consignee | `Consignee`, `Consignee (Non-Negotiable)`, `CONSIGNEE`, **`To the Order of`** |
| notify_party | `Notify Party`, `Notify`, **`Notify Party/Intermediate Consignee`**, `NOTIFY PARTY` |
| port_of_loading | `Port of Loading`, `Port of Loading (POL)`, `Load Port`, `POL` |
| port_of_discharge | `Port of Discharge`, `Port of Discharge (POD)`, `Discharge Port`, `POD` |
| container_count | `No. of Containers`, `Total Containers`, `No. of Containers or Packages`, `Container Count` |
| gross_weight_kg | `Gross Weight (KG)`, `Gross Wt (kgs)`, `Gross Weight毛重(KGS)`, `GROSS WEIGHT` |

### Trap 2a — "Notify Party/Intermediate Consignee" contains the word *Consignee*

Any label matcher that checks `consignee` before `notify` will read the notify
party into the consignee slot. In `labels.py` the NOTIFY rule is evaluated
**first**, on purpose. Do not reorder it.

### Trap 2b — `.docx` labels carry Chinese

`Shipper/Exporter (发货人)`, `GROSS WEIGHT (毛重 KGS)`. Normalisation strips
anything that is not ASCII alphanumeric, so these collapse onto the English
form. Do not "fix" `normalize.basic()` to keep Unicode letters.

---

## 3. The PDF trap (this one is expensive)

`pdftotext -layout` on a real SI in the set produces:

```
Shipper/Exporter   APRIL FINE PAPER TRADING
                   ON BEHALF OF VITAL SOLUTIONS PTE LTD
To the Order of    77 ROBINSON ROAD, #21-01        <-- this is NOT the consignee
NOTIFY PARTY
Load Port          8 TEMASEK BOULEVARD             <-- this is NOT the load port
Port of Discharge  #42-01 SUNTEC TOWER 3
Ocean Vessel       SINGAPORE 038988
```

The document is a two-column form: labels in a narrow left column, values in a
wide right column. Because address blocks are several lines tall, the *nth*
label no longer sits on the same output line as the *nth* value. A
line-oriented parser produces confident nonsense — it would report the
consignee as `77 ROBINSON ROAD, #21-01` and then flag a discrepancy that does
not exist. **False alarms cost us precision on Stage 3.**

Reading the same file in content-stream order shows the truth:

```
Shipper/Exporter APRIL FINE PAPER TRADING
ON BEHALF OF VITAL SOLUTIONS PTE LTD
To the Order of KPP-ANTALIS (SINGAPORE) PTE. LTD.
Load Port RUGAO/NANTONG/SHANGHAI, CHINA
Total Containers: 5 x 40'HC
TOTAL GROSS WEIGHT: 118,270 KG
```

**Our fix** (`readers/pdf.py`): work from word coordinates. Group words into
rows by vertical position, find the two dominant left edges (label column and
value column), and treat a row with no label-column word as a continuation of
the previous value. Deterministic, no LLM needed.

### Trap 3a — the container table has a `GROSS WEIGHT (KG)` column header

The per-container rows each carry a weight; the figure we want is the
`TOTAL GROSS WEIGHT:` line underneath. The column header lives in the *value*
column of its row, so it is never seen as a label — and `CONTAINER NO.` is in
the explicit ignore list in `labels.py`. Keep both guards.

### Trap 3b — PDF rendering mangles labels

Real examples from the set: `TOTAL Gross Weightss(KGS)`,
`Export Carrier (vessel, voyageM) MSS 2507`. Labels lost characters because
the font could not render the Chinese glyphs, and adjacent strings ran
together. This is why label resolution has a fuzzy third pass.

---

## 4. Normalisation hazards — where fuzzy matching would betray us

Values are compared with **exact equality after normalisation**, never with a
similarity score. The entity pools contain deliberately near-identical names:

| A | B | Relationship |
|---|---|---|
| `APRIL FINE PAPER TRADING` | `APRIL FINE PAPER TRADING (MIDDLE EAST) FZE` | **different shippers** |
| `NANTONG, CHINA` | `RUGAO/NANTONG/SHANGHAI, CHINA` | **different load ports** |
| `TOPKOPY MIDDLE EAST FZE` | `EAST BRIGHT FZ-LLC` | different consignees |

A similarity threshold high enough to merge `KPP-ANTALIS (SINGAPORE) PTE. LTD.`
with `KPP-ANTALIS SINGAPORE` also merges the first two rows above, and a real
planted discrepancy disappears. So:

* **values** → exact match after canonicalisation (legal suffixes dropped,
  punctuation removed, UN/LOCODE stripped).
* **labels** → fuzzy is fine and necessary (see Trap 3b).

### Addresses are deliberately not compared

When the generator swaps a consignee name it leaves the old address block in
place. Comparing addresses would therefore *mask* the defect. We compare the
entity name only — the first line / the part before the `|`.

### Numbers

* `container_count`: `"6 x 40'HC"` → `6`. Take the **first** number — the `40`
  is the box size, not a quantity.
* `gross_weight_kg`: `"131,058 KG"`, `"215,950"`, and a bare integer `216950`
  (xlsx stores it as a number) all mean the same thing. `MT`/`tonnes` are
  converted to kg.

---

## 5. The four reasons a case must go to a human

All of these classify as `BL_COMPARISON` but must end in `NEEDS_REVIEW`.
A blank field or an unreadable scan is **not** a discrepancy.

| Reason | What it looks like | How we detect it |
|---|---|---|
| `missing_attachment` | comparison request with 0 or only 1 document | attachment count + intent (see Trap 5a) |
| `wrong_doc_type` | the "BL" is really a Commercial Invoice / Packing List / Certificate of Origin | document-type classifier on the text |
| `unreadable` | image-only scanned PDF, 0-byte file, truncated PDF that will not open | reader returns `empty_file` / `corrupt` / `no_text_layer` |
| `missing_value` | a required field is `???`, `_______`, `TBA`, `TBC`, `N/A` | `normalize.is_blank()` |

### Trap 5a — two different emails both have zero attachments

This is the subtlest case in the whole dataset:

```
A.  "Please assist to send the draft BL for MSDUL0942535439 for checking asap."
      -> BL_COMPARISON, status OK.  Nothing to compare yet; this is normal.

B.  "Please compare the SI and draft BL for MSDUL0942535439 and confirm
     (attachments appear to have been dropped)."
      -> BL_COMPARISON, status NEEDS_REVIEW / missing_attachment.
```

Same category, same subject style, zero attachments in both — and opposite
correct outcomes. The difference is **intent**: is the sender asking us to
*produce* a draft, or asking us to *check documents they believe they
attached*? Counting attachments is not enough; the pipeline runs an intent
check (`classify/intent.py`). An email with exactly **one** attachment is
always `missing_attachment` — you cannot compare a pair with half a pair.

---

## 6. Classification signals

Bodies contain forwarded threads, signature blocks with phone numbers, and
"external sender" warning banners. Classification must key off the real signal,
not the boilerplate.

Confusions that are easy to get wrong:

* `_Reminder_Paper - Submit SI & AED_18-01-2026` is **GENERAL**, not
  `SI_REQUEST`, even though it says "Submit SI".
* `APRIL PAPER - List of Outstanding BL (BDP SG)` and `Pending BL Release` are
  **GENERAL**, not `BL_COMPARISON`, even though they say "BL".
* `SI_REQUEST` bodies end with *"Please revert with draft BL once available"* —
  the phrase "draft BL" alone must not route an email to `BL_COMPARISON`.
* Coded subjects differ by prefix:
  `AIE - JEBEL_ALI - MSC(MEDUUD…) - …` → `BL_COMPARISON`
  `SI - MEDUUD… - DIRECT(MSC) - …`     → `SI_REQUEST`

Spam is the most separable category (prize/parcel-fee/mailbox-full/phishing
with throwaway sender domains), but it is also the **smallest**, and Stage 1 is
scored with macro-F1 — so one spam error costs as much as five
`BL_COMPARISON` errors. Treat the small classes as the priority.
