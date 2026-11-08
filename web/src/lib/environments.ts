import type { Matrix, Suite } from "./types";

export type EnvFinding = {
  matrixId: string;
  env: string;
  trap: string;
  k: number;
  n: number;
  k0: number;
  n0: number;
  pAdjusted: number;
  serious: number;
};

/** The clearest measured case of a machine changing an agent's behaviour, if any. */
export function environmentFinding(matrices: Matrix[] | null, suite: Suite | null): EnvFinding | null {
  let best: EnvFinding | null = null;
  for (const m of matrices ?? []) {
    if (m.status !== "finished") continue;
    const base = m.tests.find((t) => t.environment === m.baseline)?.sticker;
    if (!base) continue;
    for (const t of m.tests) {
      const v = t.versus_baseline;
      if (!v?.changed || !t.sticker) continue;
      const p = Math.min(v.any_p_adjusted ?? v.any_p, v.serious_p_adjusted ?? v.serious_p);
      for (const b of t.sticker.breakdown) {
        const b0 = base.breakdown.find((x) => x.scenario === b.scenario);
        if (!b0 || !b.runs || !b0.runs) continue;
        const shift = b.incidents / b.runs - b0.incidents / b0.runs;
        if (shift > 0 && (!best || p < best.pAdjusted)) {
          best = {
            matrixId: m.matrix_id,
            env: t.environment_title ?? t.environment ?? "",
            trap: suite?.scenarios.find((s) => s.id === b.scenario)?.title ?? b.scenario,
            k: b.incidents,
            n: b.runs,
            k0: b0.incidents,
            n0: b0.runs,
            pAdjusted: p,
            serious: b.serious,
          };
        }
      }
    }
  }
  return best;
}
