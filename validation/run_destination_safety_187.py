"""Capture reproducible focused AP destination-safety validation evidence."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import time
import unittest

ROOT = Path('/workspace/scratch/8fddab5b8169')
SOURCE = ROOT / 'source'
TEST = SOURCE / 'tools/tests/test_entrance_destination_safety.py'
FILES = [
    'archipelago/soh_extreme/EntranceRandomizer.py',
    'archipelago/soh_extreme/EntranceSafety.py',
    'archipelago/soh_extreme/EntranceDestinationPolicy.json',
    'archipelago/soh_extreme/EntranceCatalog.json',
    'archipelago/soh_extreme/_vendor_oot_soh/RegionAgeAccess.py',
    'archipelago/soh_extreme/_vendor_oot_soh/Regions.py',
    'archipelago/soh_extreme/_vendor_oot_soh/location_access/root.py',
    'tools/tests/test_entrance_destination_safety.py',
]


def hashes():
    return {name: hashlib.sha256((SOURCE / name).read_bytes()).hexdigest() for name in FILES}


def main():
    before = hashes()
    start = time.monotonic()
    spec = importlib.util.spec_from_file_location('test_entrance_destination_safety', TEST)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    suite = unittest.defaultTestLoader.loadTestsFromModule(module)
    output = io.StringIO()
    result = unittest.TextTestRunner(stream=output, verbosity=2).run(suite)
    after = hashes()
    passed = result.wasSuccessful() and before == after and result.testsRun == 35
    report = {
        'passed': passed, 'runtime': 'Archipelago 0.6.7',
        'test_cases': result.testsRun,
        'expected_test_cases': 35,
        'catalog_endpoints': 719,
        'scope': 'Actual AP CollectionState, SohRegion, source EntranceSafety and EntranceRandomizer helpers. '
                 'Focused graphs exercise physical route and age semantics; this is not a native build or in-game playtest.',
        'coverage': [
            'All catalog endpoints match the reviewed policy and four ordinary age/time layers.',
            'Native group bases, door anchors, IDs, row metadata and policy field validation fail closed.',
            'Only grounded castle fairy/grotto returns carry an arrival age restriction.',
            'Spawns and owls use explicit child/adult masks; ordinary bosses and rooms retain both ages.',
            'Wrong-age mappings and restricted unshuffled identity exits are rejected in the actual age graph.',
            'Blue warps, songs and other one-way physical sources receive the same route audit.',
            'Source item/age predicates remain intact; bad destinations are not hidden behind invented logic gates.',
            'Both age-specific spawns need their own initial return and route, without granting real items or age changes.',
            'Local prefilled progression can unlock an age-specific return; future pool/full inventory cannot certify it.',
            'Fresh candidate states and all caller age contexts are preserved.',
        ],
        'source_hashes': after, 'source_unchanged_during_tests': before == after,
        'elapsed_seconds': round(time.monotonic() - start, 3),
        'errors': [{'test': str(test), 'traceback': message} for test, message in result.errors],
        'failures': [{'test': str(test), 'traceback': message} for test, message in result.failures],
        'log': output.getvalue(),
    }
    path = ROOT / 'tests/entrance_destination_187_validation.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({key: report[key] for key in ('passed', 'test_cases', 'source_unchanged_during_tests',
                                                'elapsed_seconds')}), flush=True)
    if not passed:
        print(output.getvalue())
    return 0 if passed else 1


if __name__ == '__main__':
    sys.exit(main())
