import type { ComponentType } from "react";
import { FileSearch, GitCompareArrows, Inbox, UserCheck } from "lucide-react";

export interface PipelineStep {
  icon: ComponentType<{ className?: string; strokeWidth?: number }>;
  step: string;
  text: string;
}

/**
 * The four-stage explanation of what Sentinel does — shared by the Home
 * page's scroll-driven roadmap and /demo's static walkthrough step, so the
 * wording judges see in a live click-through and the wording a presenter
 * narrates in the guided demo never quietly drift apart.
 */
export const PIPELINE_STEPS: PipelineStep[] = [
  {
    icon: Inbox,
    step: "1. Classify",
    text: "Sort the inbox — comparison requests, new SI requests, invoice queries, general mail, spam.",
  },
  {
    icon: FileSearch,
    step: "2. Extract",
    text: "Pull the 7 shipment fields from the SI and BL attachments, however each one labels them.",
  },
  {
    icon: GitCompareArrows,
    step: "3. Compare",
    text: "Show which fields agree and flag exactly which ones don't, side by side.",
  },
  {
    icon: UserCheck,
    step: "4. Escalate",
    text: "Missing, unreadable, or unsure? Send it to a person with the reason, not a silent guess.",
  },
];
