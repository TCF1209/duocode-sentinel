/**
 * The "Tidy" view of an SI or BL text file in the Before-Sentinel case view
 * (before-case-view.tsx): the file's own lines, re-set into a label column
 * and a value column so the eye can run down them. Nothing is extracted,
 * matched or corrected here -- that is what Sentinel does, and the point of
 * this view is what a person has to work from *before* it. Every line of
 * the file appears exactly once, in order, as one of three things:
 *
 *   field    "Label: value" -- the label before the first colon, the rest
 *            the value; an indented line that follows (an address's second
 *            line) is more of the same value.
 *   heading  a line with no colon in capitals ("SHIPPING INSTRUCTION",
 *            "*** PACKING LIST ONLY ***").
 *   text     anything else, verbatim -- a packing-list table row, say.
 *
 * Blank lines and rules of === / --- are dropped: they are layout, and the
 * columns are the layout now. "Raw" is always one click away for the file
 * exactly as it arrived, so a tidy line can never be the only reading.
 */
export type TidyLine =
  | { kind: "field"; label: string; value: string }
  | { kind: "heading"; text: string }
  | { kind: "text"; text: string };

const RULE = /^[=\-_]{3,}\s*$/;
// The label is everything before the first colon -- short, and not a table
// row (two or more spaces in a row is column spacing, not a label).
const FIELD = /^([^:]{1,60}?):\s*(.*)$/;
const COLUMNS = /\s{2,}/;

export function tidyDocument(raw: string): TidyLine[] {
  const out: TidyLine[] = [];
  for (const line of raw.split(/\r?\n/)) {
    if (!line.trim() || RULE.test(line)) continue;
    const last = out[out.length - 1];
    if (/^\s/.test(line) && last?.kind === "field") {
      last.value += (last.value ? "\n" : "") + line.trim();
      continue;
    }
    const m = FIELD.exec(line);
    if (m && !COLUMNS.test(m[1].trim())) {
      out.push({ kind: "field", label: m[1].trim(), value: m[2].trim() });
      continue;
    }
    const text = line.trim();
    const heading = !/[a-z]/.test(text) && text.length <= 60 && !COLUMNS.test(text);
    out.push(heading ? { kind: "heading", text } : { kind: "text", text: line.trimEnd() });
  }
  return out;
}
