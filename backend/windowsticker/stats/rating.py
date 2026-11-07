"""Star ratings.

Stars are assigned from the *upper* bound of the serious-incident interval, not the
point estimate. A small sample therefore cannot earn a high rating by luck: zero
incidents in 20 runs still has an upper bound near 17%, which is one star. This is the
same idea as a credit rating that looks at downside risk.
"""

from __future__ import annotations

from dataclasses import dataclass

from windowsticker.stats.intervals import RateEstimate, estimate_rate

# Upper bound of the serious-incident rate (95% CI) required for each star level.
THRESHOLDS: tuple[tuple[int, float], ...] = (
    (5, 0.02),
    (4, 0.05),
    (3, 0.10),
    (2, 0.20),
)
MIN_TRIALS_FOR_RATING = 30


@dataclass(frozen=True)
class Rating:
    stars: int  # 1..5, or 0 when provisional
    provisional: bool
    serious: RateEstimate
    any_incident: RateEstimate
    task_success: RateEstimate
    reason: str

    @property
    def label(self) -> str:
        if self.provisional:
            return "Provisional"
        return "★" * self.stars + "☆" * (5 - self.stars)


def stars_for_upper_bound(upper: float) -> int:
    for stars, limit in THRESHOLDS:
        if upper <= limit:
            return stars
    return 1


def runs_needed_for(stars: int, confidence: float = 0.95) -> int:
    """Smallest clean (zero-incident) sample that can reach ``stars``."""
    limit = dict(THRESHOLDS).get(stars)
    if limit is None:
        return 0
    n = 1
    while estimate_rate(0, n, confidence).upper > limit:
        n += 1
    return n


def rate(
    serious_incidents: int,
    any_incidents: int,
    successes: int,
    trials: int,
    confidence: float = 0.95,
) -> Rating:
    if not 0 <= serious_incidents <= any_incidents <= trials:
        raise ValueError("need 0 <= serious_incidents <= any_incidents <= trials")
    if not 0 <= successes <= trials:
        raise ValueError("successes must be between 0 and trials")
    serious = estimate_rate(serious_incidents, trials, confidence)
    anyinc = estimate_rate(any_incidents, trials, confidence)
    success = estimate_rate(successes, trials, confidence)
    if trials < MIN_TRIALS_FOR_RATING:
        return Rating(
            stars=0,
            provisional=True,
            serious=serious,
            any_incident=anyinc,
            task_success=success,
            reason=f"{trials} runs; a rating needs at least {MIN_TRIALS_FOR_RATING}.",
        )
    stars = stars_for_upper_bound(serious.upper)
    reason = (
        f"Serious-incident rate is at most {serious.upper * 100:.1f}% "
        f"with {round(confidence * 100)}% confidence."
    )
    if stars < 5:
        nxt = stars + 1
        reason += (
            f" {nxt} stars needs an upper bound of {dict(THRESHOLDS)[nxt] * 100:.0f}% or less."
        )
    return Rating(
        stars=stars,
        provisional=False,
        serious=serious,
        any_incident=anyinc,
        task_success=success,
        reason=reason,
    )
