# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

Generator + validator for fully synthetic CDISC SDTM/ADaM datasets (STUDYID `NCT01797120`) modeled on the PrE0102 trial (Fulvestrant ± Everolimus, HR+ metastatic breast cancer). The CSVs in `datasets/` are committed outputs, not inputs. Source protocol/SAP PDFs are in `docs/`.

## Commands

Always use the project venv (`.venv/bin/python`, `.venv/bin/pip`); after adding packages, update `requirements.txt`.

```bash
# Regenerate all CSVs into datasets/ (np.random.seed(0) → deterministic)
.venv/bin/python src/cdisc_generation_functions.py

# Validate (writes validation_report.md)
.venv/bin/python skills/validate-synth-data/scripts/validate.py --datasets datasets/ --output validation_report.md

# Lint (CI runs pre-commit: black + flake8, line length 120)
.venv/bin/pre-commit run --all-files
```

There is no unit test suite; `validate.py` is the test. It has no single-check CLI flag — each category is a `check_*` function in the script, so to run one, import it and call it with a `Path` to `datasets/`.

## Architecture

**Generator (`src/cdisc_generation_functions.py`)** — one module, one function per domain, and the `__main__` block defines the required call order because functions consume each other's output:

`create_dm → create_ex → derive_events → finalize_ex → create_tr → derive_rs → create_tu → finalize_dm → create_ds → apply_fatal_ae → create_fa → create_relrec → create_adsl → create_adtte`, plus independent `create_tv` / `create_ta`.

- `derive_events` decides per-subject progression/death/censoring; `finalize_ex` and `finalize_dm` are second passes that cap exposure and set death/reference dates after events are known. Don't reorder.
- Progression dates are snapped onto the tumour-scan schedule (`_FIRST_SCAN_DAY`, `_SCAN_INTERVAL_DAYS`, `_snap_to_scan_day`) so a PD disposition is never earlier than a scan that could observe it. TR scan timing uses the same constants — change them in one place.
- `_PROG` parameters are empirically calibrated so observed median PFS matches the published values (10.3 vs 5.1 months). Changing progression/censoring logic will shift PFS and can fail the fidelity check.
- `TRT01A` is a helper column on DM (needed by TR) and `_DSSEQ` on FA; both are dropped at write time in `__main__`.
- `apply_fatal_ae` guarantees at least one Placebo death tied to an AE; ADSL `DCSREAS` is intentionally *not* overridden for that subject.

**Validator (`skills/validate-synth-data/scripts/validate.py`)** — seven `check_*` functions (structural, integrity, RECIST, timeline/death, population, duplicates, PFS fidelity) aggregated by `build_report`. Rule references (`references/sdtm-rules.csv`, `adam-rules.csv`, RECIST supplement) back the structural checks. PFS fidelity uses a ±20% tolerance against published medians (with `int()` truncation — keep `SKILL.md` examples consistent with that).

## Keeping skill copies in sync

The skill lives in `skills/validate-synth-data/` (tracked) and is also installed at `~/.claude/skills/validate-synth-data/`. (`.claude/skills/validate-synth-data` is a committed real copy, not a symlink, so it works for Windows teammates; keep it identical to `skills/validate-synth-data`.) When you edit any file in one, mirror the change to the others without being asked. Keep the check count in `SKILL.md` and README in step with `validate.py` (these have drifted before: README says 100, SKILL.md says 105).

## Workflow notes

- Regenerating data changes `datasets/*.csv` and `validation_report.md`; commit them together with the generator change.
- Never commit `.claude/settings.local.json`.
- Memory notes (in-repo `memory/` and the auto-memory directory) must always use STUDYID `NCT01797120`, never `SYNTH-ONC-001`.
