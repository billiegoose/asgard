import importlib
from pathlib import Path

OLD_PACKAGE = "thor" + "_spec"


def test_python_packages_follow_src_library_machine_layout() -> None:
    for package in ("thor", "red2"):
        assert Path(f"src/lib/{package}/__init__.py").is_file()
    for package in (
        "thor_interpreter",
        "abstract_red2_machine",
        "concrete_red2_machine",
        "synthesizable_red2_machine",
    ):
        assert Path(f"src/machines/{package}/__init__.py").is_file()
    assert not Path("models").exists()
    assert not Path("src/lib/thor_lang").exists()
    assert not Path("src/lib/thor_compile").exists()
    assert not Path(f"src/{OLD_PACKAGE}").exists()


def test_runtime_packages_import_with_clean_top_level_names() -> None:
    for package in (
        "thor",
        "red2",
        "thor_interpreter",
        "abstract_red2_machine",
        "concrete_red2_machine",
        "synthesizable_red2_machine",
    ):
        module = importlib.import_module(package)
        assert module.__name__ == package


def test_removed_package_names_are_not_importable() -> None:
    for package in ("thor_lang", "thor_compile", OLD_PACKAGE):
        try:
            importlib.import_module(package)
        except ModuleNotFoundError:
            continue
        raise AssertionError(f"{package} package should not remain importable")
