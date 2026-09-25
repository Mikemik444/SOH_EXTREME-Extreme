"""Compatibility launcher: build the canonical arvhipelago source, not an old ZIP.

Normal Windows game builds run the same PowerShell builder automatically.
This legacy entry point builds the repository APWorld without installing it.
"""
from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys


def main() -> int:
    root = Path(__file__).resolve().parent
    script = root / "tools" / "build_standalone_apworld.ps1"
    if not script.is_file():
        print(f"ERROR: Missing canonical APWorld builder: {script}", file=sys.stderr)
        return 1
    shell = shutil.which("powershell.exe") or shutil.which("pwsh")
    if shell is None:
        print("ERROR: This compatibility launcher requires Windows PowerShell or pwsh.", file=sys.stderr)
        return 1
    try:
        return subprocess.run(
            [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script),
             "-ProjectRoot", str(root), "-SkipInstall"],
            cwd=root, check=False,
        ).returncode
    except OSError as error:
        print(f"ERROR: Could not start the APWorld builder: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
