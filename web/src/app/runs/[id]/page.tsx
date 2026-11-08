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
  // "Justified" only means something if a juror thinks a destructive action happened.
  const destructive = Math.max(0, ...jury.filter((j) => j.question === "destructive_action").map((j) => j.probability ?? 0));
  const questions = Object.keys(QUESTION_LABEL).filter(
    (q) => jury.some((j) => j.question === q) && (q !== "destructive_justified" || destructive >= 0.5),
  );
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
  const test = await api.test(run.test_id);
  const [suite, host] = await Promise.all([api.suite(test?.suite ?? "v2"), api.host()]);
  const r = run.record;
  const scenario = suite?.scenarios.find((s) => s.id === r.scenario_id);
  const v = r.verdict;
  const egress = r.evidence.egress;
  const blocked = egress.filter((e) => !e.allowed);
  const unplaced = v.tripwire_hits.filter((h) => h.step == null);
  const refused = r.evidence.steps.filter((s) => s.blocked_by);
  const leaked = v.tripwire_hits.some((h) => !h.near_miss && h.kind === "canary_leak");
  const stopped: { what: string; how: string }[] = [];
  const blockedHosts = [...new Set(blocked.map((e) => e.host))];
  if (blockedHosts.length)
    stopped.push({
      what: `${blocked.length} outbound connection${blocked.length === 1 ? "" : "s"} to ${blockedHosts.slice(0, 3).join(", ")}${blockedHosts.length > 3 ? " and more" : ""}`,
      how: "Refused by the Egress Warden. Nothing left the microVM.",
    });
  if (leaked)
    stopped.push({
      what: "A credential the agent handled",
      how: "It was a canary minted for this run only. It unlocks nothing and is scrubbed from this page.",
    });
  for (const c of r.evidence.caps)
    stopped.push({ what: c.kind.replace(/_/g, " "), how: c.detail || "Held by the microVM's resource caps." });
  if (refused.length)
    stopped.push({
      what: `${refused.length} action${refused.length === 1 ? "" : "s"} the agent tried`,
      how: `Refused by its own guardrails: ${[...new Set(refused.map((s) => s.blocked_by))].join(", ")}.`,
    });
  stopped.push({
    what: "Everything else it touched",
    how: r.teardown_verified
      ? "Lived in a microVM that was destroyed after the run, with its absence verified."
      : "Lived in a microVM that was destroyed after the run.",
  });

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

      <div className="mt-8 grid gap-8 lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
        <div className="min-w-0">
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

        <aside className="min-w-0 space-y-6">
          {(v.incident || blocked.length > 0 || refused.length > 0) && (
            <section className="rounded-xl border-2 border-ink bg-card p-5 shadow-[4px_4px_0_0_var(--yellow)]">
              <h2 className="font-semibold">What the lab stopped</h2>
              <p className="mt-1 text-[13px] text-ink-2">
                {v.incident
                  ? "The agent did something dangerous. In a real repository this would have been the damage; here is why it was not."
                  : "Nothing dangerous got through. This is what the agent or the lab held back."}
              </p>
              <ul className="mt-3 space-y-2.5">
                {stopped.map((x, i) => (
                  <li key={i} className="text-[13.5px]">
                    <span className="font-semibold">{x.what}</span>
                    <span className="block text-ink-2">{x.how}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}

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
                    <span className="break-words text-ink-2">{scrub(h.evidence, r.evidence.canaries).slice(0, 160)}</span>
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

          {r.regrades && r.regrades.length > 0 && (
            <section className="rounded-xl border border-rule bg-card p-5">
              <h2 className="font-semibold">Re-graded</h2>
              <p className="mt-1 text-[13px] text-ink-2">
                The evidence never changes; graders improve. This run was re-graded from its stored evidence after a
                tripwire was fixed. The jury&apos;s answers were reused, so nothing was re-run.
              </p>
              <ul className="mt-3 space-y-1.5 text-[13px]">
                {r.regrades.map((g, i) => (
                  <li key={i}>
                    <span className="font-mono text-[11px] text-muted">{g.at.slice(0, 16).replace("T", " ")} UTC</span>{" "}
                    was {g.previous_verdict.incident ? "an incident" : "no incident"}
                    {g.previous_verdict.incident !== v.incident && <>, now {v.incident ? "an incident" : "no incident"}</>}
                  </li>
                ))}
              </ul>
            </section>
          )}

          {run.labels && run.labels.length > 0 && (
            <section className="rounded-xl border border-rule bg-card p-5">
              <h2 className="font-semibold">Human review</h2>
              <p className="mt-1 text-[13px] text-ink-2">Every label on this run, oldest first. The latest one counts.</p>
              <ul className="mt-3 space-y-2 text-[13px]">
                {run.labels.map((l, i) => (
                  <li key={i} className="border-t border-rule pt-2 first:border-0 first:pt-0">
                    <span className={`font-semibold ${l.incident ? "text-red" : "text-green"}`}>
                      {l.incident ? "Incident" : "No incident"}
                    </span>{" "}
                    <span className="font-mono text-[11px] text-muted">{l.at.slice(0, 16).replace("T", " ")} UTC</span>
                    {l.note && <span className="block text-ink-2">{l.note}</span>}
                  </li>
                ))}
              </ul>
            </section>
          )}

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
              {r.evidence.final.claimed_success == null
                ? "nothing: it never reported back, so the hidden check alone decides"
                : r.evidence.final.claimed_success
                  ? "success"
                  : "it did not succeed"}
            </p>
          </section>

          <section className="rounded-xl border border-rule bg-card p-5">
            <h2 className="font-semibold">Where it ran</h2>
            <dl className="mt-2 grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1.5 text-[13px]">
              <dt className="text-muted">Host</dt>
              <dd className="font-mono text-[12px]">
                {host ? `${host.provider} ${host.plan} · ${host.region}` : r.host_id}
              </dd>
              <dt className="text-muted">Isolation</dt>
              <dd>{host?.runtime ?? "microVM"}, sandbox {r.sandbox_name}</dd>
              <dt className="text-muted">Timings</dt>
              <dd className="font-mono text-[12px] tabular">
                boot {seconds(r.timings.boot_s)} · agent {seconds(r.timings.agent_s)} · teardown{" "}
                {seconds(r.timings.teardown_s)}
              </dd>
              <dt className="text-muted">Model</dt>
              <dd className="font-mono text-[12px]">{r.model}</dd>
              <dt className="text-muted">Cost</dt>
              <dd className="font-mono text-[12px] tabular">
                agent {usd(r.agent_usage.cost_usd)} · jury {usd(r.jury_usage.cost_usd)}
              </dd>
            </dl>
          </section>
        </aside>
      </div>
    </div>
  );
}
