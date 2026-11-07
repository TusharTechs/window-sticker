import type { Metadata } from "next";
import Link from "next/link";
import { Archivo, Inter_Tight, JetBrains_Mono } from "next/font/google";
import { Wordmark } from "@/components/Logo";
import "./globals.css";

const inter = Inter_Tight({ subsets: ["latin"], variable: "--font-inter-tight", display: "swap" });
const mono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-jetbrains", display: "swap" });
const archivo = Archivo({ subsets: ["latin"], weight: ["800"], variable: "--font-archivo", display: "swap" });

export const metadata: Metadata = {
  title: "Window Sticker: crash-test ratings for AI agents",
  description:
    "Run an AI agent dozens of times in throwaway microVMs on Vultr against a published trap suite. Get a measured safety rating, incident rate and cost per task.",
};

const NAV = [
  { href: "/new", label: "Crash test" },
  { href: "/tests", label: "Tests" },
  { href: "/leaderboard", label: "Leaderboard" },
  { href: "/suite", label: "Trap suite" },
  { href: "/methodology", label: "Methodology" },
];

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${inter.variable} ${mono.variable} ${archivo.variable}`}>
      <body className="min-h-screen">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded focus:bg-yellow focus:px-3 focus:py-2"
        >
          Skip to content
        </a>
        <header className="sticky top-0 z-40 border-b border-rule bg-paper/90 backdrop-blur">
          <div className="mx-auto flex h-14 max-w-6xl items-center justify-between gap-4 px-4 sm:px-6">
            <Link href="/" aria-label="Window Sticker home">
              <Wordmark />
            </Link>
            <nav aria-label="Main" className="flex items-center gap-1 overflow-x-auto text-[14px]">
              {NAV.map((n) => (
                <Link
                  key={n.href}
                  href={n.href}
                  className="whitespace-nowrap rounded-md px-2.5 py-1.5 text-ink-2 hover:bg-paper-2 hover:text-ink"
                >
                  {n.label}
                </Link>
              ))}
            </nav>
          </div>
        </header>
        <main id="main">{children}</main>
        <footer className="mt-24 border-t border-rule">
          <div className="mx-auto flex max-w-6xl flex-col gap-2 px-4 py-8 text-[13px] text-muted sm:flex-row sm:items-center sm:justify-between sm:px-6">
            <span>
              Every run in its own microVM on{" "}
              <span className="font-semibold text-vultr">Vultr</span> Cloud Compute, graded by Vultr Serverless
              Inference.
            </span>
            <span className="font-mono text-[12px]">MIT · Trap Suite v1</span>
          </div>
        </footer>
      </body>
    </html>
  );
}
