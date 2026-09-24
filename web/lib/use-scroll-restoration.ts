"use client";

import { useEffect, useRef } from "react";
import { usePathname } from "next/navigation";

const KEY_PREFIX = "sentinel:scroll:";

/**
 * Next.js App Router's own scroll restoration races this page's own data
 * fetch: the case list loads client-side after mount, so on a browser back
 * navigation the page is still its empty/short pre-fetch height at the
 * moment restoration would normally run, and it lands at 0 regardless.
 * Confirmed live, not assumed: clicking into a case from partway down the
 * 520-row table, then using the browser's own back button, reproducibly
 * reset to the very top rather than back to that row.
 *
 * Saves scroll position continuously (so whatever the last position was is
 * always available, however the page is left -- a link click, the back
 * button, closing the tab) and restores it exactly once, after `ready`
 * flips true and the page has its real height to scroll within. Keyed by
 * path, so each run's table remembers its own position independently and a
 * different run starts at the top like any first visit.
 */
export function useScrollRestoration(ready: boolean) {
  const pathname = usePathname();
  const restored = useRef(false);

  useEffect(() => {
    let ticking = false;
    function onScroll() {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(() => {
        try {
          sessionStorage.setItem(KEY_PREFIX + pathname, String(window.scrollY));
        } catch {
          // sessionStorage unavailable (private mode etc.) -- a nicety, not required
        }
        ticking = false;
      });
    }
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, [pathname]);

  useEffect(() => {
    if (!ready || restored.current) return;
    restored.current = true;
    try {
      const saved = sessionStorage.getItem(KEY_PREFIX + pathname);
      if (saved !== null) window.scrollTo(0, Number(saved));
    } catch {
      // ignore -- same as above, restoration is a nicety
    }
  }, [ready, pathname]);
}
