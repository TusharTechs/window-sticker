import Link from "next/link";
import { IntervalBar, StickerCard } from "@/components/StickerCard";
import { api } from "@/lib/api";
import { per1k } from "@/lib/format";
import type { Sticker } from "@/lib/types";

type Comparison = {
  a: Sticker;
  b: Sticker;
  p_value: number;
  significant: boolean;
  absolute_change: number;
  relative_risk: number | null;
  verdict: string;
};

async function getComparison(a: string, b: string): Promise<Comparison | null> {
  try {
    const origin = process.env.WSK_API_ORIGIN ?? "http://127.0.0.1:8765";
    const res = await fetch(`${origin}/api/compare?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`, { cache: "no-store" });
    return res.ok ? ((await res.json()) as Comparison) : null;
  } catch {
    return null;
  }
}

export default async function ComparePage({ searchParams }: { searchParams: Promise<{ a?: string; b?: string }> }) {
  const { a, b } = await searchParams;
  const tests = ((await api.tests()) ?? []).filter((t) => t.status === "finished" && t.sticker);
  const cmp = a && b ? await getComparison(a, b) : null;

  return (
    <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
      <h1 className="font-display text-[34px] font-extrabold tracking-tight">Compare two tests</h1>
      <p className="mt-2 max-w-2xl text-ink-2">
        Did the guardrail actually help, or did you get lucky? A Fisher exact test on serious incidents answers that, and
        it says &ldquo;not yet&rdquo; when the sample cannot tell.
      </p>

      <form className="mt-6 flex flex-wrap items-end gap-3" action="/compare">
        {(["a", "b"] as const).map((k) => (
          <label key={k} className="block">
            <span className="font-mono text-[10.5px] font-semibold uppercase tracking-[0.14em] text-muted">
              {k === "a" ? "Before (A)" : "After (B)"}
            </span>
            <select
              name={k}
              defaultValue={k === "a" ? a : b}
              className="mt-1.5 block w-80 rounded-lg border border-rule bg-card px-3 py-2 text-[14px]"
            >
              {tests.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.agent_name} · {t.sticker!.runs} runs{t.label ? ` · ${t.label}` : ""}
                </option>
              ))}
            </select>
          </label>
        ))}
        <button className="rounded-lg bg-ink px-4 py-2 font-semibold text-paper">Compare</button>
      </form>

      {cmp && (
        <>
          <section
            className={`mt-8 rounded-xl border-2 p-6 ${cmp.significant ? "border-green bg-green-soft" : "border-ink bg-card"}`}
          >
            <div className="font-mono text-[10.5px] font-semibold uppercase tracking-[0.14em] text-muted">Verdict</div>
            <p className="mt-2 font-display text-[24px] font-extrabold leading-snug">{cmp.verdict}</p>
            <div className="mt-5 grid gap-6 md:grid-cols-2">
              {[
                { k: "A", st: cmp.a },
                { k: "B", st: cmp.b },
              ].map(({ k, st }) => {
                const max = Math.max(cmp.a.serious_per_1000.upper, cmp.b.serious_per_1000.upper) * 1.1;
                return (
                  <div key={k}>
                    <div className="flex justify-between text-[14px]">
                      <span className="font-semibold">
                        {k} · {st.agent.name}
                      </span>
                      <span className="font-mono tabular">
                        {per1k(st.serious_per_1000.point)}/1k ({per1k(st.serious_per_1000.lower)}–{per1k(st.serious_per_1000.upper)})
                      </span>
                    </div>
                    <IntervalBar range={st.serious_per_1000} max={max} label={`${k} serious incident interval`} />
                  </div>
                );
              })}
            </div>
            <p className="mt-4 font-mono text-[12px] text-ink-2">
              Fisher exact, two-sided · p = {cmp.p_value.toPrecision(3)} · change {(cmp.absolute_change * 1000).toFixed(0)} per 1,000
            </p>
          </section>
          <div className="mt-8 grid gap-8 lg:grid-cols-2">
            <StickerCard s={cmp.a} compact />
            <StickerCard s={cmp.b} compact />
          </div>
        </>
      )}
      {!cmp && tests.length < 2 && (
        <p className="mt-8 text-ink-2">
          You need two finished tests. <Link href="/new" className="font-semibold underline">Run one.</Link>
        </p>
      )}
    </div>
  );
}
