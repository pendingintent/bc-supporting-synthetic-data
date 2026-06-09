---
name: validate-synth-data
description: >
  Validates the CDISC SDTM/ADaM synthetic datasets for the NCT01797120 (PrE0102) study
  (STUDYID=NCT01797120). Runs four check categories: (1) CDISC structural compliance per
  domain, (2) cross-domain subject/treatment-arm integrity, (3) RECIST derivation consistency
  between TR and RS, and (4) PFS results fidelity vs. published trial medians (10.3 vs 5.1
  months). Use this skill whenever the user asks to validate, check, QC, or audit the
  synthetic datasets — including after regenerating data, before packaging a release ZIP, or
  when investigating unexpected analysis results.
---

# validate-synth-data

## What this skill does

Runs a four-category quality check on the CSV files in `datasets/` and produces a
markdown report (`validation_report.md`) with a pass/fail table, counts, and a PFS
fidelity section comparing generated medians to the published trial values.

## Workflow

### 1. Locate datasets

Default path is `./datasets/` relative to the project root. If the user specifies a
different path (e.g. after unzipping an archive), use that instead.

Check that these files exist before running:
`DM.csv`, `EX.csv`, `TR.csv`, `RS.csv`, `DS.csv`, `ADSL.csv`, `ADTTE.csv`, `DS.csv`

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
| DM | STUDYID=NCT01797120, DOMAIN=DM, SEX=F for all, ARMCD ∈ {TRT,PLC}, DTHFL ∈ {Y,N}, USUBJID pattern NCT01797120-NNNN |
| EX | EXTRT ∈ {FULVESTRANT,EVEROLIMUS,PLACEBO}, EXDOSU=mg, EXDOSE > 0, EXROUTE ∈ {INTRAMUSCULAR,ORAL} |
| TR | TRTESTCD=DIAM, TRSTRESU=mm, TRSTRESN > 0, ABLFL ∈ {Y,""} |
| RS | RSTESTCD=OVRLRESP, RSSTRESC ∈ {PR,SD,PD} |
| DS | DSCAT ∈ {PROTOCOL MILESTONE,DISPOSITION EVENT}, DSDECOD non-null |
| ADSL | TRT01A ∈ {Treatment,Placebo}, CNSR ∈ {0,1}, PFS > 0 |
| ADTTE | PARAMCD=PFS, CNSR ∈ {0,1}, AVAL > 0 |

### Category 2 — Cross-domain integrity
- All USUBJIDs in EX/TR/RS/DS/ADSL/ADTTE are present in DM
- All DM USUBJIDs appear in ADSL and ADTTE
- EX arm-drug consistency: subjects with ARMCD=TRT must have an EVEROLIMUS record; PLC subjects must have a PLACEBO record (not EVEROLIMUS)
- ADSL.TRT01A aligns with DM.ARMCD (TRT→Treatment, PLC→Placebo)

### Category 3 — RECIST derivation
- Each RS response for a subject can be traced to a TR record on the same date
- RSSTRESC values are consistent with RECIST v1.0: PR means ≤−30% change from baseline TRSTRESN, PD means ≥+20% change, SD is everything else
- Every RS USUBJID has a baseline (ABLFL=Y) record in TR

### Category 4 — PFS fidelity
- Compute median PFS (days) for Treatment and Placebo arms from ADTTE (CNSR-aware, using Kaplan-Meier or simple observed median as a proxy)
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
| 1. CDISC Structural | N | N | N |
| 2. Cross-domain Integrity | N | N | N |
| 3. RECIST Derivation | N | N | N |
| 4. PFS Fidelity | N | N | N |
| **Total** | **N** | **N** | **N** |

**Overall: PASS** ✓  [or **FAIL** ✗]

## Detailed Results

### Category 1 — CDISC Structural
[one line per check: ✓ PASS or ✗ FAIL — <domain>: <what was checked> (<counts if relevant>)]

### Category 2 — Cross-domain Integrity
[...]

### Category 3 — RECIST Derivation
[...]

### Category 4 — PFS Fidelity

| Arm | Observed Median (days) | Target (days) | Deviation | Result |
|-----|------------------------|---------------|-----------|--------|
| Treatment | NNN | 314 | +X% | PASS/FAIL |
| Placebo | NNN | 155 | +X% | PASS/FAIL |
```
