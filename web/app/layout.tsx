import type { Metadata } from "next";
import { Geist, Geist_Mono, Source_Serif_4 } from "next/font/google";
import { ThemeProvider } from "next-themes";
import "./globals.css";
import { Nav } from "@/components/nav";
import { Toaster } from "@/components/ui/sonner";
import { CursorGlow } from "@/components/cursor-glow";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const sourceSerif = Source_Serif_4({
  variable: "--font-serif",
  subsets: ["latin"],
  weight: ["500", "600", "700"],
});

export const metadata: Metadata = {
  title: "Sentinel — shipping document verification",
  description: "Averis x Monash Hackathon 2026 — DuoCode",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${geistSans.variable} ${geistMono.variable} ${sourceSerif.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
          <CursorGlow />
          <Nav />
          {/* pt-2, not py-6: with the sticky nav above it, a 24 px top margin
              read as an empty band on every page (the user's ask). */}
          <main className="mx-auto w-full max-w-6xl flex-1 px-4 pt-2 pb-6">{children}</main>
          <Toaster />
        </ThemeProvider>
      </body>
    </html>
  );
}
