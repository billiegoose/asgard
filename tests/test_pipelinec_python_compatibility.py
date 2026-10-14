"""Keep compiler invocation usable without a temporary distutils shim."""

import importlib.util
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "pipelinec_compatibility_test", ROOT / "scripts/pipelinec_toolchain.py"
)
toolchain = importlib.util.module_from_spec(spec)
spec.loader.exec_module(toolchain)


def test_compiler_bootstrap_preserves_arguments_and_loads_compatibility(tmp_path):
    (tmp_path / "setuptools.py").write_text(
        "import sys, types\n"
        "package = types.ModuleType('distutils')\n"
        "package.__path__ = []\n"
        "utility = types.ModuleType('distutils.dir_util')\n"
        "utility.copy_tree = lambda: 'compatibility loaded'\n"
        "package.dir_util = utility\n"
        "sys.modules['distutils'] = package\n"
        "sys.modules['distutils.dir_util'] = utility\n"
    )
    script = tmp_path / "compiler with spaces.py"
    script.write_text(
        "import json, sys\n"
        "from distutils.dir_util import copy_tree\n"
        "print(json.dumps([sys.argv, copy_tree()]))\n"
    )
    command = toolchain.compiler_python_command(
        script, "--no_synth", "output with spaces"
    )
    command.insert(1, "-S")
    result = subprocess.run(
        command,
        env={**os.environ, "PYTHONPATH": str(tmp_path)},
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(result.stdout) == [
        [str(script), "--no_synth", "output with spaces"],
        "compatibility loaded",
    ]


def test_compiler_bootstrap_preserves_an_unrelated_import_failure(tmp_path):
    package = tmp_path / "distutils"
    package.mkdir()
    (package / "__init__.py").write_text("")
    (package / "dir_util.py").write_text(
        "raise ModuleNotFoundError(\"No module named 'another_dependency'\", "
        "name='another_dependency')\n"
    )
    (tmp_path / "setuptools.py").write_text(
        "raise AssertionError('SETUPTOOLS_WAS_IMPORTED')\n"
    )
    script = tmp_path / "compiler.py"
    script.write_text("raise AssertionError('COMPILER_WAS_EXECUTED')\n")
    command = toolchain.compiler_python_command(script)
    command.insert(1, "-S")
    result = subprocess.run(
        command,
        env={**os.environ, "PYTHONPATH": str(tmp_path)},
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "another_dependency" in result.stderr
    assert "SETUPTOOLS_WAS_IMPORTED" not in result.stderr
    assert "COMPILER_WAS_EXECUTED" not in result.stderr
