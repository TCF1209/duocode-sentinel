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
 * Arrow keys, click, or the dots. Deliberately spare: this is read once, at
 * speed, by someone who has never seen the project. Anything that needs a
 * second look belongs in the README instead.
 */

import { useCallback, useEffect, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { AnimatePresence, motion } from "motion/react";
import {
  ArrowLeft,
  ArrowRight,
  FileSearch,
  Inbox,
  ScanEye,
  ShieldCheck,
  SplitSquareHorizontal,
  Stamp,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { DURATION, EASE_OUT, fadeUp, stagger, TAP, TAP_TRANSITION } from "@/lib/motion";
import { cn } from "@/lib/utils";

/**
 * Edit these two and drop matching images in `web/public/team/`. Any file the
 * browser cannot load falls back to initials rather than a broken-image icon,
 * so the page is presentable before the photos arrive and after, without a
 * code change in between.
 */
const TEAM = [
  { name: "Tang Chye Fong", role: "Engineering, demo video", photo: "/team/tang-chye-fong.png" },
  { name: "Lim Yee Teng", role: "Slides, project write-up", photo: "/team/lim-yee-teng.webp" },
];

const SLIDES = ["Sentinel", "The problem", "How it works", "What it does"] as const;

export function PitchView() {
  const [index, setIndex] = useState(0);
  const [direction, setDirection] = useState(1);

  const go = useCallback((next: number) => {
    setIndex((current) => {
      const clamped = Math.max(0, Math.min(SLIDES.length - 1, next));
      setDirection(clamped >= current ? 1 : -1);
      return clamped;
    });
  }, []);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      // Left alone when focus is in a field, so this cannot hijack typing if a
      // form is ever added to this page.
      const el = document.activeElement;
      if (el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement) return;
      if (e.key === "ArrowRight" || e.key === "PageDown" || e.key === " ") {
        e.preventDefault();
        setIndex((i) => {
          setDirection(1);
          return Math.min(SLIDES.length - 1, i + 1);
        });
      } else if (e.key === "ArrowLeft" || e.key === "PageUp") {
        e.preventDefault();
        setIndex((i) => {
          setDirection(-1);
          return Math.max(0, i - 1);
        });
      } else if (e.key === "Home") {
        setDirection(-1);
        setIndex(0);
      } else if (e.key === "End") {
        setDirection(1);
        setIndex(SLIDES.length - 1);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // 10rem, not 9, and gap-4 rather than 6: at 1280x720 -- a common recording
  // size, and this page exists to be recorded -- the "How it works" screen
  // overflowed by 8px and put a scrollbar in the frame. Measured, not guessed;
  // the other three screens had room to spare either way.
  return (
    <div className="flex min-h-[calc(100vh-10rem)] flex-col gap-4">
      <div className="relative flex flex-1 items-center">
        <AnimatePresence mode="wait" custom={direction} initial={false}>
          <motion.section
            key={index}
            custom={direction}
            className="w-full"
            initial={{ opacity: 0, x: direction * 28 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: direction * -28 }}
            transition={{ duration: DURATION.base, ease: EASE_OUT }}
          >
            {index === 0 && <Intro />}
            {index === 1 && <Problem />}
            {index === 2 && <HowItWorks />}
            {index === 3 && <Impact />}
          </motion.section>
        </AnimatePresence>
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
      className="flex flex-col items-center gap-8 text-center"
      initial="hidden"
      animate="show"
      variants={stagger(0.05, 0.08)}
    >
      <motion.p
        className="text-sm tracking-[0.2em] text-muted-foreground uppercase"
        variants={fadeUp}
      >
        DuoCode · Averis × Monash Hackathon 2026
      </motion.p>

      <motion.h1
        className="font-heading text-6xl font-semibold tracking-tight sm:text-8xl"
        variants={fadeUp}
      >
        Sentinel
      </motion.h1>

      <motion.p className="max-w-2xl text-xl text-muted-foreground sm:text-2xl" variants={fadeUp}>
        Every answer comes with its evidence.
      </motion.p>

      <motion.div className="mt-2 flex flex-wrap justify-center gap-4" variants={fadeUp}>
        {TEAM.map((m) => (
          <div
            key={m.name}
            className="flex items-center gap-3 rounded-full border bg-card py-2 pr-5 pl-2"
          >
            <Avatar name={m.name} photo={m.photo} />
            <div className="text-left">
              <div className="text-sm font-medium">{m.name}</div>
              <div className="text-xs text-muted-foreground">{m.role}</div>
            </div>
          </div>
        ))}
      </motion.div>
    </motion.div>
  );
}

/**
 * Both photos are pre-cropped to 400x400 head-and-shoulders squares, so
 * `object-cover` has nothing to crop. `object-top` is kept as the default
 * anyway: the originals are beside them in `public/team/`, one of them a 3:4
 * portrait, and a centred square crop of a portrait headshot takes the chin
 * and the collar. If anyone swaps a full-frame photo back in, this degrades
 * to "face near the top" instead of "collar".
 */
function Avatar({ name, photo }: { name: string; photo: string }) {
  const [failed, setFailed] = useState(false);
  const initials = name
    .split(" ")
    .map((w) => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  if (failed) {
    return (
      <span className="flex size-11 shrink-0 items-center justify-center rounded-full border border-primary/30 bg-primary/10 font-heading text-sm font-semibold text-primary">
        {initials}
      </span>
    );
  }
  return (
    <Image
      src={photo}
      alt={name}
      width={44}
      height={44}
      className="size-11 shrink-0 rounded-full border object-cover object-top"
      onError={() => setFailed(true)}
      unoptimized
    />
  );
}

// --------------------------------------------------------------------------
// 2 — the problem, in as few words as it can be said
// --------------------------------------------------------------------------
const MAIL = [
  { label: "Check these documents", accent: true },
  { label: "Send me a shipping instruction" },
  { label: "Question about an invoice" },
  { label: "General operations" },
  { label: "Spam" },
];

function Problem() {
  return (
    <motion.div
      className="flex flex-col gap-8"
      initial="hidden"
      animate="show"
      variants={stagger(0.05, 0.07)}
    >
      <motion.div variants={fadeUp} className="text-center">
        <h2 className="font-heading text-3xl font-semibold tracking-tight sm:text-4xl">
          One inbox. Five kinds of mail.
        </h2>
        <p className="mt-2 text-muted-foreground">
          A shipping desk reads every one of them by hand.
        </p>
      </motion.div>

      <motion.div className="flex flex-wrap justify-center gap-2" variants={fadeUp}>
        {MAIL.map((m) => (
          <span
            key={m.label}
            className={cn(
              "rounded-full border px-4 py-2 text-sm",
              m.accent
                ? "border-primary/40 bg-primary/10 font-medium text-primary"
                : "bg-card text-muted-foreground",
            )}
          >
            {m.label}
          </span>
        ))}
      </motion.div>

      <motion.div
        className="mx-auto flex max-w-3xl flex-col items-center gap-4 rounded-xl border bg-card p-6 text-center"
        variants={fadeUp}
      >
        <Inbox className="size-6 text-primary" strokeWidth={1.75} />
        <p className="text-lg">
          For a document check, someone opens two files — the instruction and the draft bill
          of lading — and compares{" "}
          <span className="font-medium text-foreground">seven fields</span> by eye.
        </p>
        <p className="text-sm text-muted-foreground">
          Shipper · Consignee · Notify party · Load port · Discharge port · Containers ·
          Gross weight
        </p>
      </motion.div>

      <motion.p
        className="mx-auto max-w-2xl text-center font-heading text-xl font-medium sm:text-2xl"
        variants={fadeUp}
      >
        The hard part is not reading the documents. It is knowing when you cannot.
      </motion.p>
    </motion.div>
  );
}

// --------------------------------------------------------------------------
// 3 — how it works
// --------------------------------------------------------------------------
const STAGES = [
  { icon: Inbox, name: "Classify", note: "Which of the five is this?" },
  { icon: ScanEye, name: "Read", note: "PDF, Word, Excel, plain text" },
  { icon: FileSearch, name: "Extract", note: "Seven fields, each with its source line" },
  { icon: SplitSquareHorizontal, name: "Compare", note: "Instruction against draft" },
  { icon: ShieldCheck, name: "Evidence gate", note: "May we report this as fact?", key: true },
  { icon: Stamp, name: "Decide", note: "Clean · Defect · Send to a human" },
];

const STACK = ["Python", "FastAPI", "Next.js", "OpenAI", "Docker on Render", "Vercel"];

function HowItWorks() {
  return (
    <motion.div
      className="flex flex-col gap-6"
      initial="hidden"
      animate="show"
      variants={stagger(0.05, 0.06)}
    >
      <motion.div variants={fadeUp} className="text-center">
        <h2 className="font-heading text-3xl font-semibold tracking-tight sm:text-4xl">
          Six steps, and one of them is unusual
        </h2>
        <p className="mt-2 text-muted-foreground">
          Rules do the work. The model is only asked where the rules give up.
        </p>
      </motion.div>

      <motion.div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3" variants={stagger(0, 0.05)}>
        {STAGES.map((s, i) => (
          <motion.div
            key={s.name}
            variants={fadeUp}
            className={cn(
              "flex items-start gap-3 rounded-xl border p-4",
              s.key ? "border-primary/40 bg-primary/8" : "bg-card",
            )}
          >
            <span
              className={cn(
                "flex size-9 shrink-0 items-center justify-center rounded-full border",
                s.key
                  ? "border-primary/40 bg-primary/15 text-primary"
                  : "bg-background text-muted-foreground",
              )}
            >
              <s.icon className="size-4" strokeWidth={1.75} />
            </span>
            <div className="min-w-0">
              <div className="flex items-baseline gap-2">
                <span className="font-mono text-xs text-muted-foreground">{i + 1}</span>
                <span className={cn("font-medium", s.key && "text-primary")}>{s.name}</span>
              </div>
              <p className="text-sm text-muted-foreground">{s.note}</p>
            </div>
          </motion.div>
        ))}
      </motion.div>

      <motion.div
        className="mx-auto max-w-3xl rounded-xl border border-primary/30 bg-primary/8 p-5 text-center"
        variants={fadeUp}
      >
        <p className="text-lg">
          Step five can <span className="font-medium">overrule</span> step four. If a value
          cannot be found again in the document it came from, we do not report it — we hand
          the case to a person, with both readings attached.
        </p>
      </motion.div>

      <motion.div className="flex flex-wrap justify-center gap-2" variants={fadeUp}>
        {STACK.map((s) => (
          <span key={s} className="rounded-full border bg-card px-3 py-1.5 text-xs">
            {s}
          </span>
        ))}
      </motion.div>
    </motion.div>
  );
}

// --------------------------------------------------------------------------
// 4 — what it does, with the baseline said out loud
// --------------------------------------------------------------------------
const NUMBERS = [
  { value: "520", label: "emails, end to end", sub: "in about 13 seconds" },
  { value: "225", label: "planted defects caught", sub: "every one with the exact fields" },
  { value: "80 / 80", label: "escalations correct", sub: "no false alarms" },
  { value: "100%", label: "decided by rules", sub: "no model call on the graded inbox" },
];

function Impact() {
  return (
    <motion.div
      className="flex flex-col gap-8"
      initial="hidden"
      animate="show"
      variants={stagger(0.05, 0.07)}
    >
      <motion.div variants={fadeUp} className="text-center">
        <h2 className="font-heading text-3xl font-semibold tracking-tight sm:text-4xl">
          What it does
        </h2>
        <p className="mt-2 text-muted-foreground">
          Four draws of the organisers&rsquo; dataset, at three sizes, scored with their own
          scorer.
        </p>
      </motion.div>

      <motion.div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4" variants={stagger(0, 0.06)}>
        {NUMBERS.map((n) => (
          <motion.div
            key={n.label}
            variants={fadeUp}
            className="flex flex-col gap-1 rounded-xl border bg-card p-5 text-center"
          >
            <span className="font-heading text-4xl font-semibold text-primary">{n.value}</span>
            <span className="text-sm font-medium">{n.label}</span>
            <span className="text-xs text-muted-foreground">{n.sub}</span>
          </motion.div>
        ))}
      </motion.div>

      {/* The number nobody has to give you, said first. A blank submission
          scores 74.65% of the same assertions, so quoting a headline without it
          invites exactly the arithmetic that deflates it. */}
      <motion.div
        className="mx-auto max-w-3xl rounded-xl border bg-card p-5 text-center"
        variants={fadeUp}
      >
        <p className="text-lg">
          A submission that answers <span className="font-medium">nothing</span> already
          scores <span className="font-mono font-medium">74.65%</span> of the graded
          assertions.
        </p>
        <p className="mt-1 text-muted-foreground">
          The part that is not free is the part we built: 514 document pairs compared, 225
          defects found, 80 cases handed to a human with a reason.
        </p>
      </motion.div>

      <motion.div className="flex justify-center" variants={fadeUp}>
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
