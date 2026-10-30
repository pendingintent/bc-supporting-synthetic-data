"""Tests for validate.py itself: clean data passes, and each broken invariant is caught."""

import shutil
import subprocess
import sys

import pandas as pd
import pytest

from tests.conftest import VALIDATE_PATH

EXPECTED_CHECKS = 109  # update deliberately when checks are added or removed

CATEGORIES = [
    "check_structural",
    "check_integrity",
    "check_recist",
    "check_timeline_death",
    "check_population",
    "check_duplicates_and_coverage",
    "check_pfs_fidelity",
]


def run_all(validator, datasets):
    """Run every category; a category that raises is reported as one failed 'CRASH' result."""
    results = []
    for name in CATEGORIES:
        try:
            results.extend(getattr(validator, name)(datasets))
        except Exception as exc:  # a crash is itself a finding
            results.append(validator.CheckResult(f"CRASH in {name}: {type(exc).__name__}", False, str(exc)))
    return results


def failed_names(validator, datasets):
    return [res.name for res in run_all(validator, datasets) if not res.passed]


# ── helpers to break a copy of the clean data ────────────────────────────────


@pytest.fixture
def work(clean_dir, tmp_path):
    shutil.copytree(clean_dir, tmp_path / "d")
    return tmp_path / "d"


def edit(work, domain, fn):
    """Apply fn(df) to <work>/<domain>.csv (read as strings, like the validator does)."""
    path = work / f"{domain}.csv"
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    result = fn(df)
    (df if result is None else result).to_csv(path, index=False)


def first(df, mask):
    return df.index[mask][0]


def set_first(col, value, where):
    def fn(df):
        df.loc[first(df, where(df)), col] = value

    return fn


# ── clean data ───────────────────────────────────────────────────────────────


def test_clean_data_passes_every_check(validator, clean_dir):
    results = run_all(validator, clean_dir)
    assert [res.name for res in results if not res.passed] == []


def test_check_count_is_pinned(validator, clean_dir):
    assert len(run_all(validator, clean_dir)) == EXPECTED_CHECKS


def test_committed_datasets_pass(validator, repo_root):
    assert failed_names(validator, repo_root / "datasets") == []


# ── mutations: (domain, edit, name of the check that must fail) ──────────────

MUTATIONS = {
    "dm_studyid": ("DM", set_first("STUDYID", "OTHER", lambda d: d.index == 0), "DM: STUDYID = NCT01797120"),
    "dm_armcd": ("DM", set_first("ARMCD", "ZZZ", lambda d: d.index == 0), "DM: ARMCD ∈"),
    "dm_usubjid_format": ("DM", set_first("USUBJID", "BAD-1", lambda d: d.index == 0), "DM: USUBJID format"),
    "dm_duplicate_subject": ("DM", lambda d: pd.concat([d, d.iloc[[0]]]), "DM: no duplicate USUBJIDs"),
    "dm_dthfl_cleared": (
        "DM",
        set_first("DTHFL", "", lambda d: d["DTHFL"] == "Y"),
        "DM/DS: DTHFL=Y ↔ DS DEATH record consistent",
    ),
    "ex_placebo_dose": (
        "EX",
        set_first("EXDOSE", "10", lambda d: d["EXTRT"] == "PLACEBO"),
        "EX: PLACEBO EXDOSE = 0",
    ),
    "ex_date_after_study_end": (
        "EX",
        set_first("EXENDTC", "2030-01-01", lambda d: d.index == 0),
        "All domains: no dates beyond study end",
    ),
    "tr_units": ("TR", set_first("TRSTRESU", "cm", lambda d: d.index == 0), "TR: TRSTRESU = mm"),
    "tr_duplicate_key": ("TR", lambda d: pd.concat([d, d.iloc[[0]]]), "TR: no duplicate sequence keys"),
    "rs_invalid_category": (
        "RS",
        set_first("RSSTRESC", "XX", lambda d: d.index == 0),
        "RS: RSSTRESC ∈ {CR, PR, SD, PD, NE}",
    ),
    "rs_inconsistent_with_sumdiam": (
        "RS",
        set_first("RSSTRESC", "PD", lambda d: d["RSSTRESC"] == "PR"),
        "RS: RSSTRESC consistent with RECIST v1.1 SUMDIAM thresholds",
    ),
    "ds_record_dropped": ("DS", lambda d: d.iloc[1:], "DS: exactly 5 records per subject"),
    "ds_invalid_decod": (
        "DS",
        set_first("DSDECOD", "NOT A TERM", lambda d: d["DSDECOD"] == "RANDOMIZED"),
        "DS: DSDECOD ∈ valid controlled vocabulary",
    ),
    "ds_death_date_differs": (
        "DS",
        set_first("DSSTDTC", "2021-01-01", lambda d: d["DSDECOD"] == "DEATH"),
        "DS: DEATH record DSSTDTC = DM DTHDTC",
    ),
    "adsl_arm_mismatch": (
        "ADSL",
        set_first("TRT01A", "Placebo", lambda d: d["TRT01A"] == "Treatment"),
        "ADSL: TRT01A consistent with DM ARMCD",
    ),
    "adtte_nonpositive_aval": (
        "ADTTE",
        set_first("AVAL", "0", lambda d: d.index == 0),
        "ADTTE: AVAL > 0",
    ),
    "adtte_aval_wrong": (
        "ADTTE",
        set_first("AVAL", "99999", lambda d: d.index == 0),
        "ADTTE: AVAL = (ADT − STARTDT) in days",
    ),
    "adtte_bad_cnsr": ("ADTTE", set_first("CNSR", "2", lambda d: d.index == 0), "ADTTE: CNSR ∈ {0, 1}"),
    "ae_aesdth_disagrees": (
        "AE",
        set_first("AESDTH", "N", lambda d: d["AEOUT"] == "FATAL"),
        "AE: AESDTH=Y ↔ AEOUT=FATAL",
    ),
    "fa_cause_removed": (
        "FA",
        lambda d: d.drop(index=first(d, d["FATESTCD"] == "DTHCAUSE")),
        "DM/FA: every DTHFL=Y subject has exactly one FA DTHCAUSE record",
    ),
    "fa_cause_differs_from_ae": (
        "FA",
        set_first("FAORRES", "UNKNOWN", lambda d: d["FAORRES"] == "PNEUMONIA"),
        "AE/FA: DTHCAUSE equals AETERM for fatal AE subjects",
    ),
}


def _everolimus_on_placebo_arm(work):
    dm = pd.read_csv(work / "DM.csv", dtype=str, keep_default_na=False)
    plc = dm.loc[dm["ARMCD"] == "PLC", "USUBJID"].iloc[0]
    edit(work, "EX", set_first("EXTRT", "EVEROLIMUS", lambda d: d["USUBJID"] == plc))


def _lesion_below_floor(work):
    edit(work, "TR", set_first("TRSTRESN", "2.0", lambda d: d["TRTESTCD"] == "LDIAM"))


def _fatal_ae_on_living_subject(work):
    dm = pd.read_csv(work / "DM.csv", dtype=str, keep_default_na=False)
    alive = dm.loc[dm["DTHFL"] == "", "USUBJID"].iloc[0]
    edit(work, "AE", lambda d: pd.concat([d, d[d["AEOUT"] == "FATAL"].assign(USUBJID=alive)]))


def _tr_record_after_death(work):
    dm = pd.read_csv(work / "DM.csv", dtype=str, keep_default_na=False)
    dead = dm.loc[dm["DTHFL"] == "Y", "USUBJID"].iloc[0]
    edit(work, "TR", set_first("TRDTC", "2026-12-30", lambda d: d["USUBJID"] == dead))


def _subject_missing_from_dm(work):
    edit(work, "DM", lambda d: d.iloc[1:])


# Mutations that need to look at another domain are applied by function instead of a table row.
SPECIAL = {
    "ex_everolimus_on_placebo_arm": (_everolimus_on_placebo_arm, "EX: EVEROLIMUS only given to TRT arm"),
    "tr_lesion_below_floor": (_lesion_below_floor, "TR: LDIAM TRSTRESN = 0"),
    "ae_fatal_on_living_subject": (
        _fatal_ae_on_living_subject,
        "AE/DM: every AEOUT=FATAL subject has DTHFL=Y",
    ),
    "tr_record_after_death": (_tr_record_after_death, "TR: no records after death"),
    "ex_subject_missing_from_dm": (_subject_missing_from_dm, "EX: all USUBJIDs present in DM"),
}


@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_mutation_is_caught(name, validator, work):
    domain, fn, expected = MUTATIONS[name]
    edit(work, domain, fn)
    failed = failed_names(validator, work)
    assert any(expected in f for f in failed), f"expected a failure containing {expected!r}; got {failed}"


@pytest.mark.parametrize("name", sorted(SPECIAL))
def test_cross_domain_mutation_is_caught(name, validator, work):
    apply, expected = SPECIAL[name]
    apply(work)
    failed = failed_names(validator, work)
    assert any(expected in f for f in failed), f"expected a failure containing {expected!r}; got {failed}"


@pytest.mark.xfail(
    strict=True, reason="check_integrity raises when DM has a duplicate USUBJID instead of failing a check"
)
def test_validator_does_not_crash_on_duplicate_subject(validator, work):
    edit(work, "DM", lambda d: pd.concat([d, d.iloc[[0]]]))
    assert not any(res.name.startswith("CRASH") for res in run_all(validator, work))


def test_pfs_fidelity_flags_shifted_medians(validator, work):
    edit(work, "ADTTE", lambda d: d.assign(AVAL=(pd.to_numeric(d["AVAL"]) * 3).astype(int).astype(str)))
    failed = failed_names(validator, work)
    assert any(f.startswith("PFS fidelity") for f in failed)


def test_missing_arm_in_adtte_is_flagged(validator, work):
    edit(work, "ADTTE", lambda d: d[d["TRT01A"] != "Placebo"])
    assert any("Placebo arm present in ADTTE" in f for f in failed_names(validator, work))


# ── command line ─────────────────────────────────────────────────────────────


def run_cli(datasets, output):
    return subprocess.run(
        [sys.executable, str(VALIDATE_PATH), "--datasets", str(datasets), "--output", str(output)],
        capture_output=True,
        text=True,
    )


def test_cli_exit_zero_and_report_on_clean_data(clean_dir, tmp_path):
    out = tmp_path / "report.md"
    proc = run_cli(clean_dir, out)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert f"{EXPECTED_CHECKS}/{EXPECTED_CHECKS} checks passed" in proc.stdout
    assert out.exists() and "PFS Fidelity" in out.read_text()


def test_cli_exit_one_when_a_check_fails(work, tmp_path):
    edit(work, "DM", set_first("STUDYID", "OTHER", lambda d: d.index == 0))
    proc = run_cli(work, tmp_path / "report.md")
    assert proc.returncode == 1
    assert "FAIL" in (tmp_path / "report.md").read_text()


def test_cli_exit_two_when_required_files_missing(work, tmp_path):
    (work / "ADTTE.csv").unlink()
    proc = run_cli(work, tmp_path / "report.md")
    assert proc.returncode == 2
    assert "ADTTE.csv" in proc.stdout
    assert not (tmp_path / "report.md").exists()
