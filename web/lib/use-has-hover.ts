import { useSyncExternalStore } from "react";

const QUERY = "(hover: hover) and (pointer: fine)";

function subscribe(callback: () => void) {
  const mq = window.matchMedia(QUERY);
  mq.addEventListener("change", callback);
  return () => mq.removeEventListener("change", callback);
}

/**
 * True only for a device with a real mouse (hover that actually persists,
 * a fine-enough pointer to aim with) — not "wide enough to be a desktop
 * layout", which a touch laptop or a tablet in landscape both satisfy
 * without ever producing a real hover. Server snapshot is `false`, same
 * reasoning as useMounted: a touch-first assumption is the safer default
 * to render first and correct once the client knows better, rather than
 * assuming a mouse that isn't there.
 */
export function useHasHover() {
  return useSyncExternalStore(
    subscribe,
    () => window.matchMedia(QUERY).matches,
    () => false,
  );
}
