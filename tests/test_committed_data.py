"""The committed datasets/ CSVs must be exactly what the generator produces."""

import pytest

from src import cdisc_generation_functions as gen

DOMAINS = ["DM", "EX", "TU", "TR", "RS", "DS", "AE", "FA", "RELREC", "ADSL", "ADTTE", "TV", "TA"]


@pytest.fixture(scope="module")
def regenerated(data, tmp_path_factory):
    out = tmp_path_factory.mktemp("regen")
    gen.write_datasets(data, out)
    return out


@pytest.mark.parametrize("domain", DOMAINS)
def test_committed_csv_matches_regeneration(domain, regenerated, repo_root):
    committed = (repo_root / "datasets" / f"{domain}.csv").read_bytes()
    fresh = (regenerated / f"{domain}.csv").read_bytes()
    assert committed == fresh, (
        f"datasets/{domain}.csv differs from regenerated output; run "
        "`python src/cdisc_generation_functions.py` and commit the result"
    )
