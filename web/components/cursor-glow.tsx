"use client";

import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { useMounted } from "@/lib/use-mounted";

/**
 * A soft brass glow that follows the cursor anywhere in the viewport.
 *
 * Portalled straight to document.body and positioned with `fixed` +
 * `clientX`/`clientY` from a `window` listener — not scoped to any
 * container. An earlier version tracked position relative to a wrapping
 * div and only showed the glow between that div's onMouseEnter/onMouseLeave,
 * which meant it vanished the moment the cursor crossed into the page's own
 * margins (still on screen, just outside that div's box). Tracking the
 * window instead of a container removes the boundary entirely: there is
 * nothing left for the cursor to "exit" short of leaving the browser
 * viewport itself.
 *
 * Position updates go straight to a CSS custom property via a ref, never
 * React state, so a fast mouse produces DOM style writes the browser
 * composites directly rather than a re-render per pixel of movement.
 */
export function CursorGlow() {
  const mounted = useMounted();
  const ref = useRef<HTMLDivElement>(null);

  // Depends on `mounted`, not `[]`: this component renders nothing until
  // mounted flips true (see below), so the ref isn't attached to a DOM node
  // yet on the mount commit where an empty-deps effect would have run — it
  // would find ref.current still null and give up permanently, since deps
  // never change again to trigger a retry.
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    let started = false;
    function handleMove(e: MouseEvent) {
      el!.style.setProperty("--mx", `${e.clientX}px`);
      el!.style.setProperty("--my", `${e.clientY}px`);
      if (!started) {
        started = true;
        el!.style.opacity = "1";
      }
    }
    window.addEventListener("mousemove", handleMove);
    return () => window.removeEventListener("mousemove", handleMove);
  }, [mounted]);

  if (!mounted) return null;

  return createPortal(
    <div
      ref={ref}
      aria-hidden
      className="pointer-events-none fixed inset-0 z-0 transition-opacity duration-500"
      style={{
        opacity: 0,
        background:
          "radial-gradient(420px circle at var(--mx, 50%) var(--my, 50%), color-mix(in srgb, var(--primary) var(--cursor-glow), transparent) 0%, transparent 70%)",
      }}
    />,
    document.body,
  );
}
