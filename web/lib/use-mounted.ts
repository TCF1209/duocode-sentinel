import { useSyncExternalStore } from "react";

const emptySubscribe = () => () => {};

/**
 * True only once the client has actually painted. Not a `useState` +
 * `useEffect` mount flag — that setState-after-mount pattern causes a flash
 * (React commits the "before" render first) and trips this repo's
 * react-hooks/set-state-in-effect rule. useSyncExternalStore's
 * getServerSnapshot forces server AND first client render to agree (both
 * `false`), so there is no hydration mismatch to fix.
 */
export function useMounted() {
  return useSyncExternalStore(
    emptySubscribe,
    () => true,
    () => false,
  );
}
