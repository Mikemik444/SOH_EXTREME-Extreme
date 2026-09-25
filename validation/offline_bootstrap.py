"""Headless harness dependencies only; never shipped in the AP world.

Network installation is unavailable. Refuse unsupported paths instead of
pretending that dependency-backed validation or binary patching succeeded.
Only an empty item_links list is accepted by the schema adapter, as in the YAML.
No gameplay rules, fill, reachability, collection, or random choices are mocked.
"""
import os, sys, types
os.environ['SKIP_REQUIREMENTS_UPDATE'] = '1'
class Schema:
    def __init__(self, *args, **kwargs):
        self.args, self.kwargs = args, kwargs
    def validate(self, value):
        if type(value) is list and not value and len(self.args) == 1 and type(self.args[0]) is list:
            return []
        raise RuntimeError('Offline harness cannot validate non-empty schema input')
class And(Schema): pass
class Or(Schema): pass
class Optional(Schema): pass
schema = types.ModuleType('schema')
for cls in (Schema, And, Or, Optional): setattr(schema, cls.__name__, cls)
sys.modules['schema'] = schema
bsdiff = types.ModuleType('bsdiff4')
def unsupported(*args, **kwargs): raise RuntimeError('Binary delta operation unavailable in this harness')
bsdiff.diff = bsdiff.patch = unsupported
sys.modules['bsdiff4'] = bsdiff
