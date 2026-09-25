import { useId, useState } from "react";
import { ChevronDown, FileCheck2, History, Play, RotateCw, Upload, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/status-badges";
import { AttachmentAction } from "@/components/attachment-action";
import { describeOutcome } from "@/components/review-panel";
import { timeAgo } from "@/lib/format-time";
import { cn } from "@/lib/utils";
import type { CaseReport, CaseVersion, DocSide } from "@/lib/api";

/**
 * Re-sent documents: the follow-up a MISMATCH or an unreadable attachment
 * actually gets. Raised as "can I drop the latest SI and BL back in and have
 * the system detect it again?" -- yes: the panel below takes one side or
 * both, POST /cases/{id}/recheck runs the same comparison /compare runs, and
 * the case's answer is replaced. The answer it replaces is not lost: the
 * backend keeps every superseded version with the review that stood against
 * it, and RecheckHistory further down shows them. The review itself is reset
 * by a re-check (it was a judgement about the old documents), which is why
 * the review panel comes back unreviewed afterwards.
 */

export type RecheckFiles = Partial<Record<DocSide, File>>;

const SIDES: DocSide[] = ["si", "bl"];
const SIDE_LABEL = { si: "Shipping Instruction (SI)", bl: "Draft Bill of Lading (BL)" } as const;
const SIDE_SHORT = { si: "SI", bl: "BL" } as const;

/** "BL" / "SI and BL" */
function sidesPhrase(sides: DocSide[]): string {
  return sides.map((s) => SIDE_SHORT[s]).join(" and ");
}

function basename(path: string): string {
  return path.split("/").pop() || path;
}

/** Offered where a case has nothing on file to re-check: the Compare page's
 *  ordinary SI, and a BL that agrees with it on all seven fields
 *  (public/samples/ordinary-corrected_BL.txt) -- so a visitor with no files
 *  of their own watches the case come back OK, the old answer kept. */
const SAMPLE_PAIR = { si: "ordinary_SI.txt", bl: "ordinary-corrected_BL.txt" } as const;

async function fetchSample(name: string): Promise<File> {
  const res = await fetch(`/samples/${name}`);
  if (!res.ok) throw new Error(`could not load sample ${name}`);
  return new File([await res.blob()], name);
}

/** What the case is read from on this side right now, for the picker's
 *  "currently: …" line -- a re-sent copy says so, because the file name
 *  alone ("email_013_BL_rev2.txt") does not tell a reader it never came
 *  through the inbox. */
function currentFile(report: CaseReport, side: DocSide): string {
  const doc = report.documents[side];
  if (!doc) return "nothing on file";
  const resent = report.recheck?.sources[side] === "resent";
  return `${basename(doc.path)}${resent ? " (re-sent)" : ""}`;
}

function FilePick({
  side,
  file,
  current,
  disabled,
  onChange,
}: {
  side: DocSide;
  file: File | undefined;
  current: string;
  disabled?: boolean;
  onChange: (file: File | undefined) => void;
}) {
  const inputId = useId();
  return (
    <div className="flex flex-col gap-1">
      <label
        htmlFor={inputId}
        className={cn(
          "flex cursor-pointer items-center gap-2 rounded-md border border-dashed p-2.5 text-sm transition-colors",
          file ? "border-ok/40 bg-ok-bg/40" : "hover:border-primary/40 hover:bg-muted/40",
          disabled && "pointer-events-none opacity-60",
        )}
      >
        <input
          id={inputId}
          type="file"
          accept=".txt,.pdf,.docx,.xlsx,.csv"
          disabled={disabled}
          onChange={(e) => onChange(e.target.files?.[0] ?? undefined)}
          className="sr-only"
        />
        {file ? <FileCheck2 className="size-4 shrink-0 text-ok" /> : <Upload className="size-4 shrink-0 text-muted-foreground" />}
        <div className="min-w-0 flex-1">
          <div className="truncate font-medium">{file ? file.name : `Attach the re-sent ${SIDE_SHORT[side]}`}</div>
          {/* The file name is the useful part and the box is narrow, so the
              side's long name goes in the title, not in front of it: seen
              live, "Shipping Instruction (SI) · currently ema…" truncated
              exactly the thing a reviewer needed to read. */}
          <div className="truncate text-xs text-muted-foreground" title={SIDE_LABEL[side]}>
            {file ? `replaces ${current}` : `currently ${current}`}
          </div>
        </div>
        {file && (
          <button
            type="button"
            aria-label={`Remove the chosen ${SIDE_SHORT[side]}`}
            onClick={(e) => {
              e.preventDefault();
              onChange(undefined);
            }}
            className="rounded p-0.5 text-muted-foreground hover:text-foreground"
          >
            <X className="size-3.5" />
          </button>
        )}
      </label>
    </div>
  );
}

/**
 * The re-sent documents area itself. Whether it is on screen is the
 * caller's (case-report-view.tsx): it opens from the "Attach re-sent SI/BL"
 * button on the review box's row of actions, and starts open when the page
 * was opened at it (?spotlight=recheck, the home tile) or when the case has
 * nothing on file -- there the sample pair below is the only way to watch a
 * re-check, and a folded area would hide it. The grey one-line bar this
 * used to fold into is gone: the user did not read it as something to click.
 */
export function RecheckPanel({
  report,
  onRecheck,
  rechecking,
  className,
  onClose,
}: {
  report: CaseReport;
  onRecheck: (files: RecheckFiles) => Promise<void>;
  rechecking?: boolean;
  className?: string;
  /** Fold the area away again (the Hide control). */
  onClose?: () => void;
}) {
  const [files, setFiles] = useState<RecheckFiles>({});
  const [error, setError] = useState<string | null>(null);
  const [loadingSample, setLoadingSample] = useState(false);
  const chosen = SIDES.filter((s) => files[s]);
  // A sample only where it replaces nothing: an email that came with no SI
  // and no BL. On a case with real documents it would swap a real answer
  // for one about unrelated paperwork, on a server every visitor shares.
  const offerSample = !report.documents.si && !report.documents.bl && chosen.length === 0;

  async function loadSample() {
    setError(null);
    setLoadingSample(true);
    try {
      const [si, bl] = await Promise.all([fetchSample(SAMPLE_PAIR.si), fetchSample(SAMPLE_PAIR.bl)]);
      setFiles({ si, bl });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoadingSample(false);
    }
  }

  async function submit() {
    setError(null);
    try {
      await onRecheck(files);
      setFiles({});
    } catch (e) {
      // The backend's refusals are written for this spot ("this case has no
      // BL on file to compare against; attach it as well"), so they are
      // shown here beside the button rather than as a passing toast.
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <div className={cn("rounded-md border bg-background p-3", className)}>
      <div className="flex items-center justify-between gap-2">
        <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Re-sent documents</div>
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            disabled={rechecking}
            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
          >
            Hide
            <ChevronDown className="size-4" />
          </button>
        )}
      </div>
      <p className="mt-1 text-sm text-muted-foreground">
        Attach the re-sent SI or BL; the same check runs again. The previous answer stays on the case.
      </p>
      <div className="mt-2 grid gap-2 sm:grid-cols-2">
        {SIDES.map((side) => (
          <FilePick
            key={side}
            side={side}
            file={files[side]}
            current={currentFile(report, side)}
            disabled={rechecking}
            onChange={(file) => setFiles((prev) => ({ ...prev, [side]: file }))}
          />
        ))}
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <Button
          size="sm"
          disabled={chosen.length === 0 || rechecking}
          onClick={submit}
          title={chosen.length === 0 ? "Attach the re-sent SI, the re-sent BL, or both" : undefined}
        >
          <RotateCw className={rechecking ? "animate-spin" : undefined} />
          {rechecking ? "Re-checking…" : chosen.length > 0 ? `Re-check with the re-sent ${sidesPhrase(chosen)}` : "Re-check"}
        </Button>
        {offerSample && (
          <Button
            size="sm"
            variant="outline"
            onClick={loadSample}
            disabled={loadingSample || rechecking}
            title="Sample paperwork, not this shipment's -- it shows the re-check working"
          >
            <Play />
            {loadingSample ? "Loading…" : "No files? Load a sample pair"}
          </Button>
        )}
        {error && <span className="text-xs text-danger">{error}</span>}
      </div>
    </div>
  );
}

/** "Mismatch on Port of Discharge — confirmed by a reviewer": what stood for a
 *  superseded version, review included, the same way the live case is
 *  reported (store.py's effective outcome), so "was" and "now" compare like
 *  with like. */
function whatStood(v: CaseVersion): string {
  const outcome = describeOutcome(v.effective.status, v.effective.defect_fields);
  if (!v.review) return outcome;
  if (v.review.decision === "confirm") return `${outcome} — confirmed by a reviewer`;
  return `${outcome} — corrected by a reviewer from Sentinel's ${describeOutcome(v.report.status, v.report.defect_fields)}`;
}

function VersionRow({ v, caseId }: { v: CaseVersion; caseId?: string }) {
  return (
    <li className="flex flex-col gap-1 rounded-md border bg-background p-2">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <span className="text-muted-foreground">v{v.version}</span>
        <StatusBadge status={v.effective.status} />
        <span>{whatStood(v)}</span>
      </div>
      {v.review?.note && <div className="text-muted-foreground">&ldquo;{v.review.note}&rdquo;</div>}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-muted-foreground">
        <span>
          Replaced {timeAgo(v.replaced_at * 1000)} by a re-check with the re-sent {sidesPhrase(v.resubmitted)}
          {v.resubmitted.length > 0 && ` (${v.resubmitted.map((s) => v.uploaded[s] ?? "?").join(", ")})`}
        </span>
        {caseId &&
          SIDES.map((side) => {
            const doc = v.report.documents[side];
            if (!doc) return null;
            return (
              <AttachmentAction
                key={side}
                caseId={caseId}
                side={side}
                ext={doc.ext}
                path={doc.path}
                version={v.version}
                label={`${SIDE_SHORT[side]} at v${v.version}`}
              />
            );
          })}
      </div>
    </li>
  );
}

/** Leads the report once a case has been re-checked: what it was, what it
 *  is now, and each superseded version behind a disclosure -- with the
 *  file that version was actually read from, so "Sentinel said MISMATCH on
 *  the first BL" can be checked against that first BL, not the current one. */
export function RecheckHistory({ report, caseId }: { report: CaseReport; caseId?: string }) {
  const info = report.recheck;
  const history = report.history ?? [];
  if (!info || history.length === 0) return null;
  const last = history[history.length - 1];
  const now = report.effective ?? report;
  return (
    <div className="rounded-md border bg-muted/40 p-3 text-sm">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <History className="size-4 shrink-0 text-muted-foreground" strokeWidth={2} />
        <span className="font-medium">
          Re-checked {timeAgo(info.last_at * 1000)} with the re-sent {sidesPhrase(info.last_resubmitted)}
        </span>
        {info.count > 1 && <span className="text-xs text-muted-foreground">{info.count} re-checks in all</span>}
      </div>
      <div className="mt-1.5 grid gap-x-3 gap-y-0.5 text-xs sm:grid-cols-[auto_1fr]">
        <span className="text-muted-foreground">Was</span>
        <span>{whatStood(last)}</span>
        <span className="text-muted-foreground">Now</span>
        <span className="font-medium">{describeOutcome(now.status, now.defect_fields)}</span>
      </div>
      <details className="mt-2 text-xs">
        <summary className="cursor-pointer select-none text-muted-foreground">
          Previous version{history.length === 1 ? "" : "s"} ({history.length})
        </summary>
        <ol className="mt-1.5 flex flex-col gap-1.5">
          {history.map((v) => (
            <VersionRow key={v.version} v={v} caseId={caseId} />
          ))}
        </ol>
      </details>
    </div>
  );
}
