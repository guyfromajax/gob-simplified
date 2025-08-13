import os
import subprocess
import sys
import textwrap
from pathlib import Path
import shutil


def test_package_includes_data(tmp_path):
    project_root = Path(__file__).resolve().parent.parent
    package_src = tmp_path / "pkg"
    shutil.copytree(project_root / "BackEnd", package_src / "BackEnd")
    shutil.copy2(project_root / "setup.cfg", package_src / "setup.cfg")
    shutil.copy2(project_root / "MANIFEST.in", package_src / "MANIFEST.in")
    (package_src / "pyproject.toml").write_text(
        "[build-system]\nrequires=['setuptools','wheel']\nbuild-backend='setuptools.build_meta'\n"
    )
    venv_dir = tmp_path / "venv"
    subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
    python = venv_dir / ("Scripts" if os.name == "nt" else "bin") / "python"
    pip = venv_dir / ("Scripts" if os.name == "nt" else "bin") / "pip"
    subprocess.run([str(pip), "install", "--no-deps", str(package_src)], check=True)
    check_code = textwrap.dedent(
        """
        import json
        import importlib.resources as res

        path = res.files('BackEnd') / 'data' / 'names' / 'franchise_names.json'
        assert path.is_file(), f"Missing resource: {path}"
        json.loads(path.read_text())
        """
    )
    subprocess.run([str(python), "-c", check_code], check=True)
