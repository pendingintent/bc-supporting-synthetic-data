# Synthetic Oncology Clinical Trial Dataset

Synthetic CDISC-compliant datasets modeled after **NCT01797120 (PrE0102)** — a Phase II randomized trial of Fulvestrant ± Everolimus in postmenopausal HR+ metastatic breast cancer.

> **All data is purely synthetic.** Study ID `SYNTH-ONC-001`. No real patient data is present in this repository.

---

## Source Trial Summary

| Field | Value |
|---|---|
| Trial | NCT01797120 (PrE0102) |
| Indication | HR+ HER2− metastatic breast cancer (AI-resistant, postmenopausal) |
| Design | Phase II, randomized, double-blind, placebo-controlled |
| Arms | Fulvestrant 500 mg + Everolimus 10 mg (n=66) vs. Fulvestrant + Placebo (n=65) |
| Primary endpoint | Progression-Free Survival (PFS) |
| Published PFS | 10.3 months (treatment) vs. 5.1 months (placebo) |
| Publication | *Journal of Clinical Oncology*, June 2018 (PMID: 29664714) |

---

## Repository Structure

```
bc-supporting-synthetic-data/
├── src/
│   └── cdisc_generation_functions.py   # Python functions that generate all datasets
├── datasets/                           # Generated CDISC CSV files
│   ├── DM.csv                          # Demographics (SDTM)
│   ├── EX.csv                          # Exposure (SDTM)
│   ├── TR.csv                          # Tumor Results (SDTM)
│   ├── RS.csv                          # Disease Response (SDTM)
│   ├── DS.csv                          # Disposition (SDTM)
│   ├── TV.csv                          # Trial Visits (SDTM)
│   ├── TA.csv                          # Trial Arms (SDTM)
│   ├── ADSL.csv                        # Subject-Level Analysis (ADaM)
│   └── ADTTE.csv                       # Time-to-Event Analysis (ADaM)
├── protocol/
│   └── NCT01797120.pdf                 # Original trial protocol
├── results/
│   ├── NCT01797120-results.md          # Human-readable results summary
│   └── NCT01797120-results.fhir.json   # FHIR EBM bundle of published results
└── CLAUDE.md                           # AI assistant instructions
```

---

## Datasets

### SDTM Domains

| Domain | Description |
|---|---|
| `DM` | Demographics — age, sex, treatment arm, randomization date |
| `EX` | Exposure — study drug, dose, start/end dates |
| `TR` | Tumor Results — per-visit lesion measurements (RECIST v1.0) |
| `RS` | Disease Response — PR/SD/PD assessments derived from TR |
| `DS` | Disposition — reason for study discontinuation |
| `TV` | Trial Visits — planned visit schedule |
| `TA` | Trial Arms — treatment arm definitions |

### ADaM Datasets

| Dataset | Description |
|---|---|
| `ADSL` | Subject-Level Analysis Dataset — one row per subject, all baseline and summary variables |
| `ADTTE` | Time-to-Event — PFS with `AVAL` (days), `CNSR` (0=event, 1=censored), `PARAMCD="PFS"` |

### Key Variables

| Variable | Description |
|---|---|
| `USUBJID` | Unique subject ID — format `SYNTH-ONC-001-NNNN` |
| `TRT01A` | Treatment arm — `"Treatment"` or `"Placebo"` |
| `RSSTRESC` | Response category — `PR`, `SD`, or `PD` (RECIST v1.0) |
| `AVAL` | Analysis value (days to event/censoring) in ADTTE |
| `CNSR` | Censoring flag — `0` = progression event, `1` = censored |

---

## Regenerating the Data

Requires Python 3.8+ with `pandas` and `numpy`.

```bash
pip install pandas numpy
```

```python
from src.cdisc_generation_functions import *

dm    = create_dm(n=200)
ex    = create_ex(dm)
events = derive_events(ex, dm)
tr    = create_tr(ex, events)
rs    = derive_rs(tr)
ds    = create_ds(dm, ex, rs)
adsl  = create_adsl(dm, ex, rs)
tv    = create_tv()
ta    = create_ta()
```

Each function depends on the output of the previous. The default `n=200` generates 200 synthetic subjects (100 per arm). Progression parameters are calibrated via simulation to reproduce the published trial KM medians.

---

## CDISC Standards

- **SDTM:** CDISC SDTM v1.7 variable naming and controlled terminology
- **ADaM:** CDISC ADaM BDS/ADTTE conventions
- **Response:** RECIST v1.0 (PR ≤ −30% change from baseline tumor sum; PD ≥ +20%)
- **FHIR:** Results bundle conforms to `http://hl7.org/fhir/uv/ebm` EBM profiles

---

## License

Synthetic data only. No patient privacy concerns. Refer to `protocol/NCT01797120.pdf` for the original trial protocol.
