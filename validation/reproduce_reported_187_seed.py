"""Attempt exact old-release reproduction; report placement parity explicitly."""
from pathlib import Path
import argparse
import hashlib
import json
import logging
import random
import time

import ModuleUpdate
ModuleUpdate.update_ran = True
import settings
settings.no_gui = True
settings.skip_autosave = True
import Utils
import yaml
from BaseClasses import CollectionState, PlandoOptions
from Generate import roll_settings
from Main import main as generate
from worlds.soh_extreme import SohExtremeWorld
from worlds.soh_extreme import EntranceRandomizer as ER


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--yaml', type=Path, required=True)
parser.add_argument('--spoiler', type=Path, required=True)
parser.add_argument('--report', type=Path, required=True)
parser.add_argument('--seed', type=int, required=True)
args = parser.parse_args()
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
random.seed(args.seed)
rolled = roll_settings(yaml.safe_load(args.yaml.read_text(encoding='utf-8-sig')))
rolled.starting_age = SohExtremeWorld.options_dataclass.type_hints['starting_age'].from_any('adult')
generate_args = argparse.Namespace(**{name: {1: value} for name, value in vars(rolled).items()})
generate_args.multi = 1
generate_args.outputpath = None
generate_args.outputname = 'reported-seed-reproduction'
generate_args.race = False
generate_args.plando = PlandoOptions.bosses
generate_args.sprite = {}
generate_args.sprite_pool = {}
generate_args.csv_output = False
generate_args.skip_output = True
generate_args.spoiler_only = False
generate_args.skip_prog_balancing = False
settings.get_settings().generator.panic_method = 'swap'
started = time.monotonic()
original_connect = SohExtremeWorld.connect_entrances


def checkpoint_mapping(self):
    original_connect(self)
    args.report.with_suffix('.mapping.json').write_text(json.dumps({
        'status': 'mapping_checkpoint_only', 'seed': args.seed,
        'archipelago_version': Utils.__version__, 'world_version': self.world_version.as_simple_string(),
        'all_placements_match_uploaded_spoiler': None,
        'mapping': self._er_mapping,
        'scope': 'Generation has connected entrances but placement parity is not yet verified.',
    }, indent=2)+'\n')


SohExtremeWorld.connect_entrances = checkpoint_mapping
mw = generate(generate_args, seed=args.seed)
world = mw.worlds[1]
spoiler = args.spoiler.read_text(encoding='utf-8-sig')
listed = set(spoiler.split('Locations:\n', 1)[1].split('Playthrough:\n', 1)[0].splitlines())
network = [loc for loc in world.get_locations() if loc.address is not None]
matched, mismatched = [], []
for loc in network:
    line = f'{loc.name}: {loc.item.name}'
    (matched if line in listed else mismatched).append({'id': loc.address, 'name': loc.name, 'item': loc.item.name})
initial = CollectionState(mw)
initial.sweep_for_advancements(locations=[loc for loc in world.get_locations() if loc.address is None])
routes = []
for source, target in sorted(world._er_mapping.items()):
    a, b = ER.ENDPOINTS[source], ER.ENDPOINTS[target]
    if a['source_scene'] == 2 or b['source_scene'] == 2:
        routes.append({'source_id': source, 'source': a['name'], 'target_id': target, 'target': b['name'],
                       'target_region': b['target']})
data = {
    'status': 'reproduced' if not mismatched else 'not_exactly_reproduced',
    'archipelago_version': Utils.__version__, 'world_version': world.world_version.as_simple_string(),
    'seed': args.seed, 'yaml_sha256': hashlib.sha256(args.yaml.read_bytes()).hexdigest(),
    'spoiler_sha256': hashlib.sha256(args.spoiler.read_bytes()).hexdigest(),
    'elapsed_seconds': round(time.monotonic()-started, 2),
    'network_checks': len(network), 'matching_placements': len(matched),
    'mismatched_placements': len(mismatched), 'first_mismatches': mismatched[:15],
    'all_placements_match_uploaded_spoiler': not mismatched,
    'jabu_routes': routes,
    'initial_checks': [{'id':loc.address,'name':loc.name,'item':loc.item.name}
                       for loc in network if ER._reachable_at_starting_age(world, initial, loc)],
    'mapping': world._er_mapping,
    'scope': 'Prior immutable release and official AP runtime. Routes describe the uploaded seed only if every placement matches.',
}
args.report.write_text(json.dumps(data, indent=2)+'\n')
print(json.dumps({key:data[key] for key in ('status','seed','archipelago_version','world_version',
                                         'network_checks','matching_placements','mismatched_placements','elapsed_seconds')}),flush=True)
