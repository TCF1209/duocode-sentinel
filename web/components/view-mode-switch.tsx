"use client";

import { motion } from "motion/react";
import { Sparkles, Inbox } from "lucide-react";
import { TAP, TAP_TRANSITION } from "@/lib/motion";
import { useViewMode, type ViewMode } from "@/lib/view-mode";
import { cn } from "@/lib/utils";

const OPTIONS: { value: ViewMode; label: string; icon: typeof Inbox; title: string }[] = [
  {
    value: "before",
    label: "Before Sentinel",
    icon: Inbox,
    title: "The inbox as it arrived, and what a person would have to do with it",
  },
  {
    value: "with",
    label: "With Sentinel",
    icon: Sparkles,
    title: "What Sentinel made of the same inbox",
  },
];

/** The same segmented control on the run page and the case page; one
 *  sessionStorage value behind both (lib/view-mode.ts). */
export function ViewModeSwitch({ className }: { className?: string }) {
  const [mode, setMode] = useViewMode();
  return (
    <div
      className={cn("flex items-center rounded-full border bg-card p-0.5 text-xs", className)}
      role="group"
      aria-label="Before or with Sentinel"
    >
      {OPTIONS.map((o) => {
        const Icon = o.icon;
        const active = mode === o.value;
        return (
          <motion.button
            key={o.value}
            type="button"
            whileTap={TAP}
            transition={TAP_TRANSITION}
            onClick={() => setMode(o.value)}
            aria-pressed={active}
            title={o.title}
            className={cn(
              "flex items-center gap-1.5 rounded-full px-2.5 py-1 font-medium transition-colors",
              active ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground",
            )}
          >
            <Icon className="size-3.5" strokeWidth={2} />
            {o.label}
          </motion.button>
        );
      })}
    </div>
  );
}
