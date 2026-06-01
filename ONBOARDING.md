# Onboarding Guide

Welcome to the **bc-supporting-synthetic-data** repository. This guide explains the purpose of the project, the clinical context behind it, and how to get oriented quickly.

---

## What Is This?

This repository provides **synthetic CDISC-compliant clinical trial datasets** modeled after a real published oncology trial (NCT01797120). The data is entirely fabricated — no real patients — but it is calibrated to reproduce the statistical properties of the published results.

The primary use case is **tooling development, testing, and demonstration** in contexts where realistic CDISC data is needed but real trial data cannot be used.

---

## Clinical Background

You don't need to be a clinician to work here, but this context helps you understand what the data represents.

### The Source Trial (PrE0102 / NCT01797120)

- **Disease:** HR+ (hormone receptor positive), HER2− metastatic breast cancer in postmenopausal women who had stopped responding to aromatase inhibitor (AI) therapy — a common second-line population with limited options.
- **Question asked:** Does adding **everolimus** (an mTOR pathway inhibitor) to **fulvestrant** (a hormonal therapy) extend time before disease progresses?
- **Design:** 131 patients randomized 1:1. Half received Fulvestrant + Everolimus; half received Fulvestrant + Placebo. Double-blind.
- **Key result:** Median progression-free survival (PFS) was **10.3 months** in the treatment arm vs. **5.1 months** in the placebo arm.
- **Published:** *Journal of Clinical Oncology*, June 2018 (PMID: 29664714)

### Why This Trial?

It is a clean, well-documented, completed Phase II trial with clearly published summary statistics (PFS medians, confidence intervals, response rates), making it ideal for calibrating synthetic data to realistic values.

---

## What "Synthetic" Means Here

The generation code in `src/cdisc_generation_functions.py` uses probability models — exponential distributions for time-to-progression, responder/non-responder tumor dynamics — that were empirically calibrated against the published KM medians via simulation:

- Treatment arm: 85% progression probability, exponential scale 350 days → median PFS ≈ 10.3 months
- Placebo arm: 90% progression probability, exponential scale 195 days → median PFS ≈ 5.1 months

Each time you regenerate the data you get a new random sample from these distributions. The aggregate statistics will be close to the published values, but individual subject records change.

---

## CDISC Standards Primer

If you're unfamiliar with CDISC, here's the minimum context:

**SDTM (Study Data Tabulation Model)** organizes collected data into domain-specific tables. Each domain has a standard two-letter code (DM = Demographics, EX = Exposure, RS = Response, etc.) and standardized variable names.

**ADaM (Analysis Data Model)** builds analysis-ready datasets on top of SDTM. `ADSL` is the subject-level summary; `ADTTE` is the time-to-event dataset used for survival analysis.

**Key conventions used here:**
- `USUBJID` uniquely identifies a subject across all domains: `SYNTH-ONC-001-NNNN`
- `TRT01A` is the treatment arm label: `"Treatment"` or `"Placebo"`
- `CNSR` in ADTTE: `0` = the event occurred (disease progressed), `1` = censored (study ended before progression)
- Response categories follow **RECIST v1.0**: `PR` (partial response, ≥30% shrinkage), `SD` (stable disease), `PD` (progressive disease, ≥20% growth)

---

## Repository Layout

```
src/
  cdisc_generation_functions.py   ← all data generation logic lives here
datasets/
  DM.csv, EX.csv, TR.csv, ...     ← pre-generated outputs (committed)
protocol/
  NCT01797120.pdf                 ← original trial protocol (read-only reference)
results/
  NCT01797120-results.md          ← plain-language results summary
  NCT01797120-results.fhir.json   ← machine-readable FHIR EBM results bundle
```

---

## Getting Started

### 1. Install dependencies

```bash
pip install pandas numpy
```

### 2. Understand the generation pipeline

Open `src/cdisc_generation_functions.py`. The functions must be called in order because each depends on the previous output:

```
create_dm()       → demographics, treatment assignment
  ↓
create_ex()       → exposure dates (sets study duration per subject)
  ↓
derive_events()   → internal: assigns progression date + responder status
  ↓
create_tr()       → tumor measurements at each visit
  ↓
derive_rs()       → response categories (PR/SD/PD) from TR
  ↓
create_ds()       → disposition (reason for discontinuation)
  ↓
create_adsl()     → subject-level analysis dataset
  ↓
create_tv/ta()    → trial visit schedule and arm definitions (static)
```

### 3. Regenerate the data (optional)

```python
from src.cdisc_generation_functions import *

dm     = create_dm(n=200)
ex     = create_ex(dm)
events = derive_events(ex, dm)
tr     = create_tr(ex, events)
rs     = derive_rs(tr)
ds     = create_ds(dm, ex, rs)
adsl   = create_adsl(dm, ex, rs)
tv     = create_tv()
ta     = create_ta()
```

Change `n=200` to generate more or fewer subjects (must be even for 1:1 randomization).

### 4. Read the results context

`results/NCT01797120-results.md` gives a complete plain-language summary of the source trial: design, eligibility, endpoints, key results, and site list. Useful for understanding what the data is supposed to represent.

---

## Common Questions

**Why does the data change each run?**
The generation uses `numpy` random sampling. Each call to `create_dm()` produces a new random sample. If you need reproducibility, set a seed before calling: `np.random.seed(42)`.

**What is `STUDYID = "SYNTH-ONC-001"`?**
A made-up study identifier that signals this is synthetic data and prevents confusion with real trial databases.

**How realistic is the data?**
The aggregate statistics (PFS medians, response rates) are calibrated to published values. Individual-level records are plausible but not meant to represent any real patient.

**Can I use this for regulatory submissions?**
No. This is synthetic data for tooling and demonstration purposes only.

---

## Further Reading

- `README.md` — technical reference for datasets and variables
- `protocol/NCT01797120.pdf` — full trial protocol
- CDISC SDTM v1.7 Implementation Guide (external)
- CDISC ADaM ADTTE Guidance (external)
