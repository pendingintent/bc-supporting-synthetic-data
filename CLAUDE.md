# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repository contains synthetic clinical trial data modeled after **NCT01797120 (PrE0102)** — a Phase II randomized trial of Fulvestrant +/- Everolimus in postmenopausal HR+ metastatic breast cancer (n=131, all female). The data is purely synthetic (`STUDYID = "SYNTH-ONC-001"`) and is not real patient data.

The source trial compared:
- **Treatment arm**: Fulvestrant 500 mg + Everolimus 10 mg daily (n=66)
- **Control arm**: Fulvestrant 500 mg + Placebo (n=65)

Primary endpoint: Progression-Free Survival (PFS). Published results: median PFS 10.3 vs. 5.1 months.

## Repository Structure

- `src/cdisc_generation_functions.py` — Python functions that generate all synthetic SDTM/ADaM datasets
- `datasets/` — Generated CSV files in CDISC SDTM and ADaM format
- `protocol/NCT01797120.pdf` — Original trial protocol
- `results/NCT01797120-results.md` — Human-readable trial results summary
- `results/NCT01797120-results.fhir.json` — FHIR EBM bundle of published results

## Dataset Domains

**SDTM domains:** `DM`, `EX`, `TR`, `RS`, `DS`, `TV`, `TA`
**ADaM datasets:** `ADSL`, `ADTTE`

Key variables: `USUBJID` (format: `SYNTH-ONC-001-NNNN`), `TRT01A` (`"Treatment"` / `"Placebo"`), `RSSTRESC` (`PR`, `SD`, `PD` per RECIST criteria), `PFS`/`CNSR` for time-to-event analysis.

## Running the Data Generation

The generation functions are in `src/cdisc_generation_functions.py` and use `pandas` and `numpy`. To regenerate datasets, call them in order — each function depends on output from the previous:

```python
from src.cdisc_generation_functions import *

dm = create_dm(n=200)
ex = create_ex(dm)
events = derive_events(ex, dm)
tr = create_tr(ex, events)
rs = derive_rs(tr)
ds = create_ds(dm, ex, rs)
adsl = create_adsl(dm, ex, rs)
tv = create_tv()
ta = create_ta()
```

Dependencies: `pip install pandas numpy`

## CDISC Standards Context

- SDTM domains follow CDISC SDTM v1.7 conventions (variable naming, controlled terminology)
- ADaM datasets follow CDISC ADaM BDS/ADTTE conventions (`AVAL`, `CNSR`, `PARAMCD`)
- Response assessments use RECIST v1.0 thresholds: PR ≤ −30% change, PD ≥ +20% change from baseline tumor sum
- PFS censoring: `CNSR=0` = event (progression), `CNSR=1` = censored
