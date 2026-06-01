
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

STUDYID = "SYNTH-ONC-001"


# ---------------- DM ----------------
def create_dm(n=200):
    dm = pd.DataFrame({
        "SUBJID": [f"{i:04d}" for i in range(1, n + 1)],
        "DMSEQ": range(1, n + 1),
        "AGE": np.clip(np.random.normal(55, 10, n), 20, 80).astype(int),
        "SEX": "F",
        "RFSTDTC": "2023-01-01",
        "TRT01A": np.random.choice(["Treatment", "Placebo"], n),
    })
    dm["STUDYID"] = STUDYID
    dm["DOMAIN"] = "DM"
    dm["USUBJID"] = STUDYID + "-" + dm["SUBJID"]
    return dm[["STUDYID", "DOMAIN", "USUBJID", "SUBJID", "DMSEQ", "AGE", "SEX", "RFSTDTC", "TRT01A"]]


# ---------------- EX ----------------
def create_ex(dm):
    records = []
    for i, (_, row) in enumerate(dm.iterrows(), start=1):
        start = datetime(2023, 1, 1) + timedelta(days=int(np.random.randint(0, 180)))
        dur = int(np.random.uniform(60, 600))
        end = start + timedelta(days=dur)
        records.append({
            "STUDYID": STUDYID,
            "DOMAIN": "EX",
            "USUBJID": row["USUBJID"],
            "EXSEQ": i,
            "EXTRT": "Study Drug",
            "EXDOSE": 100,
            "EXDOSU": "mg",
            "EXSTDTC": start.strftime("%Y-%m-%d"),
            "EXENDTC": end.strftime("%Y-%m-%d"),
        })
    return pd.DataFrame(records)


# ---------------- EVENTS (internal) ----------------
def derive_events(ex, dm):
    """Returns one row per subject with PROGDT (datetime or NaT) and WITHDRAWAL (bool)."""
    records = []
    merged = ex.merge(dm[["USUBJID", "TRT01A"]])
    for _, row in merged.iterrows():
        start = datetime.strptime(str(row["EXSTDTC"])[:10], "%Y-%m-%d")
        prob = 0.5 if row["TRT01A"] == "Treatment" else 0.7
        progdt = (
            start + timedelta(days=int(np.random.uniform(120, 600)))
            if np.random.rand() < prob
            else None
        )
        records.append({"USUBJID": row["USUBJID"], "PROGDT": progdt})

    events = pd.DataFrame(records)
    # Assign ~20% of non-progressing subjects as WITHDRAWAL BY SUBJECT
    no_prog = events["PROGDT"].isna()
    events["WITHDRAWAL"] = no_prog & (np.random.rand(len(events)) < 0.20)
    return events


# ---------------- TR ----------------
def create_tr(ex, events):
    tr = []
    seq = 1
    merged = ex.copy()
    merged["EXSTDTC"] = pd.to_datetime(merged["EXSTDTC"])
    merged = merged.merge(events[["USUBJID", "PROGDT"]])
    for _, row in merged.iterrows():
        base = np.random.normal(50, 10)
        tumor = base
        for v, day in enumerate(range(85, 800, 84), start=1):
            date = row["EXSTDTC"] + timedelta(days=day)
            progdt = row["PROGDT"]
            if progdt is not None and pd.notna(progdt) and date > progdt:
                break
            tumor = max(1, tumor + np.random.normal(-3, 8))
            tr.append({
                "STUDYID": STUDYID,
                "DOMAIN": "TR",
                "USUBJID": row["USUBJID"],
                "TRSEQ": seq,
                "TRTESTCD": "DIAM",
                "TRTEST": "Diameter",
                "TRSTRESN": round(tumor, 2),
                "TRSTRESU": "mm",
                "TRDTC": date.strftime("%Y-%m-%d"),
                "VISITNUM": v,
                "VISIT": f"Week {v * 12}",
                "TRDY": day,
                "ABLFL": "Y" if v == 1 else "",
            })
            seq += 1
    return pd.DataFrame(tr)


# ---------------- RS ----------------
def derive_rs(tr):
    rs = []
    seq = 1
    base_map = tr[tr["ABLFL"] == "Y"].set_index("USUBJID")["TRSTRESN"]
    for _, row in tr.iterrows():
        base = base_map.get(row["USUBJID"], row["TRSTRESN"])
        pct = (row["TRSTRESN"] - base) / base * 100
        if pct <= -30:
            resp = "PR"
        elif pct >= 20:
            resp = "PD"
        else:
            resp = "SD"
        rs.append({
            "STUDYID": STUDYID,
            "DOMAIN": "RS",
            "USUBJID": row["USUBJID"],
            "RSSEQ": seq,
            "RSTESTCD": "OVRLRESP",
            "RSTEST": "Overall Response",
            "RSSTRESC": resp,
            "RSDTC": row["TRDTC"],
            "VISITNUM": row["VISITNUM"],
            "VISIT": row["VISIT"],
            "RSDY": row["TRDY"],
        })
        seq += 1
    return pd.DataFrame(rs)


# ---------------- DS ----------------
def create_ds(dm, ex, events):
    ex_copy = ex.copy()
    core = dm[["USUBJID"]].merge(
        ex_copy[["USUBJID", "EXSTDTC", "EXENDTC"]]
    ).merge(events[["USUBJID", "PROGDT", "WITHDRAWAL"]], on="USUBJID", how="left")

    ds = []
    for _, row in core.iterrows():
        progdt = row["PROGDT"]
        has_prog = pd.notna(progdt)
        is_withdrawal = bool(row["WITHDRAWAL"])
        progdt_str = progdt.strftime("%Y-%m-%d") if has_prog else None

        seq = 1

        ds.append({
            "STUDYID": STUDYID, "DOMAIN": "DS",
            "USUBJID": row["USUBJID"], "DSSEQ": seq,
            "DSDECOD": "RANDOMIZED", "DSDTC": "2023-01-01", "EPOCH": "SCREENING",
        })
        seq += 1

        ds.append({
            "STUDYID": STUDYID, "DOMAIN": "DS",
            "USUBJID": row["USUBJID"], "DSSEQ": seq,
            "DSDECOD": "TREATED", "DSDTC": str(row["EXSTDTC"])[:10], "EPOCH": "TREATMENT",
        })
        seq += 1

        if has_prog:
            ds.append({
                "STUDYID": STUDYID, "DOMAIN": "DS",
                "USUBJID": row["USUBJID"], "DSSEQ": seq,
                "DSDECOD": "PROGRESSIVE DISEASE", "DSDTC": progdt_str, "EPOCH": "TREATMENT",
            })
            seq += 1
            final_decod, final_dtc = "PROGRESSIVE DISEASE", progdt_str
        else:
            final_decod = "WITHDRAWAL BY SUBJECT" if is_withdrawal else "COMPLETED"
            final_dtc = str(row["EXENDTC"])[:10]

        ds.append({
            "STUDYID": STUDYID, "DOMAIN": "DS",
            "USUBJID": row["USUBJID"], "DSSEQ": seq,
            "DSDECOD": final_decod, "DSDTC": final_dtc, "EPOCH": "FOLLOW-UP",
        })

    return pd.DataFrame(ds)


# ---------------- ADSL ----------------
def _best_response(responses):
    for r in ("PR", "SD", "PD"):
        if r in responses.values:
            return r
    return ""


def create_adsl(dm, ex, rs, events):
    ex_copy = ex.copy()
    ex_copy["EXSTDTC"] = pd.to_datetime(ex_copy["EXSTDTC"])
    ex_copy["EXENDTC"] = pd.to_datetime(ex_copy["EXENDTC"])

    bestresp_map = rs.groupby("USUBJID")["RSSTRESC"].apply(_best_response).to_dict()

    core = dm[["USUBJID", "TRT01A", "AGE"]].merge(
        ex_copy[["USUBJID", "EXSTDTC", "EXENDTC"]]
    ).merge(events[["USUBJID", "PROGDT", "WITHDRAWAL"]], on="USUBJID", how="left")

    records = []
    for _, row in core.iterrows():
        progdt = row["PROGDT"]
        if pd.notna(progdt):
            pfs = (progdt - row["EXSTDTC"]).days
            cnsr = 0
            dcsreas = "PROGRESSIVE DISEASE"
        else:
            pfs = (row["EXENDTC"] - row["EXSTDTC"]).days
            cnsr = 1
            dcsreas = "WITHDRAWAL BY SUBJECT" if row["WITHDRAWAL"] else "COMPLETED"

        records.append({
            "STUDYID": STUDYID,
            "USUBJID": row["USUBJID"],
            "TRT01A": row["TRT01A"],
            "AGE": row["AGE"],
            "PFS": pfs,
            "CNSR": cnsr,
            "BESTRESP": bestresp_map.get(row["USUBJID"], ""),
            "DCSREAS": dcsreas,
        })

    return pd.DataFrame(records)


# ---------------- ADTTE ----------------
def create_adtte(adsl):
    records = []
    for _, row in adsl.iterrows():
        records.append({
            "STUDYID": STUDYID,
            "USUBJID": row["USUBJID"],
            "PARAMCD": "PFS",
            "PARAM": "Progression-Free Survival",
            "AVAL": float(row["PFS"]),
            "CNSR": row["CNSR"],
            "TRT01A": row["TRT01A"],
        })
    return pd.DataFrame(records)


# ---------------- TV ----------------
def create_tv():
    return pd.DataFrame({
        "STUDYID": STUDYID,
        "DOMAIN": "TV",
        "VISITNUM": [1, 2, 3, 4, 5, 6],
        "VISIT": ["SCREENING", "BASELINE", "WEEK 12", "WEEK 24", "WEEK 36", "END OF TREATMENT"],
        "TVSTRL": [-14, 1, 85, 169, 253, ""],
        "TVENRL": [0, 1, 85, 169, 253, ""],
        "EPOCH": ["SCREENING", "TREATMENT", "TREATMENT", "TREATMENT", "TREATMENT", "FOLLOW-UP"],
    })


# ---------------- TA ----------------
def create_ta():
    return pd.DataFrame({
        "STUDYID": STUDYID,
        "DOMAIN": "TA",
        "ARMCD": ["TRT", "PBO"],
        "ARM": ["Treatment Arm", "Placebo Arm"],
        "TAETORD": [1, 1],
        "EPOCH": ["TREATMENT", "TREATMENT"],
    })


# ---------------- MAIN ----------------
if __name__ == "__main__":
    np.random.seed(42)

    out_dir = os.path.join(os.path.dirname(__file__), "..", "datasets")
    os.makedirs(out_dir, exist_ok=True)

    dm = create_dm(n=200)
    ex = create_ex(dm)
    events = derive_events(ex, dm)
    tr = create_tr(ex, events)
    rs = derive_rs(tr)
    ds = create_ds(dm, ex, events)
    adsl = create_adsl(dm, ex, rs, events)
    adtte = create_adtte(adsl)
    tv = create_tv()
    ta = create_ta()

    for name, df in [
        ("DM", dm), ("EX", ex), ("TR", tr), ("RS", rs), ("DS", ds),
        ("ADSL", adsl), ("ADTTE", adtte), ("TV", tv), ("TA", ta),
    ]:
        path = os.path.join(out_dir, f"{name}.csv")
        df.to_csv(path, index=False)
        print(f"Wrote {name}.csv  ({len(df)} rows)")
