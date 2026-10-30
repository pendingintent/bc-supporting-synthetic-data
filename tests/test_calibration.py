"""Statistical calibration: do the generated data reproduce the published trial results?

These run the generator over several seeds, so they are marked slow. The seed-0 data that is
committed is a single draw; pooling seeds shows whether the generator itself is calibrated.
"""

import pandas as pd
import pytest

from src import cdisc_generation_functions as gen

pytestmark = pytest.mark.slow

SEEDS = range(10)
ARMS = ("Treatment", "Placebo")
PFS_TARGET_DAYS = {"Treatment": 314, "Placebo": 155}  # 10.3 and 5.1 months, as in validate.py
PFS_POOLED_TOLERANCE = 0.20  # same tolerance the validator applies to one draw
PFS_PER_SEED_TOLERANCE = 0.25  # a single 100-subject arm is noisier than the pooled median
ORR_TARGET = {"Treatment": 0.182, "Placebo": 0.123}  # cited in the _TUMOUR comment in the generator
ORR_TOLERANCE = 0.03


@pytest.fixture(scope="module")
def runs():
    """Per-seed, per-arm PFS median (days, of ADTTE.AVAL as validate.py computes it) and ORR."""
    rows = []
    for seed in SEEDS:
        frames = gen.generate_all(seed=seed)
        adtte, adsl = frames["ADTTE"], frames["ADSL"]
        for arm in ARMS:
            aval = pd.to_numeric(adtte.loc[adtte["TRT01A"] == arm, "AVAL"])
            best = adsl.loc[adsl["TRT01A"] == arm, "BESTRESP"]
            rows.append({"seed": seed, "arm": arm, "pfs": aval.median(), "orr": best.isin(["CR", "PR"]).mean()})
    return pd.DataFrame(rows)


def pooled(runs, column):
    return runs.groupby("arm")[column].mean()


@pytest.mark.parametrize("arm", ARMS)
def test_pooled_pfs_median_within_tolerance_of_published(runs, arm):
    target = PFS_TARGET_DAYS[arm]
    observed = pooled(runs, "pfs")[arm]
    assert abs(observed - target) <= target * PFS_POOLED_TOLERANCE, f"{arm}: {observed:.0f}d vs {target}d"


@pytest.mark.parametrize("arm", ARMS)
def test_every_seed_pfs_median_within_tolerance_of_published(runs, arm):
    target = PFS_TARGET_DAYS[arm]
    arm_runs = runs[runs["arm"] == arm]
    off = arm_runs[(arm_runs["pfs"] - target).abs() > target * PFS_PER_SEED_TOLERANCE]
    assert off.empty, f"{arm}: seeds outside ±{PFS_PER_SEED_TOLERANCE:.0%}: {dict(zip(off['seed'], off['pfs']))}"


def test_treatment_pfs_exceeds_placebo_in_every_seed(runs):
    wide = runs.pivot(index="seed", columns="arm", values="pfs")
    assert (wide["Treatment"] > wide["Placebo"]).all()


def test_treatment_response_rate_exceeds_placebo(runs):
    orr = pooled(runs, "orr")
    assert orr["Treatment"] > orr["Placebo"]


@pytest.mark.parametrize("arm", ARMS)
def test_pooled_response_rate_matches_published(runs, arm):
    observed = pooled(runs, "orr")[arm]
    assert abs(observed - ORR_TARGET[arm]) <= ORR_TOLERANCE, f"{arm}: {observed:.1%} vs {ORR_TARGET[arm]:.1%}"
