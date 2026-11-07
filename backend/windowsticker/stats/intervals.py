"""Exact binomial confidence intervals.

Incident rates come from small samples (tens to hundreds of runs), where the normal
approximation is badly wrong near zero. We use the exact Clopper–Pearson interval,
which is conservative: its coverage is at least the nominal level for every n.
"""

from __future__ import annotations

from dataclasses import dataclass

from scipy.stats import beta


def clopper_pearson(k: int, n: int, confidence: float = 0.95) -> tuple[float, float]:
    """Exact two-sided interval for a binomial proportion with ``k`` events in ``n`` trials."""
    if n <= 0:
        raise ValueError("n must be positive")
    if not 0 <= k <= n:
        raise ValueError("k must be between 0 and n")
    if not 0 < confidence < 1:
        raise ValueError("confidence must be in (0, 1)")
    alpha = 1 - confidence
    lo = 0.0 if k == 0 else float(beta.ppf(alpha / 2, k, n - k + 1))
    hi = 1.0 if k == n else float(beta.ppf(1 - alpha / 2, k + 1, n - k))
    return lo, hi


@dataclass(frozen=True)
class RateEstimate:
    events: int
    trials: int
    point: float
    lower: float
    upper: float
    confidence: float

    def per_thousand(self) -> tuple[float, float, float]:
        return (self.point * 1000, self.lower * 1000, self.upper * 1000)

    def describe(self) -> str:
        p, lo, hi = self.per_thousand()
        pct = round(self.confidence * 100)
        return f"{p:.0f} per 1,000 runs ({pct}% CI {lo:.0f}–{hi:.0f}, n={self.trials})"


def estimate_rate(k: int, n: int, confidence: float = 0.95) -> RateEstimate:
    lo, hi = clopper_pearson(k, n, confidence)
    return RateEstimate(events=k, trials=n, point=k / n, lower=lo, upper=hi, confidence=confidence)
