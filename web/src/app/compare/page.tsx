import Link from "next/link";
import { IntervalBar, StickerCard } from "@/components/StickerCard";
import { api } from "@/lib/api";
import { configLabel, per1k, shortDate } from "@/lib/format";
import type { Sticker, Test } from "@/lib/types";

type Comparison = {
  a: Sticker;
  b: Sticker;
  p_value: number;
  significant: boolean;
  absolute_change: number;
  relative_risk: number | null;
  verdict: string;
};

async function getComparison(a: string, b: string): Promise<Comparison | { error: string } | null> {
  try {
    const origin = process.env.WSK_API_ORIGIN ?? "http://127.0.0.1:8765";
    const res = await fetch(`${origin}/api/compare?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`, { cache: "no-store" });
    if (res.ok) return (await res.json()) as Comparison;
    const body = (await res.json().catch(() => null)) as { detail?: unknown } | null;
    return { error: typeof body?.detail === "string" ? body.detail : `The lab could not compare these tests (${res.status}).` };
  } catch {
    return null;
  }
}

const traps = (t: Test) => (t.scenarios.length ? `${t.scenarios.length} traps` : "all traps");
const optionLabel = (t: Test) =>
  `${configLabel(t)} · suite ${t.suite} · ${traps(t)} · ${t.sticker!.runs} runs · ${shortDate(t.created_at)}`;

/** Same model, same suite and traps, different guardrails: the comparisons people actually want. */
function suggestedPairs(tests: Test[]): [Test, Test][] {
  const key = (t: Test) => `${t.suite}|${t.model}|${[...t.scenarios].sort().join(",")}`;
  const groups = new Map<string, Test[]>();
  for (const t of tests) groups.set(key(t), [...(groups.get(key(t)) ?? []), t]);
  const pairs: [Test, Test][] = [];
  for (const g of groups.values()) {
    const base = g.find((t) => t.guardrails.length === 0 && !t.agent_name.toLowerCase().startsWith("opencode"));
    if (!base) continue;
    for (const other of g) if (other.id !== base.id && other.agent_fingerprint !== base.agent_fingerprint) pairs.push([base, other]);
  }
  return pairs.sort((x, y) => (y[0].suite > x[0].suite ? 1 : -1)).slice(0, 4);
}

export default async function ComparePage({ searchParams }: { searchParams: Promise<{ a?: string; b?: string }> }) {
  const { a, b } = await searchParams;
  const tests = ((await api.tests()) ?? []).filter((t) => t.status === "finished" && t.sticker && !t.sticker.provisional);
  const result = a && b ? await getComparison(a, b) : null;
  const cmp = result && "a" in result ? result : null;
  const error = result && "error" in result ? result.error : null;
  const pairs = suggestedPairs(tests);

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
              className="mt-1.5 block w-full max-w-md rounded-lg border border-rule bg-card px-3 py-2 text-[14px]"
            >
              {tests.map((t) => (
                <option key={t.id} value={t.id}>
                  {optionLabel(t)}
                </option>
              ))}
            </select>
          </label>
        ))}
        <button className="rounded-lg bg-ink px-4 py-2 font-semibold text-paper">Compare</button>
      </form>

      {pairs.length > 0 && (
        <div className="mt-5 flex flex-wrap items-center gap-2 text-[13px]">
          <span className="text-muted">Try:</span>
          {pairs.map(([x, y]) => (
            <Link
              key={`${x.id}-${y.id}`}
              href={`/compare?a=${x.id}&b=${y.id}`}
              className="rounded-full border border-rule bg-card px-3 py-1 hover:border-ink"
            >
              {configLabel(x)} vs {configLabel(y)} · suite {x.suite}
            </Link>
          ))}
        </div>
      )}

      {error && (
        <p className="mt-8 rounded-xl border-2 border-ink bg-card p-5 text-[15px]">
          <strong>These two cannot be compared fairly.</strong> {error}
        </p>
      )}

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
