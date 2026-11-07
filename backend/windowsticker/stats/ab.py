"""Before/after comparison of two incident rates (for example, with and without a guardrail)."""

from __future__ import annotations

from dataclasses import dataclass

from scipy.stats import fisher_exact

from windowsticker.stats.intervals import RateEstimate, estimate_rate


@dataclass(frozen=True)
class ABResult:
    a: RateEstimate
    b: RateEstimate
    p_value: float
    significant: bool
    alpha: float
    absolute_change: float  # b.point - a.point
    relative_risk: float | None  # b.point / a.point
    verdict: str


def compare_rates(k_a: int, n_a: int, k_b: int, n_b: int, alpha: float = 0.05) -> ABResult:
    """Two-sided Fisher exact test on a 2x2 table of incidents vs clean runs."""
    a = estimate_rate(k_a, n_a)
    b = estimate_rate(k_b, n_b)
    _, p = fisher_exact([[k_a, n_a - k_a], [k_b, n_b - k_b]], alternative="two-sided")
    p = float(p)
    significant = p < alpha
    change = b.point - a.point
    rr = (b.point / a.point) if a.point > 0 else None
    if not significant:
        verdict = f"Not yet significant (p={p:.3f}). Run more trials before claiming a difference."
    elif change < 0:
        verdict = f"Fewer incidents with B (p={p:.3g})."
    else:
        verdict = f"More incidents with B (p={p:.3g})."
    return ABResult(
        a=a,
        b=b,
        p_value=p,
        significant=significant,
        alpha=alpha,
        absolute_change=change,
        relative_risk=rr,
        verdict=verdict,
    )
