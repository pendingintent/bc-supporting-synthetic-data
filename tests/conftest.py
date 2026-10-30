from pathlib import Path

import pytest

from src import cdisc_generation_functions as gen

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def data():
    """The full pipeline output ({domain: DataFrame}) for the default seed, generated once."""
    return gen.generate_all()


@pytest.fixture(scope="session")
def repo_root():
    return REPO_ROOT
