"""Fixtures communes : racine du depot dans sys.path, chargement d'un script de scan/ par chemin."""
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session")
def root():
    return ROOT


@pytest.fixture
def load_script():
    """Importe un fichier .py (ex. scan/overlay_vo.py) sans l'executer comme programme principal."""
    def _load(relpath):
        path = ROOT / relpath
        spec = importlib.util.spec_from_file_location(path.stem + "_under_test", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    return _load
