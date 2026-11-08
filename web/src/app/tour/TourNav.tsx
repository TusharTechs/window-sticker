"use client";

import { useEffect, useState } from "react";

/** A sticky list of tour steps that follows the reader down the page. */
export function TourNav({ steps }: { steps: { id: string; title: string }[] }) {
  const [active, setActive] = useState(steps[0]?.id);
  useEffect(() => {
    const seen = new IntersectionObserver(
      (entries) => {
        const top = entries.filter((e) => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
        if (top) setActive(top.target.id);
      },
      { rootMargin: "-30% 0px -60% 0px" },
    );
    for (const s of steps) {
      const el = document.getElementById(s.id);
      if (el) seen.observe(el);
    }
    return () => seen.disconnect();
  }, [steps]);
  const index = steps.findIndex((s) => s.id === active);
  return (
    <nav aria-label="Tour steps" className="sticky top-20 hidden lg:block">
      <div className="font-mono text-[10.5px] uppercase tracking-[0.16em] text-muted">Judge tour · {index + 1}/{steps.length}</div>
      <ol className="mt-3 space-y-1 border-l-2 border-rule">
        {steps.map((s, i) => (
          <li key={s.id}>
            <a
              href={`#${s.id}`}
              className={`-ml-[2px] block border-l-2 py-1.5 pl-3 text-[13.5px] transition ${
                s.id === active ? "border-yellow font-semibold text-ink" : i < index ? "border-ink/40 text-ink-2" : "border-transparent text-muted hover:text-ink"
              }`}
            >
              <span className="mr-2 font-mono text-[11px] tabular">{String(i + 1).padStart(2, "0")}</span>
              {s.title}
            </a>
          </li>
        ))}
      </ol>
    </nav>
  );
}
