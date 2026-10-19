"""Package the cumulative 1.8.9 complete replacement sources, never a diff.

The immutable 1.8.8 delivery supplies its already validated build helper.
The source inventory is independently compared with the original upload so
new headers, AP resources, native src/ changes and previous fixes are included.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

from prepare_source_delivery import write_source_archive

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "source"
VERSION = "1.8.9"
PACKAGE = ROOT / "delivery/SOH-EXTREME-1.8.9-source-files"
ARCHIVE = PACKAGE.parent / (PACKAGE.name + ".zip")
PREVIOUS = ROOT / "delivery/SOH-EXTREME-1.8.8-source-files.zip"
ORIGINAL = ROOT / "upload/haha.zip"
YAML = ROOT / "upload/SOH-EXTREME(20261017-230302).yaml"


def digest(data: bytes):
    return hashlib.sha256(data).hexdigest()


def packaged_yaml():
    original = YAML.read_bytes()
    marker = b"  song_note_shuffle:\r\n"
    assert original.count(marker) == 1
    selector = (
        b"  # Choose all, or replace it with song keys such as zeldas_lullaby and bolero_of_fire.\r\n"
        b"  # Only listed songs become Progressive song items when Individual Notes is enabled.\r\n"
        b"  song_note_songs:\r\n    - all\r\n\r\n"
    )
    return original.replace(marker, selector + marker, 1)


def included(path: Path):
    return path.is_file() and not any(p in {".git", "__pycache__"} for p in path.parts) and path.suffix != ".pyc"


def apworld_files():
    world = SOURCE / "archipelago/soh_extreme"
    contents = {"archipelago.json": (SOURCE / "archipelago/archipelago.json").read_bytes()}
    contents.update({"soh_extreme/" + path.relative_to(world).as_posix(): path.read_bytes()
                     for path in world.rglob("*") if included(path)})
    assert contents["archipelago.json"] == contents["soh_extreme/archipelago.json"]
    assert json.loads(contents["archipelago.json"])["world_version"] == VERSION
    return contents


def build_apworld():
    contents = apworld_files()
    target = SOURCE / "archipelago/soh_extreme.apworld"
    write_source_archive(target, contents, datetime.now(timezone.utc))
    print(json.dumps({"apworld": str(target), "entries": len(contents), "sha256": digest(target.read_bytes())}))


def inventory():
    current = {p.relative_to(SOURCE).as_posix(): p for p in SOURCE.rglob("*") if included(p)}
    changed, delta = {}, {}
    with zipfile.ZipFile(ORIGINAL) as original, zipfile.ZipFile(PREVIOUS) as previous:
        original_names = {name for name in original.namelist() if not name.endswith("/") and
                          not any(part in {".git", "__pycache__"} for part in Path(name).parts) and
                          Path(name).suffix != ".pyc"}
        missing = original_names - set(current)
        assert not missing, {"missing_original_source": sorted(missing)}
        previous_files = {row["path"] for row in json.loads(previous.read("SOURCE_FILES.json"))["files"]}
        for relative, path in sorted(current.items()):
            data = path.read_bytes()
            before = original.read(relative) if relative in original_names else None
            prior = previous.read(relative) if relative in previous_files else before
            if data != before:
                changed[relative] = {"path": relative, "size_bytes": len(data), "sha256": digest(data)}
            if data != prior:
                delta[relative] = {"change": "modified" if prior is not None else "added",
                                   "previous_sha256": digest(prior) if prior is not None else None,
                                   "sha256": digest(data), "size_bytes": len(data)}
        assert previous_files <= set(changed), {"lost_previous_replacement": sorted(previous_files - set(changed))}
        return changed, delta, len(original_names), len(current)


def prepare():
    # The APWorld must be built from the final source before this snapshot.
    with zipfile.ZipFile(SOURCE / "archipelago/soh_extreme.apworld") as archive:
        assert {name: archive.read(name) for name in archive.namelist()} == apworld_files()
    changed, delta, original_count, current_count = inventory()
    manifest = {"version": VERSION, "layout": "complete_source_files", "build_helper_revision": 4,
                "files": list(changed.values())}
    with zipfile.ZipFile(SOURCE / "archipelago/soh_extreme.apworld") as archive:
        changed["archipelago/soh_extreme.apworld"]["zip_contents"] = {
            "entries": [{"path": name, "size_bytes": len(archive.read(name)), "sha256": digest(archive.read(name))}
                        for name in sorted(archive.namelist())]}
    PACKAGE.mkdir(parents=True, exist_ok=True)
    for relative in changed:
        destination = PACKAGE / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((SOURCE / relative).read_bytes())
    (PACKAGE / "SOURCE_FILES.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    with zipfile.ZipFile(PREVIOUS) as previous:
        for name in ("BUILD_RELEASE.cmd", "BUILD_RELEASE.ps1"):
            (PACKAGE / name).write_bytes(previous.read(name).replace(b"1.8.8", b"1.8.9"))
        historical = PACKAGE / "validation/previous_1.8.8"
        historical.mkdir(parents=True, exist_ok=True)
        for name in ("VALIDATION.txt", "validation/trial_shortcut_188_release_validation.json"):
            (historical / Path(name).name).write_bytes(previous.read(name))
        (historical / "SCOPE.txt").write_text(
            "These are historical 1.8.8 results, retained as prior-release provenance.\n"
            "Current 1.8.9 results are in the parent validation folder.\n", encoding="utf-8")
    shutil.copyfile(SOURCE / "archipelago/soh_extreme.apworld", PACKAGE / "soh_extreme.apworld")
    (PACKAGE / "SOH-EXTREME.yaml").write_bytes(packaged_yaml())
    report = {"status": "passed", "version": VERSION,
              "method": "byte-for-byte comparison of every original and current source file",
              "original_archive_sha256": digest(ORIGINAL.read_bytes()),
              "previous_archive_sha256": digest(PREVIOUS.read_bytes()),
              "original_source_files": original_count, "current_source_files": current_count,
              "complete_changed_source_files": len(changed), "changed_since_1.8.8": delta,
              "source_sha256": {name: row["sha256"] for name, row in changed.items()},
              "missing_original_files": [], "unmanifested_source_changes": [],
              "all_previous_replacement_files_retained": True, "yaml_sha256": digest(packaged_yaml()),
              "original_yaml_sha256": digest(YAML.read_bytes()),
              "yaml_change": "Added explicit song_note_songs: [all]; all original setting values and weights retained."}
    (ROOT / "tests/souls_restart_189_source_completeness.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"package": str(PACKAGE), "source_files": len(changed), "new_release_files": len(delta)}))


def finalize():
    changed, delta, _, _ = inventory()
    manifest = json.loads((PACKAGE / "SOURCE_FILES.json").read_bytes())
    expected = {row["path"]: row for row in manifest["files"]}
    assert set(changed) == set(expected)
    for name, row in changed.items():
        assert row["sha256"] == expected[name]["sha256"]
        assert (PACKAGE / name).read_bytes() == (SOURCE / name).read_bytes()
    assert (PACKAGE / "soh_extreme.apworld").read_bytes() == (SOURCE / "archipelago/soh_extreme.apworld").read_bytes()
    assert (PACKAGE / "SOH-EXTREME.yaml").read_bytes() == packaged_yaml()
    for required in ("README.txt", "VALIDATION.txt", "validation/souls_restart_189_release_validation.json"):
        assert (PACKAGE / required).is_file(), required
    release = json.loads((PACKAGE / "validation/souls_restart_189_release_validation.json").read_bytes())
    assert release["status"] == "passed"
    assert release["source_sha256"] == {name: row["sha256"] for name, row in changed.items()}
    contents = {p.relative_to(PACKAGE).as_posix(): p.read_bytes() for p in PACKAGE.rglob("*") if p.is_file()}
    assert not any(name.startswith("payload/") or name.endswith((".patch", ".diff")) for name in contents)
    write_source_archive(ARCHIVE, contents, datetime.now(timezone.utc))
    verification = {"status": "passed", "version": VERSION, "archive": str(ARCHIVE),
                    "size_bytes": ARCHIVE.stat().st_size, "sha256": digest(ARCHIVE.read_bytes()),
                    "complete_source_files": len(changed), "archive_files": len(contents),
                    "all_source_bytes_match_working_source": True, "zip_crc_and_inventory_verified": True,
                    "layout": ["archipelago/", "soh/", "src/", "tools/"], "patch_files": 0}
    (ROOT / "tests/souls_restart_189_source_zip_validation.json").write_text(json.dumps(verification, indent=2) + "\n")
    print(json.dumps(verification))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("build-apworld", "prepare", "finalize"))
    option = parser.parse_args().action
    {"build-apworld": build_apworld, "prepare": prepare, "finalize": finalize}[option]()
