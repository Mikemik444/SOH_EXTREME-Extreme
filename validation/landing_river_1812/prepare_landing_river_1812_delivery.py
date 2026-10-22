"""Build the cumulative 1.8.12 grotto, river-path and last-ammo release.

Only full replacement sources are shipped. Prior validation remains historical;
current reports must bind the source or APWorld bytes that are actually shipped.
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
BASE = ROOT / "delivery/SOH-EXTREME-1.8.11-entrance-fixes-source-files.zip"
BASE_SHA = "8d105428ddd2146abaf70a6ab4ce7b05e44aefbcccdcc8076893185ce896bc3e"
VERSION = "1.8.12"
PACKAGE = ROOT / "delivery/SOH-EXTREME-1.8.12-source-files"
ARCHIVE = PACKAGE.parent / (PACKAGE.name + ".zip")
VALIDATION = PACKAGE / "validation/landing_river_1812"
REPORT_PREFIX = ROOT / "tests/landing_river_1812"
BINDING_KEYS = ("sources", "source_sha256", "test_sha256", "stable_source_sha256", "version_source_sha256", "tests")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read(path: Path):
    return json.loads(path.read_bytes())


def inventory():
    """Compare complete source with the original; the caller checks 1.8.11 retention."""
    included = lambda p: not any(part in {".git", "__pycache__"} for part in p.parts) and p.suffix != ".pyc"
    current = {p.relative_to(SOURCE).as_posix(): p for p in SOURCE.rglob("*") if p.is_file() and included(p)}
    changed = {}
    with zipfile.ZipFile(ROOT / "upload/haha.zip") as original:
        names = {name for name in original.namelist() if not name.endswith("/") and included(Path(name))}
        assert names <= set(current), {"missing_original_source": sorted(names - set(current))}
        for relative, path in sorted(current.items()):
            data = path.read_bytes()
            if relative not in names or data != original.read(relative):
                changed[relative] = {"path": relative, "size_bytes": len(data), "sha256": sha(data)}
    return changed, {}, len(names), len(current)


def source_bindings(report: dict):
    """Accept the native suite's older tests dictionary and numeric AP counts."""
    for key in BINDING_KEYS:
        values = report.get(key, {})
        if key == "tests" and not isinstance(values, dict):
            continue
        assert isinstance(values, dict), key
        for relative, expected in values.items():
            assert isinstance(expected, str), (key, relative)
            assert not Path(relative).is_absolute() and ".." not in Path(relative).parts, relative
            yield relative, expected


def ap_contents() -> dict[str, bytes]:
    world = SOURCE / "archipelago/soh_extreme"
    entries = {"archipelago.json": (SOURCE / "archipelago/archipelago.json").read_bytes()}
    entries.update({"soh_extreme/" + p.relative_to(world).as_posix(): p.read_bytes()
                    for p in world.rglob("*") if p.is_file()
                    and "__pycache__" not in p.parts and p.suffix != ".pyc"})
    assert entries["archipelago.json"] == entries["soh_extreme/archipelago.json"]
    assert json.loads(entries["archipelago.json"])["world_version"] == VERSION
    catalog = json.loads(entries["soh_extreme/EntranceCatalog.json"])
    assert len(catalog) == 721
    by_id = {row["id"]: row for row in catalog}
    assert {i: by_id[i]["reverse"] for i in (234, 385, 473, 785)} == {
        234: 385, 385: 234, 473: 785, 785: 473}
    return entries


def build_apworld() -> None:
    entries = ap_contents()
    path = SOURCE / "archipelago/soh_extreme.apworld"
    write_source_archive(path, entries, datetime.now(timezone.utc))
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None
        assert {name: archive.read(name) for name in archive.namelist()} == entries
    print(json.dumps({"status": "built", "archive": str(path), "entries": len(entries),
                      "sha256": sha(path.read_bytes())}))


def prepare() -> None:
    assert sha(BASE.read_bytes()) == BASE_SHA
    entries = ap_contents()
    ap_path = SOURCE / "archipelago/soh_extreme.apworld"
    with zipfile.ZipFile(ap_path) as archive:
        assert {name: archive.read(name) for name in archive.namelist()} == entries
    current, _, original_count, current_count = inventory()
    with zipfile.ZipFile(BASE) as base, zipfile.ZipFile(ROOT / "upload/haha.zip") as original:
        old = {row["path"]: row for row in json.loads(base.read("SOURCE_FILES.json"))["files"]}
        assert len(old) == 199 and set(old) <= set(current)
        preserved_top = {"README.txt", "VALIDATION.txt", "SOURCE_FILES.json"}
        contents = {("validation/base_1.8.11_entrance_fixes/" + name if name in preserved_top else name): base.read(name)
                    for name in base.namelist()}
        rows, delta = [], {}
        for name, metadata in sorted(current.items()):
            data = (SOURCE / name).read_bytes()
            before = base.read(name) if name in old else (
                original.read(name) if name in original.namelist() else None)
            row = dict(old.get(name, {}))
            row.update(metadata)
            if name == "archipelago/soh_extreme.apworld":
                row["zip_contents"] = {"entries": [
                    {"path": n, "size_bytes": len(b), "sha256": sha(b)} for n, b in sorted(entries.items())]}
            rows.append(row)
            contents[name] = data
            if data != before:
                delta[name] = {"change": "modified" if before is not None else "added",
                               "previous_sha256": sha(before) if before is not None else None,
                               "sha256": sha(data), "size_bytes": len(data)}
        contents["soh_extreme.apworld"] = ap_path.read_bytes()
        for name in ("BUILD_RELEASE.cmd", "BUILD_RELEASE.ps1"):
            contents[name] = base.read(name).replace(b"1.8.11", VERSION.encode())
            assert b"1.8.11" not in contents[name]
        assert contents["SOH-EXTREME.yaml"] == base.read("SOH-EXTREME.yaml")
        manifest = {"version": VERSION, "layout": "complete_source_files", "build_helper_revision": 4,
                    "release": "Safe grotto landing, independent Zora's River land/water entrance pairs, and last-ammo protection until refill access.",
                    "files": rows}
        contents["SOURCE_FILES.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
        if PACKAGE.exists():
            shutil.rmtree(PACKAGE)  # Reproducible staging only; never a user's checkout.
        for name, data in contents.items():
            path = PACKAGE / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    result = {"status": "passed", "version": VERSION, "base_archive_sha256": BASE_SHA,
              "complete_source_files": len(rows), "original_source_files": original_count,
              "current_source_files": current_count, "all_199_previous_replacement_files_retained": True,
              "missing_original_files": [], "unmanifested_source_changes": [],
              "changes_since_previous_delivery": delta, "source_sha256": {r["path"]: r["sha256"] for r in rows},
              "manifest_sha256": sha(contents["SOURCE_FILES.json"]), "apworld_sha256": sha(ap_path.read_bytes()),
              "yaml_unchanged": True, "prepared_archive_paths": sorted(contents)}
    REPORT_PREFIX.with_name(REPORT_PREFIX.name + "_source_completeness.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": "prepared", "complete_source_files": len(rows), "changes": list(delta),
                      "package": str(PACKAGE)}))


def validate_report(name: str, report: dict) -> None:
    assert report.get("status") == "passed", (name, report.get("status"))
    bound = False
    for relative, expected in source_bindings(report):
        assert sha((SOURCE / relative).read_bytes()) == expected, (name, relative)
        bound = True
    if report.get("archive_sha256"):
        assert report["archive_sha256"] == sha((SOURCE / "archipelago/soh_extreme.apworld").read_bytes()), name
        bound = True
    assert bound, (name, "Current source or archive binding is required")


def finalize(paths: list[Path]) -> None:
    required = {"grotto_landing_1812_native.json", "grotto_landing_1812_integration.json",
                "zora_river_1812_ap.json", "zora_river_1812_native.json",
                "ammo_1812_native.json", "ammo_1812_ap.json", "ammo_1812_tracker.json",
                "ammo_sources_1812_native.json",
                "ammo_refill_drop_bounds_1812_native.json",
                "landing_river_1812_apworld_validation.json"}
    assert required <= {p.name for p in paths}, sorted(required - {p.name for p in paths})
    assert sha(BASE.read_bytes()) == BASE_SHA
    completeness = read(REPORT_PREFIX.with_name(REPORT_PREFIX.name + "_source_completeness.json"))
    preflight = read(REPORT_PREFIX.with_name(REPORT_PREFIX.name + "_source_build_validation.json"))
    manifest = read(PACKAGE / "SOURCE_FILES.json")
    assert completeness["status"] == preflight["status"] == "passed"
    for relative, expected in preflight["validation_tool_sha256"].items():
        assert sha((ROOT / relative).read_bytes()) == expected, relative
    assert completeness["manifest_sha256"] == preflight["manifest_sha256"] == sha((PACKAGE / "SOURCE_FILES.json").read_bytes())
    current, _, _, _ = inventory()
    assert set(current) == {r["path"] for r in manifest["files"]}
    for row in manifest["files"]:
        assert row["sha256"] == sha((SOURCE / row["path"]).read_bytes()) == sha((PACKAGE / row["path"]).read_bytes())
    with zipfile.ZipFile(PACKAGE / "soh_extreme.apworld") as ap:
        assert {n: ap.read(n) for n in ap.namelist()} == ap_contents()
    VALIDATION.mkdir(parents=True, exist_ok=True)
    added = set()
    reports = {}
    replay_inputs = {}
    for path in paths:
        report = read(path)
        validate_report(path.name, report)
        assert path.name not in reports
        reports[path.name] = report
        destination = VALIDATION / path.name
        shutil.copyfile(path, destination)
        added.add(destination.relative_to(PACKAGE).as_posix())
    # Regression excerpts carry the digest of the full historical source from
    # which they were retained; verify that provenance against its real archive.
    with zipfile.ZipFile(ROOT / "upload/haha.zip") as original, zipfile.ZipFile(BASE) as base:
        for relative, expected in reports["ammo_1812_native.json"]["baseline"]["source_hashes"].items():
            assert sha(original.read(relative)) == expected, relative
        assert sha(original.read("src/code/z_en_item00.c")) == reports[
            "ammo_refill_drop_bounds_1812_native.json"]["legacy_source_sha256"]
        assert sha(base.read("soh/Enhancements/randomizer/randomizer_grotto.c")) == reports[
            "grotto_landing_1812_native.json"]["legacy_source_sha256"]
        retained = reports["ammo_sources_1812_native.json"]["retained_baseline_source_sha256"]
        for relative, expected in retained.items():
            matches = [label for label, archive in (("upload/haha.zip", original), (BASE.name, base))
                       if relative in archive.namelist() and sha(archive.read(relative)) == expected]
            assert matches, (relative, "Unverified observed-source baseline provenance")
            replay_inputs["observed_source_baseline/" + relative] = {
                "sha256": expected, "verified_archive": matches,
                "excerpt_location": "tools/tests/ammo_sources_legacy_functions.inc"}
    with zipfile.ZipFile(PACKAGE / "soh_extreme.apworld") as ap:
        for report_name, report in reports.items():
            for relative, expected in source_bindings(report):
                destination = PACKAGE / relative
                if destination.is_file():
                    location = relative
                    assert sha(destination.read_bytes()) == expected, relative
                elif relative.startswith("archipelago/soh_extreme/"):
                    member = relative.removeprefix("archipelago/")
                    assert sha(ap.read(member)) == expected, relative
                    location = "soh_extreme.apworld!" + member
                else:
                    destination = VALIDATION / "native_source" / relative
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(SOURCE / relative, destination)
                    assert sha(destination.read_bytes()) == expected, relative
                    location = destination.relative_to(PACKAGE).as_posix()
                    added.add(location)
                value = {"sha256": expected, "location": location}
                assert relative not in replay_inputs or replay_inputs[relative] == value, relative
                replay_inputs[relative] = value
            for key in ("native_dependencies", "dependency_sha256", "dependencies"):
                for name, expected in report.get(key, {}).items():
                    assert Path(name).name == name, name
                    dependency_root = ("tests/ammo_sources_1812_native_dependencies"
                                       if report_name == "ammo_sources_1812_native.json" and key == "dependencies"
                                       else "tests/entrance_184_native_dependencies")
                    source = ROOT / dependency_root / name
                    assert sha(source.read_bytes()) == expected, name
                    destination = VALIDATION / "native_dependencies" / name
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, destination)
                    location = destination.relative_to(PACKAGE).as_posix()
                    added.add(location)
                    value = {"sha256": expected, "location": location}
                    identity = "native_dependencies/" + name
                    assert identity not in replay_inputs or replay_inputs[identity] == value, identity
                    replay_inputs[identity] = value
    # Retain the exact user-settings and saved-map evidence consumed by the
    # current AP river test. Historical item placement is not claimed as a new
    # 1.8.12 full-fill validation.
    river_report = reports["zora_river_1812_ap.json"]
    ammo_settings = reports["ammo_1812_ap.json"]["inputs"]["settings_report"]
    assert ammo_settings["name"] == "grotto_1811_uploaded_seed_reproduction.options.json"
    assert ammo_settings["sha256"] == river_report["settings_report_sha256"]
    for key, filename in (
            ("settings_report_sha256", "grotto_1811_uploaded_seed_reproduction.options.json"),
            ("legacy_report_sha256", "grotto_1811_uploaded_seed_reproduction.json")):
        source = ROOT / "tests" / filename
        assert sha(source.read_bytes()) == river_report[key], (key, filename)
        destination = VALIDATION / "legacy_seed_inputs" / filename
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        location = destination.relative_to(PACKAGE).as_posix()
        added.add(location)
        replay_inputs["legacy_seed_inputs/" + filename] = {"sha256": river_report[key], "location": location}
    # Only the two original native source files are needed to reproduce the
    # river aliasing regressions. Keep a verified small fixture archive instead
    # of nesting an entire earlier release.
    baseline = reports["zora_river_1812_native.json"]["baseline"]
    assert baseline["sha256"] == BASE_SHA
    with zipfile.ZipFile(BASE) as base:
        baseline_contents = {name: base.read(name) for name in baseline["source_sha256"]}
    for name, expected in baseline["source_sha256"].items():
        assert sha(baseline_contents[name]) == expected, name
    baseline_zip = VALIDATION / "river_native_baseline_1.8.11.zip"
    write_source_archive(baseline_zip, baseline_contents, datetime.now(timezone.utc))
    with zipfile.ZipFile(baseline_zip) as archived:
        assert archived.testzip() is None
        assert {name: archived.read(name) for name in archived.namelist()} == baseline_contents
    baseline_location = baseline_zip.relative_to(PACKAGE).as_posix()
    added.add(baseline_location)
    replay_inputs["river_native_baseline"] = {
        "original_release_sha256": BASE_SHA,
        "source_sha256": baseline["source_sha256"],
        "fixture_archive_sha256": sha(baseline_zip.read_bytes()),
        "location": baseline_location,
        "note": "Identical compiled baseline source bodies; subset ZIP hash differs from the complete historical release."}
    version_report = read(ROOT / "tests/landing_river_1812_version_validation.json")
    validate_report("landing_river_1812_version_validation.json", version_report)
    assert set(version_report["versions"].values()) == {VERSION}
    assert version_report["tracker_sha256"] == sha((SOURCE / "archipelago/soh_extreme/TrackerMirror.py").read_bytes())
    assert ('#define SOH_EXTREME_VERSION "' + VERSION + '"').encode() in (SOURCE / "soh/SohExtremeVersion.h").read_bytes()
    for source in (REPORT_PREFIX.with_name(REPORT_PREFIX.name + "_source_completeness.json"),
                   REPORT_PREFIX.with_name(REPORT_PREFIX.name + "_source_build_validation.json"),
                   ROOT / "tests/landing_river_1812_version_validation.json",
                   ROOT / "tests/finder_hints_186_validate_apworld.py",
                   ROOT / "tests/landing_river_1812_source_build_check.py",
                   ROOT / "tests/entrance_184_source_build_probe.ps1",
                   ROOT / "prepare_source_delivery.py", ROOT / "prepare_runtime_delivery.py", Path(__file__)):
        destination = VALIDATION / source.name
        shutil.copyfile(source, destination)
        added.add(destination.relative_to(PACKAGE).as_posix())
    for filename, text in (("REPLAY_INPUTS.json", json.dumps(replay_inputs, indent=2) + "\n"),):
        destination = VALIDATION / filename
        destination.write_text(text)
        added.add(destination.relative_to(PACKAGE).as_posix())
    # Release prose is written after the final implementation and review settle.
    for name in ("README.txt", "VALIDATION.txt", "validation/landing_river_1812/REPLAY.txt"):
        assert (PACKAGE / name).is_file(), name
        assert b"_PENDING" not in (PACKAGE / name).read_bytes(), name
        added.add(name)
    with zipfile.ZipFile(BASE) as base:
        for name in base.namelist():
            if name.startswith("validation/"):
                assert (PACKAGE / name).read_bytes() == base.read(name), name
        for name in ("BUILD_RELEASE.cmd", "BUILD_RELEASE.ps1"):
            assert (PACKAGE / name).read_bytes() == base.read(name).replace(b"1.8.11", VERSION.encode()), name
    summary = {"status": "passed", "version": VERSION, "complete_source_files": len(manifest["files"]),
               "base_archive_sha256": BASE_SHA, "all_previous_replacement_files_retained": True,
               "source_sha256": completeness["source_sha256"], "manifest_sha256": completeness["manifest_sha256"],
               "apworld_sha256": completeness["apworld_sha256"], "entrance_catalog_entries": 721,
               "fresh_report_sha256": {p.name: sha(p.read_bytes()) for p in paths},
               "native_windows_build": False, "in_game_playthrough": False}
    destination = VALIDATION / "landing_river_1812_release_validation.json"
    destination.write_text(json.dumps(summary, indent=2) + "\n")
    added.add(destination.relative_to(PACKAGE).as_posix())
    contents = {p.relative_to(PACKAGE).as_posix(): p.read_bytes() for p in PACKAGE.rglob("*") if p.is_file()}
    assert set(contents) == set(completeness["prepared_archive_paths"]) | added
    assert not any(n.startswith("payload/") or n.endswith((".patch", ".diff")) for n in contents)
    write_source_archive(ARCHIVE, contents, datetime.now(timezone.utc))
    with zipfile.ZipFile(ARCHIVE) as archive:
        assert archive.testzip() is None
        assert {n: archive.read(n) for n in archive.namelist()} == contents
    output = {"status": "passed", "archive": str(ARCHIVE), "size_bytes": ARCHIVE.stat().st_size,
              "sha256": sha(ARCHIVE.read_bytes()), "complete_source_files": len(manifest["files"]),
              "archive_entries": len(contents), "every_member_byte_verified": True}
    REPORT_PREFIX.with_name(REPORT_PREFIX.name + "_archive_validation.json").write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps(output))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build-apworld", "prepare", "finalize"))
    parser.add_argument("--report", action="append", type=Path, default=[])
    args = parser.parse_args()
    {"build-apworld": build_apworld, "prepare": prepare, "finalize": lambda: finalize(args.report)}[args.action]()
