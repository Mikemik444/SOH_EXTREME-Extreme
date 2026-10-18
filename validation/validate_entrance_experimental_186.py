"""Independent source/AST and official AP-option review of Experimental labels.

No native UI build or rendered screenshot is claimed by this validation.
The native baseline is the original upload overlaid with the 1.8.5 replacement ZIP.
"""
from __future__ import annotations

import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
from types import SimpleNamespace
import zipfile

import ModuleUpdate
ModuleUpdate.update_ran = True
import settings
settings.no_gui = True
settings.skip_autosave = True


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source"
PREVIOUS = ROOT / "delivery/SOH-EXTREME-1.8.5-source-files.zip"
ORIGINAL = ROOT / "upload/haha.zip"
REPORT = ROOT / "tests/entrance_experimental_186_validation.json"
FILES = (
    "archipelago/soh_extreme/EntranceOptions.py",
    "archipelago/soh_extreme/EntranceRandomizer.py",
    "archipelago/soh_extreme/Options.py",
    "soh/Enhancements/randomizer/option.cpp",
    "soh/Enhancements/randomizer/option.h",
    "soh/Enhancements/randomizer/settings.cpp",
    "soh/Enhancements/randomizer/randomizerEnums/RandomizerSettingKey.h",
    "soh/Enhancements/randomizer/3drando/spoiler_log.cpp",
)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def text(data):
    return data.decode("utf-8-sig").replace("\r\n", "\n")


def between(value, begin, end):
    index = value.index(begin)
    return value[index:value.index(end, index)]


def assigned(module, name):
    return next(node.value for node in module.body if isinstance(node, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == name for target in node.targets))


def normalize(value):
    if isinstance(value, (set, frozenset)):
        return sorted(value)
    return value


def load_options(code, module_name):
    namespace = {"__name__": module_name}
    exec(compile(code, module_name, "exec"), namespace)
    return namespace


def pool_functions(code):
    module = ast.parse(code)
    selected = [node for node in module.body
                if isinstance(node, ast.FunctionDef) and node.name in {"enabled_categories", "mixed_categories"}
                or isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "CATEGORIES"
                                                        for target in node.targets)]
    namespace = {}
    exec(compile(ast.Module(body=selected, type_ignores=[]), "actual_pool_functions", "exec"), namespace)
    return namespace, selected


def main():
    assertions = []

    def check(condition, name, **details):
        assertions.append({"name": name, "passed": bool(condition), **details})
        if not condition:
            raise AssertionError(name)

    current = {name: (SOURCE / name).read_bytes() for name in FILES}
    before = {name: sha(data) for name, data in current.items()}
    native_files = [name for name in FILES if name.startswith("soh/")]
    with zipfile.ZipFile(PREVIOUS) as previous, zipfile.ZipFile(ORIGINAL) as original:
        previous_names = set(previous.namelist())
        baseline = {name: previous.read(name) if name in previous_names else original.read(name) for name in FILES}
        baseline_from = {name: "1.8.5 replacement source ZIP" if name in previous_names
                         else "original source inherited unchanged by 1.8.5" for name in FILES}
        completeness = json.loads(previous.read("validation/finder_hints_185_source_completeness.json"))
        manifest = json.loads(previous.read("SOURCE_FILES.json"))
    check(completeness["status"] == "passed" and completeness["version"] == "1.8.5" and
          completeness["original_archive_sha256"] == sha(ORIGINAL.read_bytes()) and
          not completeness["unmanifested_source_changes"] and not completeness["missing_original_files"],
          "inherited_native_baseline_is_tied_to_185_complete_source_audit")
    changed_185 = {row["path"] for row in manifest["files"]}
    check(all(name not in changed_185 for name in native_files),
          "reviewed_native_files_were_unchanged_and_not_replaced_in_185")

    ap_path = "archipelago/soh_extreme/EntranceOptions.py"
    ap_before = ast.parse(text(baseline[ap_path]))
    ap_after = ast.parse(text(current[ap_path]))
    old_classes = {node.name: node for node in ap_before.body if isinstance(node, ast.ClassDef)}
    new_classes = {node.name: node for node in ap_after.body if isinstance(node, ast.ClassDef)}
    check(len(old_classes) == len(new_classes) == 12 and old_classes.keys() == new_classes.keys(),
          "all_twelve_existing_ap_option_classes_are_preserved")
    restored = deepcopy(ap_after)
    class_rows = []
    old_runtime = load_options(text(baseline[ap_path]), "_entrance_experimental_baseline")
    new_runtime = load_options(text(current[ap_path]), "_entrance_experimental_current")
    old_keys, new_keys = old_runtime["ENTRANCE_OPTIONS"], new_runtime["ENTRANCE_OPTIONS"]
    check(list(old_keys) == list(new_keys) and len(new_keys) == 12,
          "all_twelve_yaml_option_keys_and_order_are_unchanged", keys=list(new_keys))
    key_for_class = {cls.__name__: key for key, cls in new_keys.items()}
    for node in restored.body:
        if not isinstance(node, ast.ClassDef):
            continue
        old = old_classes[node.name]
        doc = ast.get_docstring(node, clean=False)
        old_doc = ast.get_docstring(old, clean=False)
        check(doc.startswith("Experimental. ") and doc.removeprefix("Experimental. ") == old_doc,
              f"{node.name}_tooltip_is_experimental_and_preserves_original_help")
        node.body[0].value.value = old_doc
        label = assigned(node, "display_name")
        old_label = assigned(old, "display_name").value
        check(label.value == old_label + " (Experimental)",
              f"{node.name}_visible_label_is_experimental")
        label.value = old_label
        key = key_for_class[node.name]
        old_cls, cls = old_keys[key], new_keys[key]
        check(old_cls.__bases__ == cls.__bases__ and old_cls.default == cls.default and
              getattr(old_cls, "valid_keys", None) == getattr(cls, "valid_keys", None),
              f"{node.name}_base_default_and_valid_values_are_unchanged")
        values = [{"all"}, set(), {"overworld", "interiors"}] if key == "mixed_entrance_pools" else [0, 1, False, True]
        for value in values:
            check(old_cls.from_any(value).value == cls.from_any(value).value,
                  f"{node.name}_input_{normalize(value)!r}_serializes_unchanged")
        class_rows.append({"yaml_key": key, "class": node.name,
                           "label": cls.display_name, "default": normalize(cls.default),
                           "valid_keys": normalize(getattr(cls, "valid_keys", None)),
                           "tooltip_prefix": "Experimental. "})
    group = assigned(restored, "ENTRANCE_GROUP")
    old_group = assigned(ap_before, "ENTRANCE_GROUP")
    check(group.args[0].value == "Entrance Randomizer (Experimental)", "ap_group_heading_is_experimental")
    group.args[0].value = old_group.args[0].value
    check(ast.dump(restored, include_attributes=False) == ast.dump(ap_before, include_attributes=False),
          "entire_ap_option_ast_diff_contains_only_labels_tooltips_and_group_heading")
    check(new_runtime["ENTRANCE_GROUP"].options == list(new_keys.values()),
          "experimental_ap_group_contains_every_entrance_option")
    options_path = "archipelago/soh_extreme/Options.py"
    check(current[options_path] == baseline[options_path] and "ENTRANCE_GROUP," in text(current[options_path]),
          "existing_options_registration_still_uses_experimental_group_without_schema_changes")

    er_path = "archipelago/soh_extreme/EntranceRandomizer.py"
    old_pool, old_ast = pool_functions(text(baseline[er_path]))
    pool, new_ast = pool_functions(text(current[er_path]))
    check(ast.dump(ast.Module(body=old_ast, type_ignores=[]), include_attributes=False) ==
          ast.dump(ast.Module(body=new_ast, type_ignores=[]), include_attributes=False),
          "enabled_and_mixed_pool_algorithms_and_category_mapping_are_unchanged")
    categories = pool["CATEGORIES"]
    category_names = list(categories)
    pool_cases = 0
    for mask in range(1 << len(category_names)):
        enabled = {name for index, name in enumerate(category_names) if mask & (1 << index)}
        configured = SimpleNamespace(**{field: SimpleNamespace(value=int(category in enabled))
                                         for category, field in categories.items()})
        world = SimpleNamespace(options=configured)
        for selection in ({"all"}, {"all", "overworld", "dungeon_doors"}):
            configured.mixed_entrance_pools = SimpleNamespace(value=selection)
            assert pool["mixed_categories"](world) == enabled
            assert pool["mixed_categories"](world) == old_pool["mixed_categories"](world)
            assert {name for name, field in categories.items() if getattr(configured, field).value} == enabled
            pool_cases += 1
    check(pool_cases == 4096, "mixed_all_preserves_every_enabled_combination_without_enabling_disabled_pools",
          combinations=2048, selections_per_combination=2, evaluations=pool_cases)

    option_path = "soh/Enhancements/randomizer/option.cpp"
    option = text(current[option_path])
    old_option = text(baseline[option_path])
    helper = between(option, "static bool IsExperimentalEntranceOption(", "void Option::AddWidget(")
    helper_keys = re.findall(r"case (RSK_[A-Z_]+):", helper)
    enum_path = "soh/Enhancements/randomizer/randomizerEnums/RandomizerSettingKey.h"
    enum_keys = re.findall(r"RANDO_ENUM_ITEM\((RSK_[A-Z_]+)\)", text(current[enum_path]))
    entrance_keys = [key for key in enum_keys if "ENTRANCE" in key or key in
                     {"RSK_SHUFFLE_OWL_DROPS", "RSK_SHUFFLE_WARP_SONGS", "RSK_SHUFFLE_OVERWORLD_SPAWNS"}]
    check(len(helper_keys) == len(set(helper_keys)) == 19 and set(helper_keys) == set(entrance_keys),
          "native_experimental_helper_covers_every_one_of_the_19_entrance_control_keys",
          keys=helper_keys)
    check(current[enum_path] == baseline[enum_path], "native_setting_enum_names_order_and_values_are_unchanged")
    check("return true;" in helper and "default:\n            return false;" in helper,
          "experimental_native_scope_does_not_include_unrelated_controls")
    add_widget = between(option, "void Option::AddWidget(", "void Option::PopulateTextToNum(")
    old_add_widget = between(old_option, "void Option::AddWidget(", "void Option::PopulateTextToNum(")
    check("(GetCategory() == OptionCategory::Setting || GetCategory() == OptionCategory::Toggle)" in add_widget and
          "IsExperimentalEntranceOption(GetKey())" in add_widget,
          "every_native_setting_and_toggle_uses_the_shared_experimental_display_path")
    label_expression = 'const std::string label = experimental ? this->GetName() + " (Experimental)###" + stableId : stableId;'
    tooltip_expression = ('info.options->tooltip = experimental\n'
                          '                              ? "Experimental entrance-randomizer setting.\\n\\n" + this->GetDescription()\n'
                          '                              : this->GetDescription();')
    check(label_expression in add_widget and tooltip_expression in add_widget,
          "native_widgets_receive_experimental_labels_and_tooltip_prefixes")
    check('const std::string stableId = this->GetName() + "##Randomizer";' in add_widget,
          "native_labels_keep_the_previous_widget_id_after_imgui_triple_hash")
    reverted_widget = "void Option::AddWidget(WidgetPath& path) {\n" + add_widget[add_widget.index("    auto widget ="):]
    reverted_widget = reverted_widget.replace('AddWidget(path, label, widgetType)',
                                               'AddWidget(path, this->GetName() + "##Randomizer", widgetType)')
    reverted_widget = reverted_widget.replace('.PreFunc([this, experimental]', '.PreFunc([this]')
    reverted_widget = reverted_widget.replace(tooltip_expression, 'info.options->tooltip = this->GetDescription();')
    check(reverted_widget == old_add_widget,
          "native_widget_callbacks_cvars_options_visibility_disable_and_value_behavior_are_unchanged")
    reverted_option = option.replace(helper, "").replace(add_widget, old_add_widget)
    check(reverted_option == old_option,
          "entire_native_option_cpp_diff_is_limited_to_the_experimental_helper_and_display_changes")
    get_name = between(option, "const std::string& Option::GetName()", "const std::string& Option::GetDescription()")
    check(get_name == between(old_option, "const std::string& Option::GetName()", "const std::string& Option::GetDescription()")
          and "Experimental" not in get_name,
          "serialized_native_GetName_remains_byte_identical")
    header_path = "soh/Enhancements/randomizer/option.h"
    check(current[header_path] == baseline[header_path],
          "native_option_construction_API_and_inherited_defaults_are_unchanged")

    settings_path = "soh/Enhancements/randomizer/settings.cpp"
    native_settings = text(current[settings_path])
    old_settings = text(baseline[settings_path])
    check(native_settings.count('"Entrances (Experimental)"') == 1 and
          native_settings.replace('"Entrances (Experimental)"', '"Entrances"') == old_settings,
          "entire_native_settings_cpp_diff_is_only_the_experimental_section_heading")
    section = between(native_settings, "mOptionGroups[RSG_MENU_SECTION_ENTRANCES] =", "mOptionGroups[RSG_MENU_COLUMN_ENTRANCES]")
    section_keys = re.findall(r"&mOptions\[(RSK_[A-Z_]+)\]", section)
    check(len(section_keys) == 18 and set(section_keys) == set(helper_keys) - {"RSK_SHUFFLE_ENTRANCES"},
          "all_18_direct_native_controls_are_in_the_experimental_section_and_aggregate_toggle_is_covered")
    native_rows = []
    for key in helper_keys:
        declarations = re.findall(rf"^\s*(OPT_(?:BOOL|U8)\({key},[^\n]*);", native_settings, re.MULTILINE)
        check(len(declarations) == 1, f"{key}_has_one_unchanged_native_declaration")
        declaration = declarations[0]
        check(declaration in old_settings, f"{key}_native_cvar_default_values_and_widget_type_unchanged")
        check(declaration.startswith("OPT_BOOL(") or "OptionCategory::Setting" in declaration,
              f"{key}_uses_an_experimental_display_category")
        native_rows.append({"key": key, "declaration": declaration, "experimental_label": True,
                            "experimental_tooltip": True})
    spoiler_path = "soh/Enhancements/randomizer/3drando/spoiler_log.cpp"
    check(current[spoiler_path] == baseline[spoiler_path] and
          'jsonData["settings"][option.GetName()]' in text(current[spoiler_path]) and
          'output[mOptions[count].GetName()]' in native_settings,
          "native_spoiler_serialization_and_settings_name_lookup_still_use_unchanged_GetName")

    after = {name: sha((SOURCE / name).read_bytes()) for name in FILES}
    check(before == after, "all_reviewed_production_source_remained_unchanged_during_validation")
    result = {
        "status": "passed", "version": "1.8.6", "assertions_passed": len(assertions),
        "scope": "Read-only Python AST/official AP option runtime comparison and native source-contract review.",
        "native_compilation_performed": False, "rendered_ui_verified": False,
        "behavioral_entrance_routing_or_in_game_playthrough_tested_here": False,
        "baseline": {"release": "1.8.5", "replacement_zip": str(PREVIOUS),
                     "replacement_zip_sha256": sha(PREVIOUS.read_bytes()),
                     "original_source_zip": str(ORIGINAL), "original_source_zip_sha256": sha(ORIGINAL.read_bytes()),
                     "method": "Original uploaded source overlaid by complete replacement files from the 1.8.5 ZIP.",
                     "source_origin": baseline_from, "source_sha256": {name: sha(data) for name, data in baseline.items()}},
        "source_sha256": before, "source_unchanged_during_validation": True,
        "validator_sha256": sha(Path(__file__).read_bytes()), "ap_options": class_rows,
        "ap_group": "Entrance Randomizer (Experimental)", "native_section": "Entrances (Experimental)",
        "native_controls": native_rows, "mixed_all_evaluations": pool_cases, "assertions": assertions,
    }
    REPORT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "assertions": len(assertions), "ap_controls": len(class_rows),
                      "native_controls": len(native_rows), "mixed_all_evaluations": pool_cases, "report": str(REPORT)}))


if __name__ == "__main__":
    main()
