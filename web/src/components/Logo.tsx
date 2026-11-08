import { useId } from "react";

const BODY = "M18 4h28a14 14 0 0 1 14 14v26L44 60H18A14 14 0 0 1 4 46V18A14 14 0 0 1 18 4z";
const STAR = "M32 12.5l5.6 11.4 12.6 1.8-9.1 8.9 2.1 12.5L32 41.2l-11.2 5.9 2.1-12.5-9.1-8.9 12.6-1.8z";
const PEEL = "M60 44L44 60l-1.2-12.4a4 4 0 0 1 4.4-4.4z";

/**
 * The Window Sticker mark: the black-and-yellow quadrants painted on crash-test cars, a rating
 * star, and the corner of a sticker peeling up. `tone="dark"` adds a light keyline so the ink
 * quadrants stay visible on dark grounds.
 */
export function Mark({
  size = 28,
  tone = "light",
  className = "",
}: {
  size?: number;
  tone?: "light" | "dark";
  className?: string;
}) {
  const clip = `wsk-mark-${useId().replace(/:/g, "")}`;
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" className={className} aria-hidden="true" focusable="false">
      <defs>
        <clipPath id={clip}>
          <path d={BODY} />
        </clipPath>
      </defs>
      {tone === "dark" && <path d={BODY} fill="none" stroke="#fffdf8" strokeWidth="5" strokeLinejoin="round" />}
      <g clipPath={`url(#${clip})`}>
        <rect width="64" height="64" fill="#14161a" />
        <rect x="32" width="32" height="32" fill="#ffc400" />
        <rect y="32" width="32" height="32" fill="#ffc400" />
      </g>
      <path d={BODY} fill="none" stroke="#14161a" strokeWidth="2.6" strokeLinejoin="round" />
      <path d={STAR} fill="#fffdf8" stroke="#14161a" strokeWidth="2.6" strokeLinejoin="round" />
      <path d={PEEL} fill="#ece7db" stroke="#14161a" strokeWidth="2.6" strokeLinejoin="round" />
    </svg>
  );
}

/** Kept for existing imports: the mark at a given size. */
export function TargetMark({ size = 28, className = "" }: { size?: number; className?: string }) {
  return <Mark size={size} tone="dark" className={className} />;
}

export function Wordmark() {
  return (
    <span className="group flex items-center gap-2.5">
      <Mark size={30} className="transition-transform duration-300 group-hover:-rotate-6 group-hover:scale-105" />
      <span className="font-display text-[17px] font-extrabold uppercase leading-none tracking-[0.08em]">
        Window <span className="text-ink-2">Sticker</span>
      </span>
    </span>
  );
}
