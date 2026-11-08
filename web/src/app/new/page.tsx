import type { Metadata } from "next";
import { api } from "@/lib/api";
import { NewTestForm } from "./NewTestForm";

export const metadata: Metadata = {
  title: "Rate your agent · Window Sticker",
  description: "Start a crash test of your own agent configuration.",
};

export default async function NewTestPage() {
  const [suite, methodology] = await Promise.all([api.suite(), api.methodology()]);
  return (
    <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
      <h1 className="font-display text-[34px] font-extrabold tracking-tight">Crash-test an agent</h1>
      <p className="mb-8 mt-2 max-w-2xl text-ink-2">
        Describe the agent: its model, prompt and guardrails. That combination is what gets rated. Change any part and
        it is a different agent with its own sticker.
      </p>
      <NewTestForm scenarios={suite?.scenarios ?? []} methodology={methodology} />
    </div>
  );
}
