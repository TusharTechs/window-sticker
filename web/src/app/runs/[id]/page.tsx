import Link from "next/link";
import { notFound } from "next/navigation";
import { api } from "@/lib/api";
import { FAILURE_LABEL, TRAP_TAG, seconds, usd } from "@/lib/format";
import type { JuryAnswer, RunRecord, Step, TripwireHit } from "@/lib/types";

const SEV_STYLE: Record<TripwireHit["severity"], string> = {
  critical: "bg-red text-white",
  high: "bg-red-soft text-red",
  medium: "bg-[#fdf0d5] text-amber",
  low: "bg-paper-2 text-ink-2",
};

const QUESTION_LABEL: Record<string, string> = {
  followed_injected_instruction: "Followed an injected instruction",
  destructive_action: "Took a destructive action",
  destructive_justified: "Destructive action was justified",
  disclosed_secret: "Disclosed a secret",
  stayed_in_scope: "Stayed in scope",
  task_completed: "Completed the task",
};

function scrub(text: string, canaries: Record<string, string>): string {
  let out = text;
  for (const [name, value] of Object.entries(canaries)) out = out.split(value).join(`‹canary:${name}›`);
  return out;
}

function argText(step: Step): string {
  const a = step.tool_call?.arguments ?? {};
  if (typeof a.command === "string") return a.command;
  if (typeof a.path === "string") return a.path;
  if (typeof a.summary === "string") return a.summary;
  return JSON.stringify(a);
}

function JuryTable({ jury }: { jury: JuryAnswer[] }) {
  const models = [...new Set(jury.map((j) => j.model))];
  const questions = Object.keys(QUESTION_LABEL).filter((q) => jury.some((j) => j.question === q));
  if (!models.length) return <p className="text-[14px] text-muted">No jury for this run.</p>;
  return (
    <table className="w-full text-[13.5px]">
      <thead>
        <tr className="text-left font-mono text-[10.5px] uppercase tracking-[0.12em] text-muted">
          <th className="py-1.5 font-semibold">Question</th>
          {models.map((m) => (
            <th key={m} className="w-40 py-1.5 font-semibold">
              {m}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {questions.map((q) => (
          <tr key={q} className="border-t border-rule">
            <td className="py-2 pr-3">{QUESTION_LABEL[q]}</td>
            {models.map((m) => {
              const p = jury.find((j) => j.model === m && j.question === q)?.probability;
              return (
                <td key={m} className="py-2">
                  {p == null ? (
                    "n/a"
                  ) : (
                    <span className="flex items-center gap-2">
                      <span className="h-1.5 w-20 overflow-hidden rounded-full bg-paper-2">
                        <span className="block h-full bg-ink" style={{ width: `${p * 100}%` }} />
                      </span>
                      <span className="font-mono tabular">{p.toFixed(2)}</span>
                    </span>
                  )}
                </td>
              );
            })}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Timeline({ r }: { r: RunRecord }) {
  const hitsByStep = new Map<number, TripwireHit[]>();
  for (const h of r.verdict.tripwire_hits) {
    if (h.step == null) continue;
    hitsByStep.set(h.step, [...(hitsByStep.get(h.step) ?? []), h]);
  }
  const canaries = r.evidence.canaries;
  return (
    <ol className="relative space-y-3 border-l-2 border-rule pl-6">
      <li className="relative">
        <span className="absolute -left-[33px] top-1 grid h-4 w-4 place-items-center rounded-full border-2 border-ink bg-yellow" />
        <div className="font-mono text-[12px] text-muted">
          microVM {r.sandbox_name} booted on {r.host_id} in {seconds(r.timings.boot_s)}
        </div>
      </li>
      {r.evidence.steps.map((s) => {
        const hits = hitsByStep.get(s.index) ?? [];
        const bad = hits.some((h) => !h.near_miss);
        return (
          <li key={s.index} id={`step-${s.index}`} className="relative">
            <span
              className={`absolute -left-[31px] top-3 h-3 w-3 rounded-full border-2 ${bad ? "border-red bg-red" : s.blocked_by ? "border-amber bg-amber" : "border-ink bg-card"}`}
            />
            <div
              className={`rounded-lg border bg-card ${bad ? "border-red shadow-[0_0_0_3px_var(--red-soft)]" : "border-rule"}`}
            >
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-rule px-4 py-2">
                <span className="font-mono text-[12px]">
                  <span className="text-muted">step {s.index}</span>{" "}
                  <strong>{s.tool_call?.name ?? "message"}</strong>
                </span>
                <span className="flex items-center gap-2">
                  {s.blocked_by && (
                    <span className="rounded bg-[#fdf0d5] px-1.5 py-0.5 font-mono text-[10.5px] font-semibold text-amber">
                      refused by {s.blocked_by}
                    </span>
                  )}
                  <span className="font-mono text-[11px] text-muted tabular">{usd(s.cost_usd)}</span>
                </span>
              </div>
              {s.thought && (
                <p className="border-b border-rule px-4 py-2 text-[13.5px] italic text-ink-2">
                  {scrub(s.thought, canaries).slice(0, 600)}
                </p>
              )}
              <pre className="overflow-x-auto whitespace-pre-wrap break-words px-4 py-2.5 font-mono text-[12px] leading-relaxed">
                {s.tool_call?.name === "run_shell" ? "$ " : ""}
                {scrub(argText(s), canaries).slice(0, 1200)}
              </pre>
              {s.tool_result && s.tool_call?.name !== "finish" && (
                <details className="border-t border-rule">
                  <summary className="cursor-pointer px-4 py-1.5 font-mono text-[11px] text-muted">output</summary>
                  <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words bg-paper px-4 py-2 font-mono text-[11.5px] text-ink-2">
                    {scrub(s.tool_result, canaries).slice(0, 4000)}
                  </pre>
                </details>
              )}
              {hits.length > 0 && (
                <ul className="space-y-1 border-t border-rule px-4 py-2">
                  {hits.map((h, i) => (
                    <li key={i} className="flex items-start gap-2 text-[12.5px]">
                      <span className={`rounded px-1.5 py-0.5 font-mono text-[10px] font-bold uppercase ${SEV_STYLE[h.severity]}`}>
                        {h.near_miss ? "near miss" : h.severity}
                      </span>
                      <span>{scrub(h.evidence, canaries)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </li>
        );
      })}
      <li className="relative">
        <span className="absolute -left-[33px] top-1 grid h-4 w-4 place-items-center rounded-full border-2 border-ink bg-ink" />
        <div className="font-mono text-[12px] text-muted">
          microVM destroyed in {seconds(r.timings.teardown_s)} ·{" "}
          {r.teardown_verified ? <span className="text-green">absence verified</span> : <span className="text-red">not verified</span>}
        </div>
      </li>
    </ol>
  );
}

export default async function RunPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const run = await api.run(id);
  if (!run) notFound();
  const [suite] = await Promise.all([api.suite()]);
  const r = run.record;
  const scenario = suite?.scenarios.find((s) => s.id === r.scenario_id);
  const v = r.verdict;
  const egress = r.evidence.egress;
  const blocked = egress.filter((e) => !e.allowed);
  const unplaced = v.tripwire_hits.filter((h) => h.step == null);

  return (
    <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
      <Link href={`/tests/${run.test_id}`} className="font-mono text-[12px] text-muted hover:text-ink">
        ← {run.test_id}
      </Link>
      <div className="mt-3 flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="font-mono text-[11px] font-semibold uppercase tracking-[0.16em] text-muted">
            {scenario ? (TRAP_TAG[scenario.category] ?? scenario.category) : r.scenario_id} · crash replay
          </div>
          <h1 className="mt-1 font-display text-[30px] font-extrabold leading-tight">
            {scenario?.title ?? r.scenario_id}
          </h1>
          <p className="mt-1 font-mono text-[12px] text-muted">
            {r.run_id} · {r.model} · {r.evidence.steps.length} steps · {usd(r.cost_usd)}
          </p>
        </div>
        <div
          className={`rounded-xl border-2 px-5 py-3 text-right ${v.incident ? "border-red bg-red-soft" : "border-green bg-green-soft"}`}
        >
          <div className={`font-display text-[22px] font-extrabold ${v.incident ? "text-red" : "text-green"}`}>
            {v.incident ? "Incident" : "No incident"}
          </div>
          <div className="text-[13px] text-ink-2">
            {v.incident
              ? `${FAILURE_LABEL[v.primary_failure_mode] ?? v.primary_failure_mode} · found by ${v.incident_source}`
              : v.task_success
                ? "Task completed safely"
                : "Task not completed"}
          </div>
        </div>
      </div>

      <div className="mt-8 grid gap-8 lg:grid-cols-[1.5fr_1fr]">
        <div>
          <section className="mb-6 rounded-xl border border-rule bg-card p-5">
            <h2 className="font-mono text-[10.5px] font-semibold uppercase tracking-[0.14em] text-muted">The task the user gave</h2>
            <p className="mt-2 whitespace-pre-line text-[15px]">{scenario?.task}</p>
            {scenario && (
              <p className="mt-3 rounded-md bg-paper-2 px-3 py-2 text-[13.5px] text-ink-2">
                <strong>The trap:</strong> {scenario.summary}
              </p>
            )}
          </section>
          <Timeline r={r} />
        </div>

        <aside className="space-y-6">
          <section className="rounded-xl border border-rule bg-card p-5">
            <h2 className="font-semibold">Tripwires</h2>
            {v.tripwire_hits.length === 0 ? (
              <p className="mt-2 text-[14px] text-ink-2">None fired.</p>
            ) : (
              <ul className="mt-3 space-y-2">
                {v.tripwire_hits.slice(0, 12).map((h, i) => (
                  <li key={i} className="text-[13px]">
                    <span className={`mr-2 rounded px-1.5 py-0.5 font-mono text-[10px] font-bold uppercase ${SEV_STYLE[h.severity]}`}>
                      {h.near_miss ? "near miss" : h.severity}
                    </span>
                    {h.step != null ? (
                      <a href={`#step-${h.step}`} className="underline decoration-rule underline-offset-2">
                        step {h.step}
                      </a>
                    ) : null}{" "}
                    <span className="text-ink-2">{scrub(h.evidence, r.evidence.canaries).slice(0, 160)}</span>
                  </li>
                ))}
                {unplaced.length > 12 && <li className="text-[12px] text-muted">and {unplaced.length - 12} more</li>}
              </ul>
            )}
          </section>

          <section className="rounded-xl border border-rule bg-card p-5">
            <h2 className="font-semibold">Egress Warden</h2>
            <p className="mt-1 text-[13px] text-ink-2">
              {egress.length === 0
                ? "No outbound connection attempts."
                : `${egress.length} attempt(s), ${blocked.length} refused.`}
            </p>
            {egress.length > 0 && (
              <ul className="mt-3 space-y-1.5 font-mono text-[11.5px]">
                {egress.slice(0, 8).map((e, i) => (
                  <li key={i} className="flex gap-2">
                    <span className={e.allowed ? "text-green" : "text-red"}>{e.allowed ? "ALLOW" : "BLOCK"}</span>
                    <span className="truncate">
                      {e.protocol} {e.host}
                      {e.port ? `:${e.port}` : ""}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="rounded-xl border border-rule bg-card p-5">
            <h2 className="font-semibold">Decision-model jury</h2>
            <p className="mb-3 mt-1 text-[13px] text-ink-2">
              Vultr System One models read the scrubbed trace and answer with probabilities. They decide only what
              tripwires cannot.
            </p>
            <JuryTable jury={v.jury} />
          </section>

          <section className="rounded-xl border border-rule bg-card p-5">
            <h2 className="font-semibold">Hidden check</h2>
            <p className={`mt-1 text-[14px] font-semibold ${r.evidence.success_check?.passed ? "text-green" : "text-red"}`}>
              {r.evidence.success_check?.passed ? "Passed" : "Failed"}
            </p>
            <pre className="mt-2 overflow-x-auto rounded bg-paper-2 p-2 font-mono text-[11px]">
              {r.evidence.success_check?.command}
            </pre>
            <p className="mt-3 text-[13px] text-ink-2">
              Agent claimed:{" "}
              {r.evidence.final.claimed_success == null ? "nothing (never called finish)" : r.evidence.final.claimed_success ? "success" : "failure"}
            </p>
          </section>
        </aside>
      </div>
    </div>
  );
}
