"use client";

import { useEffect, useRef } from "react";
import { usePathname, useSearchParams } from "next/navigation";

const SCROLL_KEY = (runId: string) => `sentinel:list-scroll:${runId}`;
const URL_KEY = (runId: string) => `sentinel:list-url:${runId}`;
const RETURN_KEY = "sentinel:return-to-run";
/** Long enough to outlast the router's own scroll-to-top on the way out (it
 *  lands within the same frame as the click), short enough that a
 *  ctrl/middle-click that opened the case in a new tab leaves this page
 *  recording again almost at once. */
const FREEZE_MS = 1500;

// sessionStorage can be absent or throw (private mode, blocked site data).
// All of this is a nicety layered on a page that works without it, so every
// access is wrapped rather than letting a storage error take the page down.
function safeGet(key: string): string | null {
  try {
    return sessionStorage.getItem(key);
  } catch {
    return null;
  }
}
function safeSet(key: string, value: string): void {
  try {
    sessionStorage.setItem(key, value);
  } catch {
    // ignore
  }
}
function safeRemove(key: string): void {
  try {
    sessionStorage.removeItem(key);
  } catch {
    // ignore
  }
}

/**
 * Remembers where a reviewer was in a run's case list -- scroll position and
 * the list's own URL, filters included -- so that opening a case and coming
 * back lands on the same list at the same place, whether they come back with
 * the browser's back button or the case page's own "Back to run" link.
 *
 * Replaces a first version that recorded scroll position continuously and
 * restored it on every mount. Reproducing "back goes to the top of the
 * previous page" step by step found two things wrong with that:
 *
 * 1. The router scrolls the page to the top *as the click leaves for the
 *    case*, and a continuous recorder wrote that 0 over the real position --
 *    the stored value was already 0 by the time the case page had mounted.
 *    Now the click on any link into one of this run's cases saves the
 *    position and freezes recording for FREEZE_MS, so the router's own scroll
 *    is never mistaken for the reviewer's. Recording also stays off between
 *    mount and the restore below, for the same reason on the way back in.
 *
 * 2. "Back to run" linked to the bare run URL, dropping ?status=... and
 *    friends. The list URL is now remembered whenever it changes, and
 *    `listUrlFor` hands it back to the case page.
 *
 * Position is restored only when the case page has marked this mount as a
 * return from one of the run's cases (`markReturningToRun`); arriving from
 * the Runs list or anywhere else starts at the top like any first visit.
 */
export function useListMemory({ runId, ready }: { runId: string; ready: boolean }): void {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const restored = useRef(false);
  const frozenUntil = useRef(0);

  const qs = searchParams.toString();
  const currentUrl = qs ? `${pathname}?${qs}` : pathname;
  useEffect(() => {
    safeSet(URL_KEY(runId), currentUrl);
  }, [runId, currentUrl]);

  // Capture phase on the document: one listener covers the table rows, the
  // mobile cards and the pattern chips without each wiring its own handler,
  // and it runs before the Link's own click handler starts the navigation.
  useEffect(() => {
    function onClick(e: MouseEvent) {
      const target = e.target instanceof Element ? e.target : null;
      const href = target?.closest("a")?.getAttribute("href") ?? "";
      if (!href.startsWith(`/runs/${runId}/cases/`)) return;
      safeSet(SCROLL_KEY(runId), String(window.scrollY));
      frozenUntil.current = Date.now() + FREEZE_MS;
    }
    document.addEventListener("click", onClick, true);
    return () => document.removeEventListener("click", onClick, true);
  }, [runId]);

  useEffect(() => {
    let ticking = false;
    function onScroll() {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(() => {
        ticking = false;
        if (!restored.current || Date.now() < frozenUntil.current) return;
        safeSet(SCROLL_KEY(runId), String(window.scrollY));
      });
    }
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, [runId]);

  // Gated on `ready` (the list has its real height) and run once per mount.
  // The return flag is consumed here, not read-and-removed at mount: in
  // development React mounts twice, and removing it on the first, discarded
  // mount would leave the real one with nothing to restore from.
  useEffect(() => {
    if (!ready || restored.current) return;
    if (safeGet(RETURN_KEY) === runId) {
      safeRemove(RETURN_KEY);
      const saved = safeGet(SCROLL_KEY(runId));
      if (saved !== null) window.scrollTo(0, Number(saved));
    }
    restored.current = true;
  }, [ready, runId]);
}

/** Called by a case page on mount: the next time this run's list mounts it
 *  is a return from one of the run's cases and should land where the
 *  reviewer left, not at the top. The list consumes the mark when it does. */
export function markReturningToRun(runId: string): void {
  safeSet(RETURN_KEY, runId);
}

/** The list URL the run page last had, filters included -- or the bare run
 *  URL when this session never visited it (a case opened by direct link). */
export function listUrlFor(runId: string): string {
  return safeGet(URL_KEY(runId)) ?? `/runs/${runId}`;
}
