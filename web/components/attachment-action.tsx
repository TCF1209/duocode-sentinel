import { useState } from "react";
import { Download, Eye } from "lucide-react";
import { attachmentUrl, type DocSide } from "@/lib/api";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";

// Moved out of case-report-view.tsx unchanged, when the re-check panel
// (recheck-panel.tsx) needed the same "view this file" affordance for a
// case's superseded versions: that panel is rendered by case-report-view,
// so importing back from it would have been a circular import.

/** The real file a run read off disk, not just its evidence snippet -- shown
 *  in a dialog right on this page rather than navigated to. That was the
 *  first design (a `target="_blank"` link): it did not reliably open a
 *  second tab in this app's own preview surface, so the click navigated
 *  this page away to a different origin, and the browser's back button
 *  returned to it scrolled to the top, not to where the reviewer had been
 *  -- confirmed live, reproducible, and (separately) true of any case
 *  clicked into from partway down the run table regardless of this
 *  feature, see lib/list-memory.ts. Never leaving the page at all removes
 *  the whole class of problem rather than patching around it.
 *  A .txt/.pdf (220 of the dataset's 250 attachments, docs/DATA_NOTES.md)
 *  opens inline in the dialog; a .docx/.xlsx has no in-browser renderer
 *  either way, so those fall back to a plain download link instead of an
 *  empty preview.
 *
 *  `version` points the same link at the file a superseded answer was read
 *  from (api.ts's attachmentUrl); `label` replaces the default "View
 *  original" wording, which is wrong for a re-sent file. */
export function AttachmentAction({
  caseId,
  side,
  ext,
  path,
  version,
  label,
}: {
  caseId: string;
  side: DocSide;
  ext: string;
  path: string;
  version?: number;
  label?: string;
}) {
  const url = attachmentUrl(caseId, side, version);
  const filename = path.split("/").pop() || path;

  if (ext !== ".txt" && ext !== ".pdf") {
    return (
      <a href={url} download={filename} className="inline-flex items-center gap-1 text-primary hover:underline">
        <Download className="size-3" />
        {label ?? "Download original"}
      </a>
    );
  }
  return <AttachmentDialog url={url} filename={filename} kind={ext === ".pdf" ? "pdf" : "text"} label={label ?? "View original"} />;
}

/** Retries before surfacing an error. Empirically, not defensively: live
 *  testing against the real dev backend repeatedly showed a fetch to this
 *  route, specifically when triggered from this button's click handler,
 *  fail with a CORS-shaped `net::ERR_FAILED` -- while curl against the
 *  identical URL with the same Origin header never once failed, and a
 *  `fetch()` to the identical URL typed directly into the console
 *  (bypassing the click handler) never once failed either. That rules out
 *  the route and its CORS setup, which is why the fix here is a retry
 *  rather than a change to backend/api/main.py: something specific to this
 *  dev environment (React Strict Mode's deliberate double-invocation is
 *  the leading suspect -- this Next.js app has it on by default and a
 *  second, unrelated fetch on this same page was independently observed
 *  firing twice per mount) makes the first attempt occasionally lose a
 *  race, and a short-backoff retry is the correct mitigation regardless of
 *  which exact mechanism turns out to be responsible. */
async function fetchTextWithRetry(url: string, attempts = 3): Promise<string> {
  let lastError: unknown;
  for (let i = 0; i < attempts; i++) {
    if (i > 0) await new Promise((resolve) => setTimeout(resolve, 200));
    try {
      const r = await fetch(url);
      if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
      return await r.text();
    } catch (e) {
      lastError = e;
    }
  }
  throw lastError instanceof Error ? lastError : new Error(String(lastError));
}

function AttachmentDialog({ url, filename, kind, label }: { url: string; filename: string; kind: "text" | "pdf"; label: string }) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pdfLoaded, setPdfLoaded] = useState(false);

  function onOpenChange(next: boolean) {
    setOpen(next);
    // Closing clears a previous failure, so a second click actually retries.
    // Without this the guard below -- which is right, it stops a re-fetch of
    // a file already in hand -- also latched the error for the life of the
    // component: one failed load on a cold container and that button was
    // dead until a page reload. The retries are 200ms apart and Render's
    // free tier wakes in 30-60s, so the first click on a sleeping API
    // exhausts all three in under a second and is exactly the case that used
    // to stick.
    if (!next) {
      setError(null);
      return;
    }
    // Fetched once per mount, on first open, not on every re-open of the
    // same dialog instance -- text/error already set is the guard.
    if (next && kind === "text" && text === null && error === null) {
      fetchTextWithRetry(url)
        .then(setText)
        .catch((e) => setError(e instanceof Error ? e.message : String(e)));
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={() => onOpenChange(true)}
        className="inline-flex items-center gap-1 text-primary hover:underline"
      >
        <Eye className="size-3" />
        {label}
      </button>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="max-w-2xl sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle className="font-mono text-sm font-normal">{filename}</DialogTitle>
          </DialogHeader>
          {kind === "pdf" ? (
            // The iframe paints nothing until the PDF is ready, and an empty
            // white 70vh panel reads as broken rather than as loading -- on a
            // cold free-tier container that is a 30-60s wait. The overlay says
            // which it is, in the same words the text branch uses.
            <div className="relative h-[70vh] w-full">
              <iframe
                src={url}
                title={filename}
                onLoad={() => setPdfLoaded(true)}
                className="h-full w-full rounded-md border bg-white"
              />
              {!pdfLoaded && (
                <div className="pointer-events-none absolute inset-0 flex items-center justify-center rounded-md border bg-muted/30">
                  <p className="text-sm text-muted-foreground">Loading…</p>
                </div>
              )}
            </div>
          ) : (
            <div className="max-h-[70vh] overflow-y-auto rounded-md border bg-muted/30 p-3">
              {error && <p className="text-sm text-danger">Could not load the file: {error}</p>}
              {text === null && !error && <p className="text-sm text-muted-foreground">Loading…</p>}
              {text !== null && <pre className="whitespace-pre-wrap font-mono text-xs">{text}</pre>}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
