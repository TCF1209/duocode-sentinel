"use client";

import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { useSearchParams } from "next/navigation";
import { RotateCw } from "lucide-react";
import { CaseReportView } from "@/components/case-report-view";
import { BackLink } from "@/components/back-link";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  getCase,
  listCases,
  recheckCase,
  retryCase,
  reviewCase,
  withdrawReview,
  type CaseReport,
  type CaseSummary,
  type ReviewBody,
} from "@/lib/api";
import { listUrlFor, markReturningToRun } from "@/lib/list-memory";
import { STATUS_LABELS } from "@/lib/labels";
import {
  describeOutcome,
  draftFromReview,
  EMPTY_DRAFT,
  isEmptyDraft,
  reviewBody,
  type CorrectionDraft,
  type ReviewController,
} from "@/components/review-panel";
import type { RecheckFiles } from "@/components/recheck-panel";
import { BeforeCaseView } from "@/components/before-case-view";
import { ViewModeSwitch } from "@/components/view-mode-switch";
import { useViewMode } from "@/lib/view-mode";
import { toast } from "sonner";

// The list URL never changes while this page is open, so there is nothing
// to subscribe to -- useSyncExternalStore is used here only for its
// hydration-safe read of sessionStorage (see backHref below).
const subscribeNever = () => () => {};

/** How long "Saved" stays beside the control that was just used. */
const SAVED_FLASH_MS = 1800;

/** See run-page-view.tsx's file comment: kept out of app/runs/[runId]/... on purpose. */
export function CaseDetailPageView({ runId, emailId }: { runId: string; emailId: string }) {
  const [report, setReport] = useState<CaseReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [retrying, setRetrying] = useState(false);
  const [rechecking, setRechecking] = useState(false);
  // ?spotlight=<panel>: the home page's "See it live" tiles link to a real
  // case *and* to the panel on it that shows the feature; the report scrolls
  // there and rings it once (case-report-view.tsx). Absent on every other
  // way into this page.
  const spotlight = useSearchParams().get("spotlight") ?? undefined;
  // "Before Sentinel" (lib/view-mode.ts): the same switch as the run page,
  // showing this email as it arrived and the blank seven-field table a
  // person would fill in, instead of the report.
  const [mode] = useViewMode();
  const before = mode === "before";
  // For "this shipper has already had N mismatches on this field in this
  // run" on a mismatched field's card -- a case detail page otherwise has
  // no reason to know about any case but its own. Fetched alongside the
  // case itself, so the badge is there when the card is, not popping in
  // late. Best-effort: a failure here should not block the case report
  // itself from rendering, so it is swallowed rather than surfaced as a
  // page error.
  const [allCases, setAllCases] = useState<CaseSummary[]>([]);

  const refresh = useCallback(() => {
    getCase(runId, emailId)
      .then(setReport)
      .catch((e) => setError(e.message));
    listCases(runId, {})
      .then((r) => setAllCases(r.cases))
      .catch(() => {});
  }, [runId, emailId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // Tells the run's list that its next mount is a return from one of its
  // cases (lib/list-memory.ts): the list restores the reviewer's place only
  // then, never on a fresh visit from Runs.
  useEffect(() => {
    markReturningToRun(runId);
  }, [runId]);

  // The run's list URL, filters included, for "Back to run". Read via
  // useSyncExternalStore rather than in render or in an effect: the value
  // lives in sessionStorage, which the server cannot see, so rendering it
  // straight into the href would make server and client disagree on the
  // first pass, and setting state from an effect body is what this
  // project's lint (react-hooks/set-state-in-effect) rejects. The server
  // snapshot is the bare run URL; the client swaps in the remembered one
  // after hydration, which is exactly what this hook exists to do.
  const backHref = useSyncExternalStore(subscribeNever, () => listUrlFor(runId), () => `/runs/${runId}`);

  const priorDefectCounts = useMemo(() => {
    const self = allCases.find((c) => c.email_id === emailId);
    if (!self?.shipper) return undefined;
    const counts: Record<string, number> = {};
    for (const c of allCases) {
      if (c.email_id === emailId || c.shipper !== self.shipper) continue;
      for (const f of c.defect_fields) counts[f] = (counts[f] ?? 0) + 1;
    }
    return counts;
  }, [allCases, emailId]);

  // -- the in-place review ------------------------------------------------
  //
  // Every choice on a field card (and "I can't tell", the note, "what it
  // should read") is saved the moment it is made: there is no draft waiting
  // for a Save button, so there is nothing to lose by leaving the page.
  // `pending` is the change on its way to the server, shown as if saved so
  // the card answers the click at once; the saved review takes over as soon
  // as the fresh report is back. Saves are queued one after another, so two
  // quick clicks cannot land out of order and the last word is always the
  // server's.
  const [pending, setPending] = useState<CorrectionDraft | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [flash, setFlash] = useState<string | null>(null);
  const queue = useRef<Promise<void>>(Promise.resolve());
  const inFlight = useRef(0);
  const saved = useMemo(() => (report ? draftFromReview(report) : EMPTY_DRAFT), [report]);
  const draft = pending ?? saved;

  const persist = useCallback(
    (work: () => Promise<unknown>, what: string, next: CorrectionDraft, done?: () => void) => {
      setPending(next);
      setBusy(what);
      inFlight.current += 1;
      queue.current = queue.current.then(async () => {
        try {
          await work();
          const fresh = await getCase(runId, emailId);
          setReport(fresh);
          setFlash(what);
          setTimeout(() => setFlash((cur) => (cur === what ? null : cur)), SAVED_FLASH_MS);
          done?.();
        } catch (e) {
          toast.error(`Could not save: ${e instanceof Error ? e.message : String(e)}`);
        } finally {
          inFlight.current -= 1;
          if (inFlight.current === 0) {
            setPending(null);
            setBusy(null);
          }
        }
        // The list's review tags moved with this case; the history badges
        // on the cards read the same list. Best-effort, as on first load.
        listCases(runId, {})
          .then((r) => setAllCases(r.cases))
          .catch(() => {});
      });
    },
    [runId, emailId],
  );

  const review: ReviewController | undefined = report
    ? {
        draft,
        busy,
        flash,
        commit: (next, what) => {
          if (isEmptyDraft(next)) {
            // Nothing recorded yet and nothing to record: a note alone is
            // not a review (review-panel.tsx's isEmptyDraft).
            if (!report.review) return;
            // The last choice taken back: what the reviewer means is
            // "nothing from me", not a review that happens to equal
            // Sentinel's answer -- the list would go on tagging it.
            if (!isEmptyDraft(draft)) {
              persist(() => withdrawReview(runId, emailId), what, EMPTY_DRAFT, () =>
                toast.success("Review withdrawn — Sentinel's answer stands"),
              );
              return;
            }
            // A confirmation whose note changed.
          }
          persist(() => reviewCase(runId, emailId, reviewBody(next)), what, next);
        },
        confirm: () => {
          const next = { ...EMPTY_DRAFT, note: draft.note };
          persist(() => reviewCase(runId, emailId, reviewBody(next)), "case", next);
        },
        withdraw: () => {
          if (!report.review) return;
          persist(() => withdrawReview(runId, emailId), "case", EMPTY_DRAFT, () =>
            toast.success("Review withdrawn — Sentinel's answer stands"),
          );
        },
        // The whole-case form on a case with no field cards: its own
        // Saving… state and error line (review-panel.tsx), so errors are
        // thrown to it rather than toasted here.
        submitLegacy: async (body: ReviewBody) => {
          await reviewCase(runId, emailId, body);
          toast.success("Review saved");
          refresh();
        },
      }
    : undefined;

  if (error) {
    return <p className="text-sm text-danger">{error}</p>;
  }
  if (!report) {
    // Shaped like the page it's standing in for (back link, header, review
    // panel, a few field rows) rather than a bare "Loading…" line, which
    // read as "the page is empty" more than "the page is working" -- this
    // was raised directly, not a guess at what needed fixing.
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-8 w-36 rounded-full" />
        <Card>
          <CardContent className="flex flex-col gap-4 p-6">
            <Skeleton className="h-6 w-48" />
            <Skeleton className="h-20 w-full" />
            <div className="flex flex-col gap-2">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-20 w-full" />
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Retry is offered where it is the plausible next action and hidden where it
  // is not. Re-reading an email whose documents both parsed and matched would
  // do nothing but spend a second and invite the reviewer to doubt a clean
  // result; re-reading one that arrived corrupt is exactly what they want
  // after the sender re-sends it, because the file is read from disk again.
  //
  // For a NEEDS_REVIEW case the button now lives inside the report's own
  // workspace, next to "what to do" (case-report-view.tsx), so the header
  // only keeps it for the other case where re-reading can change the
  // answer: a run-level error on a case that was not escalated. Never once
  // the case has been re-checked on re-sent documents: a retry would read
  // the disk originals back over them, and the backend refuses it (409).
  const couldChange =
    report.status !== "NEEDS_REVIEW" && report.errors.length > 0 && !report.recheck;

  async function onRetry() {
    setRetrying(true);
    try {
      const fresh = await retryCase(runId, emailId);
      setReport(fresh);
      toast.success(
        fresh.status === report?.status
          ? `Re-processed — still ${STATUS_LABELS[fresh.status]}`
          : `Re-processed — now ${STATUS_LABELS[fresh.status]}`,
      );
    } catch (e) {
      toast.error(e instanceof Error ? e.message : String(e));
    } finally {
      setRetrying(false);
    }
  }

  // Errors are not caught here on purpose: the recheck panel shows the
  // backend's own refusal text next to its button, where the reviewer is
  // looking, which a toast that fades would only duplicate.
  async function onRecheck(files: RecheckFiles) {
    setRechecking(true);
    try {
      const was = report?.effective ?? report;
      const fresh = await recheckCase(runId, emailId, files);
      setReport(fresh);
      toast.success(
        was
          ? `Re-checked — was ${describeOutcome(was.status, was.defect_fields)}, now ${describeOutcome(fresh.status, fresh.defect_fields)}`
          : `Re-checked — now ${describeOutcome(fresh.status, fresh.defect_fields)}`,
      );
      // The list's prior-defect counts for this shipper may have moved with
      // this case; best-effort, same as on first load.
      listCases(runId, {})
        .then((r) => setAllCases(r.cases))
        .catch(() => {});
    } finally {
      setRechecking(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <BackLink href={backHref} label={`Back to ${runId}`} />
        <ViewModeSwitch className="sm:ml-auto" />
        {!before && couldChange && (
          <Button
            variant="outline"
            size="sm"
            onClick={onRetry}
            disabled={retrying}
            title="Read the attachments again and re-decide this one case"
          >
            <RotateCw className={retrying ? "animate-spin" : undefined} />
            {retrying ? "Re-processing…" : "Retry this case"}
          </Button>
        )}
      </div>
      <Card>
        <CardContent className="p-6">
          {before ? (
            <BeforeCaseView report={report} caseId={`${runId}:${emailId}`} />
          ) : (
            <CaseReportView
              // Remounts after a re-check, so nothing shown about the old
              // answer (the "Sentinel's original" toggle, say) outlives it.
              key={report.recheck?.count ?? 0}
              report={report}
              caseId={`${runId}:${emailId}`}
              review={review}
              priorDefectCounts={priorDefectCounts}
              onRecheck={onRecheck}
              rechecking={rechecking}
              spotlight={spotlight}
            />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
