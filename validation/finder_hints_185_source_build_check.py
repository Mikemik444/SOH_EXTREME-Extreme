"""Verify the 1.8.5 source manifest using the actual shipped PowerShell helper.

Only the source preflight runs. This does not build the game or execute Windows.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "delivery/SOH-EXTREME-1.8.5-source-files"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    manifest = json.loads((PACKAGE / "SOURCE_FILES.json").read_bytes())
    assert manifest["version"] == "1.8.5"
    assert manifest["build_helper_revision"] == 4
    with zipfile.ZipFile(ROOT / "delivery/SOH-EXTREME-1.8.4-source-files.zip") as prior:
        for name in ("BUILD_RELEASE.cmd", "BUILD_RELEASE.ps1"):
            assert (PACKAGE / name).read_bytes() == prior.read(name).replace(b"1.8.4", b"1.8.5"), name

    with tempfile.TemporaryDirectory(prefix="soh-185-source-preflight-", dir="/tmp") as temp:
        fixture = Path(temp)
        repository = fixture / "repository"
        repository.mkdir()
        # Discovery marker in a disposable fixture; no build is attempted.
        (repository / "CMakeLists.txt").write_text("# Source verification fixture only.\n")
        for row in manifest["files"]:
            src = PACKAGE / row["path"]
            assert sha(src) == row["sha256"], row["path"]
            dst = repository / row["path"]
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
        assert (repository / "src/code/z_message_PAL.c").is_file()
        result_path = fixture / "probe-result.json"
        env = os.environ.copy()
        for key, directory in (("XDG_CACHE_HOME", "cache"), ("XDG_CONFIG_HOME", "config"), ("XDG_DATA_HOME", "data")):
            path = fixture / directory
            path.mkdir()
            env[key] = str(path)
        command = [
            str(ROOT / "runtime/powershell-7.6.7/bin/pwsh"), "-NoLogo", "-NoProfile", "-NonInteractive",
            "-File", str(ROOT / "tests/entrance_184_source_build_probe.ps1"),
            "-PackageDirectory", str(PACKAGE), "-RepositoryPath", str(repository),
            "-BuildDirectory", str(repository / "build-vs"), "-ResultPath", str(result_path), "-VerifyOnly",
        ]
        result = subprocess.run(command, env=env, text=True, capture_output=True, timeout=60)
        (ROOT / "tests/finder_hints_185_source_build_validation.log").write_text(result.stdout + result.stderr)
        assert result.returncode == 0, result.stdout + result.stderr
        assert json.loads(result_path.read_text())["status"] == "passed"
        for row in manifest["files"]:
            assert sha(repository / row["path"]) == row["sha256"], row["path"]

    report = {
        "status": "passed", "version": "1.8.5", "utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Actual shipped helper AST functions verify all copied replacement source files in a disposable fixture.",
        "source_files_verified": len(manifest["files"]), "native_message_engine_included": True,
        "source_files_unchanged_by_helper": True, "build_helper_revision": 4,
        "helper_identical_to_1_8_4_except_release_strings": True,
        "helper_sha256": {name: sha(PACKAGE / name) for name in ("BUILD_RELEASE.cmd", "BUILD_RELEASE.ps1")},
        "manifest_sha256": sha(PACKAGE / "SOURCE_FILES.json"),
        "apworld_sha256": sha(PACKAGE / "soh_extreme.apworld"),
        "source_sha256": {row["path"]: row["sha256"] for row in manifest["files"]},
        "limitations": [
            "Source verification only; no native game or fixture compilation in this current-release check.",
            "PowerShell 7.6.7 on Linux, not Windows PowerShell or MSBuild.",
            "Main Windows OS check bypassed and two path helpers use equivalent Unix separators.",
            "The unchanged revision-4 clean-build workflow was exercised in 1.8.4; those results are historical.",
        ],
    }
    target = ROOT / "tests/finder_hints_185_source_build_validation.json"
    target.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in ("status", "version", "source_files_verified", "build_helper_revision", "helper_identical_to_1_8_4_except_release_strings")}))


if __name__ == "__main__":
    main()
