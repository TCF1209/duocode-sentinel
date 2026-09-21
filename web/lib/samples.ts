/**
 * Three pairs a judge (or a presenter) can load without preparing anything.
 * Shared by /compare and /demo so both ever describe the same three pairs
 * the same way — extracted out of compare/page.tsx rather than duplicated
 * when the demo walkthrough needed the exact "unfamiliar-labels" pair too.
 */
export const SAMPLES = [
  {
    id: "unfamiliar-labels",
    title: "Labels we have never seen",
    blurb:
      "A human reads it at a glance — Sender of Goods, Deliver To, Loading Terminal. Our synonym table has none of them. Rules alone find nothing and escalate; the model reads it and the real defect surfaces.",
    si: "unfamiliar-labels_SI.txt",
    bl: "unfamiliar-labels_BL.txt",
    needsModel: true,
  },
  {
    id: "scanned",
    title: "A scan with no text layer",
    blurb:
      "Image-only PDFs. No parser can read them. With the model on, the vision path transcribes both for the reviewer — and the case still escalates, because a transcript is evidence for a person, not grounds for a verdict.",
    si: "scanned_SI.pdf",
    bl: "scanned_BL.pdf",
    needsModel: true,
  },
  {
    id: "ordinary",
    title: "Ordinary wording (the control)",
    blurb:
      "The same shipment, labelled the way our table expects. The rules answer it in milliseconds for nothing. This is the 100% of the graded inbox, and the reason the model is a fallback rather than the engine.",
    si: "ordinary_SI.txt",
    bl: "ordinary_BL.txt",
    needsModel: false,
  },
] as const;

export type Sample = (typeof SAMPLES)[number];

export async function fetchSample(name: string): Promise<File> {
  const res = await fetch(`/samples/${name}`);
  if (!res.ok) throw new Error(`could not load sample ${name}`);
  return new File([await res.blob()], name);
}

export async function loadSamplePair(s: Sample): Promise<{ si: File; bl: File }> {
  const [si, bl] = await Promise.all([fetchSample(s.si), fetchSample(s.bl)]);
  return { si, bl };
}
