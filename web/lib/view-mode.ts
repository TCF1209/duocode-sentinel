"use client";

import { useCallback, useSyncExternalStore } from "react";

/**
 * "Before Sentinel" / "With Sentinel" -- the run page and the case page can
 * show the inbox as it arrived (subject lines, attachments, the seven fields
 * a person would read out by hand) or what Sentinel made of it. From the
 * mentor session of 24 Sep: the intro must say why the system was built and
 * what a manual check costs, and the clearest way to say it is to show the
 * same inbox both ways and flip between them.
 *
 * It is a way of looking, not a setting: kept in sessionStorage so the run
 * page and its case pages agree within one visit, not in the URL (a shared
 * link should always open on what Sentinel found) and not in localStorage
 * (the next visit starts on the product, not the comparison).
 */
export type ViewMode = "before" | "with";

const KEY = "sentinel:view-mode";
const EVENT = "sentinel:view-mode-change";

function read(): ViewMode {
  try {
    return window.sessionStorage.getItem(KEY) === "before" ? "before" : "with";
  } catch {
    return "with";
  }
}

function subscribe(onChange: () => void): () => void {
  window.addEventListener(EVENT, onChange);
  window.addEventListener("storage", onChange);
  return () => {
    window.removeEventListener(EVENT, onChange);
    window.removeEventListener("storage", onChange);
  };
}

export function useViewMode(): [ViewMode, (next: ViewMode) => void] {
  // The server never knows the mode, so it renders "with" and the client
  // corrects itself after hydration -- the same hydration-safe pattern as
  // the list URL memory (case-detail-page-view.tsx).
  const mode = useSyncExternalStore(subscribe, read, () => "with" as ViewMode);
  const setMode = useCallback((next: ViewMode) => {
    try {
      window.sessionStorage.setItem(KEY, next);
    } catch {
      // Storage blocked: the switch still works for this render tree.
    }
    window.dispatchEvent(new Event(EVENT));
  }, []);
  return [mode, setMode];
}
