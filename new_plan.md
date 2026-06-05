# Plan: Fix DS, DM, and EX Dataset Issues

## Context

The current synthetic data generation in `src/cdisc_generation_functions.py` produces several CDISC standards violations and unrealistic structures across the DS, DM, and EX SDTM domains. The user has identified specific issues with invalid DSDECOD values, missing DSCAT/DSSCAT variables, an ADaM variable (TRT01A) in an SDTM domain, incorrect EXSEQ sequencing, missing EXFREQ, wrong drug names/doses in EX, and an unrealistic all-same-date RFSTDTC. This plan addresses all of those.

---

## Files to Modify

- `src/cdisc_generation_functions.py` — all changes are here

---

## Change 1: `derive_events` — add death simulation

Add `DIED` (bool) and `DTHDT` (datetime | None) to the returned DataFrame.

- ~75% of progressors die during follow-up; death date = `PROGDT + Exponential(scale=180 days)`
- ~15% of non-progressors who withdrew die; death date = `treatment_end + Exponential(scale=365 days)`
- Non-withdrawing non-progressors: no death record (censored/ongoing)
- Cap all death dates at a reasonable study end (e.g. 2026-12-31)

---

## Change 2: `create_dm` — fix RFSTDTC, replace TRT01A with ARM columns, defer death fields

**Replace:**
- `"RFSTDTC": "2023-01-01"` → random date per subject drawn uniformly from a 24-month enrollment window (2021-01-01 to 2022-12-31). Store as `RFSTDTC`.
- `"TRT01A": arms` → keep `arms` array internally but expose as SDTM arm variables:
  - `ARMCD`: `"TRT"` / `"PLC"`
  - `ARM`: `"Fulvestrant + Everolimus"` / `"Fulvestrant + Placebo"`
  - `ACTARMCD` = `ARMCD`, `ACTARM` = `ARM` (no off-protocol treatment in synthetic data)
- Keep `TRT01A` as an **internal helper column** (not in the final column list) so `derive_events` and `create_tr` continue to work unchanged.

**Output column list:** `STUDYID, DOMAIN, USUBJID, SUBJID, DMSEQ, AGE, SEX, RFSTDTC, ARMCD, ARM, ACTARMCD, ACTARM`

Note: `DTHFL`/`DTHDTC` and `RFXSTDTC`/`RFXENDTC` require downstream data (events, EX); they are added by the new `finalize_dm` function below.

---

## Change 3: New `finalize_dm(dm, ex, events)` function

Called after `derive_events`. Adds four columns to DM in-place and returns the updated DataFrame:

- `DTHFL`: `"Y"` if `events.DIED == True`, else `"N"`
- `DTHDTC`: `events.DTHDT.strftime("%Y-%m-%d")` where `DTHFL == "Y"`, else `""`
- `RFXSTDTC`: earliest `EXSTDTC` per subject from EX (first exposure date)
- `RFXENDTC`: latest `EXENDTC` per subject from EX (last exposure date)

Final DM column order: `STUDYID, DOMAIN, USUBJID, SUBJID, DMSEQ, AGE, SEX, RFSTDTC, RFXSTDTC, RFXENDTC, ARMCD, ARM, ACTARMCD, ACTARM, DTHFL, DTHDTC`

---

## Change 4: `create_ex` — per-drug records, correct names/doses, fixed EXSEQ

Completely replace the current single-record-per-subject approach.

**Fulvestrant record(s) — one record per injection:**
- `EXTRT = "FULVESTRANT"`, `EXDOSE = 500`, `EXDOSU = "mg"`, `EXROUTE = "INTRAMUSCULAR"`, `EXFREQ = "ONCE"`
- `EXSTDTC = EXENDTC` (injection is a single day)
- Schedule from treatment start (`RFSTDTC`): Day 1, Day 15, then Day 29+28*(n) for each subsequent cycle until treatment end
- Treatment end date: `RFSTDTC + random duration` (keep current 60–600 day range)

**Everolimus / Placebo — one record covering full treatment period:**
- Treatment arm: `EXTRT = "EVEROLIMUS"`, `EXDOSE = 10`, `EXDOSU = "mg"`, `EXROUTE = "ORAL"`, `EXFREQ = "QD"`
- Placebo arm: `EXTRT = "PLACEBO"`, `EXDOSE = 10`, `EXDOSU = "mg"`, `EXROUTE = "ORAL"`, `EXFREQ = "QD"` (matching tablet dose)
- `EXSTDTC = RFSTDTC`, `EXENDTC = treatment end date`

**EXSEQ:** Reset to 1 per subject, incrementing for each record within that subject (not globally).

**Needs from DM:** `RFSTDTC` (start date) and internal `TRT01A` (to pick Everolimus vs Placebo).

---

## Change 5: `create_ds` — remove "TREATED", add DSCAT/DSSCAT, per-drug stopping records, death records

**Remove** all "TREATED" records entirely.

**Record structure per subject:**

| # | DSCAT | DSDECOD | DSSCAT | EPOCH | DSDTC |
|---|-------|---------|--------|-------|-------|
| 1 | `PROTOCOL MILESTONE` | `RANDOMIZED` | _(blank)_ | `SCREENING` | `RFSTDTC` from DM |
| 2 | `DISPOSITION EVENT` | `PROGRESSIVE DISEASE` or `WITHDRAWAL BY SUBJECT` | `FULVESTRANT` | `TREATMENT` | treatment end date |
| 3 | `DISPOSITION EVENT` | same as #2 | `EVEROLIMUS` (Trt) or `PLACEBO` (Ctl) | `TREATMENT` | treatment end date |
| 4* | `DISPOSITION EVENT` | `DEATH` | `STUDY` | `FOLLOW-UP` | `DTHDTC` |

\* Record 4 only added if `events.DIED == True`.

- Treatment end date = `PROGDT` for progressors, `EXENDTC` for others (same logic as current)
- Both drug-stopping records (#2 and #3) get the same date and reason for simplicity
- Needs `dm` (for RFSTDTC, ARMCD), `ex` (for treatment end), `events` (for PROGDT, DIED, DTHDT)

**Add `DSCAT` and `DSSCAT` to the output column list.**

---

## Change 6: `create_adsl` — derive TRT01A from ARM

Replace the line that reads `TRT01A` from DM:
```python
# Current
core = dm[["USUBJID", "TRT01A", "AGE"]].merge(...)

# New — derive TRT01A from ARMCD (PLC → "Placebo", TRT → "Treatment")
dm_copy = dm.copy()
dm_copy["TRT01A"] = dm_copy["ARMCD"].map({"TRT": "Treatment", "PLC": "Placebo"})
core = dm_copy[["USUBJID", "TRT01A", "AGE"]].merge(...)
```

TRT01A in the ADSL output (`"Treatment"` / `"Placebo"`) remains unchanged — only the source changes from DM to derived from ARMCD.

---

## Updated Pipeline (caller code in docstring / README)

```python
dm     = create_dm(n=200)
ex     = create_ex(dm)
events = derive_events(ex, dm)
dm     = finalize_dm(dm, ex, events)   # new step
tr     = create_tr(ex, events)
rs     = derive_rs(tr)
ds     = create_ds(dm, ex, events)     # signature change: rs → events
adsl   = create_adsl(dm, ex, rs, events)
tv     = create_tv()
ta     = create_ta()
```

Note: `create_ds` currently takes `(dm, ex, rs)` — the `rs` parameter is unused in the function body (it only uses `dm`, `ex`, and the `events`-derived columns). The signature change replaces `rs` with `events`.

---

## Verification

1. Run the full pipeline and confirm no exceptions.
2. Check DS: `ds.DSDECOD.unique()` should return only `RANDOMIZED`, `PROGRESSIVE DISEASE`, `WITHDRAWAL BY SUBJECT`, `DEATH`. No `TREATED` or `COMPLETED`.
3. Check DS: `ds.DSCAT.unique()` returns `PROTOCOL MILESTONE` and `DISPOSITION EVENT`. `ds.DSSCAT.unique()` returns `FULVESTRANT`, `EVEROLIMUS`, `PLACEBO`, and blank.
4. Check DM: `dm.RFSTDTC.nunique()` >> 1 (spread over enrollment window). Columns include `ARMCD`, `ARM`, `ACTARMCD`, `ACTARM`, `DTHFL`, `DTHDTC`, `RFXSTDTC`, `RFXENDTC`. No `TRT01A`.
5. Check EX: `ex.EXTRT.unique()` returns `FULVESTRANT`, `EVEROLIMUS`, `PLACEBO`. Check that `ex.groupby("USUBJID")["EXSEQ"].min().eq(1).all()` is True (per-subject EXSEQ starts at 1). `"EXFREQ"` column present.
6. Check ADSL: `adsl.TRT01A.unique()` still returns `Treatment` and `Placebo`.
7. Regenerate CSV files and spot-check a few subjects across DS, DM, EX for consistency.
