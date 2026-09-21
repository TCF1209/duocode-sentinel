"use client";

/**
 * The pitch, as four screens inside the product rather than a slide file.
 *
 * The demo video is recorded entirely in this app, so the three parts of the
 * submission brief that are *not* a live demo — who we are, the problem, the
 * stack — need somewhere on screen to exist. Putting them here means the whole
 * recording is one browser tab with no cutting to a deck, and a judge who opens
 * the deployed link gets the same four screens rather than only the dashboard.
 *
 * Arrow keys, click, or the dots. Every screen has to fit 1280x720 without a
 * scrollbar, because that is the size it will be recorded at.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { motion } from "motion/react";
import {
  ArrowLeft,
  ArrowRight,
  Clock,
  Eye,
  FileWarning,
  HandHelping,
  Repeat,
  Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { DURATION, EASE_OUT, fadeUp, stagger, TAP, TAP_TRANSITION } from "@/lib/motion";
import { cn } from "@/lib/utils";

/**
 * Names, courses and photo paths in one place. Photos live in
 * `web/public/team/` and are 4:5 portraits; `public/team/README.md` has the
 * sizes and the originals. A file the browser cannot load falls back to
 * initials rather than a broken-image icon.
 */
const TEAM = [
  {
    name: "Tang Chye Fong",
    course: "BSc Computer Science (AI)",
    year: "Final year",
    photo: "/team/tang-chye-fong.png",
  },
  {
    name: "Lim Yee Teng",
    course: "BSc Computer Science",
    year: "First year",
    photo: "/team/lim-yee-teng.webp",
  },
];
const UNIVERSITY = "Asia Pacific University";

const SLIDES = ["Sentinel", "The problem", "Tech stack", "What it does"] as const;

// The last slide's button sends a presenter on to /runs for the live part of
// the demo, which unmounts this component — coming back (to re-check Tech
// stack, say) landed back on slide 0 every time, because `index` lived only
// in this component's own state. sessionStorage survives that round trip
// without turning slide position into a URL a judge would ever share.
const STORAGE_KEY = "sentinel-pitch-slide";

function readStoredIndex(): number {
  if (typeof window === "undefined") return 0;
  try {
    const n = Number(window.sessionStorage.getItem(STORAGE_KEY));
    return Number.isInteger(n) && n >= 0 && n < SLIDES.length ? n : 0;
  } catch {
    return 0;
  }
}

export function PitchView() {
  const [index, setIndex] = useState(readStoredIndex);
  const [direction, setDirection] = useState(1);

  /**
   * The current slide, mirrored in a ref, and the reason is a bug that made
   * the dots inert: `go` used to compute the direction *inside* the `setIndex`
   * updater, so one setState was being called from another's updater. React
   * requires an updater to be pure and runs it twice under StrictMode, and the
   * result was that clicking a dot -- verified by calling `.click()` on the
   * button directly -- left the heading unchanged. Arrow keys shared the same
   * shape and were only accidentally surviving it.
   *
   * With the index in a ref, the direction is worked out before any state is
   * touched, `go` is the single entry point, and the keyboard handler is a
   * thin wrapper over it instead of a second copy of the clamping logic.
   */
  const indexRef = useRef(readStoredIndex());

  const go = useCallback((next: number) => {
    const clamped = Math.max(0, Math.min(SLIDES.length - 1, next));
    if (clamped === indexRef.current) return;
    setDirection(clamped > indexRef.current ? 1 : -1);
    indexRef.current = clamped;
    setIndex(clamped);
    try {
      window.sessionStorage.setItem(STORAGE_KEY, String(clamped));
    } catch {
      // Private mode or blocked storage — losing the remembered slide is a
      // minor inconvenience, not worth surfacing to whoever is rehearsing.
    }
  }, []);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      // Left alone when focus is in a field, so this cannot hijack typing if a
      // form is ever added to this page.
      const el = document.activeElement;
      if (el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement) return;

      if (e.key === "ArrowRight" || e.key === "PageDown" || e.key === " ") {
        e.preventDefault();
        go(indexRef.current + 1);
      } else if (e.key === "ArrowLeft" || e.key === "PageUp") {
        e.preventDefault();
        go(indexRef.current - 1);
      } else if (e.key === "Home") {
        go(0);
      } else if (e.key === "End") {
        go(SLIDES.length - 1);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [go]);

  // 10rem reserved and gap-4, both measured rather than guessed: at 1280x720
  // the densest screen overflowed by 8px on the first attempt and put a
  // scrollbar in the frame.
  return (
    <div className="flex min-h-[calc(100vh-10rem)] flex-col gap-4">
      {/*
        No AnimatePresence, and this is the second time today that component
        has been the wrong tool here. With `mode="wait"` the switch hung:
        `aria-current` moved from one dot to the next -- so the state update
        was fine -- while the DOM kept exactly one <section> and the old
        heading, forever. The exiting child never finished exiting, so the
        entering one was never mounted.

        Changing `key` remounts instead, which plays the new screen's
        `initial -> animate` and simply discards the old one. The cost is
        losing the outgoing half of the transition; the benefit is that it
        works, and a dot that does nothing when clicked is not a trade worth
        making on a page whose whole job is to be clicked through on camera.
      */}
      {/* perspective on the static parent, not the animated child -- the
          child's own rotateY needs a 3D space to rotate *into*, and putting
          perspective on the thing that is itself transforming warps the
          effect as it animates instead of holding a fixed vanishing point. */}
      <div className="relative flex flex-1 items-center" style={{ perspective: 1200 }}>
        <motion.section
          key={index}
          className="w-full"
          initial={{ opacity: 0, x: direction * 28, rotateY: direction * -10, scale: 0.98 }}
          animate={{ opacity: 1, x: 0, rotateY: 0, scale: 1 }}
          transition={{ duration: DURATION.slow, ease: EASE_OUT }}
          style={{ transformStyle: "preserve-3d" }}
        >
          {index === 0 && <Intro />}
          {index === 1 && <Problem />}
          {index === 2 && <TechStack />}
          {index === 3 && <Impact />}
        </motion.section>
      </div>

      <nav className="flex items-center justify-between gap-4" aria-label="Pitch navigation">
        <IconButton onClick={() => go(index - 1)} disabled={index === 0} label="Previous">
          <ArrowLeft className="size-4" />
        </IconButton>

        <div className="flex items-center gap-2">
          {SLIDES.map((label, i) => (
            <button
              key={label}
              onClick={() => go(i)}
              aria-label={label}
              aria-current={i === index}
              className="group flex items-center gap-2 px-1 py-2"
            >
              <span
                className={cn(
                  "h-1.5 rounded-full transition-all duration-300",
                  i === index ? "w-7 bg-primary" : "w-1.5 bg-border group-hover:bg-muted-foreground",
                )}
              />
              <span
                className={cn(
                  "hidden text-xs sm:inline",
                  i === index ? "text-foreground" : "text-muted-foreground",
                )}
              >
                {label}
              </span>
            </button>
          ))}
        </div>

        <IconButton
          onClick={() => go(index + 1)}
          disabled={index === SLIDES.length - 1}
          label="Next"
        >
          <ArrowRight className="size-4" />
        </IconButton>
      </nav>
    </div>
  );
}

function IconButton({
  onClick,
  disabled,
  label,
  children,
}: {
  onClick: () => void;
  disabled: boolean;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <motion.button
      whileTap={disabled ? undefined : TAP}
      transition={TAP_TRANSITION}
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      className="flex size-9 shrink-0 items-center justify-center rounded-full border bg-card text-muted-foreground transition-colors enabled:hover:text-foreground disabled:opacity-35"
    >
      {children}
    </motion.button>
  );
}

// --------------------------------------------------------------------------
// 1 — who and what
// --------------------------------------------------------------------------
function Intro() {
  return (
    <motion.div
      className="flex flex-col items-center gap-6 text-center"
      initial="hidden"
      animate="show"
      variants={stagger(0.05, 0.08)}
    >
      <motion.p
        className="text-xs tracking-[0.2em] text-muted-foreground uppercase sm:text-sm"
        variants={fadeUp}
      >
        DuoCode · Averis × Monash Hackathon 2026
      </motion.p>

      <motion.h1
        className="font-heading text-5xl font-semibold tracking-tight sm:text-7xl"
        variants={fadeUp}
      >
        Sentinel
      </motion.h1>

      <motion.p className="max-w-2xl text-lg text-muted-foreground sm:text-xl" variants={fadeUp}>
        Every answer comes with its evidence.
      </motion.p>

      {/*
        Cards lie down rather than stand up, and that is a height decision as
        much as a design one. Measured at 1280x720 there are 520px for a
        screen's content; portrait cards put the photo above the text and came
        to 603px. Laid on their side the photo is 112x140 -- far bigger than the
        44px circles this replaced, which is the point -- and the pair costs
        about 150px instead of 300.
      */}
      <motion.div className="flex flex-wrap items-stretch justify-center gap-4" variants={fadeUp}>
        {TEAM.map((m) => (
          <div
            key={m.name}
            className="flex items-stretch overflow-hidden rounded-xl border bg-card text-left"
          >
            <Portrait name={m.name} photo={m.photo} />
            <div className="flex min-w-0 flex-col justify-center gap-0.5 px-4 py-3">
              <div className="font-heading text-lg leading-tight font-semibold">{m.name}</div>
              <div className="text-sm leading-snug text-muted-foreground">{m.course}</div>
              <div className="text-sm text-primary">{m.year}</div>
              <div className="mt-1 text-xs text-muted-foreground">{UNIVERSITY}</div>
            </div>
          </div>
        ))}
      </motion.div>
    </motion.div>
  );
}

function Portrait({ name, photo }: { name: string; photo: string }) {
  const [failed, setFailed] = useState(false);
  const initials = name
    .split(" ")
    .map((w) => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  if (failed) {
    return (
      <span className="flex h-35 w-28 shrink-0 items-center justify-center bg-primary/10 font-heading text-3xl font-semibold text-primary">
        {initials}
      </span>
    );
  }
  return (
    <Image
      src={photo}
      alt={name}
      width={224}
      height={280}
      className="h-35 w-28 shrink-0 object-cover"
      onError={() => setFailed(true)}
      unoptimized
    />
  );
}

// --------------------------------------------------------------------------
// 2 — the problem, in the organisers' own terms
//
// The first version of this screen was written from memory and read as a
// slogan ("the hard part is knowing when you cannot"). The problem statement
// names three problems outright, so these are those three, plus the capability
// it calls "ask for help". Using their words about their problem beats a line
// we invented about it.
// --------------------------------------------------------------------------
const PROBLEMS = [
  {
    icon: Clock,
    title: "Finding the right emails takes time",
    body: "Every message has to be read and routed by hand. A document request that is overlooked never reaches the checking step at all.",
  },
  {
    icon: Repeat,
    title: "Comparing by hand is repetitive and easy to get wrong",
    body: "Names, ports, quantities and weight, across two documents. A missed discrepancy means corrections, delays and rework.",
  },
  {
    icon: Eye,
    title: "The same information looks different",
    body: "One document says Port of Loading, the other says Load Port. Same field, and nothing in the text says so.",
  },
];

function Problem() {
  return (
    <motion.div
      className="flex flex-col gap-5"
      initial="hidden"
      animate="show"
      variants={stagger(0.05, 0.07)}
    >
      <motion.div variants={fadeUp} className="text-center">
        <h2 className="font-heading text-3xl font-semibold tracking-tight sm:text-4xl">
          A shipping desk checks every bill of lading by hand
        </h2>
        <p className="mx-auto mt-2 max-w-3xl text-muted-foreground">
          Five kinds of mail arrive in one inbox. For a document check, someone opens the
          Shipping Instruction and the draft Bill of Lading and compares seven fields — shipper,
          consignee, notify party, load port, discharge port, containers, gross weight.
        </p>
      </motion.div>

      <motion.div className="grid gap-3 md:grid-cols-3" variants={stagger(0, 0.06)}>
        {PROBLEMS.map((p) => (
          <motion.div
            key={p.title}
            variants={fadeUp}
            className="flex flex-col gap-2 rounded-xl border bg-card p-4"
          >
            <span className="flex size-8 items-center justify-center rounded-full border bg-background text-muted-foreground">
              <p.icon className="size-4" strokeWidth={1.75} />
            </span>
            <div className="font-medium">{p.title}</div>
            <p className="text-sm leading-relaxed text-muted-foreground">{p.body}</p>
          </motion.div>
        ))}
      </motion.div>

      <motion.div
        className="mx-auto flex max-w-3xl items-start gap-3 rounded-xl border border-primary/40 bg-primary/8 p-4"
        variants={fadeUp}
      >
        <span className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-full border border-primary/40 bg-primary/15 text-primary">
          <HandHelping className="size-4" strokeWidth={1.75} />
        </span>
        <p className="text-base">
          <span className="font-medium">And when it cannot be done.</span> An unreadable scan, a
          blank field, the wrong document attached — the case has to reach a person{" "}
          <span className="font-medium">with the reason and the evidence</span>, rather than be
          guessed at or fail quietly.
        </p>
      </motion.div>
    </motion.div>
  );
}

// --------------------------------------------------------------------------
// 3 — tech stack
// --------------------------------------------------------------------------
const CORE = [
  {
    step: "Read",
    detail:
      "pdfplumber word coordinates rebuild a PDF's rows and columns — not flattened text. python-docx for tables, openpyxl for cells, markitdown as a fallback.",
  },
  {
    step: "Resolve labels",
    detail:
      "Three passes: exact match, then ordered regex rules, then rapidfuzz at cutoff 88 with a minimum-length guard so short synonyms cannot match inside long strings.",
  },
  {
    step: "Normalise",
    detail:
      "Legal suffixes dropped from company names, UN/LOCODEs stripped from ports, “138 MT” read as 138,000 kg.",
  },
  {
    step: "Compare",
    detail:
      "Exact equality on the canonical form. Never a similarity score — a threshold loose enough to forgive a typo also merges two real companies.",
  },
];

const MODEL = [
  { purpose: "classify", when: "an email the rule scorer is not confident about" },
  { purpose: "extract", when: "a field label our table has never seen" },
  { purpose: "vision", when: "an image-only PDF with no text layer to read" },
];

const INFRA = [
  "Python 3.10",
  "FastAPI · 11 routes",
  "Docker on Render",
  "Next.js 16 on Vercel",
  "574 tests",
];

function TechStack() {
  return (
    <motion.div
      className="flex flex-col gap-4"
      initial="hidden"
      animate="show"
      variants={stagger(0.05, 0.06)}
    >
      <motion.div variants={fadeUp} className="text-center">
        <h2 className="font-heading text-3xl font-semibold tracking-tight sm:text-4xl">
          Tech stack
        </h2>
        <p className="mt-1 text-muted-foreground">
          A deterministic core that answers all 520, and a model tier for what it cannot read.
        </p>
      </motion.div>

      <motion.div className="grid gap-3 lg:grid-cols-5" variants={stagger(0, 0.05)}>
        <motion.div
          variants={fadeUp}
          className="flex flex-col gap-2.5 rounded-xl border bg-card p-4 lg:col-span-3"
        >
          <div className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
            Deterministic core · no key, no network
          </div>
          {CORE.map((c) => (
            <div key={c.step} className="flex gap-3">
              <span className="w-24 shrink-0 text-sm font-medium">{c.step}</span>
              <span className="text-sm leading-snug text-muted-foreground">{c.detail}</span>
            </div>
          ))}
        </motion.div>

        <motion.div
          variants={fadeUp}
          className="flex flex-col gap-2.5 rounded-xl border border-ai/40 bg-ai-bg/50 p-4 lg:col-span-2"
        >
          <div className="flex items-center gap-1.5 text-xs font-medium tracking-wide text-ai uppercase">
            <Sparkles className="size-3.5" strokeWidth={2} />
            Model tier · gpt-5-mini
          </div>
          {MODEL.map((m) => (
            <div key={m.purpose} className="flex gap-2.5">
              <span className="w-16 shrink-0 font-mono text-sm text-ai">{m.purpose}</span>
              <span className="text-sm leading-snug text-muted-foreground">{m.when}</span>
            </div>
          ))}
          <p className="mt-auto border-t pt-2.5 text-sm">
            Every answer the model gives is{" "}
            <span className="font-medium">re-located in the document</span> before it is accepted.
            Anything it cannot ground is dropped.
          </p>
        </motion.div>
      </motion.div>

      <motion.div
        className="flex items-start gap-3 rounded-xl border border-primary/40 bg-primary/8 p-3"
        variants={fadeUp}
      >
        <span className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-full border border-primary/40 bg-primary/15 text-primary">
          <FileWarning className="size-4" strokeWidth={1.75} />
        </span>
        <p className="text-base">
          <span className="font-medium">The evidence gate sits after the comparison and can
          overrule it.</span>{" "}
          A value nobody can trace back to its source line is not reported as a discrepancy — the
          case goes to a person with both readings attached.
        </p>
      </motion.div>

      <motion.div className="flex flex-wrap justify-center gap-2" variants={fadeUp}>
        {INFRA.map((s) => (
          <span key={s} className="rounded-full border bg-card px-3 py-1 text-xs">
            {s}
          </span>
        ))}
      </motion.div>
    </motion.div>
  );
}

// --------------------------------------------------------------------------
// 4 — what it does
// --------------------------------------------------------------------------
const NUMBERS = [
  { value: "520", label: "emails, end to end", sub: "in 13 seconds, on a free-tier container" },
  { value: "225", label: "planted defects caught", sub: "every one with the exact field set" },
  { value: "80 / 80", label: "escalations correct", sub: "no false alarms" },
  { value: "$0", label: "to run the graded inbox", sub: "every decision made by rules" },
];

function Impact() {
  return (
    <motion.div
      className="flex flex-col gap-5"
      initial="hidden"
      animate="show"
      variants={stagger(0.05, 0.07)}
    >
      <motion.div variants={fadeUp} className="text-center">
        <h2 className="font-heading text-3xl font-semibold tracking-tight sm:text-4xl">
          What it does
        </h2>
        <p className="mt-1 text-muted-foreground">
          Four draws of the organisers&rsquo; dataset, at three sizes, scored with their own
          scorer.
        </p>
      </motion.div>

      <motion.div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4" variants={stagger(0, 0.06)}>
        {NUMBERS.map((n) => (
          <motion.div
            key={n.label}
            variants={fadeUp}
            className="flex flex-col gap-1 rounded-xl border bg-card p-4 text-center"
          >
            <span className="font-heading text-4xl font-semibold text-primary">{n.value}</span>
            <span className="text-sm font-medium">{n.label}</span>
            <span className="text-xs leading-snug text-muted-foreground">{n.sub}</span>
          </motion.div>
        ))}
      </motion.div>

      <motion.div
        className="mx-auto max-w-3xl rounded-xl border border-ai/40 bg-ai-bg/50 p-4 text-center"
        variants={fadeUp}
      >
        <p className="text-lg">
          Cheap because the model is <span className="font-medium">aimed</span>, not because it
          is absent.
        </p>
        <p className="mt-1 text-sm text-muted-foreground">
          Rules carry the whole volume at no marginal cost. The model is spent only on the tail
          they cannot read — <span className="font-mono">$0.0013</span> per document when it runs,
          and it is what lets the system handle a form nobody anticipated.
        </p>
      </motion.div>

      <motion.div className="flex flex-col items-center gap-3" variants={fadeUp}>
        {/* Labelled as an estimate on purpose. The 13 seconds is measured; the
            hours are arithmetic on an assumed pace, and a number that looks
            measured but is not is the easiest thing for a judge to pull on. */}
        <p className="text-center text-sm text-muted-foreground">
          One inbox is 520 emails to triage and 124 document pairs to compare. At a conservative
          20 seconds an email and 4 minutes a pair — <em>an estimate, not a measurement</em> —
          that is about <span className="font-medium text-foreground">11 hours</span> of desk
          work. Sentinel does it in <span className="font-medium text-foreground">13 seconds</span>.
        </p>

        <motion.div whileTap={TAP} transition={TAP_TRANSITION}>
          <Link href="/runs">
            <Button size="lg">
              See it read all 520
              <ArrowRight className="size-4" />
            </Button>
          </Link>
        </motion.div>
      </motion.div>
    </motion.div>
  );
}
