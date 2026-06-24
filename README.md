# Synthetic Oncology Clinical Trial Dataset

Synthetic CDISC-compliant datasets modeled after **NCT01797120 (PrE0102)** — a Phase II randomized trial of Fulvestrant ± Everolimus in postmenopausal HR+ metastatic breast cancer.

> **All data is purely synthetic.** Study ID `NCT01797120`. No real patient data is present in this repository.

---

## Source Trial Summary

| Field | Value |
|---|---|
| Trial | NCT01797120 (PrE0102) |
| Indication | HR+ HER2− metastatic breast cancer (AI-resistant, postmenopausal) |
| Design | Phase II, randomized, double-blind, placebo-controlled |
| Arms | Fulvestrant 500 mg + Everolimus 10 mg (n=100) vs. Fulvestrant + Placebo (n=100) |
| Primary endpoint | Progression-Free Survival (PFS) |
| Published PFS | 10.3 months (treatment) vs. 5.1 months (placebo) |
| Publication | *Journal of Clinical Oncology*, June 2018 (PMID: 29664714) |

---

## Repository Structure

```
bc-supporting-synthetic-data/
├── .github/
│   └── workflows/
│       └── lint.yml                    # GitHub Actions: black + flake8 on every push/PR
├── src/
│   └── cdisc_generation_functions.py   # Python functions that generate all datasets
├── datasets/                           # Generated CDISC CSV files (see Datasets section)
├── skills/
│   └── validate-synth-data/            # Claude Code skill for dataset validation
│       ├── SKILL.md                    # Skill definition and workflow
│       ├── scripts/validate.py         # 100-check validation script
│       ├── evals/evals.json            # Skill test prompts
│       └── references/                 # CDISC rule sets and RECIST 1.1 supplement
├── protocol/
│   └── NCT01797120.pdf                 # Original trial protocol
├── results/
│   ├── NCT01797120-results.md          # Human-readable results summary
│   └── NCT01797120-results.fhir.json   # FHIR EBM bundle of published results
├── .pre-commit-config.yaml             # Pre-commit hooks (black, flake8)
├── ONBOARDING.md                       # Onboarding guide for new contributors
├── requirements.txt                    # Python dependencies
├── setup.cfg                           # Flake8 and black configuration (max-line-length=120)
└── validation_report.md                # Latest validation output (100/100 checks)
```

---

## Datasets

### SDTM Domains

| Domain | File | Description |
|---|---|---|
| `DM` | `DM.csv` | Demographics — age, sex, arm, randomization/consent/reference dates |
| `EX` | `EX.csv` | Exposure — drug, dose, route, start/end dates, study days |
| `TU` | `TU.csv` | Tumor Identification — target lesion locations per RECIST 1.1 (TU domain) |
| `TR` | `TR.csv` | Tumor Results — per-lesion LDIAM and visit-level SUMDIAM measurements |
| `RS` | `RS.csv` | Disease Response — CR/PR/SD/PD/NE derived from SUMDIAM per RECIST 1.1 |
| `DS` | `DS.csv` | Disposition — informed consent, randomization, treatment stop, study end |
| `FA` | `FA.csv` | Findings About — occurrence indicators for DS disposition/milestone events (`FAOBJ = DSDECOD`) |
| `RELREC` | `RELREC.csv` | Related Records — links FA and DS records per subject |
| `TV` | `TV.csv` | Trial Visits — planned visit schedule through ~18 cycles |
| `TA` | `TA.csv` | Trial Arms — SCREENING / INDUCTION / CONTINUATION / FOLLOW-UP epochs |

### ADaM Datasets

| Dataset | File | Description |
|---|---|---|
| `ADSL` | `ADSL.csv` | Subject-Level Analysis — baseline, flags (ITTFL, SAFFL, PPROTFL), PFS, best response |
| `ADTTE` | `ADTTE.csv` | Time-to-Event — PFS with `AVAL` (days), `CNSR`, `PARAMCD="PFS"` |

### Key Variables

| Variable | Description |
|---|---|
| `USUBJID` | Unique subject ID — format `NCT01797120-NNNN` |
| `TRT01A` | Actual treatment arm — `"Treatment"` or `"Placebo"` |
| `RSSTRESC` | RECIST 1.1 response — `CR`, `PR`, `SD`, `PD`, or `NE` |
| `AVAL` | Analysis value (days to progression or censoring) in ADTTE |
| `CNSR` | Censoring flag — `0` = progression event, `1` = censored |
| `TRLOBXFL` | Last observation before exposure flag (baseline) in TR |
| `TRLNKID` | Links TR lesion records to TU tumor identification records |

---

## Regenerating the Data

### Prerequisites

```bash
pip install -r requirements.txt
# or, using the project venv:
python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
```

### Run the generator

```bash
python src/cdisc_generation_functions.py
```

This writes all CSV files to `datasets/` using `numpy.random.seed(0)` for reproducibility.

### Generation order (if calling functions directly)

Each function depends on the previous output:

```python
from src.cdisc_generation_functions import *
import numpy as np

np.random.seed(0)

dm     = create_dm(n=200)
ex     = create_ex(dm)
events = derive_events(ex, dm)
ex     = finalize_ex(ex, events, dm)   # cap EX end dates at progression
tr     = create_tr(ex, events, dm)
rs     = derive_rs(tr)
tu     = create_tu(dm, tr)
dm     = finalize_dm(dm, ex, events)
ds     = create_ds(dm, ex, events)
adsl   = create_adsl(dm, ex, rs, events)
adtte  = create_adtte(adsl)
tv     = create_tv()
ta     = create_ta()
```

---

## Validating the Datasets

A dedicated validation script checks 100 rules across seven categories:

| Category | Checks |
|---|---|
| CDISC Structural | Required variables, controlled terminology, value formats per domain |
| Cross-domain Integrity | USUBJID consistency, arm-drug assignments, DS record completeness |
| RECIST Derivation | SUMDIAM traceability, response classification, TU-TR linkage |
| Timeline & Death Logic | Date ordering, no post-death observations, DTHDTC consistency |
| Population Distribution | Age range, enrollment spread, variability across subjects |
| Duplicate & Study Consistency | Sequence key uniqueness, domain coverage |
| PFS Fidelity | Observed median PFS vs. published trial results (±20% tolerance) |

### Run directly

```bash
python skills/validate-synth-data/scripts/validate.py \
  --datasets datasets/ \
  --output validation_report.md
```

### Run via Claude Code

If you have the skill installed (see Claude Code Setup below), you can ask Claude to validate the datasets in plain language:

> *"validate my datasets"*  
> *"check the CSVs before I package the ZIP"*  
> *"something looks off with the RS domain — audit the RECIST derivation"*

Claude will run the script and present the report with plain-language explanations of any failures.

---

## Claude Code Setup

This project includes a Claude Code skill (`skills/validate-synth-data/`) that adds dataset validation as a natural-language command. To activate it:

### 1. Install Claude Code

```bash
npm install -g @anthropic-ai/claude-code
```

Or download the desktop app from [claude.ai/code](https://claude.ai/code).

### 2. Install the skill

Copy (or symlink) the skill into your Claude Code skills directory:

```bash
# Copy
cp -r skills/validate-synth-data ~/.claude/skills/validate-synth-data

# Or symlink (changes in the repo are reflected immediately)
ln -s "$(pwd)/skills/validate-synth-data" ~/.claude/skills/validate-synth-data
```

### 3. Open the project in Claude Code

```bash
claude  # from the project root
```
In the Claude session, run:

```
/init
```

This will prompt you for instructions and create the `CLAUDE.md` file.

Claude will pick up the skill from `~/.claude/skills/`.

### 4. Verify the skill is active

In the Claude Code session, run:

> *"validate my datasets"*

You should see a report confirming 100/100 checks pass against the committed datasets.

### Updating the skill

If you modify `skills/validate-synth-data/scripts/validate.py` and used a symlink, the changes are live immediately. If you copied, re-run the `cp` command above.

---

## CDISC Standards Conformance

The datasets are generated to conform to the following standards. The `validation_report.md` in this repository reflects the current conformance status.

| Standard | Version | Coverage |
|---|---|---|
| SDTMIG | 3.4 | DM, EX, TU, TR, RS, DS, FA, RELREC, TV, TA |
| ADaMIG | 1.3 | ADSL (OCCDS), ADTTE (TTE) |
| RECIST | 1.1 | LDIAM/SUMDIAM in TR; CR/PR/SD/PD/NE in RS; TU domain |
| CDISC Conformance Rules | CORE | Key rules: CG0102, CG0073, CG0066, CG0432, CG0142, FB2201, FB0611, CG0563 |

---

## License

Synthetic data only. No patient privacy concerns. Refer to `protocol/NCT01797120.pdf` for the original trial protocol (copyright-exempt for non-commercial use per the RECIST Working Group).
