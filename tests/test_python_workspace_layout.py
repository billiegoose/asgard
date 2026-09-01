from __future__ import annotations

import importlib
from pathlib import Path

OLD_PACKAGE = "thor" + "_spec"


def test_python_packages_live_under_models_python() -> None:
    assert Path("models/python/thor_lang/__init__.py").is_file()
    assert Path("models/python/thor_engine/__init__.py").is_file()
    assert Path("models/python/red2_engine/__init__.py").is_file()
    assert Path("models/python/thor_compile/__init__.py").is_file()
    assert not Path(f"models/python/{OLD_PACKAGE}").exists()
    assert not Path(f"src/{OLD_PACKAGE}").exists()


def test_runtime_packages_import_from_models_python() -> None:
    thor_lang = importlib.import_module("thor_lang")
    thor_engine = importlib.import_module("thor_engine")
    red2_engine = importlib.import_module("red2_engine")
    thor_compile = importlib.import_module("thor_compile")

    assert thor_lang.__name__ == "thor_lang"
    assert thor_engine.__name__ == "thor_engine"
    assert red2_engine.__name__ == "red2_engine"
    assert thor_compile.__name__ == "thor_compile"


def test_old_package_is_removed() -> None:
    try:
        importlib.import_module(OLD_PACKAGE)
    except ModuleNotFoundError:
        return
    raise AssertionError(f"{OLD_PACKAGE} package should not remain importable")
