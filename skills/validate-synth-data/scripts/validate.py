#!/usr/bin/env python3
"""
Validation script for NCT01797120 synthetic CDISC datasets.
Usage: python validate.py --datasets <path> [--output <report.md>]
Exit code: 0 = all pass, 1 = any failure.
"""

import argparse
import re
import sys
from datetime import date
from pathlib import Path

import pandas as pd

STUDYID = "NCT01797120"
USUBJID_RE = re.compile(r"^NCT01797120-\d{4}$")

TARGET_PFS = {"Treatment": 314, "Placebo": 155}
PFS_TOLERANCE = 0.20  # ±20%


# ── helpers ──────────────────────────────────────────────────────────────────


def _load(datasets: Path, name: str) -> pd.DataFrame:
    path = datasets / f"{name}.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing: {path}")
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def _num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


class CheckResult:
    def __init__(self, name: str, passed: bool, detail: str = ""):
        self.name = name
        self.passed = passed
        self.detail = detail

    def __repr__(self):
        icon = "✓" if self.passed else "✗"
        line = f"{icon} {'PASS' if self.passed else 'FAIL'} — {self.name}"
        if self.detail:
            line += f" ({self.detail})"
        return line


def _check(results: list, name: str, cond: bool, detail: str = "") -> bool:
    results.append(CheckResult(name, cond, detail))
    return cond


# ── category 1: CDISC structural ─────────────────────────────────────────────


def check_structural(datasets: Path) -> list[CheckResult]:
    r: list[CheckResult] = []

    # DM
    dm = _load(datasets, "DM")
    _check(
        r,
        "DM: STUDYID = NCT01797120",
        (dm["STUDYID"] == STUDYID).all(),
        f"{(dm['STUDYID'] != STUDYID).sum()} bad rows",
    )
    _check(r, "DM: DOMAIN = DM", (dm["DOMAIN"] == "DM").all())
    _check(
        r,
        "DM: all subjects female (SEX=F)",
        (dm["SEX"] == "F").all(),
        f"{(dm['SEX'] != 'F').sum()} non-F rows",
    )
    _check(
        r,
        "DM: ARMCD ∈ {TRT, PLC}",
        dm["ARMCD"].isin({"TRT", "PLC"}).all(),
        f"{(~dm['ARMCD'].isin({'TRT', 'PLC'})).sum()} bad values",
    )
    _check(r, "DM: DTHFL ∈ {Y, N}", dm["DTHFL"].isin({"Y", "N"}).all())
    bad_ids = (~dm["USUBJID"].str.match(USUBJID_RE)).sum()
    _check(
        r,
        "DM: USUBJID format NCT01797120-NNNN",
        bad_ids == 0,
        f"{bad_ids} malformed IDs",
    )
    _check(
        r,
        "DM: AGEU = YEARS (CG0432)",
        ("AGEU" in dm.columns) and (dm["AGEU"] == "YEARS").all(),
    )
    _check(
        r,
        "DM: RFENDTC present and = RFPENDTC (CG0142)",
        "RFENDTC" in dm.columns and (dm["RFENDTC"] == dm["RFPENDTC"]).all(),
    )
    _check(
        r,
        "DM: RFICDTC non-empty",
        (dm["RFICDTC"].str.strip() != "").all() if "RFICDTC" in dm.columns else False,
        "" if "RFICDTC" in dm.columns else "column missing",
    )
    _check(
        r,
        "DM: RFPENDTC non-empty",
        (dm["RFPENDTC"].str.strip() != "").all() if "RFPENDTC" in dm.columns else False,
        "" if "RFPENDTC" in dm.columns else "column missing",
    )

    # EX
    ex = _load(datasets, "EX")
    _check(
        r,
        "EX: EXTRT ∈ {FULVESTRANT, EVEROLIMUS, PLACEBO}",
        ex["EXTRT"].isin({"FULVESTRANT", "EVEROLIMUS", "PLACEBO"}).all(),
        f"{(~ex['EXTRT'].isin({'FULVESTRANT', 'EVEROLIMUS', 'PLACEBO'})).sum()} bad values",
    )
    _check(r, "EX: EXDOSU = mg", (ex["EXDOSU"] == "mg").all())
    # Non-placebo records must have EXDOSE > 0; PLACEBO must have EXDOSE = 0 (CG0102)
    non_plc = ex[ex["EXTRT"] != "PLACEBO"]
    bad_nonplc = (_num(non_plc["EXDOSE"]) <= 0).sum()
    _check(
        r,
        "EX: EXDOSE > 0 for non-PLACEBO records",
        bad_nonplc == 0,
        f"{bad_nonplc} bad values",
    )
    _check(
        r,
        "EX: EXROUTE ∈ {INTRAMUSCULAR, ORAL}",
        ex["EXROUTE"].isin({"INTRAMUSCULAR", "ORAL"}).all(),
    )
    _check(
        r,
        "EX: EXSTDY and EXENDY present",
        ("EXSTDY" in ex.columns and "EXENDY" in ex.columns),
    )
    # Fulvestrant C1D1 and C1D15 must be 250 mg loading doses; subsequent cycles 500 mg
    fulv = ex[ex["EXTRT"] == "FULVESTRANT"].copy()
    first_two = fulv.groupby("USUBJID").head(2)
    bad_loading = (~(_num(first_two["EXDOSE"]) == 250)).sum()
    _check(
        r,
        "EX: Fulvestrant C1D1 and C1D15 doses = 250 mg",
        bad_loading == 0,
        f"{bad_loading} records with wrong loading dose",
    )
    # CG0102: EXTRT=PLACEBO must have EXDOSE=0
    plc = ex[ex["EXTRT"] == "PLACEBO"]
    bad_plc_dose = (~(_num(plc["EXDOSE"]) == 0)).sum()
    _check(
        r,
        "EX: PLACEBO EXDOSE = 0 (CG0102)",
        bad_plc_dose == 0,
        f"{bad_plc_dose} records with non-zero placebo dose",
    )

    # TR
    tr = _load(datasets, "TR")
    _check(
        r,
        "TR: TRTESTCD ∈ {LDIAM, SUMDIAM}",
        tr["TRTESTCD"].isin({"LDIAM", "SUMDIAM"}).all(),
    )
    _check(r, "TR: TRSTRESU = mm", (tr["TRSTRESU"] == "mm").all())
    _check(r, "TR: LOBXFL ∈ {Y, ''}", tr["LOBXFL"].isin({"Y", ""}).all())
    _check(
        r,
        "TR: TRLNKID present (not TRLINKID)",
        "TRLNKID" in tr.columns and "TRLINKID" not in tr.columns,
    )
    _check(
        r,
        "TR: EPOCH ∈ {INDUCTION, CONTINUATION} (FB2201)",
        "EPOCH" in tr.columns and tr["EPOCH"].isin({"INDUCTION", "CONTINUATION"}).all(),
    )
    _check(
        r,
        "TR: TRMETHOD = CT SCAN present",
        "TRMETHOD" in tr.columns and (tr["TRMETHOD"] == "CT SCAN").all(),
    )
    _check(
        r,
        "TR: TREVAL = INVESTIGATOR present",
        "TREVAL" in tr.columns and (tr["TREVAL"] == "INVESTIGATOR").all(),
    )
    # SUMDIAM records: one baseline per subject, TRGRPID=TARGET
    sumdiam = tr[tr["TRTESTCD"] == "SUMDIAM"] if "TRTESTCD" in tr.columns else pd.DataFrame()
    _check(r, "TR: SUMDIAM records present (RECIST supplement)", len(sumdiam) > 0)
    if len(sumdiam):
        bl_sumd = sumdiam[sumdiam["TRLOBXFL"] == "Y"]
        _check(
            r,
            "TR: exactly one baseline SUMDIAM per subject",
            bl_sumd.groupby("USUBJID").size().eq(1).all(),
        )
        _check(r, "TR: SUMDIAM TRGRPID = TARGET", (sumdiam["TRGRPID"] == "TARGET").all())
    # TRSTRESN ≥ 5 mm for evaluable LDIAM records (NOT DONE records may be empty)
    ldiam_eval = (
        tr[(tr["TRTESTCD"] == "LDIAM") & (tr.get("TRSTAT", pd.Series([""])) != "NOT DONE")]
        if "TRSTAT" in tr.columns
        else tr[tr["TRTESTCD"] == "LDIAM"]
    )
    # Allow 0 (absent lesion) or ≥ 5 mm
    ldiam_num = _num(ldiam_eval["TRSTRESN"])
    bad_ldiam = ((ldiam_num > 0) & (ldiam_num < 5)).sum()
    _check(
        r,
        "TR: LDIAM TRSTRESN = 0 (absent) or ≥ 5 mm for evaluable records",
        bad_ldiam == 0,
        f"{bad_ldiam} values between 0 and 5 mm",
    )

    # RS
    rs = _load(datasets, "RS")
    _check(r, "RS: RSTESTCD = OVRLRESP", (rs["RSTESTCD"] == "OVRLRESP").all())
    _check(
        r,
        "RS: RSSTRESC ∈ {CR, PR, SD, PD, NE} (RECIST 1.1)",
        rs["RSSTRESC"].isin({"CR", "PR", "SD", "PD", "NE"}).all(),
        f"{(~rs['RSSTRESC'].isin({'CR', 'PR', 'SD', 'PD', 'NE'})).sum()} bad values",
    )
    _check(
        r,
        "RS: EPOCH ∈ {INDUCTION, CONTINUATION} (FB2201)",
        "EPOCH" in rs.columns and rs["EPOCH"].isin({"INDUCTION", "CONTINUATION"}).all(),
    )
    _check(
        r,
        "RS: RSDRVFL = Y for derived records (CG0563)",
        "RSDRVFL" in rs.columns and (rs["RSDRVFL"] == "Y").all(),
    )

    # DS
    ds = _load(datasets, "DS")
    _check(
        r,
        "DS: DSCAT ∈ {PROTOCOL MILESTONE, DISPOSITION EVENT}",
        ds["DSCAT"].isin({"PROTOCOL MILESTONE", "DISPOSITION EVENT"}).all(),
    )
    _valid_dsdecod = {
        "INFORMED CONSENT OBTAINED",
        "RANDOMIZED",
        "PROGRESSIVE DISEASE",
        "WITHDRAWAL BY SUBJECT",
        "LOST TO FOLLOW-UP",
        "DEATH",
    }
    bad_decod = (~ds["DSDECOD"].isin(_valid_dsdecod)).sum()
    _check(
        r,
        "DS: DSDECOD ∈ valid controlled vocabulary",
        bad_decod == 0,
        f"{bad_decod} unexpected values",
    )
    # CG0073: EPOCH must be null/empty for PROTOCOL MILESTONE records
    pm = ds[ds["DSCAT"] == "PROTOCOL MILESTONE"]
    bad_pm_epoch = (pm["EPOCH"].str.strip() != "").sum()
    _check(
        r,
        "DS: EPOCH empty for PROTOCOL MILESTONE records (CG0073)",
        bad_pm_epoch == 0,
        f"{bad_pm_epoch} PROTOCOL MILESTONE records with non-empty EPOCH",
    )
    _valid_epoch = {"", "INDUCTION", "CONTINUATION", "FOLLOW-UP"}
    bad_epoch = (~ds["EPOCH"].isin(_valid_epoch)).sum()
    _check(
        r,
        "DS: EPOCH ∈ {'' (milestone), INDUCTION, CONTINUATION, FOLLOW-UP}",
        bad_epoch == 0,
        f"{bad_epoch} unexpected values",
    )
    # CG0066: DSTERM must equal DSDECOD for PROTOCOL MILESTONE records
    _check(
        r,
        "DS: DSTERM present",
        "DSTERM" in ds.columns and (ds["DSTERM"].str.strip() != "").all(),
        (f"{(ds['DSTERM'].str.strip() == '').sum()} empty" if "DSTERM" in ds.columns else "column missing"),
    )
    if "DSTERM" in ds.columns:
        pm_mismatch = (pm["DSTERM"] != pm["DSDECOD"]).sum()
        _check(
            r,
            "DS: DSTERM = DSDECOD for PROTOCOL MILESTONE records (CG0066)",
            pm_mismatch == 0,
            f"{pm_mismatch} mismatches",
        )
    # FB0611: DS DEATH record DSDTC must equal DM DTHDTC
    death_ds = ds[ds["DSDECOD"] == "DEATH"][["USUBJID", "DSDTC"]].rename(columns={"DSDTC": "_ds_dtc"})
    if len(death_ds):
        dm_death = dm[dm["DTHFL"] == "Y"][["USUBJID", "DTHDTC"]]
        merged_d = death_ds.merge(dm_death, on="USUBJID", how="left")
        bad_dth = (merged_d["_ds_dtc"] != merged_d["DTHDTC"]).sum()
        _check(
            r,
            "DS: DEATH record DSDTC = DM DTHDTC (FB0611)",
            bad_dth == 0,
            f"{bad_dth} mismatches",
        )

    # ADSL
    adsl = _load(datasets, "ADSL")
    _check(
        r,
        "ADSL: TRT01A ∈ {Treatment, Placebo}",
        adsl["TRT01A"].isin({"Treatment", "Placebo"}).all(),
    )
    _check(
        r,
        "ADSL: TRT01P present and = TRT01A (no crossover)",
        "TRT01P" in adsl.columns and (adsl["TRT01P"] == adsl["TRT01A"]).all(),
    )
    _check(r, "ADSL: CNSR ∈ {0, 1}", adsl["CNSR"].isin({"0", "1"}).all())
    _check(
        r,
        "ADSL: PFS > 0",
        (_num(adsl["PFS"]) > 0).all(),
        f"{(_num(adsl['PFS']) <= 0).sum()} bad values",
    )
    for flag in ("ITTFL", "SAFFL", "PPROTFL"):
        _check(
            r,
            f"ADSL: {flag} present and ∈ {{Y, N}}",
            flag in adsl.columns and adsl[flag].isin({"Y", "N"}).all(),
        )

    # ADTTE
    adtte = _load(datasets, "ADTTE")
    _check(r, "ADTTE: PARAMCD = PFS", (adtte["PARAMCD"] == "PFS").all())
    _check(r, "ADTTE: CNSR ∈ {0, 1}", adtte["CNSR"].isin({"0", "1"}).all())
    _check(r, "ADTTE: AVAL > 0", (_num(adtte["AVAL"]) > 0).all())

    return r


# ── category 2: cross-domain integrity ───────────────────────────────────────


def check_integrity(datasets: Path) -> list[CheckResult]:
    r: list[CheckResult] = []
    dm = _load(datasets, "DM")
    ex = _load(datasets, "EX")
    tr = _load(datasets, "TR")
    rs = _load(datasets, "RS")
    ds = _load(datasets, "DS")
    adsl = _load(datasets, "ADSL")
    adtte = _load(datasets, "ADTTE")

    dm_ids = set(dm["USUBJID"])

    tu = _load(datasets, "TU") if (datasets / "TU.csv").exists() else pd.DataFrame(columns=["USUBJID"])
    for name, df in [
        ("EX", ex),
        ("TR", tr),
        ("RS", rs),
        ("DS", ds),
        ("ADSL", adsl),
        ("ADTTE", adtte),
        ("TU", tu),
    ]:
        orphans = set(df["USUBJID"]) - dm_ids
        _check(
            r,
            f"{name}: all USUBJIDs present in DM",
            len(orphans) == 0,
            f"{len(orphans)} orphan subjects",
        )

    missing_adsl = dm_ids - set(adsl["USUBJID"])
    _check(
        r,
        "DM: all subjects in ADSL",
        len(missing_adsl) == 0,
        f"{len(missing_adsl)} subjects missing from ADSL",
    )

    missing_adtte = dm_ids - set(adtte["USUBJID"])
    _check(
        r,
        "DM: all subjects in ADTTE",
        len(missing_adtte) == 0,
        f"{len(missing_adtte)} subjects missing from ADTTE",
    )

    # Arm-drug consistency
    trt_ids = set(dm.loc[dm["ARMCD"] == "TRT", "USUBJID"])
    plc_ids = set(dm.loc[dm["ARMCD"] == "PLC", "USUBJID"])

    everolimus_users = set(ex.loc[ex["EXTRT"] == "EVEROLIMUS", "USUBJID"])
    placebo_users = set(ex.loc[ex["EXTRT"] == "PLACEBO", "USUBJID"])

    wrong_ever = everolimus_users - trt_ids
    _check(
        r,
        "EX: EVEROLIMUS only given to TRT arm",
        len(wrong_ever) == 0,
        f"{len(wrong_ever)} PLC subjects received EVEROLIMUS",
    )

    wrong_plac = placebo_users - plc_ids
    _check(
        r,
        "EX: PLACEBO only given to PLC arm",
        len(wrong_plac) == 0,
        f"{len(wrong_plac)} TRT subjects received PLACEBO",
    )

    trt_missing_ever = trt_ids - everolimus_users
    _check(
        r,
        "EX: all TRT subjects have EVEROLIMUS record",
        len(trt_missing_ever) == 0,
        f"{len(trt_missing_ever)} TRT subjects missing EVEROLIMUS",
    )

    plc_missing_plac = plc_ids - placebo_users
    _check(
        r,
        "EX: all PLC subjects have PLACEBO record",
        len(plc_missing_plac) == 0,
        f"{len(plc_missing_plac)} PLC subjects missing PLACEBO",
    )

    # DS structural integrity
    ds = _load(datasets, "DS")
    recs_per_subj = ds.groupby("USUBJID").size()
    bad_count = (recs_per_subj != 5).sum()
    _check(
        r,
        "DS: exactly 5 records per subject",
        bad_count == 0,
        f"{bad_count} subjects with wrong record count",
    )
    study_part_ids = set(ds.loc[ds["DSSCAT"] == "STUDY PARTICIPATION", "USUBJID"])
    missing_sp = dm_ids - study_part_ids
    _check(
        r,
        "DS: every subject has a STUDY PARTICIPATION end record",
        len(missing_sp) == 0,
        f"{len(missing_sp)} subjects missing record",
    )

    # ADSL TRT01A consistency with DM ARMCD
    arm_map = dm.set_index("USUBJID")["ARMCD"].map({"TRT": "Treatment", "PLC": "Placebo"})
    adsl_indexed = adsl.set_index("USUBJID")["TRT01A"]
    common = arm_map.index.intersection(adsl_indexed.index)
    mismatched = (arm_map.loc[common] != adsl_indexed.loc[common]).sum()
    _check(
        r,
        "ADSL: TRT01A consistent with DM ARMCD",
        mismatched == 0,
        f"{mismatched} mismatched subjects",
    )

    return r


# ── category 3: RECIST derivation ────────────────────────────────────────────


def check_recist(datasets: Path) -> list[CheckResult]:
    r: list[CheckResult] = []
    tr = _load(datasets, "TR")
    rs = _load(datasets, "RS")

    tr["TRSTRESN"] = _num(tr["TRSTRESN"])

    # Every RS USUBJID must have a baseline SUMDIAM in TR
    rs_ids = set(rs["USUBJID"])
    sumd_bl_ids = (
        set(tr[(tr.get("TRTESTCD", pd.Series()) == "SUMDIAM") & (tr["LOBXFL"] == "Y")]["USUBJID"])
        if "TRTESTCD" in tr.columns
        else set(tr[tr["LOBXFL"] == "Y"]["USUBJID"])
    )
    missing_baseline = rs_ids - sumd_bl_ids
    _check(
        r,
        "TR: every RS subject has a baseline SUMDIAM record",
        len(missing_baseline) == 0,
        f"{len(missing_baseline)} RS subjects missing TR baseline",
    )

    # TU domain: all DM subjects should have TU records
    tu = _load(datasets, "TU") if (datasets / "TU.csv").exists() else pd.DataFrame(columns=["USUBJID"])
    if len(tu):
        tu_ids = set(tu["USUBJID"])
        dm_ids_local = set(tr["USUBJID"])  # use TR subjects as proxy (all treated)
        missing_tu = dm_ids_local - tu_ids
        _check(
            r,
            "TU: all subjects have tumor identification records",
            len(missing_tu) == 0,
            f"{len(missing_tu)} subjects missing TU records",
        )
        _check(
            r,
            "TU: TUTESTCD ∈ {TIND, NTIND, TUMIDENT}",
            tu["TUTESTCD"].isin({"TIND", "NTIND", "TUMIDENT"}).all(),
        )
        tumident = tu[tu["TUTESTCD"] == "TUMIDENT"]
        tr_lnkids = set(tr[tr["TRTESTCD"] == "LDIAM"]["TRLNKID"].unique()) if "TRTESTCD" in tr.columns else set()
        orphan_tu = (~tumident["TULNKID"].isin(tr_lnkids)).sum()
        _check(
            r,
            "TU: TUMIDENT TULNKID links to a TR TRLNKID",
            orphan_tu == 0,
            f"{orphan_tu} unlinked TU records",
        )

    # RS dates should match a TR assessment date for that subject
    tr_date_keys = set(zip(tr["USUBJID"], tr["TRDTC"]))
    unmatched = [(u, d) for u, d in zip(rs["USUBJID"], rs["RSDTC"]) if (u, d) not in tr_date_keys]
    _check(
        r,
        "RS: every response date matches a TR assessment date",
        len(unmatched) == 0,
        f"{len(unmatched)} RS records with no matching TR date",
    )

    # No subject should have more than one PD record (once PD is declared, no further scans)
    pd_counts = rs[rs["RSSTRESC"] == "PD"].groupby("USUBJID").size()
    multi_pd = (pd_counts > 1).sum()
    _check(
        r,
        "RS: no subject has more than one PD assessment",
        multi_pd == 0,
        f"{multi_pd} subjects with repeated PD records",
    )

    # RECIST consistency: use SUMDIAM records from TR (the authoritative aggregate)
    sumdiam = tr[tr["TRTESTCD"] == "SUMDIAM"].copy() if "TRTESTCD" in tr.columns else pd.DataFrame()
    if len(sumdiam) == 0:
        _check(
            r,
            "RS: RSSTRESC consistent with RECIST v1.1 SUMDIAM thresholds",
            False,
            "no SUMDIAM records found in TR",
        )
    else:
        bl_sumd = sumdiam[sumdiam["LOBXFL"] == "Y"].set_index("USUBJID")["TRSTRESN"]
        post_sumd = sumdiam[sumdiam["LOBXFL"] != "Y"].copy()
        post_sumd = post_sumd.merge(bl_sumd.rename("BASE_SUMD").reset_index(), on="USUBJID", how="left")
        post_sumd = post_sumd.dropna(subset=["BASE_SUMD"])

        def _exp_resp(row):
            if row.get("TRSTAT", "") == "NOT DONE" or pd.isna(row["TRSTRESN"]):
                return "NE"
            if row["TRSTRESN"] == 0:
                return "CR"
            base = row["BASE_SUMD"]
            if pd.isna(base) or base == 0:
                return "NE"
            pct = (row["TRSTRESN"] - base) / base * 100
            return "PR" if pct <= -30 else ("PD" if pct >= 20 else "SD")

        post_sumd["EXP_RESP"] = post_sumd.apply(_exp_resp, axis=1)
        rs_keyed = rs.set_index(["USUBJID", "RSDTC"])["RSSTRESC"]
        sumd_keyed = post_sumd.set_index(["USUBJID", "TRDTC"])["EXP_RESP"]
        common = rs_keyed.index.intersection(sumd_keyed.index)
        if len(common) == 0:
            _check(
                r,
                "RS: RSSTRESC consistent with RECIST v1.1 SUMDIAM thresholds",
                False,
                "no matchable keys",
            )
        else:
            mm = (rs_keyed.loc[common] != sumd_keyed.loc[common]).sum()
            _check(
                r,
                "RS: RSSTRESC consistent with RECIST v1.1 SUMDIAM thresholds",
                mm == 0,
                f"{mm} mismatches out of {len(common)} checked",
            )

    return r


# ── category 4: timeline & death logic ───────────────────────────────────────

STUDY_END = pd.Timestamp("2026-12-31")


def check_timeline_death(datasets: Path) -> list[CheckResult]:
    """
    Covers DM check-set sections 1 (Study Timeline), 2 (Death & Post-Death),
    and 3 (Within-Domain Temporal Logic).
    """
    r: list[CheckResult] = []
    dm = _load(datasets, "DM")
    ex = _load(datasets, "EX")
    tr = _load(datasets, "TR")
    rs = _load(datasets, "RS")
    ds = _load(datasets, "DS")

    def dt(s):
        return pd.to_datetime(s, errors="coerce")

    # ── Section 1: Study Timeline & Anchoring ─────────────────────────────
    n_rfstdtc = dm["RFSTDTC"].nunique()
    _check(
        r,
        "DM: RFSTDTC has variability (>10 distinct dates)",
        n_rfstdtc > 10,
        f"{n_rfstdtc} distinct dates",
    )

    durations = (dt(dm["RFXENDTC"]) - dt(dm["RFXSTDTC"])).dt.days.dropna()
    dur_std = durations.std()
    _check(
        r,
        "DM: Study durations vary (stddev > 30 days)",
        dur_std > 30,
        f"stddev={dur_std:.0f}d",
    )

    rfst_map = dm.set_index("USUBJID")["RFSTDTC"].apply(dt)
    # rfend_map = dm.set_index("USUBJID")["RFXENDTC"].apply(dt)

    ex_stdt = dt(ex["EXSTDTC"])
    bad_ex_start = (ex_stdt < ex["USUBJID"].map(rfst_map)).sum()
    _check(
        r,
        "EX: EXSTDTC ≥ RFSTDTC",
        bad_ex_start == 0,
        f"{bad_ex_start} records before study start",
    )

    tr_dt = dt(tr["TRDTC"])
    bad_tr = (tr_dt < tr["USUBJID"].map(rfst_map)).sum()
    _check(r, "TR: TRDTC ≥ RFSTDTC", bad_tr == 0, f"{bad_tr} records before study start")

    bad_rfxend = (dt(dm["RFXENDTC"]) < dt(dm["RFSTDTC"])).sum()
    _check(
        r,
        "DM: RFXENDTC ≥ RFSTDTC",
        bad_rfxend == 0,
        f"{bad_rfxend} subjects with end before start",
    )

    bad_rfpend = (dt(dm["RFPENDTC"]) < dt(dm["RFXENDTC"])).sum()
    _check(
        r,
        "DM: RFPENDTC ≥ RFXENDTC",
        bad_rfpend == 0,
        f"{bad_rfpend} subjects with participation end before treatment end",
    )

    # ── Section 2: Death & Post-Death Logic ────────────────────────────────
    dead = dm[dm["DTHFL"] == "Y"].copy()
    bad_dth_before_rfst = (dt(dead["DTHDTC"]) < dt(dead["RFSTDTC"])).sum()
    _check(
        r,
        "DM: DTHDTC ≥ RFSTDTC (no death before study start)",
        bad_dth_before_rfst == 0,
        f"{bad_dth_before_rfst} violations",
    )

    dthdtc_map = dead.set_index("USUBJID")["DTHDTC"].apply(dt).to_dict()
    dead_ids = set(dthdtc_map.keys())

    def _after_death(df, date_col):
        sub = df[df["USUBJID"].isin(dead_ids)].copy()
        sub["_dth"] = sub["USUBJID"].map(dthdtc_map)
        sub["_d"] = dt(sub[date_col])
        return (sub["_d"] > sub["_dth"]).sum()

    bad_tr_dth = _after_death(tr, "TRDTC")
    _check(
        r,
        "TR: no records after death (TRDTC ≤ DTHDTC)",
        bad_tr_dth == 0,
        f"{bad_tr_dth} records after death",
    )

    bad_rs_dth = _after_death(rs, "RSDTC")
    _check(
        r,
        "RS: no records after death (RSDTC ≤ DTHDTC)",
        bad_rs_dth == 0,
        f"{bad_rs_dth} records after death",
    )

    bad_ex_dth = _after_death(ex, "EXSTDTC")
    _check(
        r,
        "EX: no records starting after death (EXSTDTC ≤ DTHDTC)",
        bad_ex_dth == 0,
        f"{bad_ex_dth} records after death",
    )

    # DS: DTHFL=Y ↔ DS DSDECOD=DEATH
    death_ds_ids = set(ds[ds["DSDECOD"] == "DEATH"]["USUBJID"])
    dthfl_y_ids = set(dm[dm["DTHFL"] == "Y"]["USUBJID"])
    missing_ds = len(dthfl_y_ids - death_ds_ids)
    spurious_ds = len(death_ds_ids - dthfl_y_ids)
    _check(
        r,
        "DM/DS: DTHFL=Y ↔ DS DEATH record consistent",
        missing_ds == 0 and spurious_ds == 0,
        f"{missing_ds} missing, {spurious_ds} spurious DS DEATH records",
    )

    # ── Section 3: Within-Domain Temporal Logic ────────────────────────────
    bad_ex_order = (dt(ex["EXSTDTC"]) > dt(ex["EXENDTC"])).sum()
    _check(
        r,
        "EX: EXSTDTC ≤ EXENDTC",
        bad_ex_order == 0,
        f"{bad_ex_order} records with start after end",
    )

    future_dates = sum(
        [
            (dt(tr["TRDTC"]) > STUDY_END).sum(),
            (dt(rs["RSDTC"]) > STUDY_END).sum(),
            (dt(ex["EXENDTC"]) > STUDY_END).sum(),
        ]
    )
    _check(
        r,
        "All domains: no dates beyond study end (2026-12-31)",
        future_dates == 0,
        f"{future_dates} future dates",
    )

    return r


# ── category 5: population distribution & plausibility ───────────────────────


def check_population(datasets: Path) -> list[CheckResult]:
    """
    Covers DM check-set sections 5 (Demographic Plausibility),
    7 (Population Distribution), and 9 (Missingness Patterns).
    """
    r: list[CheckResult] = []
    dm = _load(datasets, "DM")
    tr = _load(datasets, "TR")
    rs = _load(datasets, "RS")

    ages = _num(dm["AGE"])
    _check(
        r,
        "DM: all ages in plausible range (18–85)",
        ((ages >= 18) & (ages <= 85)).all(),
        f"{((ages < 18) | (ages > 85)).sum()} implausible values",
    )

    age_std = ages.std()
    _check(
        r,
        "DM: age has realistic variability (stddev > 5 years)",
        age_std > 5,
        f"stddev={age_std:.1f}",
    )

    enroll_span = (
        pd.to_datetime(dm["RFSTDTC"], errors="coerce").max() - pd.to_datetime(dm["RFSTDTC"], errors="coerce").min()
    ).days
    _check(
        r,
        "DM: enrollment dates span > 90 days (not all same date)",
        enroll_span > 90,
        f"span={enroll_span} days",
    )

    tr_counts = tr.groupby("USUBJID")["TRSEQ"].count()
    _check(
        r,
        "TR: record counts vary across subjects (not all identical)",
        tr_counts.nunique() > 1,
        f"{tr_counts.nunique()} distinct counts (min={tr_counts.min()}, max={tr_counts.max()})",
    )

    rs_counts = rs.groupby("USUBJID")["RSSEQ"].count()
    _check(
        r,
        "RS: record counts vary across subjects (realistic missingness)",
        rs_counts.nunique() > 1,
        f"{rs_counts.nunique()} distinct counts (min={rs_counts.min()}, max={rs_counts.max()})",
    )

    return r


# ── category 6: duplicate & study-level consistency ──────────────────────────


def check_duplicates_and_coverage(datasets: Path) -> list[CheckResult]:
    """
    Covers DM check-set sections 8 (Duplicate/Pattern Detection)
    and 10 (Study-Level Consistency).
    """
    r: list[CheckResult] = []
    dm = _load(datasets, "DM")
    ex = _load(datasets, "EX")
    tr = _load(datasets, "TR")
    rs = _load(datasets, "RS")
    ds = _load(datasets, "DS")
    adsl = _load(datasets, "ADSL")

    # ── Section 8: Duplicate Detection ────────────────────────────────────
    dup_dm = dm["USUBJID"].duplicated().sum()
    _check(r, "DM: no duplicate USUBJIDs", dup_dm == 0, f"{dup_dm} duplicates")

    for name, df, keys in [
        ("EX", ex, ["USUBJID", "EXSEQ"]),
        ("TR", tr, ["USUBJID", "TRSEQ"]),
        ("RS", rs, ["USUBJID", "RSSEQ"]),
        ("DS", ds, ["USUBJID", "DSSEQ"]),
    ]:
        dups = df.duplicated(keys).sum()
        _check(
            r,
            f"{name}: no duplicate sequence keys (USUBJID+{keys[1]})",
            dups == 0,
            f"{dups} duplicates",
        )

    # Visit schedules not perfectly identical: check TR baseline dates vary
    bl_dates = tr[tr["LOBXFL"] == "Y"].groupby("USUBJID")["TRDTC"].first()
    _check(
        r,
        "TR: baseline dates are not all identical (schedules vary)",
        bl_dates.nunique() > 1,
        f"{bl_dates.nunique()} distinct baseline dates",
    )

    # ── Section 10: Study-Level Consistency ───────────────────────────────
    dm_ids = set(dm["USUBJID"])
    # Every DM subject must appear in at least one clinical domain
    covered = set(ex["USUBJID"]) | set(tr["USUBJID"]) | set(rs["USUBJID"])
    uncovered = dm_ids - covered
    _check(
        r,
        "DM: every subject appears in ≥1 clinical domain (EX/TR/RS)",
        len(uncovered) == 0,
        f"{len(uncovered)} subjects with no domain records",
    )

    # Subject IDs consistent across key analytical datasets
    adsl_ids = set(adsl["USUBJID"])
    mismatch = dm_ids.symmetric_difference(adsl_ids)
    _check(
        r,
        "DM ↔ ADSL: subject sets match exactly",
        len(mismatch) == 0,
        f"{len(mismatch)} mismatched subjects",
    )

    return r


# ── category 7: PFS fidelity ─────────────────────────────────────────────────


def check_pfs_fidelity(datasets: Path) -> list[CheckResult]:
    r: list[CheckResult] = []
    adtte = _load(datasets, "ADTTE")
    adtte["AVAL"] = _num(adtte["AVAL"])
    adtte["CNSR"] = _num(adtte["CNSR"])

    for arm, target in TARGET_PFS.items():
        subset = adtte.loc[adtte["TRT01A"] == arm, "AVAL"].dropna().sort_values()
        if len(subset) == 0:
            _check(
                r,
                f"PFS fidelity: {arm} arm present in ADTTE",
                False,
                "no records found",
            )
            continue

        # Simple observed median (events only give lower bound but is informative)
        median = subset.median()
        pct_dev = (median - target) / target * 100
        tol = target * PFS_TOLERANCE
        passed = abs(median - target) <= tol
        _check(
            r,
            f"PFS fidelity: {arm} median within ±20% of {target}d target",
            passed,
            f"observed={median:.0f}d, target={target}d, dev={pct_dev:+.1f}%",
        )

    return r


# ── report ───────────────────────────────────────────────────────────────────


def build_report(datasets: Path, categories: dict[str, list[CheckResult]], n_subjects: int) -> str:
    lines: list[str] = []
    lines.append("# Synthetic Dataset Validation Report")
    lines.append(f"**Study:** {STUDYID}  ")
    lines.append(f"**Datasets path:** {datasets}  ")
    lines.append(f"**Generated:** {date.today().isoformat()}  ")
    lines.append(f"**N subjects:** {n_subjects}")
    lines.append("")

    total_checks = total_passed = total_failed = 0
    summary_rows = []
    for cat_name, results in categories.items():
        n = len(results)
        p = sum(1 for x in results if x.passed)
        f = n - p
        total_checks += n
        total_passed += p
        total_failed += f
        summary_rows.append((cat_name, n, p, f))

    lines.append("## Summary")
    lines.append("")
    lines.append("| Category | Checks | Passed | Failed |")
    lines.append("|----------|--------|--------|--------|")
    for name, n, p, f in summary_rows:
        lines.append(f"| {name} | {n} | {p} | {f} |")
    overall = total_failed == 0
    verdict = "**PASS ✓**" if overall else "**FAIL ✗**"
    lines.append(f"| **Total** | **{total_checks}** | **{total_passed}** | **{total_failed}** |")
    lines.append("")
    lines.append(f"**Overall: {verdict}**")
    lines.append("")

    lines.append("## Detailed Results")
    for cat_name, results in categories.items():
        lines.append("")
        lines.append(f"### {cat_name}")
        for res in results:
            lines.append(str(res))

    # PFS fidelity table
    lines.append("")
    lines.append("### PFS Fidelity Detail")
    lines.append("")
    lines.append("| Arm | Observed Median (days) | Target (days) | Tolerance | Deviation | Result |")
    lines.append("|-----|------------------------|---------------|-----------|-----------|--------|")
    for res in categories.get("Category 7 — PFS Fidelity", []):
        if "observed=" in res.detail:
            # Strip trailing unit suffixes from values only, not from key names.
            # detail format: "observed=226d, target=314d, dev=+24.2%"
            parts = {}
            for token in res.detail.split(", "):
                key, val = token.split("=", 1)
                parts[key.strip()] = re.sub(r"[d%]+$", "", val.strip())
            obs = parts.get("observed", "?")
            tgt = parts.get("target", "?")
            dev = parts.get("dev", "?") + "%"
            arm = res.name.split(":")[1].strip().split(" ")[0]
            tol_str = f"±{int(float(tgt) * PFS_TOLERANCE):.0f}d" if tgt != "?" else ""
            result = "PASS" if res.passed else "FAIL"
            lines.append(f"| {arm} | {obs} | {tgt} | {tol_str} | {dev} | {result} |")

    return "\n".join(lines) + "\n"


# ── main ─────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Validate NCT01797120 datasets")
    parser.add_argument(
        "--datasets",
        default="./datasets",
        help="Path to directory containing CSV files",
    )
    parser.add_argument("--output", default="validation_report.md", help="Output markdown report path")
    args = parser.parse_args()

    datasets = Path(args.datasets).resolve()
    required = ["DM", "EX", "TR", "RS", "DS", "ADSL", "ADTTE"]
    missing = [f for f in required if not (datasets / f"{f}.csv").exists()]
    if missing:
        print(f"ERROR: Missing dataset files: {', '.join(m + '.csv' for m in missing)}")
        print(f"       Looked in: {datasets}")
        sys.exit(2)

    dm = pd.read_csv(datasets / "DM.csv", dtype=str, keep_default_na=False)
    n_subjects = len(dm)

    categories = {
        "Category 1 — CDISC Structural": check_structural(datasets),
        "Category 2 — Cross-domain Integrity": check_integrity(datasets),
        "Category 3 — RECIST Derivation": check_recist(datasets),
        "Category 4 — Timeline & Death Logic": check_timeline_death(datasets),
        "Category 5 — Population Distribution": check_population(datasets),
        "Category 6 — Duplicate & Study Consistency": check_duplicates_and_coverage(datasets),
        "Category 7 — PFS Fidelity": check_pfs_fidelity(datasets),
    }

    report = build_report(datasets, categories, n_subjects)

    out_path = Path(args.output)
    out_path.write_text(report)
    print(f"Report written to: {out_path}")

    total_failed = sum(1 for results in categories.values() for res in results if not res.passed)
    total = sum(len(v) for v in categories.values())
    print(f"Result: {total - total_failed}/{total} checks passed")

    sys.exit(1 if total_failed > 0 else 0)


if __name__ == "__main__":
    main()
