#!/usr/bin/env python3
"""Exercise the production destination-policy verifier with mutated inputs."""

from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import hashlib
import importlib.util
from io import StringIO
import json
from pathlib import Path
import shutil
import tempfile


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-include-root", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[2]
    generator_path = source / "tools/generate_entrance_destination_policy.py"
    spec = importlib.util.spec_from_file_location("entrance_destination_generator", generator_path)
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    policy_relative = Path("archipelago/soh_extreme/EntranceDestinationPolicy.json")
    native_relative = Path("soh/Network/Archipelago/EntranceDestinationData.inc")
    catalog_relative = Path("archipelago/soh_extreme/EntranceCatalog.json")
    files = [policy_relative, native_relative, catalog_relative,
             Path("soh/Network/Archipelago/EntranceRandomizerData.inc"),
             Path("archipelago/soh_extreme/DungeonDoorCatalog.json"),
             Path("soh/Enhancements/randomizer/randomizer_entrance.c"),
             Path("soh/Enhancements/randomizer/randomizer_grotto.c")]
    cases = []

    def write_json(path, value):
        path.write_text(json.dumps(value, indent=2) + "\n")

    def alter_json(relative, transform):
        def mutate(root, include):
            path = root / relative
            value = json.loads(path.read_text())
            transform(value)
            write_json(path, value)
        return mutate

    def run_case(name, mutate=None, error_fragment=None, check=True):
        with tempfile.TemporaryDirectory(prefix="soh-entrance-policy-") as directory:
            root = Path(directory)
            for relative in files:
                (root / relative).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source / relative, root / relative)
            include = root / "native_headers"
            include.mkdir()
            for filename in ("entrance_table.h", "scene_table.h"):
                shutil.copyfile(generator.native_header(args.native_include_root, filename), include / filename)
            if mutate:
                mutate(root, include)
            output = StringIO()
            cli = ["--source-root", str(root), "--native-include-root", str(include)]
            if check:
                cli.append("--check")
            with redirect_stdout(output), redirect_stderr(output):
                code = generator.main(cli)
            actual = output.getvalue()
            if error_fragment is None:
                assert code == 0, (name, actual)
                baseline = generator.render_native(json.loads((root / policy_relative).read_text()))
                assert (root / native_relative).read_text() == baseline, name
            else:
                assert code == 1 and error_fragment in actual, (name, error_fragment, actual)
            cases.append({"name": name, "status": "passed", "rejected": error_fragment is not None})

    run_case("all 721 reviewed endpoints and 2884 normal layer facts match")
    run_case("native output regenerates exactly", check=False)

    facts, evidence = generator.derive_endpoints(source, args.native_include_root)
    catalog = json.loads((source / catalog_relative).read_text())
    known_ids = {row["id"] for row in catalog}
    approved_scenes = set(json.loads((source / policy_relative).read_text())["approved_scene_ids"])
    candidate = next(row for row in evidence["entrances"].values()
                     if row["index"] == row["group_base"] and row["index"] not in known_ids
                     and row["scene"] in approved_scenes
                     and all(evidence["entrances"].get(row["index"] + layer, {}).get("scene") in approved_scenes
                             for layer in range(4)))

    def add_unreviewed(root, include):
        value = json.loads((root / catalog_relative).read_text())
        added = deepcopy(value[0])
        added.update({"id": candidate["index"], "index": candidate["name"], "scene": candidate["scene"]})
        value.append(added)
        write_json(root / catalog_relative, value)
        native = root / "soh/Network/Archipelago/EntranceRandomizerData.inc"
        fields = [added["id"], added["reverse"], added["scene"], added["source_scene"], added["check_id"],
                  -1, -1, -1, -1, added["id"], 0, 0, 0, 0, added["name"]]
        native.write_text(native.read_text() + "{" + json.dumps(fields)[1:-1] + "},\n")
    run_case("unknown endpoint in a normal scene is not auto-approved",
             add_unreviewed, "EntranceCatalog changed")

    def add_debug(value):
        added = deepcopy(value[0])
        added.update({"id": 0x18, "index": "ENTR_SASATEST_0", "scene": 0x6C})
        value.append(added)
    run_case("debug endpoint rejected before manifest comparison",
             alter_json(catalog_relative, add_debug), "prohibited scene")

    def add_duplicate_gallery(value):
        added = deepcopy(value[0])
        added.update({"id": 0x2EA, "index": "ENTR_TEST_SHOOTING_GALLERY_0", "scene": 0x42})
        value.append(added)
    run_case("debug duplicate entry in an ordinary scene is prohibited",
             alter_json(catalog_relative, add_duplicate_gallery), "debug-only native entrance")

    def change_door(root, include):
        for relative in (catalog_relative, Path("archipelago/soh_extreme/DungeonDoorCatalog.json")):
            value = json.loads((root / relative).read_text())
            row = next(row for row in value if row["index"] == "DOOR_0_0_0")
            row["position"][0] += 50
            write_json(root / relative, value)
        path = root / "soh/Network/Archipelago/EntranceRandomizerData.inc"
        value = path.read_text()
        old = "{8192, 8193, 0, 0, 11200000, 0, 0, 0, 1, 0, -455, 400, 455, -8192,"
        assert old in value
        path.write_text(value.replace(old, old.replace("-455", "-405"), 1))
    run_case("coordinated catalog and native door position edits require manifest review", change_door,
             "EntranceCatalog changed")

    def change_compiled_door(root, include):
        path = root / "soh/Network/Archipelago/EntranceRandomizerData.inc"
        value = path.read_text()
        old = "{8192, 8193, 0, 0, 11200000, 0, 0, 0, 1, 0, -455, 400, 455, -8192,"
        assert old in value
        path.write_text(value.replace(old, old.replace("-455", "-405"), 1))
    run_case("native-only stale door position is rejected", change_compiled_door,
             "Compiled entrance endpoint 8192 metadata differs from catalog")

    def change_grotto(root, include):
        path = root / "soh/Enhancements/randomizer/randomizer_grotto.c"
        text = path.read_text()
        assert "62.5078f" in text
        path.write_text(text.replace("62.5078f", "63.5078f", 1))
    run_case("native grotto return position changes are detected", change_grotto, "grotto_metadata")

    def change_layer(scene):
        def mutate(root, include):
            path = include / "entrance_table.h"
            value = path.read_text()
            old = "DEFINE_ENTRANCE(ENTR_DEKU_TREE_0_2, SCENE_DEKU_TREE, 0,"
            assert old in value
            path.write_text(value.replace(old, f"DEFINE_ENTRANCE(ENTR_DEKU_TREE_0_2, {scene}, 0,", 1))
        return mutate
    run_case("changed normal age-layer scene invalidates door anchor", change_layer("SCENE_DODONGOS_CAVERN"),
             "anchor changes scene by age/time")
    run_case("cutscene-only age-layer scene is prohibited", change_layer("SCENE_CHAMBER_OF_THE_SAGES"), "prohibited scene")

    def unrepair_alias(root, include):
        path = root / "soh/Enhancements/randomizer/randomizer_entrance.c"
        value = path.read_text()
        old = "gEntranceTable[ENTR_HYRULE_FIELD_10 + i] = gEntranceTable[ENTR_TEMPLE_OF_TIME_WARP_PAD + i];"
        assert old in value
        path.write_text(value.replace(old, "/* removed alias */", 1))
    run_case("removed runtime alias cannot leave policy claiming copied rows", unrepair_alias, "Native alias implementation changed")

    def disable_ap_child_warps(root, include):
        path = root / "soh/Enhancements/randomizer/randomizer_entrance.c"
        value = path.read_text()
        old = "if (Archipelago_EntranceShuffleActive() ||"
        assert old in value
        path.write_text(value.replace(old, "if (", 1))
    run_case("AP-only pools must still repair all child temple blue warps", disable_ap_child_warps,
             "AP-active child blue-warp repair guard")

    def stale_native(root, include):
        path = root / native_relative
        value = path.read_text()
        path.write_text(value.replace("{0, 0, 0, 3, 3,", "{0, 0, 0, 3, 1,", 1))
    run_case("stale native policy is rejected", stale_native, "native destination policy is stale")
    run_case("zero age mask is rejected",
             alter_json(policy_relative, lambda value: value["endpoints"][0].update(source_age_mask=0)), "Invalid reviewed age mask")
    run_case("duplicate reviewed endpoint is rejected",
             alter_json(policy_relative, lambda value: value["endpoints"].append(deepcopy(value["endpoints"][0]))),
             "Duplicate reviewed endpoint")
    run_case("cutscene scene cannot be manually added to positive scene list",
             alter_json(policy_relative, lambda value: value["approved_scene_ids"].append(0x44)),
             "Policy approves a cutscene/debug/undefined scene")

    # Native enum values are the reverse of these policy bits. Assert the reviewed
    # integer contract directly to keep generator tests from adopting that error.
    reviewed = json.loads((source / policy_relative).read_text())
    rows = {row["id"]: row for row in reviewed["endpoints"]}
    assert {row["id"]: row["source_age_mask"] for row in rows.values() if row["source_age_mask"] != 3} == {
        187: 1, 638: 1, 1364: 1, 642: 2, 781: 2}
    assert {row["id"]: row["arrival_age_mask"] for row in rows.values() if row["arrival_age_mask"] != 3} == {
        781: 2, 1000: 2, 832: 1, 2060: 1}
    assert all(rows[endpoint]["source_age_mask"] == 3 for endpoint in (1000, 832, 2060))
    cases.append({"name": "reviewed age masks preserve shared interior source ages", "status": "passed", "rejected": False})

    report = {
        "status": "passed", "cases": cases, "case_count": len(cases),
        "endpoint_count": len(facts), "normal_layer_resolution_count": len(facts) * 4,
        "scope": "Production Python generator and actual native table/catalog inputs; no ROM/renderer/gameplay execution.",
        "source_hashes": {str(relative): hashlib.sha256((source / relative).read_bytes()).hexdigest()
                          for relative in files + [Path("tools/generate_entrance_destination_policy.py"),
                                                   Path("tools/tests/test_entrance_destination_policy.py")]},
        "header_hashes": {name: evidence["source_hashes"][name]
                          for name in ("entrance_table.h", "scene_table.h")},
    }
    if args.report:
        args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": "passed", "cases": len(cases), "endpoints": len(facts), "layers": len(facts) * 4}))


if __name__ == "__main__":
    main()
