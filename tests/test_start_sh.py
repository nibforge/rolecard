"""start.sh behaviour, run with bash against a fake Python (nothing is installed)."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

FAKE_PY = """#!/bin/bash
echo "py $*" >> "$FAKE_LOG"
if [ "$1" = -c ]; then exit "${FAKE_PY_EXIT:-0}"; fi
if [ "$1 $2" = "-m venv" ]; then
  mkdir -p "$3/bin"
  [ -n "$FAKE_VENV_FAIL" ] && exit 1
  cp "$FAKE_DIR/venvpy" "$3/bin/python"
  chmod +x "$3/bin/python"
  exit 0
fi
exit 9
"""
VENV_PY = """#!/bin/bash
echo "venv $*" >> "$FAKE_LOG"
if [ "$2" = pip ]; then exit "${FAKE_PIP_EXIT:-0}"; fi
exit 0
"""
OPENER = """#!/bin/bash
echo "open $1" >> "$FAKE_LOG"
"""


def _bash():
    if sys.platform != "win32":
        return shutil.which("bash")
    git = shutil.which("git")  # Git Bash, never WSL's bash.exe
    for folder in Path(git).resolve().parents if git else []:
        if (folder / "bin" / "bash.exe").exists():
            return str(folder / "bin" / "bash.exe")
    return None


BASH = _bash()
pytestmark = pytest.mark.skipif(not BASH, reason="needs bash")


def _write(path, text):
    path.write_bytes(text.encode())
    path.chmod(0o755)


@pytest.fixture
def launcher(tmp_path):
    fake, work = tmp_path / "fake", tmp_path / "work"
    fake.mkdir()
    work.mkdir()
    for name in ["python3.15", "python3.14", "python3.13", "python3.12", "python3"]:
        _write(fake / name, FAKE_PY)
    for name in ["open", "xdg-open"]:
        _write(fake / name, OPENER)
    _write(fake / "venvpy", VENV_PY)
    shutil.copy(ROOT / "start.sh", work / "start.sh")
    (work / "requirements.txt").write_bytes(b"flask==1\n")
    log = tmp_path / "log"

    def run(**extra):
        log.write_text("")
        env = dict(os.environ, PATH=str(fake) + os.pathsep + os.environ["PATH"],
                   LANG="en_US.UTF-8", FAKE_DIR=fake.as_posix(), FAKE_LOG=log.as_posix(),
                   **extra)
        env.pop("LC_ALL", None)
        env.pop("LC_MESSAGES", None)
        done = subprocess.run([BASH, "start.sh"], cwd=work, env=env, timeout=60,
                              stdin=subprocess.DEVNULL, capture_output=True)
        return done.returncode, log.read_text().splitlines()

    return work, run


PIP = "venv -m pip install --disable-pip-version-check --require-hashes -r requirements.txt"


def test_first_run_installs_then_later_runs_only_start(launcher):
    work, run = launcher
    code, log = run()
    assert code == 0
    assert "py -m venv .venv" in log
    assert log[-2:] == [PIP, "venv -m rolecard"]
    assert (work / ".venv/rolecard-requirements.txt").read_bytes() == b"flask==1\n"
    code, log = run()
    assert (code, log) == (0, ["venv -m rolecard"])


def test_changed_requirements_reinstall_in_the_same_venv(launcher):
    work, run = launcher
    run()
    (work / "requirements.txt").write_bytes(b"flask==2\n")
    code, log = run()
    assert (code, log) == (0, [PIP, "venv -m rolecard"])


def test_a_half_made_venv_is_rebuilt(launcher):
    work, run = launcher
    (work / ".venv/bin").mkdir(parents=True)
    shutil.copy(work.parent / "fake/venvpy", work / ".venv/bin/python")
    (work / ".venv/stale").write_text("x")
    code, log = run()
    assert code == 0
    assert "py -m venv .venv" in log and PIP in log
    assert not (work / ".venv/stale").exists()


def test_pip_failure_leaves_no_marker_and_fails(launcher):
    work, run = launcher
    code, log = run(FAKE_PIP_EXIT="1")
    assert code == 1
    assert "venv -m rolecard" not in log
    assert not (work / ".venv/rolecard-requirements.txt").exists()


def test_old_python_opens_the_download_page(launcher):
    work, run = launcher
    code, log = run(FAKE_PY_EXIT="1")
    assert code == 1
    assert "open https://www.python.org/downloads/" in log
    assert not (work / ".venv").exists()


def test_a_failed_venv_is_removed(launcher):
    work, run = launcher
    code, log = run(FAKE_VENV_FAIL="1")
    assert code == 1
    assert not (work / ".venv").exists()
