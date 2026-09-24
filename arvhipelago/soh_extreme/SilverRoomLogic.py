"""Exact native room + local collection routes for the existing 80 silver checks.

A proxy has one incoming edge per native collection alternative. This avoids
flattening (room A AND method A) OR (room B AND method B) into unrelated ORs.
No extra network locations or item IDs are introduced.
"""
from __future__ import annotations
import json
from importlib.resources import files
from Options import OptionError
from rule_builder.rules import True_
from ._vendor_oot_soh.Regions import SohRegion
from ._vendor_oot_soh import LogicHelpers as H
from .EnemyRoomLogic import GRAPH, NativeEnemyRegions

ROUTES = json.loads(files(__package__).joinpath("SilverRoomRoutes.json").read_text())

def create_silver_location_region(world, definition):
    routes = ROUTES.get(definition.rc)
    if not routes or any(r["region"] not in GRAPH for r in routes):
        raise OptionError("Missing exact native silver route: " + definition.rc)
    region = SohRegion("EXTREME Silver Access: " + definition.name, world.player, world.multiworld)
    world.multiworld.regions.append(region)
    if not hasattr(world, "_extreme_silver_regions"):
        world._extreme_silver_regions = {}
    world._extreme_silver_regions[definition.rc] = (definition.name, region)
    return region

def install_silver_routes(world):
    compiler = world._extreme_room_compiler
    for rc, (_, target) in getattr(world, "_extreme_silver_regions", {}).items():
        for route in ROUTES[rc]:
            source = route["region"]
            rule = compiler.expr(route["condition"], source)
            # H.connect_regions registers rule dependencies and preserves SoH's
            # child/adult graph semantics. Deferred local events are installed by
            # NativeRoomCompiler.install() immediately after this call.
            H.connect_regions(NativeEnemyRegions[source], world, [(target.name, rule)])

def finalize_silver_locations(world):
    for name, region in getattr(world, "_extreme_silver_regions", {}).values():
        location = world.get_location(name)
        if location.parent_region is not region:
            raise OptionError("Silver location lost its exact route: " + name)
        location.access_rule = True_().resolve(world)
