import type { Metadata } from "next";
import { PitchView } from "@/components/pitch-view";

export const metadata: Metadata = {
  title: "Sentinel — the pitch",
  description:
    "Who built it, the problem it solves, how it works, the evidence behind the numbers, and what it does — five screens, inside the product.",
};

export default function PitchPage() {
  return <PitchView />;
}
