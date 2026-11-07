import pytest

from windowsticker.stats import clopper_pearson, compare_rates, estimate_rate, rate
from windowsticker.stats.rating import MIN_TRIALS_FOR_RATING, runs_needed_for, stars_for_upper_bound


def test_clopper_pearson_zero_events_upper_bound():
    lo, hi = clopper_pearson(0, 100)
    assert lo == 0.0
    assert hi == pytest.approx(0.0362, abs=1e-4)  # the "rule of three" neighbourhood


def test_clopper_pearson_known_value():
    lo, hi = clopper_pearson(6, 100)
    assert lo == pytest.approx(0.0223, abs=1e-3)
    assert hi == pytest.approx(0.1260, abs=1e-3)


def test_clopper_pearson_all_events():
    lo, hi = clopper_pearson(10, 10)
    assert hi == 1.0
    assert lo == pytest.approx(0.6915, abs=1e-3)


@pytest.mark.parametrize("k,n", [(-1, 10), (11, 10), (0, 0)])
def test_clopper_pearson_rejects_bad_input(k, n):
    with pytest.raises(ValueError):
        clopper_pearson(k, n)


def test_describe_uses_per_thousand():
    assert estimate_rate(6, 100).describe() == "60 per 1,000 runs (95% CI 22–126, n=100)"


def test_small_samples_are_provisional():
    r = rate(0, 0, 10, MIN_TRIALS_FOR_RATING - 1)
    assert r.provisional and r.stars == 0 and r.label == "Provisional"


def test_stars_come_from_upper_bound_not_point_estimate():
    # 0 incidents in 40 runs: point estimate 0%, upper bound ~8.8% -> 3 stars, not 5.
    r = rate(0, 0, 30, 40)
    assert r.stars == 3
    assert "3" not in r.label or r.label.count("★") == 3


def test_many_clean_runs_earn_five_stars():
    n = runs_needed_for(5)
    assert rate(0, 0, n, n).stars == 5
    assert rate(0, 0, n - 1, n - 1).stars == 4


def test_threshold_edges():
    assert stars_for_upper_bound(0.02) == 5
    assert stars_for_upper_bound(0.0201) == 4
    assert stars_for_upper_bound(0.5) == 1


def test_rate_validates_counts():
    with pytest.raises(ValueError):
        rate(3, 2, 0, 10)


def test_ab_significant_improvement():
    res = compare_rates(30, 100, 5, 100)
    assert res.significant
    assert res.absolute_change < 0
    assert "Fewer incidents" in res.verdict


def test_ab_not_significant_with_small_samples():
    res = compare_rates(3, 16, 1, 16)
    assert not res.significant
    assert res.verdict.startswith("Not yet significant")
