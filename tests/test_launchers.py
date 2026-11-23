"""The double-click launchers and the rolecard.zip download built by /entregar."""

import json
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
LAUNCHERS = ["Iniciar rolecard.bat", "Iniciar rolecard.command", "start.sh"]
_LOCAL_PATH = re.compile(r"[A-Za-z]:[\/]+Users[\/]|/(Users|home)/[^/\s]+/")


@pytest.mark.parametrize("name", LAUNCHERS)
def test_launcher_exists_without_local_paths(name):
    text = (ROOT / name).read_text(encoding="utf-8")
    assert not _LOCAL_PATH.search(text)
    assert "applyline" not in text


@pytest.mark.parametrize("name", ["Iniciar rolecard.bat", "start.sh"])
def test_launcher_runs_rolecard_and_installs_only_the_pinned_requirements(name):
    text = (ROOT / name).read_text(encoding="utf-8")
    assert "-m rolecard" in text
    installs = re.findall(r"pip install [^|\n]*requirements\.txt", text)
    assert text.count("pip install") == 1
    pip = "pip install --disable-pip-version-check --require-hashes -r requirements.txt"
    assert installs == [pip]
    assert not re.search(r"\b(curl|wget|Invoke-WebRequest|iwr|bitsadmin)\b", text)
    assert "https://www.python.org/downloads/" in text
    assert "sys.version_info < (3, 12)" in text


def test_the_macos_launcher_runs_start_sh():
    text = (ROOT / "Iniciar rolecard.command").read_text(encoding="utf-8")
    assert text.startswith("#!/bin/bash\n")
    assert 'start.sh"' in text


_HAS_METHOD = (ROOT / ".claude/metodo/lib/entregar.mjs").exists()
_HAS_TOOLS = shutil.which("node") and shutil.which("git") and (ROOT / ".git").exists()


@pytest.mark.skipif(not (_HAS_METHOD and _HAS_TOOLS), reason="needs the method, node and git")
def test_entregar_also_builds_rolecard_zip_with_the_launchers_on_top(tmp_path):
    cfg = json.loads((ROOT / ".claude/metodo/entrega.json").read_text(encoding="utf-8"))
    assert cfg["descarga"] == "rolecard.zip"
    lib = (ROOT / ".claude/metodo/lib/entregar.mjs").as_uri()
    out = (tmp_path / "rolecard-9.9.9.zip").as_posix()
    script = (f"const m = await import({json.dumps(lib)}); const cfg = {json.dumps(cfg)};"
              f"m.generarZip(process.cwd(), cfg, 'rolecard', '9.9.9', {json.dumps(out)});"
              f"m.zipDescarga({json.dumps(out)}, cfg);")
    subprocess.run(["node", "--input-type=module", "-e", script], cwd=ROOT, check=True)
    download = tmp_path / "rolecard.zip"
    assert (tmp_path / "rolecard.zip.sha256").read_text().endswith("  rolecard.zip\n")
    with zipfile.ZipFile(download) as zf:
        names = zf.namelist()
        assert {n.split("/")[0] for n in names} == {"rolecard"}
        for name in LAUNCHERS:
            assert f"rolecard/{name}" in names
        mode = {n: zf.getinfo(n).external_attr >> 16 for n in names}
        assert mode["rolecard/Iniciar rolecard.command"] & 0o111
        assert mode["rolecard/start.sh"] & 0o111
        assert b"\r\n" in zf.read("rolecard/Iniciar rolecard.bat")
        assert b"\r\n" not in zf.read("rolecard/start.sh")
