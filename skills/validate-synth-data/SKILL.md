---
name: validate-synth-data
description: >
  Validates the CDISC SDTM/ADaM synthetic datasets for the NCT01797120 (PrE0102) study
  (STUDYID=NCT01797120). Runs seven check categories: (1) CDISC structural compliance per
  domain, (2) cross-domain subject/treatment-arm integrity, (3) RECIST derivation consistency
  between TR and RS, (4) study timeline and death logic, (5) population distribution and
  demographic plausibility, (6) duplicate and study-level consistency, and (7) PFS results
  fidelity vs. published trial medians (10.3 vs 5.1 months). Use this skill whenever the user
  asks to validate, check, QC, or audit the synthetic datasets — including after regenerating
  data, before packaging a release ZIP, or when investigating unexpected analysis results.
---

# validate-synth-data

## What this skill does

Runs a seven-category (105-check) quality check on the CSV files in `datasets/` and produces a
markdown report (`validation_report.md`) with a pass/fail table, counts, and a PFS
fidelity section comparing generated medians to the published trial values.

## Workflow

### 1. Locate datasets

Default path is `./datasets/` relative to the project root. If the user specifies a
different path (e.g. after unzipping an archive), use that instead.

Check that these files exist before running (required by the script):
`DM.csv`, `EX.csv`, `TR.csv`, `RS.csv`, `DS.csv`, `ADSL.csv`, `ADTTE.csv`
If `TU.csv` is present it will also be validated (RECIST TU↔TR linkage checks).
If any are missing, report them and stop early with a clear message.

### 2. Run the validation script

Use the bundled script at `scripts/validate.py` (path relative to this SKILL.md):

```bash
python <skill_dir>/scripts/validate.py --datasets <datasets_dir> --output validation_report.md
```

`<skill_dir>` is the directory containing this SKILL.md file.
`<datasets_dir>` is the resolved path to the CSV files.

The script exits 0 on success (all checks pass) and 1 if any check fails.

### 3. Present the report

Read `validation_report.md` and show it to the user in the conversation. Draw attention to:
- Any FAILED checks (explain what the failure means in plain terms)
- The PFS fidelity section — flag if medians are outside the ±20% tolerance window
- A one-sentence overall verdict: "All N checks passed" or "X of N checks failed"

If the user wants to investigate a failure, read the relevant CSV and reason through the
specific rows that triggered it.

## Check categories

### Category 1 — CDISC structural
Per-domain checks on required columns, controlled terminology, and value formats:

| Domain | Key checks |
|--------|-----------|
| DM | STUDYID=NCT01797120, DOMAIN=DM, SEX=F for all, ARMCD ∈ {TRT,PLC}, DTHFL ∈ {Y,''}, USUBJID pattern NCT01797120-NNNN, AGEU=YEARS, RFENDTC=RFPENDTC, RFICDTC/RFPENDTC non-empty |
| EX | EXTRT ∈ {FULVESTRANT,EVEROLIMUS,PLACEBO}, EXDOSU=mg, EXDOSE > 0 for non-PLACEBO, PLACEBO EXDOSE=0, EXROUTE ∈ {INTRAMUSCULAR,ORAL}, Fulvestrant C1D1/C1D15 loading doses = 250 mg |
| TR | TRTESTCD ∈ {LDIAM,SUMDIAM}, TRSTRESU=mm for evaluable rows, TRLOBXFL ∈ {Y,''}, TRLNKID present, EPOCH ∈ {INDUCTION,CONTINUATION}, TRMETHOD=CT SCAN, TREVAL=INVESTIGATOR, exactly one baseline SUMDIAM per subject, LDIAM = 0 or ≥5 mm for evaluable records |
| RS | RSTESTCD=OVRLRESP, RSSTRESC ∈ {CR,PR,SD,PD,NE}, EPOCH ∈ {INDUCTION,CONTINUATION}, RSDRVFL=Y |
| DS | DSCAT ∈ {PROTOCOL MILESTONE,DISPOSITION EVENT}, DSDECOD ∈ valid CT (includes ADVERSE EVENT, DEATH), EPOCH empty for PROTOCOL MILESTONE (CG0073), EPOCH ∈ {'',INDUCTION,CONTINUATION,FOLLOW-UP}, DSTERM=DSDECOD for PROTOCOL MILESTONE (CG0066), DEATH record DSSTDTC=DM DTHDTC (FB0611) |
| ADSL | TRT01A ∈ {Treatment,Placebo}, TRT01P=TRT01A (no crossover), ITTFL/SAFFL/PPROTFL ∈ {Y,N} |
| ADTTE | PARAMCD=PFS, CNSR ∈ {0,1}, AVAL > 0, STARTDT/ADT present and parseable, ADT ≥ STARTDT, AVAL = (ADT − STARTDT) in days, ITTFL/SAFFL/PPROTFL ∈ {Y,N} |

### Category 2 — Cross-domain integrity
- All USUBJIDs in EX/TR/RS/DS/ADSL/ADTTE/TU (if present) are present in DM
- All DM USUBJIDs appear in ADSL and ADTTE
- EX arm-drug consistency: EVEROLIMUS only to TRT subjects, PLACEBO only to PLC subjects, and every subject in that arm has the corresponding record
- DS: exactly 5 records per subject, every subject has a STUDY PARTICIPATION end record
- ADSL.TRT01A consistent with DM.ARMCD (TRT→Treatment, PLC→Placebo)

### Category 3 — RECIST derivation
- Every RS USUBJID has a baseline (TRLOBXFL=Y) SUMDIAM record in TR
- TU domain (if present): all subjects have TU records, TUTESTCD ∈ {TIND,NTIND,TUMIDENT}, TUMIDENT TULNKID links to a TR TRLNKID
- Every RS response date matches a TR assessment date for that subject
- No subject has more than one PD record (assessments stop once PD is declared)
- RSSTRESC values are consistent with RECIST v1.1 thresholds derived from TR SUMDIAM (CR=0, PR ≤−30% vs baseline, PD ≥+20% vs baseline, SD otherwise, NE when TRSTAT=NOT DONE)

### Category 4 — Timeline & death logic
- Study timeline anchoring: RFSTDTC/study-duration variability, EX/TR dates ≥ RFSTDTC, RFXENDTC ≥ RFSTDTC, RFPENDTC ≥ RFXENDTC
- Death & post-death logic: DTHDTC ≥ RFSTDTC, no TR/RS/EX records after death, DM.DTHFL=Y ↔ DS DEATH record consistency
- Within-domain temporal logic: EXSTDTC ≤ EXENDTC, no dates beyond study end (2026-12-31)

### Category 5 — Population distribution & plausibility
- Ages in plausible range (18–85) with realistic variability (stddev > 5 years)
- Enrollment dates span > 90 days (not all identical)
- TR/RS record counts vary across subjects (realistic missingness, not a fixed schedule for everyone)

### Category 6 — Duplicate & study-level consistency
- No duplicate USUBJIDs in DM; no duplicate sequence keys (USUBJID+SEQ) in EX/TR/RS/DS
- TR baseline dates are not all identical (enrollment/visit schedules vary)
- Every DM subject appears in ≥1 clinical domain (EX/TR/RS)
- DM and ADSL subject sets match exactly

### Category 7 — PFS fidelity
- Compute observed median PFS (days) for Treatment and Placebo arms from ADTTE
- Published targets: Treatment ≈ 314 days (10.3 months), Placebo ≈ 155 days (5.1 months)
- Tolerance: ±20% of target (Treatment: 251–377 days, Placebo: 124–186 days)
- Report observed medians, targets, percent deviation, and PASS/FAIL

## Output format

The report must follow this template exactly:

```markdown
# Synthetic Dataset Validation Report
**Study:** NCT01797120  
**Datasets path:** <path>  
**Generated:** <date>  
**N subjects:** <n>

## Summary

| Category | Checks | Passed | Failed |
|----------|--------|--------|--------|
| Category 1 — CDISC Structural | N | N | N |
| Category 2 — Cross-domain Integrity | N | N | N |
| Category 3 — RECIST Derivation | N | N | N |
| Category 4 — Timeline & Death Logic | N | N | N |
| Category 5 — Population Distribution | N | N | N |
| Category 6 — Duplicate & Study Consistency | N | N | N |
| Category 7 — PFS Fidelity | N | N | N |
| **Total** | **N** | **N** | **N** |

**Overall: PASS** ✓  [or **FAIL** ✗]

## Detailed Results

### Category 1 — CDISC Structural
[one line per check: ✓ PASS or ✗ FAIL — <domain>: <what was checked> (<counts if relevant>)]

### Category 2 — Cross-domain Integrity
[...]

### Category 3 — RECIST Derivation
[...]

### Category 4 — Timeline & Death Logic
[...]

### Category 5 — Population Distribution
[...]

### Category 6 — Duplicate & Study Consistency
[...]

### Category 7 — PFS Fidelity
[...]

### PFS Fidelity Detail

| Arm | Observed Median (days) | Target (days) | Tolerance | Deviation | Result |
|-----|------------------------|---------------|-----------|-----------|--------|
| Treatment | NNN | 314 | ±63d | +X% | PASS/FAIL |
| Placebo | NNN | 155 | ±31d | +X% | PASS/FAIL |
```
