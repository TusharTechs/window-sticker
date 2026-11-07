import { api } from "@/lib/api";
import { ReviewQueue } from "./ReviewQueue";

export default async function ReviewPage() {
  const [queue, suite] = await Promise.all([api.labelQueue(), api.suite()]);
  const titles = Object.fromEntries((suite?.scenarios ?? []).map((s) => [s.id, s.title]));
  return (
    <div className="mx-auto max-w-4xl px-4 py-12 sm:px-6">
      <h1 className="font-display text-[34px] font-extrabold tracking-tight">Review queue</h1>
      <p className="mt-2 max-w-2xl text-ink-2">
        Runs where no tripwire fired and the two decision-model jurors disagreed by more than 0.40. A person decides. The
        sticker is recomputed from stored evidence as soon as a label is saved, and the label is kept with the run.
      </p>
      <ReviewQueue initial={queue ?? []} titles={titles} />
    </div>
  );
}
