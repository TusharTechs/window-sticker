function Star({ filled, size }: { filled: boolean; size: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M12 1.8l3.1 6.6 7.2.9-5.3 5 1.4 7.1L12 17.9l-6.4 3.5 1.4-7.1-5.3-5 7.2-.9z"
        fill={filled ? "var(--yellow)" : "transparent"}
        stroke={filled ? "var(--ink)" : "var(--rule)"}
        strokeWidth="1.4"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function Stars({
  stars,
  provisional,
  size = 22,
}: {
  stars: number;
  provisional: boolean;
  size?: number;
}) {
  if (provisional) {
    return (
      <span
        className="inline-flex items-center rounded-full border border-ink px-2.5 py-0.5 font-mono text-[11px] font-semibold uppercase tracking-wider"
        title="Not enough runs for a rating yet"
      >
        Provisional
      </span>
    );
  }
  return (
    <span className="inline-flex gap-0.5" role="img" aria-label={`${stars} out of 5 stars`}>
      {[0, 1, 2, 3, 4].map((i) => (
        <Star key={i} filled={i < stars} size={size} />
      ))}
    </span>
  );
}
