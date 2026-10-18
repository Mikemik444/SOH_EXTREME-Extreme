"""Bind the retained start, coupled-pool and restore tests to release sources."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source"
SUITES = (
    ("tools/tests/test_entrance_start.py", 13),
    ("tools/tests/test_overworld_entrances.py", 27),
)


def hashes():
    paths = [p for p in (SOURCE / "archipelago/soh_extreme").rglob("*")
             if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"]
    paths.extend(SOURCE / name for name, _ in SUITES)
    return {p.relative_to(SOURCE).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in paths}


def main():
    before = hashes()
    cases = []
    start = time.monotonic()
    for name, expected in SUITES:
        result = subprocess.run([sys.executable, str(SOURCE / name)], text=True,
                                capture_output=True, timeout=120)
        log = result.stdout + result.stderr
        found = re.search(r"Ran (\d+) tests? in", log)
        assert result.returncode == 0 and found and int(found[1]) == expected, log
        assert re.search(r"^OK\s*$", log, re.MULTILINE), log
        cases.append({"suite": name, "test_cases": expected, "status": "passed", "log": log})
    after = hashes()
    assert before == after, "Source changed during the retained AP tests"
    report = {
        "status": "passed", "runtime": "Archipelago 0.6.7", "test_cases": sum(n for _, n in SUITES),
        "suites": cases, "source_sha256": after, "source_unchanged_during_tests": True,
        "elapsed_seconds": round(time.monotonic() - start, 3),
        "scope": "Retained AP CollectionState regressions for usable starting checks, physical escape, "
                 "Swim/age/item requirements, coupled overworld and mixed pools, all-enabled expansion, "
                 "and legacy saved-map restoration. No native launch or full fill in this suite.",
    }
    path = ROOT / "tests/entrance_destination_187_core_regressions.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ("status", "test_cases", "elapsed_seconds")}))


if __name__ == "__main__":
    main()
