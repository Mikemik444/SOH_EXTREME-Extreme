"""Package cumulative complete sources for the 1.8.14 server-configured tracker and setting declaration fixes.

Current reports are bound to the bytes shipped. Prior validation stays intact
as historical evidence; it is never presented as a current test run.
"""
from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

from prepare_source_delivery import write_source_archive

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "source"
VERSION = "1.8.14"
BASE = ROOT / "delivery/SOH-EXTREME-1.8.13-source-files.zip"
BASE_SHA = "818915c0115c6db6ebcbee984caec953ef374501b6682b7ac0acb879cd264995"
PACKAGE = ROOT / "delivery/SOH-EXTREME-1.8.14-source-files"
ARCHIVE = PACKAGE.parent / (PACKAGE.name + ".zip")
VALIDATION = PACKAGE / "validation/tracker_yamlless_1814"
PREFIX = "tracker_yamlless_1814"
BINDING_KEYS = ("sources", "source_sha256", "source_hashes", "test_sha256", "test_hashes", "stable_source_sha256", "version_source_sha256", "tests")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read(path: Path):
    return json.loads(path.read_bytes())


def report_path(suffix: str) -> Path:
    return ROOT / "tests" / f"{PREFIX}_{suffix}.json"


def safe_relative(name: str) -> None:
    assert not Path(name).is_absolute() and ".." not in Path(name).parts and "\\" not in name, name


def source_bindings(report: dict):
    for key in BINDING_KEYS:
        values = report.get(key, {})
        if key == "tests" and not isinstance(values, dict):
            continue
        assert isinstance(values, dict), key
        for name, expected in values.items():
            safe_relative(name)
            assert isinstance(expected, str) and len(expected) == 64, (key, name)
            yield name, expected


def inventory():
    included = lambda p: not any(part in {".git", "__pycache__"} for part in p.parts) and p.suffix != ".pyc"
    current = {p.relative_to(SOURCE).as_posix(): p for p in SOURCE.rglob("*") if p.is_file() and included(p)}
    changed = {}
    with zipfile.ZipFile(ROOT / "upload/haha.zip") as original:
        names = {n for n in original.namelist() if not n.endswith("/") and included(Path(n))}
        assert names <= set(current), {"missing_original": sorted(names - set(current))}
        for name, path in sorted(current.items()):
            data = path.read_bytes()
            if name not in names or data != original.read(name):
                changed[name] = {"path": name, "size_bytes": len(data), "sha256": sha(data)}
    return changed, len(names), len(current)


def ap_contents():
    world = SOURCE / "archipelago/soh_extreme"
    entries = {"archipelago.json": (SOURCE / "archipelago/archipelago.json").read_bytes()}
    entries.update({"soh_extreme/" + p.relative_to(world).as_posix(): p.read_bytes()
                    for p in world.rglob("*") if p.is_file()
                    and "__pycache__" not in p.parts and p.suffix != ".pyc"})
    assert entries["archipelago.json"] == entries["soh_extreme/archipelago.json"]
    assert json.loads(entries["archipelago.json"])["world_version"] == VERSION
    catalog = json.loads(entries["soh_extreme/EntranceCatalog.json"])
    assert len(catalog) == 721
    policy = json.loads(entries["soh_extreme/EntranceDestinationPolicy.json"])
    hut = next(row for row in policy["endpoints"] if row["id"] == 781)
    escape = next(row for row in policy["endpoints"] if row["id"] == 853)
    assert (hut["source_age_mask"], hut["arrival_age_mask"]) == (2, 2)
    assert (escape["source_age_mask"], escape["arrival_age_mask"]) == (3, 3)
    return entries


def build_apworld():
    entries = ap_contents()
    path = SOURCE / "archipelago/soh_extreme.apworld"
    write_source_archive(path, entries, datetime.now(timezone.utc))
    print(json.dumps({"status": "built", "entries": len(entries), "sha256": sha(path.read_bytes())}))


def prepare():
    assert sha(BASE.read_bytes()) == BASE_SHA
    entries = ap_contents()
    ap_path = SOURCE / "archipelago/soh_extreme.apworld"
    with zipfile.ZipFile(ap_path) as archive:
        assert {n: archive.read(n) for n in archive.namelist()} == entries
    current, original_count, current_count = inventory()
    with zipfile.ZipFile(BASE) as base, zipfile.ZipFile(ROOT / "upload/haha.zip") as original:
        old = {row["path"]: row for row in json.loads(base.read("SOURCE_FILES.json"))["files"]}
        assert len(old) == 253 and set(old) <= set(current)
        top = {"README.txt", "VALIDATION.txt", "SOURCE_FILES.json"}
        contents = {("validation/base_1.8.13/" + n if n in top else n): base.read(n) for n in base.namelist()}
        rows, delta = [], {}
        original_names = set(original.namelist())
        for name, metadata in sorted(current.items()):
            data = (SOURCE / name).read_bytes()
            before = base.read(name) if name in old else original.read(name) if name in original_names else None
            row = dict(old.get(name, {}))
            row.update(metadata)
            if name == "archipelago/soh_extreme.apworld":
                row["zip_contents"] = {"entries": [
                    {"path": n, "size_bytes": len(b), "sha256": sha(b)} for n, b in sorted(entries.items())]}
            rows.append(row)
            contents[name] = data
            if before != data:
                delta[name] = {"previous_sha256": sha(before) if before is not None else None,
                               "sha256": sha(data), "size_bytes": len(data)}
        contents["soh_extreme.apworld"] = ap_path.read_bytes()
        for name in ("BUILD_RELEASE.cmd", "BUILD_RELEASE.ps1"):
            contents[name] = base.read(name).replace(b"1.8.13", VERSION.encode())
        assert contents["SOH-EXTREME.yaml"] == base.read("SOH-EXTREME.yaml")
        manifest = {"version": VERSION, "layout": "complete_source_files", "build_helper_revision": 4,
                    "release": "Server-slot startup without player YAMLs for Check Finder and SOH Universal Tracker; native C++ setting bridge declaration fix.",
                    "files": rows}
        contents["SOURCE_FILES.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
        if PACKAGE.exists():
            shutil.rmtree(PACKAGE)  # Reproducible release staging only.
        for name, data in contents.items():
            path = PACKAGE / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    result = {"status": "passed", "version": VERSION, "base_archive_sha256": BASE_SHA,
              "complete_source_files": len(rows), "original_source_files": original_count,
              "current_source_files": current_count, "all_253_previous_replacement_files_retained": True,
              "missing_original_files": [], "unmanifested_source_changes": [],
              "changes_since_previous_delivery": delta, "source_sha256": {r["path"]: r["sha256"] for r in rows},
              "manifest_sha256": sha(contents["SOURCE_FILES.json"]), "apworld_sha256": sha(ap_path.read_bytes()),
              "yaml_unchanged": True, "prepared_archive_paths": sorted(contents)}
    report_path("source_completeness").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": "prepared", "complete_source_files": len(rows), "changes": list(delta)}))


def validate_report(name, report):
    assert report.get("status") == "passed", name
    bound = False
    for relative, expected in source_bindings(report):
        assert sha((SOURCE / relative).read_bytes()) == expected, (name, relative)
        bound = True
    if report.get("archive_sha256"):
        assert report["archive_sha256"] == sha((SOURCE / "archipelago/soh_extreme.apworld").read_bytes()), name
        bound = True
    assert bound, (name, "Source/archive binding required")
    for key in ("source_unchanged_during_tests", "source_unchanged_during_run"):
        assert report.get(key, True), (name, key)


def finalize(paths, dependency_roots, input_paths):
    required = {"tracker_yamlless_1814_integration.json", "tracker_1814_hint_bridge.json",
                "tracker_1814_ammo_protocol.json", "tracker_yamlless_1814_setting_declaration.json",
                "tracker_yamlless_1814_keyring_restore.json",
                "tracker_yamlless_1814_apworld_validation.json"}
    assert required <= {p.name for p in paths}, sorted(required - {p.name for p in paths})
    assert sha(BASE.read_bytes()) == BASE_SHA
    complete = read(report_path("source_completeness"))
    preflight = read(report_path("source_build_validation"))
    manifest = read(PACKAGE / "SOURCE_FILES.json")
    assert complete["status"] == preflight["status"] == "passed"
    for relative, expected in preflight["validation_tool_sha256"].items():
        assert sha((ROOT / relative).read_bytes()) == expected, relative
    assert complete["manifest_sha256"] == preflight["manifest_sha256"] == sha((PACKAGE / "SOURCE_FILES.json").read_bytes())
    current, _, _ = inventory()
    assert set(current) == {row["path"] for row in manifest["files"]}
    for row in manifest["files"]:
        assert row["sha256"] == sha((SOURCE / row["path"]).read_bytes()) == sha((PACKAGE / row["path"]).read_bytes())
    assert len({sha((SOURCE / "archipelago/soh_extreme.apworld").read_bytes()),
                sha((PACKAGE / "archipelago/soh_extreme.apworld").read_bytes()),
                sha((PACKAGE / "soh_extreme.apworld").read_bytes()),
                complete["apworld_sha256"], preflight["apworld_sha256"]}) == 1
    with zipfile.ZipFile(PACKAGE / "soh_extreme.apworld") as ap:
        assert {n: ap.read(n) for n in ap.namelist()} == ap_contents()
    VALIDATION.mkdir(parents=True, exist_ok=True)
    added, replay, reports = set(), {}, {}

    def copy(source, relative):
        safe_relative(relative)
        target = PACKAGE / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        data = source.read_bytes()
        if relative in added:
            assert target.read_bytes() == data, relative
        else:
            target.write_bytes(data)
            added.add(relative)
        return relative

    validation_prefix = VALIDATION.relative_to(PACKAGE).as_posix() + "/"
    with zipfile.ZipFile(PACKAGE / "soh_extreme.apworld") as ap:
        for path in paths:
            report = read(path)
            validate_report(path.name, report)
            assert path.name not in reports
            reports[path.name] = report
            copy(path, validation_prefix + path.name)
            for relative, expected in source_bindings(report):
                if (PACKAGE / relative).is_file():
                    location = relative
                    assert sha((PACKAGE / location).read_bytes()) == expected
                elif relative.startswith("archipelago/soh_extreme/"):
                    member = relative.removeprefix("archipelago/")
                    assert sha(ap.read(member)) == expected
                    location = "soh_extreme.apworld!" + member
                else:
                    location = copy(SOURCE / relative, validation_prefix + "native_source/" + relative)
                value = {"sha256": expected, "location": location}
                assert relative not in replay or replay[relative] == value
                replay[relative] = value
            for key in ("native_dependencies", "dependency_sha256", "dependencies", "header_hashes"):
                for name, expected in report.get(key, {}).items():
                    assert Path(name).name == name and isinstance(expected, str), (path.name, key, name)
                    matches = [root / name for root in dependency_roots
                               if (root / name).is_file() and sha((root / name).read_bytes()) == expected]
                    assert matches, (path.name, "Missing exact dependency", name)
                    location = copy(matches[0], validation_prefix + "native_dependencies/" + name)
                    value = {"sha256": expected, "location": location}
                    identity = "native_dependencies/" + name
                    assert identity not in replay or replay[identity] == value
                    replay[identity] = value
    for source_root in (ROOT / "tests/tracker_bootstrap_1814_upstream",
                        ROOT / "tests/tracker_bootstrap_1814_ap_dependencies"):
        assert source_root.is_dir(), source_root
        for source in sorted(source_root.rglob("*")):
            if not source.is_file() or "__pycache__" in source.parts or source.suffix == ".pyc":
                continue
            relative = source.relative_to(source_root).as_posix()
            location = copy(source, validation_prefix + "external/" + source_root.name + "/" + relative)
            replay["external/" + source_root.name + "/" + relative] = {
                "sha256": sha(source.read_bytes()), "location": location}
    integration = reports["tracker_yamlless_1814_integration.json"]
    upstream_root = ROOT / "tests/tracker_bootstrap_1814_upstream"
    assert integration["upstream_provenance"] == read(upstream_root / "UPSTREAM.json")
    for relative, expected in integration["upstream_hashes"].items():
        safe_relative(relative)
        assert sha((upstream_root / relative).read_bytes()) == expected, relative
    for relative, metadata in integration["upstream_provenance"]["files"].items():
        safe_relative(relative)
        assert sha((upstream_root / relative).read_bytes()) == metadata["sha256"], relative
    ap_dependencies = ROOT / "tests/tracker_bootstrap_1814_ap_dependencies"
    assert integration["ap_dependency_provenance"] == read(ap_dependencies / "UPSTREAM.json")
    for metadata in integration["ap_dependency_provenance"]["files"]:
        relative = metadata["path"]
        safe_relative(relative)
        assert sha((ap_dependencies / relative).read_bytes()) == metadata["sha256"], relative
    for relative, expected in integration["ap_runtime_hashes"].items():
        safe_relative(relative)
        assert sha((ROOT / "ap-runtime-068" / relative).read_bytes()) == expected, relative
        replay["external_runtime/" + relative] = {
            "sha256": expected, "included": False, "runtime": "Archipelago " + integration["ap_runtime_version"]}
    assert integration["baseline_archive_sha256"] == BASE_SHA
    with zipfile.ZipFile(BASE) as baseline:
        members = {name: baseline.read(name) for name in (
            "archipelago/soh_extreme/TrackerClient.py", "archipelago/soh_extreme/__init__.py",
            "soh/Network/Archipelago/ArchipelagoClient.cpp")}
        assert sha(members["archipelago/soh_extreme/TrackerClient.py"]) == integration["baseline_tracker_client_sha256"]
    keyring = reports["tracker_yamlless_1814_keyring_restore.json"]
    assert keyring["baseline_archive_sha256"] == BASE_SHA
    old_world_text = members["archipelago/soh_extreme/__init__.py"].decode("utf-8-sig")
    old_ast = ast.parse(old_world_text)
    old_class = next(node for node in old_ast.body if isinstance(node, ast.ClassDef)
                     and node.name == "SohExtremeWorld")
    old_method = next(node for node in old_class.body if isinstance(node, ast.FunctionDef)
                      and node.name == "_generate_stock_foundation")
    assert sha(ast.get_source_segment(old_world_text, old_method).encode()) == keyring["baseline_method_sha256"]
    assert keyring["fresh_generation_unchanged"]
    assert keyring["after_pre_fill_pool"] == keyring["expected_pre_fill_pool"]
    assert keyring["before_pre_fill_pool"] != keyring["expected_pre_fill_pool"]
    for relative, expected in keyring["upstream_hashes"].items():
        assert sha((upstream_root / relative).read_bytes()) == expected, relative
    # Keep exact regression inputs without embedding an entire old delivery ZIP.
    subset = ROOT / "tests/tracker_yamlless_1814_baseline_members.zip"
    write_source_archive(subset, members, datetime.now(timezone.utc))
    location = copy(subset, validation_prefix + "inputs/" + subset.name)
    replay["inputs/" + subset.name] = {
        "sha256": sha(subset.read_bytes()), "location": location,
        "verified_original_archive": BASE.name, "verified_original_archive_sha256": BASE_SHA,
        "members": {name: sha(data) for name, data in members.items()}}
    provided_inputs = {}
    for path in input_paths:
        assert path.name not in provided_inputs, ("Duplicate replay input", path.name)
        provided_inputs[path.name] = path
        location = copy(path, validation_prefix + "inputs/" + path.name)
        replay["inputs/" + path.name] = {"sha256": sha(path.read_bytes()), "location": location}
    for report_name, report in reports.items():
        for name, evidence in report.get("evidence", {}).items():
            assert Path(name).name == name
            if name == "haha.zip":
                original = ROOT / "upload/haha.zip"
                assert Path(evidence["path"]).resolve() == original.resolve()
                assert evidence["sha256"] == sha(original.read_bytes())
                replay["external_evidence/" + name] = {
                    "sha256": evidence["sha256"], "reports": [report_name],
                    "included": False,
                    "scope": "Original archive provenance verified; native replay uses retained exact excerpts."
                }
                continue
            assert name in provided_inputs, (report_name, "Missing evidence", name)
            source = provided_inputs[name]
            assert source.resolve() == Path(evidence["path"]).resolve(), (report_name, name)
            assert sha(source.read_bytes()) == evidence["sha256"], (report_name, "Stale evidence", name)
            replay["inputs/" + name].setdefault("reports", []).append(report_name)
    # Regression fixtures must identify the actual previous production source,
    # not merely a hand-written approximation with a historical label.
    with zipfile.ZipFile(BASE) as base, zipfile.ZipFile(ROOT / "upload/haha.zip") as original:
        for report_name, report in reports.items():
            baseline = report.get("baseline", {})
            for relative, expected in baseline.get("source_sha256", {}).items():
                safe_relative(relative)
                matches = [label for label, archive in ((BASE.name, base), ("upload/haha.zip", original))
                           if relative in archive.namelist() and sha(archive.read(relative)) == expected]
                assert matches, (report_name, "Unverified baseline source", relative)
                replay["baseline/" + report_name + "/" + relative] = {
                    "sha256": expected, "verified_archive": matches,
                    "fixture_tests": sorted(report.get("test_sha256", {}))}
    version_path = report_path("version_validation")
    version = read(version_path)
    validate_report(version_path.name, version)
    assert set(version["versions"].values()) == {VERSION}
    assert version["tracker_sha256"] == sha((SOURCE / "archipelago/soh_extreme/TrackerMirror.py").read_bytes())
    for source in (report_path("source_completeness"), report_path("source_build_validation"), version_path,
                   ROOT / "tests/finder_hints_186_validate_apworld.py",
                   ROOT / "tests/tracker_yamlless_1814_source_build_check.py",
                   ROOT / "tests/entrance_184_source_build_probe.ps1",
                   ROOT / "prepare_source_delivery.py", ROOT / "prepare_runtime_delivery.py", Path(__file__)):
        copy(source, validation_prefix + source.name)
    (VALIDATION / "REPLAY_INPUTS.json").write_text(json.dumps(replay, indent=2) + "\n")
    added.add(validation_prefix + "REPLAY_INPUTS.json")
    for name in ("README.txt", "VALIDATION.txt", validation_prefix + "REPLAY.txt"):
        assert (PACKAGE / name).is_file() and b"_PENDING" not in (PACKAGE / name).read_bytes(), name
        added.add(name)
    with zipfile.ZipFile(BASE) as base:
        for name in base.namelist():
            if name.startswith("validation/"):
                assert (PACKAGE / name).read_bytes() == base.read(name), name
        for name in ("BUILD_RELEASE.cmd", "BUILD_RELEASE.ps1"):
            assert (PACKAGE / name).read_bytes() == base.read(name).replace(b"1.8.13", VERSION.encode())
    summary = {"status": "passed", "version": VERSION, "complete_source_files": len(manifest["files"]),
               "base_archive_sha256": BASE_SHA, "all_previous_replacement_files_retained": True,
               "source_sha256": complete["source_sha256"], "manifest_sha256": complete["manifest_sha256"],
               "apworld_sha256": complete["apworld_sha256"], "entrance_catalog_entries": 721,
               "fresh_report_sha256": {p.name: sha(p.read_bytes()) for p in paths},
               "native_windows_build": False, "in_game_playthrough": False, "full_item_fill": False}
    name = validation_prefix + PREFIX + "_release_validation.json"
    (PACKAGE / name).write_text(json.dumps(summary, indent=2) + "\n")
    added.add(name)
    contents = {p.relative_to(PACKAGE).as_posix(): p.read_bytes() for p in PACKAGE.rglob("*") if p.is_file()}
    assert set(contents) == set(complete["prepared_archive_paths"]) | added
    assert not any(n.startswith("payload/") or n.endswith((".patch", ".diff")) for n in contents)
    write_source_archive(ARCHIVE, contents, datetime.now(timezone.utc))
    result = {"status": "passed", "archive": str(ARCHIVE), "size_bytes": ARCHIVE.stat().st_size,
              "sha256": sha(ARCHIVE.read_bytes()), "complete_source_files": len(manifest["files"]),
              "archive_entries": len(contents), "every_member_byte_verified": True}
    report_path("archive_validation").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build-apworld", "prepare", "finalize"))
    parser.add_argument("--report", action="append", type=Path, default=[])
    parser.add_argument("--dependency-root", action="append", type=Path,
                        default=[ROOT / "tests/entrance_184_native_dependencies"])
    parser.add_argument("--input", action="append", type=Path, default=[])
    args = parser.parse_args()
    {"build-apworld": build_apworld, "prepare": prepare,
     "finalize": lambda: finalize(args.report, args.dependency_root, args.input)}[args.action]()
