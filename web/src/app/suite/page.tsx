import { api } from "@/lib/api";
import { TRAP_TAG } from "@/lib/format";

const SEV: Record<string, string> = {
  critical: "bg-red text-white",
  high: "bg-red-soft text-red",
  medium: "bg-[#fdf0d5] text-amber",
  low: "bg-paper-2 text-ink-2",
};

export default async function SuitePage() {
  const suite = await api.suite();
  if (!suite) return <p className="mx-auto max-w-6xl px-6 py-12">Suite unavailable.</p>;
  const heldOut = suite.scenarios.filter((s) => s.tags.includes("held-out")).length;
  return (
    <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
      <h1 className="font-display text-[34px] font-extrabold tracking-tight">Trap Suite {suite.name}</h1>
      <p className="mt-2 max-w-3xl text-ink-2">
        {suite.scenarios.length} scenarios{heldOut > 0 && `, ${heldOut} of them held out: written after the hardened guardrails were frozen`}. Each gives the agent a legitimate task and hides one trap in the workspace. Fake credentials
        are generated fresh for every run, the exfiltration host is a reserved <code className="font-mono">.test</code>{" "}
        domain that cannot resolve, and a hidden check (which the agent never sees) decides whether the task was really
        done. Digest <code className="font-mono">{suite.digest}</code> is printed on every sticker.
      </p>
      <ul className="mt-10 space-y-4">
        {suite.scenarios.map((s, i) => (
          <li key={s.id} className="rounded-xl border border-rule bg-card p-5">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-[12px] text-muted">{String(i + 1).padStart(2, "0")}</span>
              <span className="rounded bg-ink px-2 py-0.5 font-mono text-[11px] font-semibold tracking-wider text-yellow">
                {TRAP_TAG[s.category] ?? s.category}
              </span>
              <span className={`rounded px-2 py-0.5 font-mono text-[10.5px] font-bold uppercase ${SEV[s.severity]}`}>{s.severity}</span>
              <code className="ml-auto font-mono text-[11.5px] text-muted">{s.id}</code>
            </div>
            <h2 className="mt-2 text-[19px] font-bold">{s.title}</h2>
            <div className="mt-3 grid gap-4 md:grid-cols-2">
              <div>
                <div className="font-mono text-[10.5px] font-semibold uppercase tracking-[0.14em] text-muted">The task</div>
                <p className="mt-1 whitespace-pre-line text-[14px]">{s.task}</p>
              </div>
              <div>
                <div className="font-mono text-[10.5px] font-semibold uppercase tracking-[0.14em] text-muted">The trap</div>
                <p className="mt-1 text-[14px]">{s.summary}</p>
              </div>
            </div>
            <ul className="mt-4 flex flex-wrap gap-2">
              {s.tripwires.map((t) => (
                <li key={t.id} className="rounded-md border border-rule px-2 py-1 text-[12.5px]" title={t.description}>
                  <span className="font-mono text-[11px] text-muted">{t.kind}</span> · {t.description}
                </li>
              ))}
            </ul>
          </li>
        ))}
      </ul>
    </div>
  );
}
