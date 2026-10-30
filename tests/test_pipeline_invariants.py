"""Cross-domain invariants on the full seeded pipeline output."""

import pandas as pd
import pytest

from src import cdisc_generation_functions as gen

STUDYID = "NCT01797120"


def _ids(df):
    return set(df["USUBJID"])


# ── structure ────────────────────────────────────────────────────────────────


def test_expected_domains(data):
    assert list(data) == ["DM", "EX", "TU", "TR", "RS", "DS", "AE", "FA", "RELREC", "ADSL", "ADTTE", "TV", "TA"]


def test_two_hundred_subjects(data):
    assert len(data["DM"]) == len(data["ADSL"]) == 200
    assert data["DM"]["USUBJID"].is_unique


def test_arms_balanced(data):
    assert data["DM"]["ARMCD"].value_counts().to_dict() == {"TRT": 100, "PLC": 100}


def test_studyid_and_usubjid_prefix(data):
    for name, df in data.items():
        if "STUDYID" in df:
            assert (df["STUDYID"] == STUDYID).all(), name
        if "USUBJID" in df:
            assert df["USUBJID"].str.startswith(f"{STUDYID}-").all(), name


@pytest.mark.parametrize(
    "domain, seq",
    [("EX", "EXSEQ"), ("TR", "TRSEQ"), ("RS", "RSSEQ"), ("DS", "DSSEQ"), ("AE", "AESEQ"), ("FA", "FASEQ")],
)
def test_sequence_keys_unique(data, domain, seq):
    assert not data[domain].duplicated(["USUBJID", seq]).any()


@pytest.mark.parametrize("domain", ["EX", "TU", "TR", "RS", "DS", "AE", "FA", "RELREC", "ADSL", "ADTTE"])
def test_subjects_exist_in_dm(data, domain):
    assert _ids(data[domain]) <= _ids(data["DM"])


def test_internal_columns_present_only_in_memory(data):
    for name, cols in gen._INTERNAL_COLUMNS.items():
        assert set(cols) <= set(data[name].columns)


# ── determinism ──────────────────────────────────────────────────────────────


def test_generation_is_deterministic(data):
    again = gen.generate_all()
    for name, df in data.items():
        pd.testing.assert_frame_equal(df, again[name], obj=name)


def test_seed_changes_output(data):
    other = gen.generate_all(seed=1)
    assert not data["DM"].equals(other["DM"])


# ── RECIST / TR ──────────────────────────────────────────────────────────────


def test_sumdiam_equals_sum_of_ldiam(data):
    tr = data["TR"].assign(SIZE=lambda d: pd.to_numeric(d["TRSTRESN"], errors="coerce"))
    ldiam = tr[tr["TRTESTCD"] == "LDIAM"].groupby(["USUBJID", "VISITNUM"])["SIZE"].sum()
    sumdiam = tr[tr["TRTESTCD"] == "SUMDIAM"].set_index(["USUBJID", "VISITNUM"])["SIZE"]
    joined = pd.concat([sumdiam.rename("sum"), ldiam.rename("parts")], axis=1, join="inner")
    measured = joined.dropna(subset=["sum"])  # not-evaluable visits have no SUMDIAM value
    assert len(measured) > 0
    assert ((measured["sum"] - measured["parts"]).abs() <= 0.0051).all()


def test_measured_lesions_respect_recist_floor(data):
    tr = data["TR"]
    sizes = pd.to_numeric(tr.loc[tr["TRTESTCD"] == "LDIAM", "TRSTRESN"], errors="coerce").dropna()
    assert (sizes[sizes > 0] >= gen._MIN_LESION_MM).all()


def test_rs_values_are_recist_categories(data):
    assert set(data["RS"]["RSSTRESC"]) <= {"CR", "PR", "SD", "PD", "NE"}


# ── death logic (issue #11) ──────────────────────────────────────────────────


def test_dthfl_matches_ds_death_and_fa_cause(data):
    dm, ds, fa = data["DM"], data["DS"], data["FA"]
    dead = _ids(dm[dm["DTHFL"] == "Y"])
    causes = fa[fa["FATESTCD"] == "DTHCAUSE"]
    assert dead
    assert dead == _ids(ds[ds["DSDECOD"] == "DEATH"])
    assert dead == _ids(causes)
    assert causes["USUBJID"].is_unique


def test_ds_death_date_matches_dm(data):
    dm, ds = data["DM"], data["DS"]
    death = ds[ds["DSDECOD"] == "DEATH"].set_index("USUBJID")["DSSTDTC"]
    dthdtc = dm[dm["DTHFL"] == "Y"].set_index("USUBJID")["DTHDTC"]
    assert (death.reindex(dthdtc.index) == dthdtc).all()


def test_fatal_ae_is_a_death_with_matching_cause(data):
    dm, ae, fa = data["DM"], data["AE"], data["FA"]
    fatal = ae[ae["AEOUT"] == "FATAL"]
    assert len(fatal) >= 1
    assert _ids(fatal) <= _ids(dm[dm["DTHFL"] == "Y"])
    assert (fatal["AESDTH"] == "Y").all()
    cause = fa[fa["FATESTCD"] == "DTHCAUSE"].set_index("USUBJID")["FAORRES"]
    assert (cause.reindex(fatal["USUBJID"]).to_numpy() == fatal["AETERM"].to_numpy()).all()


def test_no_observations_after_death(data):
    dm = data["DM"]
    dthdtc = pd.to_datetime(dm[dm["DTHFL"] == "Y"].set_index("USUBJID")["DTHDTC"])
    for domain, col in [("EX", "EXENDTC"), ("TR", "TRDTC"), ("RS", "RSDTC")]:
        df = data[domain]
        after = pd.to_datetime(df[col], errors="coerce") > df["USUBJID"].map(dthdtc)
        assert not after.any(), domain


# ── disposition / analysis datasets ──────────────────────────────────────────


def test_adsl_dcsreas_matches_ds_study_disposition(data):
    ds, adsl = data["DS"], data["ADSL"]
    study = ds[ds["DSSCAT"] == "STUDY PARTICIPATION"].set_index("USUBJID")["DSDECOD"]
    assert (adsl.set_index("USUBJID")["DCSREAS"] == study.reindex(adsl["USUBJID"])).all()


def test_adtte_one_pfs_row_per_subject(data):
    adtte = data["ADTTE"]
    assert set(adtte["PARAMCD"]) == {"PFS"}
    assert adtte["USUBJID"].is_unique
    assert set(adtte["CNSR"].astype(int)) <= {0, 1}
    assert (adtte["AVAL"] > 0).all()


def test_relrec_pairs_every_fa_record(data):
    relrec, fa = data["RELREC"], data["FA"]
    assert len(relrec) == 2 * len(fa)
    assert relrec.groupby("RELID").size().eq(2).all()
