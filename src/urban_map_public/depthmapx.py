"""Run depthmapXcli as a local process without shell interpolation."""

from __future__ import annotations

import math
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class DepthmapXResult:
    """Captured result from one successful depthmapXcli invocation."""

    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


class DepthmapXError(RuntimeError):
    """Raised when the CLI cannot be resolved, times out, or exits unsuccessfully."""

    def __init__(
        self,
        message: str,
        *,
        returncode: int | None = None,
        stdout: str = "",
        stderr: str = "",
    ) -> None:
        super().__init__(message)
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _resolve_executable(executable: str | Path | None) -> Path:
    configured = str(
        executable or os.environ.get("DEPTHMAPX_CLI_PATH", "depthmapXcli")
    ).strip()
    if not configured:
        raise DepthmapXError("Set DEPTHMAPX_CLI_PATH or pass an executable path.")

    located = shutil.which(configured)
    if located:
        return Path(located).resolve()

    candidate = Path(configured).expanduser()
    if candidate.is_file():
        return candidate.resolve()

    raise DepthmapXError("depthmapXcli was not found on PATH or at the configured path.")


def _child_environment() -> dict[str, str]:
    """Pass only runtime variables commonly needed by a local CLI process."""
    allowed = (
        "PATH",
        "HOME",
        "TMPDIR",
        "TMP",
        "TEMP",
        "LANG",
        "LC_ALL",
        "SYSTEMROOT",
        "WINDIR",
        "LD_LIBRARY_PATH",
        "QT_QPA_PLATFORM",
    )
    environment = {key: os.environ[key] for key in allowed if key in os.environ}
    environment.setdefault("QT_QPA_PLATFORM", "offscreen")
    return environment


def run_depthmapx(
    args: Sequence[str],
    *,
    executable: str | Path | None = None,
    timeout: float = 14_400,
    cwd: str | Path | None = None,
) -> DepthmapXResult:
    """Run depthmapXcli with argument-list semantics and a reduced environment.

    Args are passed directly to the executable with shell execution disabled.
    The default executable may be overridden with DEPTHMAPX_CLI_PATH.
    """
    if isinstance(args, (str, bytes)) or not isinstance(args, Sequence) or not args:
        raise ValueError("Pass one or more CLI arguments as a sequence of strings.")
    if any(not isinstance(arg, str) or "\x00" in arg for arg in args):
        raise ValueError("CLI arguments must be strings without NUL characters.")
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
        raise ValueError("Timeout must be a positive finite number of seconds.")
    if not math.isfinite(float(timeout)) or timeout <= 0:
        raise ValueError("Timeout must be a positive finite number of seconds.")

    cli = _resolve_executable(executable)
    working_directory = Path(cwd).expanduser() if cwd is not None else None
    if working_directory is not None and not working_directory.is_dir():
        raise ValueError("The requested working directory does not exist.")

    command = (str(cli), *args)
    try:
        completed = subprocess.run(
            command,
            cwd=working_directory,
            env=_child_environment(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=float(timeout),
            check=False,
            shell=False,
        )
    except subprocess.TimeoutExpired as error:
        raise DepthmapXError(f"depthmapXcli exceeded the {timeout:g}-second timeout.") from error
    except OSError as error:
        raise DepthmapXError("depthmapXcli could not be started.") from error

    result = DepthmapXResult(
        command=command,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )
    if completed.returncode != 0:
        raise DepthmapXError(
            f"depthmapXcli exited with status {completed.returncode}.",
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
    return result
