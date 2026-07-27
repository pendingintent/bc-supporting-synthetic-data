# Synthetic Dataset Validation Report
**Study:** NCT01797120  
**Datasets path:** datasets  
**Generated:** 2026-07-27  
**N subjects:** 200

## Summary

| Category | Checks | Passed | Failed |
|----------|--------|--------|--------|
| Category 1 — CDISC Structural | 54 | 54 | 0 |
| Category 2 — Cross-domain Integrity | 16 | 16 | 0 |
| Category 3 — RECIST Derivation | 7 | 7 | 0 |
| Category 4 — Timeline & Death Logic | 13 | 13 | 0 |
| Category 5 — Population Distribution | 5 | 5 | 0 |
| Category 6 — Duplicate & Study Consistency | 8 | 8 | 0 |
| Category 7 — PFS Fidelity | 2 | 2 | 0 |
| **Total** | **105** | **105** | **0** |

**Overall: **PASS ✓****

## Detailed Results

### Category 1 — CDISC Structural
✓ PASS — DM: STUDYID = NCT01797120 (0 bad rows)
✓ PASS — DM: DOMAIN = DM
✓ PASS — DM: all subjects female (SEX=F) (0 non-F rows)
✓ PASS — DM: ARMCD ∈ {TRT, PLC} (0 bad values)
✓ PASS — DM: DTHFL ∈ {Y, ''}
✓ PASS — DM: USUBJID format NCT01797120-NNNN (0 malformed IDs)
✓ PASS — DM: AGEU = YEARS (CG0432)
✓ PASS — DM: RFENDTC present and = RFPENDTC (CG0142)
✓ PASS — DM: RFICDTC non-empty
✓ PASS — DM: RFPENDTC non-empty
✓ PASS — EX: EXTRT ∈ {FULVESTRANT, EVEROLIMUS, PLACEBO} (0 bad values)
✓ PASS — EX: EXDOSU = mg
✓ PASS — EX: EXDOSE > 0 for non-PLACEBO records (0 bad values)
✓ PASS — EX: EXROUTE ∈ {INTRAMUSCULAR, ORAL}
✓ PASS — EX: EXSTDY and EXENDY present
✓ PASS — EX: Fulvestrant C1D1 and C1D15 doses = 250 mg (0 records with wrong loading dose)
✓ PASS — EX: PLACEBO EXDOSE = 0 (CG0102) (0 records with non-zero placebo dose)
✓ PASS — TR: TRTESTCD ∈ {LDIAM, SUMDIAM}
✓ PASS — TR: TRSTRESU = mm (evaluable rows)
✓ PASS — TR: TRLOBXFL ∈ {Y, ''}
✓ PASS — TR: TRLNKID present (not TRLINKID)
✓ PASS — TR: EPOCH ∈ {INDUCTION, CONTINUATION} (FB2201)
✓ PASS — TR: TRMETHOD = CT SCAN present
✓ PASS — TR: TREVAL = INVESTIGATOR present
✓ PASS — TR: SUMDIAM records present (RECIST supplement)
✓ PASS — TR: exactly one baseline SUMDIAM per subject
✓ PASS — TR: SUMDIAM TRGRPID = TARGET
✓ PASS — TR: LDIAM TRSTRESN = 0 (absent) or ≥ 5 mm for evaluable records (0 values between 0 and 5 mm)
✓ PASS — RS: RSTESTCD = OVRLRESP
✓ PASS — RS: RSSTRESC ∈ {CR, PR, SD, PD, NE} (RECIST 1.1) (0 bad values)
✓ PASS — RS: EPOCH ∈ {INDUCTION, CONTINUATION} (FB2201)
✓ PASS — RS: RSDRVFL = Y for derived records (CG0563)
✓ PASS — DS: DSCAT ∈ {PROTOCOL MILESTONE, DISPOSITION EVENT}
✓ PASS — DS: DSDECOD ∈ valid controlled vocabulary (0 unexpected values)
✓ PASS — DS: EPOCH empty for PROTOCOL MILESTONE records (CG0073) (0 PROTOCOL MILESTONE records with non-empty EPOCH)
✓ PASS — DS: EPOCH ∈ {'' (milestone), INDUCTION, CONTINUATION, FOLLOW-UP} (0 unexpected values)
✓ PASS — DS: DSTERM present (0 empty)
✓ PASS — DS: DSTERM = DSDECOD for PROTOCOL MILESTONE records (CG0066) (0 mismatches)
✓ PASS — DS: DEATH record DSSTDTC = DM DTHDTC (FB0611) (0 mismatches)
✓ PASS — ADSL: TRT01A ∈ {Treatment, Placebo}
✓ PASS — ADSL: TRT01P present and = TRT01A (no crossover)
✓ PASS — ADSL: ITTFL present and ∈ {Y, N}
✓ PASS — ADSL: SAFFL present and ∈ {Y, N}
✓ PASS — ADSL: PPROTFL present and ∈ {Y, N}
✓ PASS — ADTTE: PARAMCD = PFS
✓ PASS — ADTTE: CNSR ∈ {0, 1}
✓ PASS — ADTTE: AVAL > 0
✓ PASS — ADTTE: STARTDT present and parseable (0 missing/unparseable values)
✓ PASS — ADTTE: ADT present and parseable (0 missing/unparseable values)
✓ PASS — ADTTE: ADT ≥ STARTDT (0 records with ADT before STARTDT)
✓ PASS — ADTTE: AVAL = (ADT − STARTDT) in days (0 inconsistent records)
✓ PASS — ADTTE: ITTFL present and ∈ {Y, N}
✓ PASS — ADTTE: SAFFL present and ∈ {Y, N}
✓ PASS — ADTTE: PPROTFL present and ∈ {Y, N}

### Category 2 — Cross-domain Integrity
✓ PASS — EX: all USUBJIDs present in DM (0 orphan subjects)
✓ PASS — TR: all USUBJIDs present in DM (0 orphan subjects)
✓ PASS — RS: all USUBJIDs present in DM (0 orphan subjects)
✓ PASS — DS: all USUBJIDs present in DM (0 orphan subjects)
✓ PASS — ADSL: all USUBJIDs present in DM (0 orphan subjects)
✓ PASS — ADTTE: all USUBJIDs present in DM (0 orphan subjects)
✓ PASS — TU: all USUBJIDs present in DM (0 orphan subjects)
✓ PASS — DM: all subjects in ADSL (0 subjects missing from ADSL)
✓ PASS — DM: all subjects in ADTTE (0 subjects missing from ADTTE)
✓ PASS — EX: EVEROLIMUS only given to TRT arm (0 PLC subjects received EVEROLIMUS)
✓ PASS — EX: PLACEBO only given to PLC arm (0 TRT subjects received PLACEBO)
✓ PASS — EX: all TRT subjects have EVEROLIMUS record (0 TRT subjects missing EVEROLIMUS)
✓ PASS — EX: all PLC subjects have PLACEBO record (0 PLC subjects missing PLACEBO)
✓ PASS — DS: exactly 5 records per subject (0 subjects with wrong record count)
✓ PASS — DS: every subject has a STUDY PARTICIPATION end record (0 subjects missing record)
✓ PASS — ADSL: TRT01A consistent with DM ARMCD (0 mismatched subjects)

### Category 3 — RECIST Derivation
✓ PASS — TR: every RS subject has a baseline SUMDIAM record (0 RS subjects missing TR baseline)
✓ PASS — TU: all subjects have tumor identification records (0 subjects missing TU records)
✓ PASS — TU: TUTESTCD ∈ {TIND, NTIND, TUMIDENT}
✓ PASS — TU: TUMIDENT TULNKID links to a TR TRLNKID (0 unlinked TU records)
✓ PASS — RS: every response date matches a TR assessment date (0 RS records with no matching TR date)
✓ PASS — RS: no subject has more than one PD assessment (0 subjects with repeated PD records)
✓ PASS — RS: RSSTRESC consistent with RECIST v1.1 SUMDIAM thresholds (0 mismatches out of 722 checked)

### Category 4 — Timeline & Death Logic
✓ PASS — DM: RFSTDTC has variability (>10 distinct dates) (174 distinct dates)
✓ PASS — DM: Study durations vary (stddev > 30 days) (stddev=262d)
✓ PASS — EX: EXSTDTC ≥ RFSTDTC (0 records before study start)
✓ PASS — TR: TRDTC ≥ RFSTDTC (0 records before study start)
✓ PASS — DM: RFXENDTC ≥ RFSTDTC (0 subjects with end before start)
✓ PASS — DM: RFPENDTC ≥ RFXENDTC (0 subjects with participation end before treatment end)
✓ PASS — DM: DTHDTC ≥ RFSTDTC (no death before study start) (0 violations)
✓ PASS — TR: no records after death (TRDTC ≤ DTHDTC) (0 records after death)
✓ PASS — RS: no records after death (RSDTC ≤ DTHDTC) (0 records after death)
✓ PASS — EX: no records starting after death (EXSTDTC ≤ DTHDTC) (0 records after death)
✓ PASS — DM/DS: DTHFL=Y ↔ DS DEATH record consistent (0 missing, 0 spurious DS DEATH records)
✓ PASS — EX: EXSTDTC ≤ EXENDTC (0 records with start after end)
✓ PASS — All domains: no dates beyond study end (2026-12-31) (0 future dates)

### Category 5 — Population Distribution
✓ PASS — DM: all ages in plausible range (18–85) (0 implausible values)
✓ PASS — DM: age has realistic variability (stddev > 5 years) (stddev=9.8)
✓ PASS — DM: enrollment dates span > 90 days (not all same date) (span=723 days)
✓ PASS — TR: record counts vary across subjects (not all identical) (25 distinct counts (min=4, max=48))
✓ PASS — RS: record counts vary across subjects (realistic missingness) (16 distinct counts (min=1, max=16))

### Category 6 — Duplicate & Study Consistency
✓ PASS — DM: no duplicate USUBJIDs (0 duplicates)
✓ PASS — EX: no duplicate sequence keys (USUBJID+EXSEQ) (0 duplicates)
✓ PASS — TR: no duplicate sequence keys (USUBJID+TRSEQ) (0 duplicates)
✓ PASS — RS: no duplicate sequence keys (USUBJID+RSSEQ) (0 duplicates)
✓ PASS — DS: no duplicate sequence keys (USUBJID+DSSEQ) (0 duplicates)
✓ PASS — TR: baseline dates are not all identical (schedules vary) (174 distinct baseline dates)
✓ PASS — DM: every subject appears in ≥1 clinical domain (EX/TR/RS) (0 subjects with no domain records)
✓ PASS — DM ↔ ADSL: subject sets match exactly (0 mismatched subjects)

### Category 7 — PFS Fidelity
✓ PASS — PFS fidelity: Treatment median within ±20% of 314d target (observed=300d, target=314d, dev=-4.6%)
✓ PASS — PFS fidelity: Placebo median within ±20% of 155d target (observed=169d, target=155d, dev=+9.0%)

### PFS Fidelity Detail

| Arm | Observed Median (days) | Target (days) | Tolerance | Deviation | Result |
|-----|------------------------|---------------|-----------|-----------|--------|
| Treatment | 300 | 314 | ±62d | -4.6% | PASS |
| Placebo | 169 | 155 | ±31d | +9.0% | PASS |
