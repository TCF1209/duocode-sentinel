"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "motion/react";
import { ArrowRight, ShipCargo } from "lucide-react";
import { cn } from "@/lib/utils";
import { EASE_OUT, SPRING, TAP } from "@/lib/motion";
import { ThemeToggle } from "@/components/theme-toggle";

const LINKS = [
  { href: "/", label: "Home" },
  { href: "/runs", label: "Runs" },
  { href: "/compare", label: "Compare" },
  { href: "/demo", label: "Demo" },
];

export function Nav() {
  const pathname = usePathname();
  return (
    <header className="sticky top-0 z-30 px-3 pt-3 pb-2 sm:px-4">
      <div className="mx-auto flex max-w-5xl items-center justify-between gap-1 rounded-full border bg-card/95 py-2 pr-2 pl-2.5 shadow-sm backdrop-blur-sm sm:gap-4 sm:pr-2 sm:pl-4">
        <Link href="/" className="flex shrink-0 items-center gap-2 sm:gap-2.5">
          <span className="flex size-8 shrink-0 items-center justify-center rounded-full border border-primary/30 bg-primary/10 sm:size-9">
            <ShipCargo className="size-4 text-primary" strokeWidth={1.75} />
          </span>
          <span className="hidden font-heading text-lg font-semibold tracking-tight text-foreground sm:inline">
            Sentinel
          </span>
        </Link>

        <nav className="flex items-center gap-0 rounded-full sm:gap-1">
          {LINKS.map((l) => {
            const active = pathname === l.href;
            return (
              <Link
                key={l.href}
                href={l.href}
                className={cn(
                  "relative rounded-full px-2 py-1.5 text-sm text-muted-foreground transition-colors sm:px-4 sm:text-base",
                  active ? "text-primary" : "hover:text-foreground",
                )}
              >
                {active && (
                  <motion.span
                    layoutId="nav-pill"
                    className="absolute inset-0 rounded-full bg-primary/12"
                    transition={SPRING}
                  />
                )}
                <span className="relative font-medium">{l.label}</span>
              </Link>
            );
          })}
        </nav>

        <div className="flex shrink-0 items-center gap-1.5 sm:gap-2">
          <ThemeToggle />
          {/* The nav's own "Runs" link already covers this on narrow screens
              — a text+icon CTA has nowhere to go at 375px next to a logo,
              three links and the toggle, so it only earns its place once
              there's room instead of forcing everything else to shrink. */}
          <div className="hidden sm:block">
            <ShinyButton href="/runs">
              Go to Runs
              <ArrowRight className="size-4" strokeWidth={2} />
            </ShinyButton>
          </div>
        </div>
      </div>
    </header>
  );
}

/**
 * The "make it shine" ask, played as a one-shot hover sweep rather than a
 * looping shimmer — a permanently looping glint on a nav button visible on
 * every page is exactly the always-on animation that made scrolling janky
 * before, so this stays inert until a pointer actually arrives.
 *
 * The sweep's transform is driven by Framer Motion's `variants`/`style`,
 * not Tailwind's `-translate-x-[...]`/`skew-x-[...]` utilities: that
 * combination compiled to a transform matrix with the skew applied but the
 * translate silently dropped (checked with getComputedStyle — the class
 * was present in the DOM, the resulting CSS was not), the same class of
 * "this exact utility combination didn't survive the build" issue as the
 * lg: breakpoint earlier. Motion computes the transform itself instead of
 * relying on Tailwind to compose several transform utilities into one
 * declaration, so there is nothing here for that bug to happen to again.
 */
function ShinyButton({ href, children }: { href: string; children: ReactNode }) {
  return (
    <motion.div initial="rest" whileHover="hover" whileTap={TAP} className="inline-block">
      <Link
        href={href}
        className="relative flex items-center gap-1.5 overflow-hidden rounded-full bg-primary px-3.5 py-2 text-sm font-medium text-primary-foreground sm:px-4 sm:text-base"
      >
        <span className="relative z-10 flex items-center gap-1.5">{children}</span>
        <motion.span
          aria-hidden
          className="absolute inset-y-0 left-0 w-1/3 bg-white/40"
          style={{ skewX: -20 }}
          variants={{ rest: { x: "-250%" }, hover: { x: "350%" } }}
          transition={{ duration: 0.7, ease: EASE_OUT }}
        />
      </Link>
    </motion.div>
  );
}
