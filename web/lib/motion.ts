/**
 * Shared motion vocabulary — every animated screen imports from here rather
 * than inventing its own durations/easings, so the whole app moves on one
 * clock. If a transition feels off, fix it here and every screen inherits
 * the correction; don't special-case durations at the call site.
 */
import { useEffect, useState } from "react";
import { animate, type Transition, type Variants } from "motion/react";

// Confident deceleration, no spring overshoot — the "precise", not "bouncy",
// register (docs/DESIGN.md motion direction: Linear-esque, not playful).
export const EASE_OUT = [0.16, 1, 0.3, 1] as const;
export const EASE_IN_OUT = [0.65, 0, 0.35, 1] as const;

export const DURATION = {
  fast: 0.18,
  base: 0.32,
  slow: 0.5,
} as const;

// For anything that should feel physically pressed/dragged rather than
// merely faded (the nav's active-link underline, layout reflows).
export const SPRING: Transition = { type: "spring", stiffness: 300, damping: 32, mass: 0.7 };

/** One row/card/section settling into place. The default building block. */
export const fadeUp: Variants = {
  hidden: { opacity: 0, y: 6 },
  show: { opacity: 1, y: 0, transition: { duration: DURATION.base, ease: EASE_OUT } },
};

/** A quieter version for things already near the top of view (badges, stat values). */
export const fadeIn: Variants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { duration: DURATION.fast, ease: EASE_OUT } },
};

/**
 * Wrap a list's parent in this (variants={stagger()} initial="hidden"
 * animate="show") and give each child variants={fadeUp} — the parent times
 * the cascade, the child just says how it settles.
 */
export function stagger(delayChildren = 0, staggerChildren = 0.045): Variants {
  return {
    hidden: {},
    show: { transition: { staggerChildren, delayChildren } },
  };
}

/** Buttons/pressable rows: press it, feel it — pair with whileTap. */
export const TAP = { scale: 0.98 };
export const TAP_TRANSITION: Transition = { duration: DURATION.fast, ease: EASE_OUT };

/** Ticks from 0 to `target` once, on mount or whenever `target` changes. */
export function useCountUp(target: number, decimals = 0) {
  const [display, setDisplay] = useState(0);
  useEffect(() => {
    const controls = animate(0, target, {
      duration: DURATION.slow * 2,
      ease: EASE_OUT,
      onUpdate: (v) => setDisplay(Number(v.toFixed(decimals))),
    });
    return controls.stop;
  }, [target, decimals]);
  return display;
}
