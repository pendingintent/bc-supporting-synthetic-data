import pandas as pd
import pytest

from src import cdisc_generation_functions as gen

FIRST, STEP = gen._FIRST_SCAN_DAY, gen._SCAN_INTERVAL_DAYS


@pytest.mark.parametrize(
    "day, expected",
    [
        (-5, FIRST),
        (0, FIRST),
        (FIRST, FIRST),
        (FIRST + 1, FIRST + STEP),
        (FIRST + STEP, FIRST + STEP),
        (FIRST + STEP + 1, FIRST + 2 * STEP),
    ],
)
def test_snap_to_scan_day(day, expected):
    assert gen._snap_to_scan_day(day) == expected


def test_study_day_has_no_day_zero():
    assert gen._study_day("2021-03-10", "2021-03-10") == 1
    assert gen._study_day("2021-03-11", "2021-03-10") == 2
    assert gen._study_day("2021-03-09", "2021-03-10") == -1


def test_study_day_ignores_time_component():
    assert gen._study_day("2021-03-11T08:00:00", "2021-03-10") == 2


@pytest.mark.parametrize("value", [None, pd.NaT])
def test_fmt_missing_is_empty_string(value):
    assert gen._fmt(value) == ""


def test_fmt_iso_date():
    assert gen._fmt(pd.Timestamp("2021-03-10 14:30")) == "2021-03-10"
    assert gen._fmt("2021-03-10") == "2021-03-10"


@pytest.mark.parametrize(
    "responses, expected",
    [
        (["PD", "SD", "PR"], "PR"),
        (["PD", "SD"], "SD"),
        (["PD"], "PD"),
        (["NE"], ""),
        ([], ""),
    ],
)
def test_best_response_ordering(responses, expected):
    assert gen._best_response(pd.Series(responses, dtype=object)) == expected


def _ds(*rows):
    return pd.DataFrame(rows, columns=["USUBJID", "DSDECOD"])


def _ae(*rows):
    return pd.DataFrame(rows, columns=["USUBJID", "AETERM", "AEOUT"])


def test_death_cause_prefers_fatal_ae_term():
    ds = _ds(("S1", "PROGRESSIVE DISEASE"), ("S1", "DEATH"))
    ae = _ae(("S1", "PNEUMONIA", "FATAL"))
    assert gen._death_cause("S1", ds, ae) == "PNEUMONIA"


def test_death_cause_progression_when_no_fatal_ae():
    ds = _ds(("S1", "PROGRESSIVE DISEASE"), ("S1", "DEATH"))
    assert gen._death_cause("S1", ds, _ae()) == "DISEASE PROGRESSION"


def test_death_cause_unknown_otherwise():
    ds = _ds(("S1", "DEATH"), ("S2", "PROGRESSIVE DISEASE"))
    ae = _ae(("S2", "NAUSEA", "RECOVERED"))
    assert gen._death_cause("S1", ds, ae) == "UNKNOWN"
