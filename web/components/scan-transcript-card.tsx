import { Sparkles } from "lucide-react";
import type { DocumentReport } from "@/lib/api";
import { FIELD_LABELS } from "@/lib/labels";

// The shape of readers/scan.py's ScanTranscript.as_dict(), carried on a
// document by schema._doc(). It is declared here rather than added to
// lib/api.ts's DocumentReport on purpose: DocumentReport is the pipeline's
// contract for every document, and this is optional reviewer evidence that
// exists only when a vision model was allowed to read an image-only scan.
// Nothing about it is a verified extraction -- the case that carries it is
// still NEEDS_REVIEW / unreadable, and this card says so in its own words.
export interface ScanTranscript {
  kind: "scan_transcript";
  advisory: string;
  fields: { field: string; value: string; legible: boolean }[];
  overall_legible: boolean;
  legible_count: number;
  confidence: number;
  model: string;
  pages_read: number;
  note: string;
}

/** The transcript on a report document, or null when there is none. */
export function transcriptOf(doc: DocumentReport | null | undefined): ScanTranscript | null {
  const raw = (doc as (DocumentReport & { scan_transcript?: unknown }) | null | undefined)?.scan_transcript;
  if (!raw || typeof raw !== "object") return null;
  const t = raw as Partial<ScanTranscript>;
  return t.kind === "scan_transcript" && Array.isArray(t.fields) ? (t as ScanTranscript) : null;
}

export function ScanTranscriptCard({ role, transcript }: { role: "SI" | "BL"; transcript: ScanTranscript }) {
  const pages = transcript.pages_read === 1 ? "1 page" : `${transcript.pages_read} pages`;
  return (
    <div className="flex flex-col gap-2 rounded-xl border border-ai/40 bg-ai-bg/40 p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-ai">
          <Sparkles className="size-3.5" strokeWidth={2} />
          {role} scan — transcribed by {transcript.model}
        </div>
        <div className="text-xs text-muted-foreground tabular-nums">
          {transcript.legible_count}/{transcript.fields.length} fields legible · confidence{" "}
          {Math.round(transcript.confidence * 100)}% · {pages}
        </div>
      </div>

      <dl className="grid gap-x-4 gap-y-1 text-sm sm:grid-cols-[max-content_1fr]">
        {transcript.fields.map((f) => (
          <div key={f.field} className="contents">
            <dt className="text-muted-foreground">{FIELD_LABELS[f.field] ?? f.field}</dt>
            <dd className={f.legible ? "font-medium" : "text-muted-foreground italic"}>
              {f.legible ? f.value : "illegible — left blank, not guessed"}
            </dd>
          </div>
        ))}
      </dl>

      {/* The one sentence a reviewer must carry away: the model transcribed
          the page so they do not start from zero, but the page still has no
          text layer, so nothing here was compared to anything and the case
          stays escalated until a reviewer verifies it against the image. */}
      <p className="border-t border-ai/30 pt-2 text-xs text-muted-foreground">
        Transcribed from the image, not compared. Verify each value against the scan.
      </p>
    </div>
  );
}
