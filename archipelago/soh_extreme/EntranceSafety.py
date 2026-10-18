"""Reviewed playable arrival facts shared with the native entrance router.

The policy records ordinary child/adult day/night table entries. A catalog
entry is not approved merely because its name or numeric scene looks valid.
Changes to the catalog or its native resolution require reviewing the policy
and regenerating its native counterpart with the supplied source tool.
"""
from hashlib import sha256
from importlib.resources import files
import json

from Options import OptionError


POLICY_REVISION = 1
CHILD = 1
ADULT = 2
BOTH = CHILD | ADULT
POLICY = json.loads(files(__package__).joinpath('EntranceDestinationPolicy.json').read_text())
POLICIES = {row['id']: row for row in POLICY['endpoints']}


def _fingerprint(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                             ensure_ascii=True).encode('utf-8')).hexdigest()


def validate_catalog(catalog, policy=None):
    """Fail closed when the reviewed manifest and the actual catalog differ."""
    policy = POLICY if policy is None else policy
    error = ('Entrance destinations do not match the reviewed playable-scene policy. '
             'Install the matching SOH-EXTREME APWorld and source files.')
    try:
        if type(policy['revision']) is not int or policy['revision'] != POLICY_REVISION:
            raise ValueError('Unsupported destination policy revision')
        rows = policy['endpoints']
        approved = {row['id']: row for row in rows}
        actual = {row['id']: row for row in catalog}
        if len(approved) != len(rows) or len(actual) != len(catalog) or actual.keys() != approved.keys():
            raise ValueError('Unreviewed, missing or duplicate endpoint')
        if _fingerprint(sorted(catalog, key=lambda row: row['id'])) != policy['catalog_sha256']:
            raise ValueError('Catalog fingerprint differs')
        scenes = set(policy['approved_scene_ids'])
        if not scenes or any(type(scene) is not int or scene < 0 for scene in scenes):
            raise ValueError('Invalid approved scene list')
        for endpoint_id, row in approved.items():
            if type(endpoint_id) is not int or endpoint_id < 0:
                raise ValueError('Invalid endpoint ID')
            if row['catalog_row_sha256'] != _fingerprint(actual[endpoint_id]):
                raise ValueError('Endpoint metadata differs')
            if row['kind'] not in ('native', 'grotto_load', 'grotto_return', 'door'):
                raise ValueError('Unknown arrival kind')
            if type(row['native_index']) is not int or row['native_index'] < 0:
                raise ValueError('Invalid native entrance base')
            endpoint = actual[endpoint_id]
            if row['kind'] == 'native' and (endpoint['door'] >= 0
                                          or row['native_index'] != endpoint_id):
                raise ValueError('Native destination is not its reviewed group base')
            if row['kind'] == 'door' and (endpoint['door'] < 0
                                        or row['native_index'] != endpoint['anchor']):
                raise ValueError('Room-door destination has a different scene anchor')
            if row['kind'] == 'grotto_load' and not 0x700 <= endpoint_id < 0x721:
                raise ValueError('Grotto load is outside the reviewed resolver range')
            if row['kind'] == 'grotto_return' and not 0x800 <= endpoint_id < 0x821:
                raise ValueError('Grotto return is outside the reviewed resolver range')
            for key in ('source_age_mask', 'arrival_age_mask'):
                if type(row[key]) is not int or row[key] not in (CHILD, ADULT, BOTH):
                    raise ValueError('Invalid age policy')
            if len(row['normal_layers']) != 4:
                raise ValueError('Ordinary age/time layers are incomplete')
            for layer in row['normal_layers']:
                if (type(layer['scene']) is not int or layer['scene'] not in scenes
                        or type(layer['spawn']) is not int or layer['spawn'] < 0):
                    raise ValueError('Unapproved scene or spawn')
    except (KeyError, TypeError, ValueError) as exc:
        raise OptionError(f'{error} ({exc})') from exc


def source_age_mask(endpoint_id):
    row = POLICIES.get(endpoint_id)
    return row['source_age_mask'] if row is not None else 0


def arrival_age_mask(endpoint_id):
    row = POLICIES.get(endpoint_id)
    return row['arrival_age_mask'] if row is not None else 0


def allowed_age(endpoint_id, age_mask):
    """Accept only a reviewed destination for one concrete age."""
    return age_mask in (CHILD, ADULT) and bool(arrival_age_mask(endpoint_id) & age_mask)


def allowed_route(source_id, destination_id):
    """Reject impossible ages before graph placement.

    Shared interior exits can be used by either age physically. The actual
    incoming topology decides which ages can reach them; the generator must
    separately prove that no reachable age uses a forbidden destination.
    """
    return bool(source_age_mask(source_id) & arrival_age_mask(destination_id))
