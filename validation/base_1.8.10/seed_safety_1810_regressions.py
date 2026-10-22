"""Check retained dungeon blockers after changing the shared Water Temple arrival and action helpers."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time

import Utils

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source"
USER_YAML = ROOT / "upload/SOH-EXTREME(20261017-230302).yaml"
REPORTED_SEED = ROOT / "tests/reported_seed_187_reproduction.json"
SUITES = (
    ("tools/tests/test_trial_medallion_logic.py", 13),
    ("tools/tests/test_entrance_blockers.py", 22),
)


def hashes():
    paths = [p for p in (SOURCE / "archipelago/soh_extreme").rglob("*")
             if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"]
    paths.extend(SOURCE / name for name, _ in SUITES)
    return {p.relative_to(SOURCE).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in paths}


def main():
    before = hashes()
    suites = []
    started = time.monotonic()
    input_hashes = {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in (USER_YAML, REPORTED_SEED)}
    for name, expected in SUITES:
        command = [sys.executable, str(SOURCE / name)]
        if name == "tools/tests/test_entrance_blockers.py":
            command += ["--yaml", str(USER_YAML),
                        "--report", str(ROOT / "tests/seed_safety_1810_entrance_blockers.json"),
                        "--reported-seed", str(REPORTED_SEED)]
        result = subprocess.run(command, text=True, capture_output=True, timeout=120)
        output = result.stdout + result.stderr
        count = re.search(r"Ran (\d+) tests? in", output)
        assert result.returncode == 0 and count and int(count[1]) == expected, output
        assert re.search(r"^OK\s*$", output, re.MULTILINE), output
        suites.append({"suite": name, "test_cases": expected, "status": "passed",
                       "command": command, "output": output})
    assert before == hashes(), "AP source changed during the regression run"
    assert input_hashes == {path.relative_to(ROOT).as_posix():
                            hashlib.sha256(path.read_bytes()).hexdigest()
                            for path in (USER_YAML, REPORTED_SEED)}, "Regression input changed"
    report = {
        "status": "passed", "version": "1.8.10", "archipelago_version": Utils.__version__,
        "test_cases": sum(row["test_cases"] for row in suites), "suites": suites,
        "source_sha256": before, "source_unchanged_during_tests": True,
        "input_sha256": input_hashes,
        "fixture_sha256": {str(Path(__file__).relative_to(ROOT)):
                           hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "scope": "Existing AP trial medallion, age-specific switch, Jabu tentacle, "
                 "room-clear, carrier and shortcut regressions after the Water Temple arrival and action rule updates. "
                 "This suite is neither a native game run nor a full item fill.",
    }
    path = ROOT / "tests/seed_safety_1810_regressions.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in
                      ("status", "archipelago_version", "test_cases", "elapsed_seconds")}))


if __name__ == "__main__":
    main()
