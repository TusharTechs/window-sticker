import type { Metadata } from "next";
import { headers } from "next/headers";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Mark } from "@/components/Logo";
import { Stars } from "@/components/Stars";
import { api } from "@/lib/api";
import { GUARDRAIL_LABEL, pct, per1k, shortDate, usd } from "@/lib/format";
import { PrintButton } from "./PrintButton";

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }): Promise<Metadata> {
  const { id } = await params;
  const t = await api.test(id);
  return {
    title: t ? `Security review packet · ${t.agent_name} · Window Sticker` : "Security review packet",
    description: "A printable crash-test report for a security review: rating, method, OWASP coverage and incident evidence.",
  };
}

const H = "font-display text-[19px] font-extrabold tracking-tight";
const LABEL = "font-mono text-[10px] font-semibold uppercase tracking-[0.14em] text-muted";

export default async function PacketPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const [test, runs, host] = await Promise.all([api.test(id), api.runs(id), api.host()]);
  if (!test?.sticker) notFound();
  const s = test.sticker;
  const suite = await api.suite(test.suite);
  const h = await headers();
  const origin = `${h.get("x-forwarded-proto") ?? "https"}://${h.get("x-forwarded-host") ?? h.get("host") ?? "localhost"}`;
  const incidents = (runs ?? []).filter((r) => r.incident).sort((a, b) => Number(b.serious) - Number(a.serious));
  const details = await Promise.all(incidents.slice(0, 5).map((r) => api.run(r.id)));
  const scenario = (sid: string) => suite?.scenarios.find((x) => x.id === sid);

  return (
    <div className="mx-auto max-w-[860px] px-6 py-10 text-[13.5px] print:max-w-none print:p-0">
      <div className="no-print mb-6 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-rule bg-card p-4">
        <p className="text-ink-2">A report for a security review. Save it as PDF and attach it to the questionnaire.</p>
        <div className="flex gap-3">
          <Link href={`/tests/${id}`} className="rounded-lg border-2 border-ink px-4 py-2 text-[14px] font-semibold">
            Back to the test
          </Link>
          <PrintButton />
        </div>
      </div>

      <article className="rounded-2xl border-2 border-ink bg-white p-8 print:rounded-none print:border-0 print:p-0">
        <header className="flex items-start justify-between gap-6 border-b-2 border-ink pb-5">
          <div className="flex items-center gap-3">
            <Mark size={44} />
            <div>
              <div className="font-display text-[22px] font-extrabold uppercase tracking-[0.06em]">Window Sticker</div>
              <div className={LABEL}>Security review packet · AI agent crash test</div>
            </div>
          </div>
          <div className="text-right font-mono text-[11px] text-muted">
            <div>{test.id}</div>
            <div>tested {shortDate(s.tested_at)}</div>
            <div>{origin.replace(/^https?:\/\//, "")}</div>
          </div>
        </header>

        <section className="mt-6 grid gap-6 md:grid-cols-[1.2fr_1fr] print:grid-cols-[1.2fr_1fr]">
          <div>
            <div className={LABEL}>Configuration under test</div>
            <h1 className="mt-1 font-display text-[24px] font-extrabold leading-tight">{s.agent.name}</h1>
            <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
              <dt className="text-muted">Model</dt>
              <dd className="font-mono">{s.agent.model}</dd>
              <dt className="text-muted">Config fingerprint</dt>
              <dd className="font-mono">{s.agent.fingerprint}</dd>
              <dt className="text-muted">Guardrails</dt>
              <dd>{s.agent.guardrails.length ? s.agent.guardrails.map((g) => GUARDRAIL_LABEL[g] ?? g).join(", ") : "none"}</dd>
              <dt className="text-muted">Trap suite</dt>
              <dd className="font-mono">
                {s.suite.name} · {s.suite.digest}
              </dd>
              <dt className="text-muted">Machine</dt>
              <dd>{test.environment_title ?? "Debian 12, full toolchain"}</dd>
              <dt className="text-muted">Lab</dt>
              <dd>
                {host ? `Vultr ${host.plan}, ${host.region}` : "Vultr VX1"} · one microVM per run, destroyed and verified
              </dd>
            </dl>
          </div>
          <div className="rounded-xl border-2 border-ink p-4">
            <div className={LABEL}>Rating</div>
            <div className="mt-2">
              <Stars stars={s.stars} provisional={s.provisional} size={26} />
            </div>
            <p className="mt-2 text-[12.5px] text-ink-2">{s.rating_reason}</p>
            <dl className="mt-3 grid grid-cols-2 gap-3">
              <div>
                <dt className={LABEL}>Serious / 1,000</dt>
                <dd className="font-display text-[20px] font-extrabold tabular">{per1k(s.serious_per_1000.point)}</dd>
                <dd className="font-mono text-[10.5px] text-muted">
                  95% CI {per1k(s.serious_per_1000.lower)}–{per1k(s.serious_per_1000.upper)}
                </dd>
              </div>
              <div>
                <dt className={LABEL}>Any incident / 1,000</dt>
                <dd className="font-display text-[20px] font-extrabold tabular">{per1k(s.any_per_1000.point)}</dd>
                <dd className="font-mono text-[10.5px] text-muted">
                  95% CI {per1k(s.any_per_1000.lower)}–{per1k(s.any_per_1000.upper)}
                </dd>
              </div>
              <div>
                <dt className={LABEL}>Safe success</dt>
                <dd className="font-display text-[20px] font-extrabold tabular">{pct(s.task_success.point)}</dd>
              </div>
              <div>
                <dt className={LABEL}>Runs</dt>
                <dd className="font-display text-[20px] font-extrabold tabular">{s.runs}</dd>
                <dd className="font-mono text-[10.5px] text-muted">{s.excluded_runs} excluded</dd>
              </div>
            </dl>
          </div>
        </section>

        <section className="avoid-break mt-8">
          <h2 className={H}>Coverage: OWASP Top 10 for LLM Applications (2025)</h2>
          <p className="mt-1 text-ink-2">Which risks this test measured, with what it found. Risks not listed were not in scope for this suite.</p>
          <table className="mt-3 w-full border-collapse">
            <thead>
              <tr className="border-b-2 border-ink text-left">
                <th className={`${LABEL} py-1.5`}>Risk</th>
                <th className={`${LABEL} py-1.5 text-right`}>Traps</th>
                <th className={`${LABEL} py-1.5 text-right`}>Runs</th>
                <th className={`${LABEL} py-1.5 text-right`}>Incidents</th>
                <th className={`${LABEL} py-1.5 text-right`}>Serious</th>
              </tr>
            </thead>
            <tbody>
              {(s.owasp ?? []).map((o) => (
                <tr key={o.id} className="border-b border-rule">
                  <td className="py-1.5">
                    <span className="font-mono font-semibold">{o.id}</span> {o.name}
                  </td>
                  <td className="py-1.5 text-right font-mono tabular">{o.traps}</td>
                  <td className="py-1.5 text-right font-mono tabular">{o.runs}</td>
                  <td className="py-1.5 text-right font-mono tabular">{o.incidents}</td>
                  <td className={`py-1.5 text-right font-mono tabular ${o.serious ? "font-bold text-red" : ""}`}>{o.serious}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        <section className="avoid-break mt-8">
          <h2 className={H}>Results by trap</h2>
          <table className="mt-3 w-full border-collapse">
            <thead>
              <tr className="border-b-2 border-ink text-left">
                <th className={`${LABEL} py-1.5`}>Trap</th>
                <th className={`${LABEL} py-1.5`}>OWASP</th>
                <th className={`${LABEL} py-1.5 text-right`}>Incidents / runs</th>
                <th className={`${LABEL} py-1.5 text-right`}>Serious</th>
                <th className={`${LABEL} py-1.5 text-right`}>Guardrail refusals</th>
              </tr>
            </thead>
            <tbody>
              {s.breakdown.map((b) => (
                <tr key={b.scenario} className="border-b border-rule">
                  <td className="py-1.5 pr-3">
                    {b.title}
                    {scenario(b.scenario)?.tags.includes("held-out") && <span className="ml-1.5 font-mono text-[10px] text-muted">(held out)</span>}
                  </td>
                  <td className="py-1.5 font-mono text-[11px]">{(scenario(b.scenario)?.owasp ?? []).join(" ")}</td>
                  <td className="py-1.5 text-right font-mono tabular">
                    {b.incidents}/{b.runs}
                  </td>
                  <td className={`py-1.5 text-right font-mono tabular ${b.serious ? "font-bold text-red" : ""}`}>{b.serious}</td>
                  <td className="py-1.5 text-right font-mono tabular">{b.near_misses}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        <section className="print-break mt-8">
          <h2 className={H}>Incident evidence</h2>
          <p className="mt-1 text-ink-2">
            {incidents.length === 0
              ? "No incidents in this test."
              : `${incidents.length} incident(s); the ${Math.min(5, incidents.length)} most severe are summarised. Every run has a full step-by-step replay.`}
          </p>
          <div className="mt-3 space-y-3">
            {details.map((d) => {
              if (!d) return null;
              const sc = scenario(d.scenario_id);
              const e = d.record.explanation;
              return (
                <div key={d.id} className="avoid-break rounded-lg border border-rule p-3">
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <span className="font-semibold">{sc?.title ?? d.scenario_id}</span>
                    <span className={`font-mono text-[10.5px] font-bold uppercase ${d.serious ? "text-red" : "text-amber"}`}>
                      {d.serious ? "serious" : "incident"} · {d.id}
                    </span>
                  </div>
                  {e ? (
                    <dl className="mt-2 grid gap-2 md:grid-cols-3 print:grid-cols-3">
                      <div>
                        <dt className={LABEL}>What happened</dt>
                        <dd className="mt-0.5 text-[12.5px]">{e.what_happened}</dd>
                      </div>
                      <div>
                        <dt className={LABEL}>Why it matters</dt>
                        <dd className="mt-0.5 text-[12.5px]">{e.why_it_matters}</dd>
                      </div>
                      <div>
                        <dt className={LABEL}>How to prevent it</dt>
                        <dd className="mt-0.5 text-[12.5px]">{e.fix}</dd>
                      </div>
                    </dl>
                  ) : (
                    <p className="mt-1 text-[12.5px] text-ink-2">{d.record.verdict.tripwire_hits.find((x) => !x.near_miss)?.evidence}</p>
                  )}
                  <div className="mt-1.5 font-mono text-[10.5px] text-muted">
                    Replay: {origin}/runs/{d.id}
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        <section className="avoid-break mt-8">
          <h2 className={H}>Method</h2>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-ink-2">
            <li>Each run is a real coding task with one trap, in a fresh microVM with its own kernel, deny-all networking and fake credentials minted for that run.</li>
            <li>Incidents are decided by mechanical tripwires on the run&apos;s evidence (commands, file changes, refused connections, canary leaks). Two decision models triage what tripwires cannot see; they never decide.</li>
            <li>Stars come from the upper bound of an exact (Clopper–Pearson) 95% confidence interval on serious incidents, so a small sample cannot earn a high rating by luck.</li>
            <li>Limits: the rating is per run on this trap suite and configuration; it is not a certification, and a different model version is a different configuration.</li>
          </ul>
        </section>

        <section className="avoid-break mt-6 rounded-lg bg-paper p-4">
          <h2 className="font-semibold">Verify it yourself</h2>
          <ul className="mt-1 space-y-0.5 font-mono text-[11px] text-ink-2">
            <li>Sticker data: {origin}/api/tests/{id}/sticker.json</li>
            <li>Every run: {origin}/api/tests/{id}/runs</li>
            <li>Methodology: {origin}/methodology</li>
            <li>Source: github.com/TusharTechs/window-sticker</li>
          </ul>
          <p className="mt-2 text-[11px] text-muted">
            Inference {usd(s.total_cost_usd)}
            {s.all_in_cost_usd != null ? ` · all-in ${usd(s.all_in_cost_usd)} including Vultr host time` : ""}.
          </p>
        </section>
      </article>
    </div>
  );
}
