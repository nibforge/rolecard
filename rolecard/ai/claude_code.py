"""Claude Code in headless mode (``claude -p``) as a provider, with no tools at all.

The prompt (which carries untrusted CV / offer text) goes through stdin, never on the
command line; the process runs without a shell, in an empty temporary folder, with no
tools, no MCP servers, no slash commands, no saved session and a hard timeout.

It also runs in safe mode (``--safe-mode``: none of the user's CLAUDE.md, hooks, plugins
or MCP servers; sign-in works as usual) and with a closed list of environment variables
(``ENV_ALLOWED``), so rolecard's own keys (``ROLECARD_*``, Adzuna) never reach it.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import tempfile
from collections.abc import Callable

from rolecard.ai.base import SYSTEM_PROMPT, AIError, AIProvider

FLAGS = (
    "-p",
    "--output-format", "json",
    "--tools", "",
    "--strict-mcp-config",
    "--disable-slash-commands",
    "--no-session-persistence",
    "--safe-mode",
    "--append-system-prompt", SYSTEM_PROMPT,
)


# What the CLI needs to start, sign in and reach the network; nothing else is passed on.
ENV_ALLOWED = frozenset({
    "PATH", "PATHEXT", "HOME", "USERPROFILE", "HOMEDRIVE", "HOMEPATH", "USERNAME", "USER",
    "LOGNAME", "APPDATA", "LOCALAPPDATA", "PROGRAMDATA", "PROGRAMFILES", "SYSTEMROOT",
    "SYSTEMDRIVE", "WINDIR", "COMSPEC", "TEMP", "TMP", "TMPDIR", "LANG", "TERM", "SHELL",
    "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_RUNTIME_DIR",
    "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "no_proxy",
    "NODE_EXTRA_CA_CERTS", "SSL_CERT_FILE", "SSL_CERT_DIR",
})
ENV_ALLOWED_PREFIXES = ("LC_", "ANTHROPIC_", "CLAUDE_")


def child_env(env: dict[str, str] | None = None) -> dict[str, str]:
    """The environment for the ``claude`` process: only the allowed variables."""
    env = os.environ if env is None else env
    return {k: v for k, v in env.items()
            if k.upper() in ENV_ALLOWED or k.upper().startswith(ENV_ALLOWED_PREFIXES)}


def find_claude() -> str | None:
    """Full path of the ``claude`` executable, or None if it is not installed."""
    return shutil.which("claude")


class ClaudeCodeProvider(AIProvider):
    name = "claude"

    def __init__(self, timeout: int = 120, executable: str | None = None,
                 runner: Callable[..., subprocess.CompletedProcess] | None = None) -> None:
        self.timeout = timeout
        self.executable = executable
        self._run = runner or run_tree

    def command(self) -> list[str]:
        exe = self.executable or find_claude()
        if not exe:
            raise AIError("not_installed", "claude is not on PATH")
        return [exe, *FLAGS]

    def complete(self, prompt: str, schema: dict | None = None) -> str:
        cmd = self.command()
        with tempfile.TemporaryDirectory(prefix="rolecard-ai-") as workdir:
            try:
                proc = self._run(
                    cmd, input=prompt, capture_output=True, text=True, encoding="utf-8",
                    cwd=workdir, timeout=self.timeout, shell=False, check=False,
                    env=child_env(),
                )
            except FileNotFoundError as exc:
                raise AIError("not_installed", str(exc)) from exc
            except subprocess.TimeoutExpired as exc:
                raise AIError("timeout", f"after {self.timeout}s") from exc
            except OSError as exc:
                raise AIError("failed", str(exc)) from exc
        if proc.returncode != 0:
            raise AIError("failed", f"exit code {proc.returncode}")
        return _result_text(proc.stdout or "")


def _kill_tree(proc: subprocess.Popen) -> None:
    """Kill ``proc`` and its children (``claude.cmd`` starts node under cmd.exe)."""
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)],
                           capture_output=True, check=False, timeout=10)
        else:
            os.killpg(proc.pid, signal.SIGKILL)
    except (OSError, subprocess.SubprocessError):
        pass
    proc.kill()


def run_tree(cmd: list[str], *, input: str, cwd: str, timeout: float,  # noqa: PLR0913
             env: dict[str, str] | None = None, **_ignored) -> subprocess.CompletedProcess:
    """Like ``subprocess.run`` (no shell), but a timeout kills the whole process tree so
    the call cannot hang on pipes held open by grandchildren. Output decoded as UTF-8
    with replacement."""
    if os.name == "nt":
        new_group = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    else:
        new_group = {"start_new_session": True}
    with subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, cwd=cwd, env=env, shell=False,
                          **new_group) as proc:
        try:
            out, err = proc.communicate(input.encode("utf-8"), timeout=timeout)
        except subprocess.TimeoutExpired:
            _kill_tree(proc)
            try:
                proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                pass
            raise
    return subprocess.CompletedProcess(cmd, proc.returncode,
                                       out.decode("utf-8", "replace"),
                                       err.decode("utf-8", "replace"))


def _result_text(stdout: str) -> str:
    """The ``result`` field of claude's JSON envelope."""
    try:
        envelope = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise AIError("failed", "claude did not return its JSON envelope") from exc
    if not isinstance(envelope, dict) or envelope.get("is_error"):
        raise AIError("failed", "claude reported an error")
    result = envelope.get("result")
    if not isinstance(result, str):
        raise AIError("failed", "claude envelope has no text result")
    return result
