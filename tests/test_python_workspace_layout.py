from __future__ import annotations

import importlib
from pathlib import Path


def test_python_packages_live_under_models_python() -> None:
    assert Path("models/python/thor_spec/__init__.py").is_file()
    assert Path("models/python/pypeline_red2/__init__.py").is_file()
    assert not Path("src/thor_spec").exists()
    assert not Path("pypeline_red2").exists()


def test_python_import_names_stay_stable() -> None:
    thor_spec = importlib.import_module("thor_spec")
    stepper = importlib.import_module("pypeline_red2.red2_stepper")

    assert thor_spec.__name__ == "thor_spec"
    assert hasattr(stepper, "red2_step_word")
