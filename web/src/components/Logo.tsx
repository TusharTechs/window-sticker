/** The crash-test dummy target: a quartered circle, the mark used on test vehicles. */
export function TargetMark({ size = 28, className = "" }: { size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      className={className}
      aria-hidden="true"
      focusable="false"
    >
      <circle cx="16" cy="16" r="15" fill="var(--ink)" />
      <path d="M16 1 A15 15 0 0 1 31 16 L16 16 Z" fill="var(--yellow)" />
      <path d="M16 31 A15 15 0 0 1 1 16 L16 16 Z" fill="var(--yellow)" />
      <circle cx="16" cy="16" r="15" fill="none" stroke="var(--ink)" strokeWidth="2" />
    </svg>
  );
}

export function Wordmark() {
  return (
    <span className="flex items-center gap-2.5">
      <TargetMark size={26} />
      <span className="font-display text-[17px] font-extrabold uppercase tracking-[0.08em]">
        Window Sticker
      </span>
    </span>
  );
}
