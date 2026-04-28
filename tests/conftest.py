import pathlib
import pytest

DATA_DIR = pathlib.Path(__file__).parent / "data"
INPUT_DIR = DATA_DIR / "CD_PDX_010/CD_PDX_010_Final"
GOLDEN_DIR = DATA_DIR / "CD_PDX_010_expected"


@pytest.fixture
def input_dir():
    return INPUT_DIR


@pytest.fixture
def golden_dir():
    return GOLDEN_DIR
