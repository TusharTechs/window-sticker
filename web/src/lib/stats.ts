/** Small exact statistics used to group leaderboard rows honestly. */

function logFactorial(n: number): number {
  let s = 0;
  for (let i = 2; i <= n; i++) s += Math.log(i);
  return s;
}

function hypergeom(a: number, b: number, c: number, d: number): number {
  const n = a + b + c + d;
  return Math.exp(
    logFactorial(a + b) + logFactorial(c + d) + logFactorial(a + c) + logFactorial(b + d) -
      (logFactorial(n) + logFactorial(a) + logFactorial(b) + logFactorial(c) + logFactorial(d)),
  );
}

/** Two-sided Fisher exact test on incidents k1/n1 vs k2/n2. */
export function fisherP(k1: number, n1: number, k2: number, n2: number): number {
  const row1 = n1;
  const col1 = k1 + k2;
  const total = n1 + n2;
  const pObs = hypergeom(k1, n1 - k1, k2, n2 - k2);
  let p = 0;
  for (let a = Math.max(0, col1 - (total - row1)); a <= Math.min(row1, col1); a++) {
    const pa = hypergeom(a, row1 - a, col1 - a, total - row1 - (col1 - a));
    if (pa <= pObs * (1 + 1e-7)) p += pa;
  }
  return Math.min(1, p);
}

/** Clean runs needed for each star level (95% Clopper–Pearson upper bound thresholds). */
const CLEAN_RUNS_FOR = [
  { stars: 5, runs: 183 },
  { stars: 4, runs: 72 },
  { stars: 3, runs: 36 },
  { stars: 2, runs: 17 },
];

/** The most stars a test of n runs can earn, even with zero incidents. */
export function maxStarsFor(n: number): number {
  if (n < 30) return 0;
  return CLEAN_RUNS_FOR.find((x) => n >= x.runs)?.stars ?? 1;
}

export function seriousCount(per1000: number, runs: number): number {
  return Math.round((per1000 * runs) / 1000);
}
