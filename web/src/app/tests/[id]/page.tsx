import Link from "next/link";
import { headers } from "next/headers";
import { notFound } from "next/navigation";
import { LiveGrid } from "@/components/LiveGrid";
import { StickerCard } from "@/components/StickerCard";
import { api } from "@/lib/api";

export default async function TestPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const [test, runs] = await Promise.all([api.test(id), api.runs(id)]);
  if (!test) notFound();
  const suite = await api.suite(test.suite);
  const h = await headers();
  const origin = `${h.get("x-forwarded-proto") ?? "https"}://${h.get("x-forwarded-host") ?? h.get("host") ?? "localhost"}`;
  const scenarios = Object.fromEntries(
    (suite?.scenarios ?? []).map((s) => [s.id, { category: s.category, title: s.title }]),
  );

  return (
    <>
      <LiveGrid test={test} initialRuns={runs ?? []} scenarios={scenarios} />
      <section className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
        {test.sticker ? (
          <div className="grid gap-10 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
            <StickerCard s={test.sticker} />
            <aside className="space-y-6">
              <div className="rounded-xl border border-rule bg-card p-5">
                <h2 className="font-semibold">Use this sticker</h2>
                <p className="mt-1 text-[14px] text-ink-2">Embed the badge in a README. It updates if runs are re-labelled.</p>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={`/api/tests/${test.id}/badge.svg`} alt="Crash-test badge" className="mt-4 h-5" />
                <pre className="mt-3 overflow-x-auto rounded-md bg-paper-2 p-3 font-mono text-[11.5px]">
                  {`[![agent crash test](${origin}/api/tests/${test.id}/badge.svg)](${origin}/tests/${test.id})`}
                </pre>
                <div className="mt-4 flex flex-wrap gap-3 text-[14px] font-semibold">
                  <a className="underline decoration-yellow decoration-2 underline-offset-4" href={`/api/tests/${test.id}/sticker.svg`}>
                    Download SVG
                  </a>
                  <a className="underline decoration-yellow decoration-2 underline-offset-4" href={`/api/tests/${test.id}/sticker.json`}>
                    Raw data
                  </a>
                </div>
              </div>
              <div className="rounded-xl border border-rule bg-card p-5">
                <h2 className="font-semibold">How to read it</h2>
                <ul className="mt-2 list-disc space-y-1.5 pl-5 text-[14px] text-ink-2">
                  <li>Stars come from the worst plausible serious-incident rate (the upper end of the interval), not the average.</li>
                  <li>An incident is something the lab had to stop. Actions the agent&apos;s own guardrails refused count as near misses.</li>
                  <li>Click any tile to replay that run step by step.</li>
                </ul>
                <Link href="/methodology" className="mt-3 inline-block text-[14px] font-semibold underline decoration-yellow decoration-2 underline-offset-4">
                  Methodology
                </Link>
              </div>
            </aside>
          </div>
        ) : (
          <p className="text-ink-2">The sticker appears as soon as the first run is graded.</p>
        )}
      </section>
    </>
  );
}
