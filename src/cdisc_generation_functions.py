import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

STUDYID = "NCT01797120"

# Boundary between INDUCTION (blinded) and CONTINUATION (open) epochs: 12 x 28 days
_INDUCTION_DAYS = 12 * 28  # 336 days

# Progression parameters empirically calibrated (n=50k simulation) to match
# FHIR-published KM medians with U(60,600) censoring:
#   Treatment target: 10.3 months (314 days)  → p=0.85, exp scale=350 days
#   Placebo   target:  5.1 months (155 days)  → p=0.90, exp scale=195 days
_PROG = {
    "Treatment": {"prob": 0.85, "scale": 350},
    "Placebo":   {"prob": 0.90, "scale": 195},
}

# Tumour dynamics: responder/non-responder model calibrated to match FHIR-published ORR
# (Trt 18.2%, Pbo 12.3%).  Responders: −12 mm/visit drift; non-responders: +2 mm/visit.
_TUMOUR = {
    "Treatment": {"resp_frac": 0.21, "drift_resp": -12.0, "drift_nonresp": +2.0, "noise": 8.0},
    "Placebo":   {"resp_frac": 0.20, "drift_resp": -12.0, "drift_nonresp": +2.0, "noise": 8.0},
}

_ENROLL_START = datetime(2021, 1, 1)
_STUDY_END    = datetime(2026, 12, 31)
_MIN_LESION_MM = 5.0   # RECIST 1.1: "too small to measure" → 5 mm floor


def _fmt(d):
    """Format a date-like value as ISO-8601 string, or empty string if missing."""
    if d is None or (hasattr(d, "__class__") and d.__class__.__name__ == "NaTType"):
        return ""
    try:
        return pd.Timestamp(d).strftime("%Y-%m-%d")
    except Exception:
        return str(d)[:10]


def _study_day(event_date, rfstdtc):
    """CDISC study day: day 1 = RFSTDTC, no day 0 (days before baseline are negative)."""
    delta = (pd.Timestamp(str(event_date)[:10]) - pd.Timestamp(str(rfstdtc)[:10])).days
    return delta + 1 if delta >= 0 else delta


# ── DM ───────────────────────────────────────────────────────────────────────

def create_dm(n=200):
    # Balanced 1:1 randomisation via permutation
    arms = np.random.permutation(["Treatment"] * (n // 2) + ["Placebo"] * (n // 2))

    # Spread enrollment over a 24-month window (2021-01-01 to 2022-12-31)
    enroll_offsets = np.random.randint(0, 730, size=n)
    rfstdtc_dates = [_ENROLL_START + timedelta(days=int(d)) for d in enroll_offsets]

    # RFICDTC: informed consent 7–28 days before first study activity (RFSTDTC)
    ic_offsets = np.random.randint(7, 29, size=n)
    rficdtc = [
        (d - timedelta(days=int(ic))).strftime("%Y-%m-%d")
        for d, ic in zip(rfstdtc_dates, ic_offsets)
    ]
    rfstdtc = [d.strftime("%Y-%m-%d") for d in rfstdtc_dates]

    _race = np.random.choice(
        ["WHITE", "BLACK OR AFRICAN AMERICAN", "ASIAN", "OTHER"],
        size=n, p=[0.75, 0.12, 0.08, 0.05],
    )
    _ethnic = np.random.choice(
        ["NOT HISPANIC OR LATINO", "HISPANIC OR LATINO"],
        size=n, p=[0.85, 0.15],
    )

    dm = pd.DataFrame({
        "SUBJID":  [f"{i:04d}" for i in range(1, n + 1)],
        "AGE":     np.clip(np.random.normal(55, 10, n), 20, 80).astype(int),
        "AGEU":    "YEARS",
        "SEX":     "F",
        "RACE":    _race,
        "ETHNIC":  _ethnic,
        "RFICDTC": rficdtc,
        "RFSTDTC": rfstdtc,
        "TRT01A":  arms,  # internal helper; excluded from CSV DM output
        "ARMCD":   ["TRT" if a == "Treatment" else "PLC" for a in arms],
        "ARM": [
            "Fulvestrant + Everolimus" if a == "Treatment" else "Fulvestrant + Placebo"
            for a in arms
        ],
    })
    dm["STUDYID"]  = STUDYID
    dm["DOMAIN"]   = "DM"
    dm["USUBJID"]  = STUDYID + "-" + dm["SUBJID"]
    dm["SITEID"]   = "0001"
    dm["COUNTRY"]  = "USA"
    dm["ACTARMCD"] = dm["ARMCD"]
    dm["ACTARM"]   = dm["ARM"]
    return dm


def finalize_dm(dm, ex, events):
    """
    Add RFXSTDTC / RFXENDTC (from EX), DTHFL / DTHDTC (from events),
    and RFPENDTC (end of study participation, from events.FOLLOWUP_END).

    DTHDTC is constrained to be after RFXENDTC: a subject cannot die
    while still receiving treatment.
    """
    rfx = (
        ex.groupby("USUBJID")
        .agg(RFXSTDTC=("EXSTDTC", "min"), RFXENDTC=("EXENDTC", "max"))
        .reset_index()
    )
    dm = dm.merge(rfx, on="USUBJID", how="left")
    dm = dm.merge(
        events[["USUBJID", "DIED", "DTHDT", "FOLLOWUP_END"]], on="USUBJID", how="left"
    )

    dm["DTHFL"] = dm["DIED"].map({True: "Y"}).fillna("")

    def _safe_dthdtc(row):
        if row["DIED"] and pd.notna(row["DTHDT"]):
            rfxend = pd.Timestamp(str(row["RFXENDTC"])[:10])
            dthdtc = pd.Timestamp(row["DTHDT"])
            # Death must occur after end of treatment
            if dthdtc <= rfxend:
                dthdtc = rfxend + timedelta(days=max(1, int(np.random.exponential(30))))
                dthdtc = min(dthdtc, _STUDY_END)
            return dthdtc.strftime("%Y-%m-%d")
        return ""

    dm["DTHDTC"]   = dm.apply(_safe_dthdtc, axis=1)
    dm["RFPENDTC"] = dm.apply(
        lambda r: r["DTHDTC"] if (r["DTHFL"] == "Y" and r["DTHDTC"])
        else _fmt(r["FOLLOWUP_END"]),
        axis=1,
    )
    # CG0142: RFENDTC required for all treated subjects; equals RFPENDTC in this study
    dm["RFENDTC"] = dm["RFPENDTC"]
    dm = dm.drop(columns=["DIED", "DTHDT", "FOLLOWUP_END"])

    return dm[[
        "STUDYID", "DOMAIN", "USUBJID", "SUBJID",
        "RFSTDTC", "RFENDTC", "RFXSTDTC", "RFXENDTC", "RFICDTC", "RFPENDTC",
        "DTHDTC", "DTHFL", "SITEID", "AGE", "AGEU", "SEX", "RACE", "ETHNIC",
        "ARMCD", "ARM", "ACTARMCD", "ACTARM", "COUNTRY",
        "TRT01A",   # internal helper — stripped from CSV output in __main__
    ]]


# ── EX ───────────────────────────────────────────────────────────────────────

def create_ex(dm):
    """
    Two drug records per subject:
      FULVESTRANT IM: 250 mg on C1D1 and C1D15 (loading doses), then 500 mg Q28D
      EVEROLIMUS 10 mg oral (TRT) or PLACEBO 10 mg oral (PLC): one spanning record

    EXSTDY / EXENDY are populated relative to RFSTDTC (= RFXSTDTC in this trial).
    """
    rfstdtc_map = dm.set_index("USUBJID")["RFSTDTC"].to_dict()
    records = []

    for _, row in dm.iterrows():
        usubjid = row["USUBJID"]
        arm     = row["TRT01A"]
        rfstdtc = datetime.strptime(rfstdtc_map[usubjid], "%Y-%m-%d")
        start   = rfstdtc           # RFXSTDTC = RFSTDTC for this trial
        dur     = int(np.random.uniform(60, 600))
        end     = start + timedelta(days=dur)

        # Fulvestrant injection schedule
        # C1D1 and C1D15: 250 mg each (loading doses); subsequent cycles: 500 mg Q28D
        inj_schedule = [(0, 250), (14, 250)]
        cycle_day = 28
        while start + timedelta(days=cycle_day) <= end:
            inj_schedule.append((cycle_day, 500))
            cycle_day += 28

        seq = 1
        for offset, dose in inj_schedule:
            inj_date = start + timedelta(days=offset)
            stdy = _study_day(inj_date, rfstdtc)
            ex_epoch = "INDUCTION" if offset <= _INDUCTION_DAYS else "CONTINUATION"
            records.append({
                "STUDYID": STUDYID, "DOMAIN": "EX", "USUBJID": usubjid,
                "EXSEQ": seq, "EXTRT": "FULVESTRANT",
                "EXDOSE": dose, "EXDOSU": "mg", "EXDOSFRM": "SOLUTION",
                "EXDOSFRQ": "ONCE", "EXROUTE": "INTRAMUSCULAR",
                "EXSTDTC": inj_date.strftime("%Y-%m-%d"),
                "EXENDTC": inj_date.strftime("%Y-%m-%d"),
                "EXSTDY": stdy, "EXENDY": stdy,
                "EPOCH": ex_epoch,
            })
            seq += 1

        # Everolimus (TRT) or Placebo (PLC): one continuous record spanning the period
        # Per CG0102: EXTRT=PLACEBO must have EXDOSE=0
        second_drug = "EVEROLIMUS" if arm == "Treatment" else "PLACEBO"
        second_dose = 10 if arm == "Treatment" else 0
        records.append({
            "STUDYID": STUDYID, "DOMAIN": "EX", "USUBJID": usubjid,
            "EXSEQ": seq, "EXTRT": second_drug,
            "EXDOSE": second_dose, "EXDOSU": "mg", "EXDOSFRM": "TABLET",
            "EXDOSFRQ": "QD", "EXROUTE": "ORAL",
            "EXSTDTC": start.strftime("%Y-%m-%d"),
            "EXENDTC": end.strftime("%Y-%m-%d"),
            "EXSTDY": _study_day(start, rfstdtc),
            "EXENDY": _study_day(end,   rfstdtc),
            "EPOCH": "INDUCTION",
        })

    return pd.DataFrame(records)


def finalize_ex(ex, events, dm):
    """
    Remove EX records that start after a subject's progression date, and cap
    EXENDTC (and EXENDY) at that date.  This ensures RFXENDTC derived from EX
    correctly reflects when treatment actually stopped for progressors.
    """
    rfstdtc_map = dm.set_index("USUBJID")["RFSTDTC"].to_dict()
    prog_map = (
        events.dropna(subset=["PROGDT"])
        .set_index("USUBJID")["PROGDT"]
        .apply(lambda x: pd.Timestamp(x))
        .to_dict()
    )

    ex = ex.copy()
    ex["_stdt"] = pd.to_datetime(ex["EXSTDTC"])
    ex["_endt"] = pd.to_datetime(ex["EXENDTC"])

    keep = []
    for _, row in ex.iterrows():
        uid = row["USUBJID"]
        if uid in prog_map:
            prog = prog_map[uid]
            if row["_stdt"] > prog:
                continue  # drop records that begin after progression
            if row["_endt"] > prog:
                row = row.copy()
                row["EXENDTC"] = prog.strftime("%Y-%m-%d")
                row["_endt"]   = prog
                row["EXENDY"]  = _study_day(prog, rfstdtc_map[uid])
        keep.append(row)

    return (
        pd.DataFrame(keep)
        .drop(columns=["_stdt", "_endt"])
        .reset_index(drop=True)
    )


# ── EVENTS (internal) ────────────────────────────────────────────────────────

def derive_events(ex, dm):
    """
    One row per subject with columns:
      PROGDT, RESPONDER, WITHDRAWAL, DIED, DTHDT, FOLLOWUP_END.

    FOLLOWUP_END is the end of study participation — it drives RFPENDTC in DM
    and the date of the STUDY PARTICIPATION disposition record in DS.
    For progressors treatment ends at PROGDT, so follow-up is measured from there.
    """
    ex_start = ex.groupby("USUBJID")["EXSTDTC"].min().reset_index()
    ex_end   = ex.groupby("USUBJID")["EXENDTC"].max().reset_index()
    merged   = ex_start.merge(dm[["USUBJID", "TRT01A"]])

    records = []
    for _, row in merged.iterrows():
        start  = datetime.strptime(str(row["EXSTDTC"])[:10], "%Y-%m-%d")
        arm    = row["TRT01A"]
        params = _PROG[arm]
        if np.random.rand() < params["prob"]:
            days   = max(84, int(np.random.exponential(params["scale"])))
            progdt = start + timedelta(days=days)
        else:
            progdt = None
        responder = np.random.rand() < _TUMOUR[arm]["resp_frac"]
        records.append({"USUBJID": row["USUBJID"], "PROGDT": progdt, "RESPONDER": responder})

    events = pd.DataFrame(records)
    no_prog = events["PROGDT"].isna()
    events["WITHDRAWAL"] = no_prog & (np.random.rand(len(events)) < 0.20)

    events = events.merge(ex_end, on="USUBJID", how="left")
    died_list, dthdt_list, followup_list = [], [], []

    for _, row in events.iterrows():
        progdt     = row["PROGDT"]
        withdrawal = bool(row["WITHDRAWAL"])
        exendtc    = datetime.strptime(str(row["EXENDTC"])[:10], "%Y-%m-%d")
        # Effective treatment end: progression date for progressors, EX end for others
        tx_end = progdt if (progdt is not None and pd.notna(progdt)) else exendtc

        if progdt is not None and pd.notna(progdt):
            if np.random.rand() < 0.75:
                days   = max(1, int(np.random.exponential(180)))
                dthdtc = min(tx_end + timedelta(days=days), _STUDY_END)
                died_list.append(True)
                dthdt_list.append(dthdtc)
                followup_list.append(dthdtc)
            else:
                died_list.append(False)
                dthdt_list.append(None)
                fu_end = min(tx_end + timedelta(days=int(np.random.uniform(30, 180))), _STUDY_END)
                followup_list.append(fu_end)
        elif withdrawal:
            if np.random.rand() < 0.15:
                days   = max(1, int(np.random.exponential(365)))
                dthdtc = min(tx_end + timedelta(days=days), _STUDY_END)
                died_list.append(True)
                dthdt_list.append(dthdtc)
                followup_list.append(dthdtc)
            else:
                died_list.append(False)
                dthdt_list.append(None)
                followup_list.append(tx_end)  # withdrew, participation ends with treatment
        else:
            died_list.append(False)
            dthdt_list.append(None)
            fu_end = min(tx_end + timedelta(days=int(np.random.uniform(30, 120))), _STUDY_END)
            followup_list.append(fu_end)

    events["DIED"]         = died_list
    events["DTHDT"]        = dthdt_list
    events["FOLLOWUP_END"] = followup_list
    return events.drop(columns=["EXENDTC"])


# ── TR ───────────────────────────────────────────────────────────────────────

_NE_PROB = 0.03   # probability that any individual post-baseline assessment is not evaluable

def _tr_record(studyid, usubjid, seq, testcd, test, grpid, lnkid,
               trstresn, trdtc, visitnum, visit, trdy, trlobxfl, epoch,
               trstat="", trreasnd=""):
    _resn_str = str(trstresn) if trstresn != "" else ""
    return {
        "STUDYID": studyid, "DOMAIN": "TR",
        "USUBJID":  usubjid, "TRSEQ": seq,
        "TRTESTCD": testcd,  "TRTEST": test,
        "TRGRPID":  grpid,   "TRLNKID": lnkid,
        "TRORRES":  _resn_str, "TRSTRESC": _resn_str,
        "TRSTRESN": trstresn, "TRSTRESU": "mm",
        "TRSTAT":   trstat,   "TRREASND": trreasnd,
        "TRMETHOD": "CT SCAN", "TREVAL": "INVESTIGATOR",
        "TRDTC": trdtc, "VISITNUM": visitnum, "VISIT": visit,
        "TRDY": trdy, "TRLOBXFL": trlobxfl, "EPOCH": epoch,
    }


def create_tr(ex, events, dm):
    """
    RECIST target lesion measurements per SDTMIG and the CDISC RECIST 1.1 supplement.

    Per subject:
      - 1–3 target lesions (TRTESTCD=LDIAM, TRGRPID=TARGET LESION N, TRLNKID=TLN)
      - One SUMDIAM aggregate record per visit (TRTESTCD=SUMDIAM, TRGRPID=TARGET)
      - Baseline records carry LOBXFL=Y

    Tumour dynamics:
      - Minimum measurable lesion: 5 mm (RECIST floor for visible lesions)
      - Absent lesion: 0 mm (complete disappearance; allowed for strong responders)
      - ~3% of post-baseline visits are not evaluable (TRSTAT=NOT DONE)
    """
    tr  = []
    seq = 1

    ex_starts = ex.groupby("USUBJID")["EXSTDTC"].min().reset_index()
    ex_starts["EXSTDTC"] = pd.to_datetime(ex_starts["EXSTDTC"])
    ex_end_map = pd.to_datetime(ex.groupby("USUBJID")["EXENDTC"].max()).to_dict()
    merged = (
        ex_starts
        .merge(events[["USUBJID", "PROGDT", "RESPONDER"]])
        .merge(dm[["USUBJID", "TRT01A", "RFSTDTC"]])
    )

    for _, row in merged.iterrows():
        uid         = row["USUBJID"]
        arm         = row["TRT01A"]
        rfstdtc_str = str(row["RFSTDTC"])[:10]
        tp    = _TUMOUR[arm]
        drift = tp["drift_resp"] if row["RESPONDER"] else tp["drift_nonresp"]
        noise = tp["noise"]

        n_lesions     = int(np.random.choice([1, 2, 3], p=[0.3, 0.5, 0.2]))
        baseline_sizes = np.maximum(np.random.normal(25, 8, n_lesions), _MIN_LESION_MM)
        current_sizes  = baseline_sizes.copy()
        baseline_date  = row["EXSTDTC"]
        bl_dtc         = baseline_date.strftime("%Y-%m-%d")

        # Baseline LDIAM records
        for li in range(n_lesions):
            tr.append(_tr_record(
                STUDYID, uid, seq,
                "LDIAM", "Longest Diameter",
                f"TARGET LESION {li + 1}", f"TL{li + 1}",
                round(float(baseline_sizes[li]), 2),
                bl_dtc, 2, "BASELINE", 1, "Y", "INDUCTION",
            )); seq += 1

        # Baseline SUMDIAM aggregate
        bl_sumd = round(float(sum(baseline_sizes)), 2)
        tr.append(_tr_record(
            STUDYID, uid, seq,
            "SUMDIAM", "Sum of Diameter", "TARGET", "",
            bl_sumd, bl_dtc, 2, "BASELINE", 1, "Y", "INDUCTION",
        )); seq += 1

        progdt  = row["PROGDT"]
        ex_end  = ex_end_map.get(uid)

        for v, day in enumerate(range(85, 1500, 84), start=1):
            date = row["EXSTDTC"] + timedelta(days=day)
            if progdt is not None and pd.notna(progdt) and date > progdt:
                break
            if ex_end is not None and date > ex_end:
                break

            dtc      = date.strftime("%Y-%m-%d")
            visitnum = v + 2
            visit    = f"WEEK {v * 12}"
            epoch    = "INDUCTION" if day <= _INDUCTION_DAYS else "CONTINUATION"
            trdy     = _study_day(date, rfstdtc_str)

            # ~3% of visits are not evaluable (imaging quality)
            if np.random.rand() < _NE_PROB:
                for li in range(n_lesions):
                    tr.append(_tr_record(
                        STUDYID, uid, seq,
                        "LDIAM", "Longest Diameter",
                        f"TARGET LESION {li + 1}", f"TL{li + 1}",
                        "", dtc, visitnum, visit, trdy, "", epoch,
                        trstat="NOT DONE", trreasnd="IMAGING QUALITY ISSUES",
                    )); seq += 1
                tr.append(_tr_record(
                    STUDYID, uid, seq,
                    "SUMDIAM", "Sum of Diameter", "TARGET", "",
                    "", dtc, visitnum, visit, trdy, "", epoch,
                    trstat="NOT DONE", trreasnd="IMAGING QUALITY ISSUES",
                )); seq += 1
                continue

            # Normal visit: update each lesion
            for li in range(n_lesions):
                new_size = current_sizes[li] + np.random.normal(drift, noise)
                if row["RESPONDER"] and new_size <= _MIN_LESION_MM and np.random.rand() < 0.25:
                    current_sizes[li] = 0.0   # lesion absent — CR possible
                else:
                    current_sizes[li] = max(_MIN_LESION_MM, new_size)
                tr.append(_tr_record(
                    STUDYID, uid, seq,
                    "LDIAM", "Longest Diameter",
                    f"TARGET LESION {li + 1}", f"TL{li + 1}",
                    round(float(current_sizes[li]), 2),
                    dtc, visitnum, visit, trdy, "", epoch,
                )); seq += 1

            sumd = round(float(sum(current_sizes[:n_lesions])), 2)
            tr.append(_tr_record(
                STUDYID, uid, seq,
                "SUMDIAM", "Sum of Diameter", "TARGET", "",
                sumd, dtc, visitnum, visit, trdy, "", epoch,
            )); seq += 1

    return pd.DataFrame(tr)


# ── RS ───────────────────────────────────────────────────────────────────────

def derive_rs(tr):
    """
    RECIST overall response derived from SUMDIAM records in TR.

    Response rules (RECIST 1.1):
      CR  — SUMD = 0 (all target lesions absent)
      PR  — SUMD ≤ −30% of baseline SUMD
      PD  — SUMD ≥ +20% of baseline SUMD (or nadir, simplified here to baseline)
      SD  — all other evaluable visits
      NE  — visit not evaluable (TRSTAT = NOT DONE on the SUMDIAM record)

    Stops generating RS records after the first PD — once progression is declared
    the subject is taken off treatment and receives no further tumour assessments.
    """
    tr = tr.copy()
    tr["TRSTRESN"] = pd.to_numeric(tr["TRSTRESN"], errors="coerce")

    sumdiam = tr[tr["TRTESTCD"] == "SUMDIAM"].copy()

    # Baseline SUMDIAM (LOBXFL=Y)
    baseline_sumd = (
        sumdiam[sumdiam["TRLOBXFL"] == "Y"]
        .set_index("USUBJID")["TRSTRESN"]
        .rename("BASE_SUMD")
    )

    # Post-baseline SUMDIAM rows
    post = (
        sumdiam[sumdiam["TRLOBXFL"] != "Y"]
        .merge(baseline_sumd.reset_index(), on="USUBJID", how="left")
    )

    def _resp(row):
        if row.get("TRSTAT", "") == "NOT DONE" or pd.isna(row["TRSTRESN"]):
            return "NE"
        if row["TRSTRESN"] == 0:
            return "CR"
        base = row["BASE_SUMD"]
        if pd.isna(base) or base == 0:
            return "NE"
        pct = (row["TRSTRESN"] - base) / base * 100
        if pct <= -30:
            return "PR"
        if pct >= 20:
            return "PD"
        return "SD"

    post["RSSTRESC"] = post.apply(_resp, axis=1)

    rs  = []
    seq = 1
    for usubjid, grp in post.groupby("USUBJID", sort=False):
        for _, row in grp.sort_values("TRDY").iterrows():
            rs_epoch = "INDUCTION" if int(row["TRDY"]) <= _INDUCTION_DAYS else "CONTINUATION"
            rs.append({
                "STUDYID":  STUDYID, "DOMAIN": "RS",
                "USUBJID":  usubjid,
                "RSSEQ":    seq,
                "RSTESTCD": "OVRLRESP", "RSTEST": "Overall Response",
                "RSSTRESC": row["RSSTRESC"],
                "RSDTC":    row["TRDTC"],
                "VISITNUM": row["VISITNUM"],
                "VISIT":    row["VISIT"],
                "RSDY":     int(row["TRDY"]),
                "EPOCH":    rs_epoch,
                "RSDRVFL":  "Y",
            })
            seq += 1
            if row["RSSTRESC"] == "PD":
                break

    df = pd.DataFrame(rs)
    df["RSCAT"]   = "TUMOR MEASUREMENT"
    df["RSORRES"] = df["RSSTRESC"]
    return df[[
        "STUDYID", "DOMAIN", "USUBJID", "RSSEQ", "RSTESTCD", "RSTEST",
        "RSCAT", "RSORRES", "RSSTRESC",
        "RSDTC", "VISITNUM", "VISIT", "RSDY", "EPOCH", "RSDRVFL",
    ]]


# ── TU ───────────────────────────────────────────────────────────────────────

# Common metastatic sites for HR+ breast cancer (weighted toward most frequent)
_TU_SITES = [
    "BONE", "BONE", "LIVER", "LIVER", "LUNG", "LUNG",
    "LYMPH NODE", "BREAST", "SKIN", "PLEURA",
]
_TU_LAT = {
    "BONE":        [""],
    "LIVER":       [""],
    "LUNG":        ["LEFT", "RIGHT", "BILATERAL"],
    "LYMPH NODE":  ["LEFT", "RIGHT"],
    "BREAST":      ["LEFT", "RIGHT"],
    "SKIN":        ["LEFT", "RIGHT"],
    "PLEURA":      ["LEFT", "RIGHT"],
}


def create_tu(dm, tr):
    """
    TU domain: Tumor Identification (required by RECIST 1.1 SDTM supplement).
    Per subject:
      TIND   — confirms subject has measurable target disease (Y)
      NTIND  — confirms absence of non-target disease (N, simplified)
      TUMIDENT — one record per target lesion, linked via TULNKID = TR.TRLNKID
    All records at VISITNUM=1 (SCREENING), dated to RFSTDTC.
    """
    rfstdtc_map = dm.set_index("USUBJID")["RFSTDTC"].to_dict()
    # Lesion baselines from TR (LDIAM + LOBXFL=Y, excludes SUMDIAM)
    ldiam_bl = tr[(tr["TRTESTCD"] == "LDIAM") & (tr["TRLOBXFL"] == "Y")]

    tu  = []
    seq = 1
    for uid, lesions in ldiam_bl.groupby("USUBJID"):
        rfstdtc = rfstdtc_map.get(uid, "")

        tu.append({
            "STUDYID": STUDYID, "DOMAIN": "TU", "USUBJID": uid, "TUSEQ": seq,
            "TUTESTCD": "TIND", "TUTEST": "Target Indicator",
            "TULNKID": "", "TUORRES": "Y", "TUSTRESC": "Y",
            "TULOC": "", "TULAT": "", "TUMETHOD": "CT SCAN", "TUEVAL": "INVESTIGATOR",
            "EPOCH": "SCREENING", "VISITNUM": 1, "VISIT": "SCREENING",
            "TUDTC": rfstdtc, "TUDY": 1,
        }); seq += 1

        tu.append({
            "STUDYID": STUDYID, "DOMAIN": "TU", "USUBJID": uid, "TUSEQ": seq,
            "TUTESTCD": "NTIND", "TUTEST": "Non-Target Indicator",
            "TULNKID": "", "TUORRES": "N", "TUSTRESC": "N",
            "TULOC": "", "TULAT": "", "TUMETHOD": "CT SCAN", "TUEVAL": "INVESTIGATOR",
            "EPOCH": "SCREENING", "VISITNUM": 1, "VISIT": "SCREENING",
            "TUDTC": rfstdtc, "TUDY": 1,
        }); seq += 1

        for _, lesion in lesions.iterrows():
            loc = np.random.choice(_TU_SITES)
            lat = np.random.choice(_TU_LAT.get(loc, [""]))
            tu.append({
                "STUDYID": STUDYID, "DOMAIN": "TU", "USUBJID": uid, "TUSEQ": seq,
                "TUTESTCD": "TUMIDENT", "TUTEST": "Tumor Identification",
                "TULNKID": lesion["TRLNKID"],
                "TUORRES": "TARGET", "TUSTRESC": "TARGET",
                "TULOC": loc, "TULAT": lat,
                "TUMETHOD": "CT SCAN", "TUEVAL": "INVESTIGATOR",
                "EPOCH": "SCREENING", "VISITNUM": 1, "VISIT": "SCREENING",
                "TUDTC": rfstdtc, "TUDY": 1,
            }); seq += 1

    df = pd.DataFrame(tu)
    df["TULOBXFL"] = "Y"
    return df[[
        "STUDYID", "DOMAIN", "USUBJID", "TUSEQ", "TUTESTCD", "TUTEST",
        "TULNKID", "TUORRES", "TUSTRESC", "TULOC", "TULAT",
        "TUMETHOD", "TUEVAL", "TULOBXFL",
        "EPOCH", "VISITNUM", "VISIT", "TUDTC", "TUDY",
    ]]


# ── DS ───────────────────────────────────────────────────────────────────────

def create_ds(dm, ex, events):
    """
    DS records per subject (5 records each):
      1. INFORMED CONSENT OBTAINED   (PROTOCOL MILESTONE / SCREENING)
      2. RANDOMIZED                  (PROTOCOL MILESTONE / SCREENING)
      3. FULVESTRANT stop            (DISPOSITION EVENT / INDUCTION or CONTINUATION)
      4. EVEROLIMUS or PLACEBO stop  (DISPOSITION EVENT / INDUCTION or CONTINUATION)
      5. STUDY PARTICIPATION end     (DISPOSITION EVENT / FOLLOW-UP)
             DSDECOD=DEATH for deceased subjects, else withdrawal/LTFU reason

    Treatment epoch for records 3–4:
      INDUCTION   if treatment duration ≤ 336 days (12 × 28)
      CONTINUATION if treatment duration  > 336 days
    """
    ex_dates = (
        ex.groupby("USUBJID")
        .agg(EXSTDTC=("EXSTDTC", "min"), EXENDTC=("EXENDTC", "max"))
        .reset_index()
    )
    # Use finalized DM for DTHFL/DTHDTC so DS DEATH date matches DM exactly (FB0611)
    core = (
        dm[["USUBJID", "RFICDTC", "RFSTDTC", "ARMCD", "DTHFL", "DTHDTC"]]
        .merge(ex_dates, on="USUBJID")
        .merge(
            events[["USUBJID", "PROGDT", "WITHDRAWAL", "FOLLOWUP_END"]],
            on="USUBJID",
            how="left",
        )
    )

    ds = []
    for _, row in core.iterrows():
        progdt     = row["PROGDT"]
        has_prog   = pd.notna(progdt)
        withdrawal = bool(row["WITHDRAWAL"])
        did_die    = (row["DTHFL"] == "Y")
        arm        = row["ARMCD"]

        exstdtc = datetime.strptime(str(row["EXSTDTC"])[:10], "%Y-%m-%d")
        exendtc = datetime.strptime(str(row["EXENDTC"])[:10], "%Y-%m-%d")
        tx_days = (exendtc - exstdtc).days
        tx_epoch = "INDUCTION" if tx_days <= _INDUCTION_DAYS else "CONTINUATION"

        if has_prog:
            stop_reason = "PROGRESSIVE DISEASE"
            stop_dtc    = _fmt(progdt)
        elif withdrawal:
            stop_reason = "WITHDRAWAL BY SUBJECT"
            stop_dtc    = str(row["EXENDTC"])[:10]
        else:
            stop_reason = "LOST TO FOLLOW-UP"
            stop_dtc    = str(row["EXENDTC"])[:10]

        # Use DM DTHDTC directly — ensures DS DEATH date = DM DTHDTC (FB0611)
        if did_die and row["DTHDTC"]:
            final_reason = "DEATH"
            final_dtc    = str(row["DTHDTC"])[:10]
        else:
            final_reason = stop_reason
            final_dtc    = _fmt(row["FOLLOWUP_END"])

        secondary = "EVEROLIMUS" if arm == "TRT" else "PLACEBO"
        seq = 1

        # 1. Informed consent
        # CG0066: DSTERM must equal DSDECOD for PROTOCOL MILESTONE records
        # FB2201: EPOCH required for all subject-level clinical observations
        ds.append({
            "STUDYID": STUDYID, "DOMAIN": "DS", "USUBJID": row["USUBJID"],
            "DSSEQ": seq, "DSCAT": "PROTOCOL MILESTONE", "DSSCAT": "",
            "DSTERM": "INFORMED CONSENT OBTAINED",
            "DSDECOD": "INFORMED CONSENT OBTAINED",
            "DSSTDTC": str(row["RFICDTC"])[:10], "EPOCH": "SCREENING",
        }); seq += 1

        # 2. Randomization
        ds.append({
            "STUDYID": STUDYID, "DOMAIN": "DS", "USUBJID": row["USUBJID"],
            "DSSEQ": seq, "DSCAT": "PROTOCOL MILESTONE", "DSSCAT": "",
            "DSTERM": "RANDOMIZED",
            "DSDECOD": "RANDOMIZED",
            "DSSTDTC": str(row["RFSTDTC"])[:10], "EPOCH": "SCREENING",
        }); seq += 1

        # 3. Fulvestrant discontinuation
        ds.append({
            "STUDYID": STUDYID, "DOMAIN": "DS", "USUBJID": row["USUBJID"],
            "DSSEQ": seq, "DSCAT": "DISPOSITION EVENT", "DSSCAT": "FULVESTRANT",
            "DSTERM": stop_reason, "DSDECOD": stop_reason,
            "DSSTDTC": stop_dtc, "EPOCH": tx_epoch,
        }); seq += 1

        # 4. Everolimus / Placebo discontinuation
        ds.append({
            "STUDYID": STUDYID, "DOMAIN": "DS", "USUBJID": row["USUBJID"],
            "DSSEQ": seq, "DSCAT": "DISPOSITION EVENT", "DSSCAT": secondary,
            "DSTERM": stop_reason, "DSDECOD": stop_reason,
            "DSSTDTC": stop_dtc, "EPOCH": tx_epoch,
        }); seq += 1

        # 5. End of study participation (all subjects)
        ds.append({
            "STUDYID": STUDYID, "DOMAIN": "DS", "USUBJID": row["USUBJID"],
            "DSSEQ": seq, "DSCAT": "DISPOSITION EVENT", "DSSCAT": "STUDY PARTICIPATION",
            "DSTERM": final_reason, "DSDECOD": final_reason,
            "DSSTDTC": final_dtc, "EPOCH": "FOLLOW-UP",
        })

    df = pd.DataFrame(ds)
    _rfstdtc_ds = dm.set_index("USUBJID")["RFSTDTC"].to_dict()
    df["DSSTDY"] = df.apply(
        lambda r: _study_day(r["DSSTDTC"], _rfstdtc_ds[r["USUBJID"]]) if r["DSSTDTC"] else "",
        axis=1,
    )
    return df[[
        "STUDYID", "DOMAIN", "USUBJID", "DSSEQ", "DSCAT", "DSSCAT",
        "DSTERM", "DSDECOD", "DSSTDTC", "DSSTDY", "EPOCH",
    ]]


# ── FA ────────────────────────────────────────────────────────────────────────

def create_fa(ds):
    """
    FA domain: Findings About — satisfies CG0603, which requires that for every
    DS record with a non-null DSDECOD there is a corresponding FA record where
    FAOBJ = DSDECOD.
    """
    fa_rows = []
    seq = 1
    for _, row in ds[ds["DSDECOD"].notna() & (ds["DSDECOD"] != "")].iterrows():
        fa_rows.append({
            "STUDYID":  STUDYID,
            "DOMAIN":   "FA",
            "USUBJID":  row["USUBJID"],
            "FASEQ":    seq,
            "FATESTCD": "OCCUR",
            "FATEST":   "Occurrence Indicator",
            "FAOBJ":    row["DSDECOD"],
            "FAORRES":  "Y",
            "FASTRESC": "Y",
            "EPOCH":    row["EPOCH"],
            "FADTC":    row["DSSTDTC"],
        })
        seq += 1
    return pd.DataFrame(fa_rows)


# ── RELREC ───────────────────────────────────────────────────────────────────

def create_relrec(fa, ds):
    """
    RELREC domain: Related Records — for each FA record, creates a row linking
    it to its parent DS record (FAOBJ = DSDECOD), satisfying CG0603 (CORE-000767).
    """
    ds_idx = ds.groupby(["USUBJID", "DSDECOD"])["DSSEQ"].apply(list).to_dict()
    rows = []
    for _, fa_row in fa.iterrows():
        for dsseq in ds_idx.get((fa_row["USUBJID"], fa_row["FAOBJ"]), []):
            rows.append({
                "STUDYID":  STUDYID,
                "RDOMAIN":  "DS",
                "USUBJID":  fa_row["USUBJID"],
                "IDVAR":    "FASEQ",
                "IDVARVAL": str(int(fa_row["FASEQ"])),
                "RELTYPE":  "",
                "RELID":    str(int(dsseq)),
            })
    return pd.DataFrame(rows)


# ── ADSL ─────────────────────────────────────────────────────────────────────

def _best_response(responses):
    for r in ("PR", "SD", "PD"):
        if r in responses.values:
            return r
    return ""


def create_adsl(dm, ex, rs, events):
    ex_dates = (
        ex.groupby("USUBJID")
        .agg(EXSTDTC=("EXSTDTC", "min"), EXENDTC=("EXENDTC", "max"))
        .reset_index()
    )
    ex_dates["EXSTDTC"] = pd.to_datetime(ex_dates["EXSTDTC"])
    ex_dates["EXENDTC"] = pd.to_datetime(ex_dates["EXENDTC"])

    bestresp_map = rs.groupby("USUBJID")["RSSTRESC"].apply(_best_response).to_dict()

    dm_copy        = dm.copy()
    dm_copy["TRT01A"] = dm_copy["ARMCD"].map({"TRT": "Treatment", "PLC": "Placebo"})

    core = (
        dm_copy[["USUBJID", "TRT01A", "AGE"]]
        .merge(ex_dates[["USUBJID", "EXSTDTC", "EXENDTC"]])
        .merge(events[["USUBJID", "PROGDT", "WITHDRAWAL"]], on="USUBJID", how="left")
    )

    records = []
    for _, row in core.iterrows():
        progdt = row["PROGDT"]
        if pd.notna(progdt):
            pfs    = (progdt - row["EXSTDTC"]).days
            cnsr   = 0
            dcsreas = "PROGRESSIVE DISEASE"
        else:
            pfs    = (row["EXENDTC"] - row["EXSTDTC"]).days
            cnsr   = 1
            dcsreas = "WITHDRAWAL BY SUBJECT" if row["WITHDRAWAL"] else "LOST TO FOLLOW-UP"

        records.append({
            "STUDYID":  STUDYID,
            "USUBJID":  row["USUBJID"],
            "TRT01P":   row["TRT01A"],   # planned = actual (no crossover in this study)
            "TRT01A":   row["TRT01A"],
            "AGE":      row["AGE"],
            "PFS":      pfs,
            "CNSR":     cnsr,
            "BESTRESP": bestresp_map.get(row["USUBJID"], ""),
            "DCSREAS":  dcsreas,
            "ITTFL":    "Y",   # all randomised subjects are in the ITT population
            "SAFFL":    "Y",   # all subjects with ≥1 treatment exposure
            "PPROTFL":  "N" if dcsreas == "LOST TO FOLLOW-UP" else "Y",
        })

    return pd.DataFrame(records)


# ── ADTTE ─────────────────────────────────────────────────────────────────────

def create_adtte(adsl):
    return pd.DataFrame([
        {
            "STUDYID": STUDYID,
            "USUBJID": row["USUBJID"],
            "PARAMCD": "PFS",
            "PARAM":   "Progression-Free Survival",
            "AVAL":    float(row["PFS"]),
            "CNSR":    row["CNSR"],
            "TRT01A":  row["TRT01A"],
        }
        for _, row in adsl.iterrows()
    ])


# ── TV ────────────────────────────────────────────────────────────────────────

def create_tv():
    """
    Planned visit schedule through approximately 18 cycles (~1500 days).
    Assessment visits are assigned to INDUCTION or CONTINUATION epoch based on
    the 12-cycle (336-day) boundary.
    """
    # Tuples: (VISITNUM, VISIT, VISITDY, TVSTRL, TVENRL, EPOCH)
    # END OF TREATMENT is excluded — it has no defined planned study day and
    # TVSTRL would be null, violating CORE-000356 (required variable null).
    visits = [
        (1, "SCREENING",  -14, -14, 0,   "SCREENING"),
        (2, "BASELINE",     1,   1, 1,   "INDUCTION"),
    ]
    for v, day in enumerate(range(85, 1500, 84), start=1):
        epoch = "INDUCTION" if day <= _INDUCTION_DAYS else "CONTINUATION"
        visits.append((v + 2, f"WEEK {v * 12}", day, day, day, epoch))

    return pd.DataFrame([
        {
            "STUDYID": STUDYID, "DOMAIN": "TV",
            "VISITNUM": vn, "VISIT": v, "VISITDY": vd,
            "ARMCD": "", "TVSTRL": s, "TVENRL": e, "EPOCH": ep,
        }
        for vn, v, vd, s, e, ep in visits
    ])


# ── TA ────────────────────────────────────────────────────────────────────────

def create_ta():
    """
    Trial arms with four epochs:
      SCREENING    → subject randomised
      INDUCTION    → blinded treatment (TRT: Fulv + Ever; PLC: Fulv + Pbo)
      CONTINUATION → open-label (TRT: Fulv + Ever; PLC: Fulv only — placebo discontinued)
      FOLLOW-UP    → survival follow-up after treatment ends

    TRANS captures the conditional branch to FOLLOW-UP on PD or unacceptable toxicity.
    """
    rows = []
    for armcd, arm, induction_el, continuation_el in [
        ("TRT", "Fulvestrant + Everolimus",
         "Fulvestrant + Everolimus",   "Fulvestrant + Everolimus"),
        ("PLC", "Fulvestrant + Placebo",
         "Fulvestrant + Placebo",      "Fulvestrant"),
    ]:
        epochs = [
            (1, "Screen",          "",               "Subject randomised",                              "SCREENING"),
            (2, induction_el,      "",               "If PD or unacceptable toxicity, go to Follow-Up", "INDUCTION"),
            (3, continuation_el,   "",               "If PD or unacceptable toxicity, go to Follow-Up", "CONTINUATION"),
            (4, "Follow-Up",       "",               "",                                                "FOLLOW-UP"),
        ]
        _etcd_map = {"SCREENING": "SCRN", "INDUCTION": "IND",
                     "CONTINUATION": "CONT", "FOLLOW-UP": "FLWP"}
        for taetord, element, tabranch, tatrans, epoch in epochs:
            rows.append({
                "STUDYID":  STUDYID, "DOMAIN": "TA",
                "ARMCD":    armcd,   "ARM": arm,
                "TAETORD":  taetord,
                "ETCD":     _etcd_map[epoch],
                "ELEMENT":  element,
                "TABRANCH": tabranch,
                "TATRANS":  tatrans,
                "EPOCH":    epoch,
            })
    return pd.DataFrame(rows)


# ── MAIN ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    np.random.seed(0)

    out_dir = os.path.join(os.path.dirname(__file__), "..", "datasets")
    os.makedirs(out_dir, exist_ok=True)

    dm      = create_dm(n=200)
    ex      = create_ex(dm)
    events  = derive_events(ex, dm)
    ex      = finalize_ex(ex, events, dm)      # cap EX dates at progression
    tr      = create_tr(ex, events, dm)        # needs TRT01A; run before finalize_dm
    rs      = derive_rs(tr)
    tu      = create_tu(dm, tr)                # tumor identification; needs TR baselines
    dm      = finalize_dm(dm, ex, events)
    ds      = create_ds(dm, ex, events)
    fa      = create_fa(ds)                    # findings about DS disposition events
    relrec  = create_relrec(fa, ds)            # links FA records to parent DS records (CG0603)
    adsl    = create_adsl(dm, ex, rs, events)
    adtte   = create_adtte(adsl)
    tv      = create_tv()
    ta      = create_ta()

    for name, df in [
        ("DM", dm), ("EX", ex), ("TU", tu), ("TR", tr), ("RS", rs), ("DS", ds),
        ("FA", fa), ("RELREC", relrec), ("ADSL", adsl), ("ADTTE", adtte), ("TV", tv), ("TA", ta),
    ]:
        # Exclude internal helper column TRT01A from SDTM DM output
        out_df = df.drop(columns=["TRT01A"], errors="ignore") if name == "DM" else df
        path   = os.path.join(out_dir, f"{name}.csv")
        out_df.to_csv(path, index=False)
        print(f"Wrote {name}.csv  ({len(out_df)} rows)")
