"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/", label: "Runs" },
  { href: "/compare", label: "Compare (demo)" },
];

export function Nav() {
  const pathname = usePathname();
  return (
    <header className="border-b">
      <div className="mx-auto flex max-w-6xl items-center gap-6 px-4 py-3">
        <Link href="/" className="font-semibold tracking-tight">
          Sentinel
        </Link>
        <nav className="flex gap-4 text-sm">
          {LINKS.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className={cn(
                "text-muted-foreground hover:text-foreground",
                pathname === l.href && "font-medium text-foreground",
              )}
            >
              {l.label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}
