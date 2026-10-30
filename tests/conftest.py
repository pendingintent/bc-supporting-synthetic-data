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


VALIDATE_PATH = REPO_ROOT / ".claude" / "skills" / "validate-synth-data" / "scripts" / "validate.py"


@pytest.fixture(scope="session")
def validator():
    """The validate.py module, loaded by path (it lives in a dashed skill directory)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("validate_synth_data", VALIDATE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def clean_dir(data, tmp_path_factory):
    """A directory holding the freshly generated, unmodified CSVs."""
    out = tmp_path_factory.mktemp("clean")
    gen.write_datasets(data, out)
    return out
