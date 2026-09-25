import importlib
from pathlib import Path

OLD_PACKAGE = "thor" + "_spec"


def test_python_packages_live_under_models() -> None:
    for package in (
        "thor_lang",
        "thor_compile",
        "thor_interpreter",
        "abstract_red2_machine",
        "concrete_red2_machine",
        "synthesizable_red2_machine",
    ):
        assert Path(f"models/{package}/__init__.py").is_file()
    assert not Path("models/python").exists()
    assert not Path(f"models/{OLD_PACKAGE}").exists()
    assert not Path(f"src/{OLD_PACKAGE}").exists()


def test_runtime_packages_import_from_models() -> None:
    for package in (
        "thor_lang",
        "thor_compile",
        "thor_interpreter",
        "abstract_red2_machine",
        "concrete_red2_machine",
        "synthesizable_red2_machine",
    ):
        module = importlib.import_module(package)
        assert module.__name__ == package


def test_old_package_is_removed() -> None:
    try:
        importlib.import_module(OLD_PACKAGE)
    except ModuleNotFoundError:
        return
    raise AssertionError(f"{OLD_PACKAGE} package should not remain importable")
