"""macOS DDC/CI backend using the m1ddc command-line tool.

This backend supports Apple Silicon Macs (M1/M2/M3/M4+) where the
``monitorcontrol`` library's native backend is not available.  It shells out
to ``m1ddc`` (https://github.com/waydabber/m1ddc) which is available via
Homebrew::

    brew install m1ddc

Supported m1ddc commands used here:
  m1ddc display list            -> list displays
  m1ddc display <n> get input   -> get current input source (VCP 0x60)
  m1ddc display <n> set input <val> -> set input source
"""
from __future__ import annotations

import re
import shutil
import subprocess
import logging
from pathlib import Path
from typing import NamedTuple

_logger = logging.getLogger(__name__)

_M1DDC_NOT_FOUND_MSG = (
    "未找到 m1ddc 命令。请先安装：brew install m1ddc\n"
    "详情: https://github.com/waydabber/m1ddc"
)

_M1DDC_CANDIDATE_PATHS = (
    "/opt/homebrew/bin/m1ddc",  # Apple Silicon Homebrew default prefix
    "/usr/local/bin/m1ddc",     # Intel Homebrew default prefix
)


class MacOSDisplayInfo(NamedTuple):
    index: int          # 1-based index used by m1ddc
    name: str
    uuid: str


def _resolve_m1ddc_binary() -> str | None:
    """Resolve m1ddc executable even when PATH is minimal (e.g., Finder-launched app)."""
    discovered = shutil.which("m1ddc")
    if discovered:
        return discovered

    for candidate in _M1DDC_CANDIDATE_PATHS:
        path = Path(candidate)
        if path.is_file() and path.exists():
            return str(path)
    return None


def _run(args: list[str], timeout: int = 5) -> str:
    """Run a command and return stdout. Raises RuntimeError on failure."""
    result = subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"命令失败: {' '.join(args)}")
    return result.stdout.strip()


def _run_m1ddc(args: list[str], timeout: int = 5) -> str:
    """Run m1ddc with resolved absolute path."""
    binary = _resolve_m1ddc_binary()
    if not binary:
        raise RuntimeError(_M1DDC_NOT_FOUND_MSG)
    return _run([binary, *args], timeout=timeout)


def is_available() -> bool:
    """Return True if m1ddc is installed and executable."""
    return _resolve_m1ddc_binary() is not None


def list_displays() -> list[MacOSDisplayInfo]:
    """Return all displays reported by ``m1ddc display list``."""
    if not is_available():
        raise RuntimeError(_M1DDC_NOT_FOUND_MSG)

    output = _run_m1ddc(["display", "list"])
    displays: list[MacOSDisplayInfo] = []
    # Each line looks like:  [1] My Monitor Name (UUID-STRING)
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r"\[(\d+)\]\s*(.*?)\s*\(([^)]+)\)\s*$", line)
        if m:
            idx = int(m.group(1))
            raw_name = m.group(2).strip()
            uuid = m.group(3).strip()
            name = raw_name if raw_name and raw_name != "(null)" else f"Display {idx}"
            displays.append(MacOSDisplayInfo(index=idx, name=name, uuid=uuid))
        else:
            _logger.warning("m1ddc display list: 无法解析行: %r", line)

    return displays


def get_input(display_index: int) -> int | None:
    """Return the current input source code for a display, or None on error."""
    try:
        raw = _run_m1ddc(["display", str(display_index), "get", "input"])
        return int(raw)
    except Exception as exc:
        _logger.warning("m1ddc 读取输入源失败 display=%s: %s", display_index, exc)
        return None


def set_input(display_index: int, input_code: int) -> None:
    """Set the input source for a display."""
    _run_m1ddc(["display", str(display_index), "set", "input", str(input_code)])
