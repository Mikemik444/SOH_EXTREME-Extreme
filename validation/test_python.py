from __future__ import annotations
import asyncio
import importlib
import io
import json
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
from source_path import ap_source
AP_SOURCE = ap_source(ROOT)
# Load the production transport modules without importing AP world generation.
# The upstream host below is a controlled API service, NOT a real UT UI/server.
pkg = types.ModuleType("soh_extreme")
pkg.__path__ = [str(AP_SOURCE)]
sys.modules["soh_extreme"] = pkg
from soh_extreme.TrackerWorker import parse_config, read_config, make_managed_context, run_managed, register_worker, WORKER_COMPONENT
from soh_extreme.TrackerClient import make_context_class
from soh_extreme.TrackerMirror import PROTOCOL, VERSION, encode_snapshot, snapshot_rows

CONFIG = {"server":"localhost:38281", "slot_name":"Mike \"quoted\" \\ tester", "password":"Secret & % ! \\ \"", "slot":1,"nonce":"a"*32}

class ConfigTests(unittest.TestCase):
    def test_valid_pipe(self):
        self.assertEqual(read_config(io.BytesIO(json.dumps(CONFIG).encode()+b"\n")), CONFIG)
    def test_unicode(self):
        data=dict(CONFIG,slot_name="míké",password="🔑")
        self.assertEqual(parse_config(json.dumps(data,ensure_ascii=False).encode()),data)
    def test_invalid_fields(self):
        bad=[dict(CONFIG,slot=0),dict(CONFIG,slot=True),dict(CONFIG,slot=65536),dict(CONFIG,slot="1"),
             dict(CONFIG,nonce="b"*31),dict(CONFIG,nonce="G"*32),dict(CONFIG,server=""),dict(CONFIG,slot_name=""),
             dict(CONFIG,password="x\ny"),dict(CONFIG,server="https://host"),dict(CONFIG,server="ws://a:secret@host"),
             dict(CONFIG,server="ws://host:70000"),dict(CONFIG,server="ws://host:not_a_port"),
             dict(CONFIG,extra=True),dict(CONFIG,slot_name="m"*129),dict(CONFIG,password="x"*4097)]
        for data in bad:
            with self.subTest(data={k:v for k,v in data.items() if k!='password'}):
                with self.assertRaises(ValueError):parse_config(json.dumps(data).encode())
    def test_invalid_bytes(self):
        for data in [b"",b"{}",b"null",b"[]",b"\xff",b"x"*16002,b"{}\n{}"]:
            with self.assertRaises(ValueError):parse_config(data)

class Host:
    tags = {"AP","Tracker"}
    last = None
    def __init__(self, server=None, password=None, **kwargs):
        Host.last = self
        self.server_address=server;self.password=password
        self.exit_event=asyncio.Event(); self.game="SOH-EXTREME";self.slot=1
        self.disconnected_intentionally=False
        self.server_locations={11,12,13,14};self.checked_locations={14};self.tracker_items_received=[1,2]
        self.sent=[];self.calls=0;self.generator_calls=0;self.shutdown_called=False
        self.locations={name:types.SimpleNamespace(address=i,name=name,parent_region=types.SimpleNamespace(name=region))
                        for name,i,region in [("Fish %s",11,"Lake Hylia"),("Bush",12,"Kokiri Forest"),("Rock",13,"Death Mountain") ]}
        world=types.SimpleNamespace(get_location=lambda name:self.locations[name])
        self.tracker_core=types.SimpleNamespace(manual_items=['Injected item'],ignored_locations={999},multiworld=object(),
            tracker_disabled=False,enable_glitched_logic=True,location_alias_map={},get_current_world=lambda:world)
        self.result=types.SimpleNamespace(state=object(),in_logic_locations=["Fish %s","Bush"],glitched_locations=["Rock"])
    def on_package(self,cmd,args):pass
    def updateTracker(self):self.calls+=1;return self.result
    async def send_msgs(self,packets):self.sent.extend(packets)
    async def send_connect(self,**kwargs):self.connect_args=kwargs
    async def disconnect(self,allow_autoreconnect=False):pass
    async def shutdown(self):
        # Real CommonContext.shutdown awaits any non-null server_task.
        if getattr(self,'server_task',None):await self.server_task
        self.shutdown_called=True
    def run_generator(self):self.generator_calls+=1

class ManagedTests(unittest.IsolatedAsyncioTestCase):
    def create(self):return make_managed_context(make_context_class(Host),CONFIG)("localhost",CONFIG['password'])
    def request(self,nonce="a"*32,slot=1):
        return {'data':{'soh_extreme_tracker':PROTOCOL,'kind':'request','slot':slot,'nonce':nonce,'request':1}}
    async def test_same_evaluator_and_pinned_session(self):
        ctx=self.create()
        ctx.on_package('Bounced',self.request('b'*32))
        ctx.on_package('Bounced',self.request(slot=2))
        self.assertEqual(ctx.calls,0)
        ctx.on_package('Bounced',self.request())
        await asyncio.sleep(0)
        self.assertEqual(ctx.calls,1)
        self.assertEqual(len(ctx.sent),1)
        self.assertEqual(ctx.sent[0]['slots'],[1])
        self.assertEqual(ctx.sent[0]['data']['nonce'],'a'*32)
        rows=snapshot_rows(ctx.tracker_core,ctx.result,ctx.tracker_core.get_current_world(),ctx.server_locations,ctx.checked_locations)
        self.assertEqual({(r['id'],r['state']) for r in rows},{(11,1),(12,1),(13,2)})
        self.assertEqual(ctx.sent[0]['cmd'],'Bounce')
        await ctx.disconnect()
        self.assertIsNone(ctx._mirror_subscription)
    async def test_no_credentials_prompt(self):
        ctx=self.create();ctx.password=None
        await ctx.server_auth(True)
        self.assertTrue(ctx.exit_event.is_set());self.assertEqual(ctx.worker_exit_code,22)
        ctx=self.create();await ctx.server_auth(True)
        self.assertEqual(ctx.connect_args,{'game':'SOH-EXTREME'})
    async def test_wrong_slot(self):
        for slot,game in [(2,'SOH-EXTREME'),(1,'Other Game')]:
            ctx=self.create();ctx.on_package('Connected',{'slot':slot,'slot_info':{str(slot):['name',game]}})
            self.assertTrue(ctx.exit_event.is_set());self.assertEqual(ctx.worker_exit_code,22)
    async def test_invalid_reconstruction(self):
        ctx=self.create();ctx.tracker_core.multiworld=None
        ctx.on_package('Connected',{'slot':1,'slot_info':{'1':['name','SOH-EXTREME']}})
        self.assertEqual(ctx.worker_exit_code,23)
    async def test_no_gui_console_or_manual_overrides(self):
        ctx=self.create();ctx.load_seed_data()
        self.assertEqual(ctx.tracker_core.manual_items,[])
        self.assertEqual(ctx.tracker_core.ignored_locations,set())
        self.assertFalse(ctx._persistence_enabled)
        with self.assertRaises(RuntimeError):ctx.make_gui()
        with self.assertRaises(RuntimeError):ctx.run_cli()
        with self.assertRaises(RuntimeError):await ctx.console_input()
    async def test_full_managed_lifecycle(self):
        async def server_loop(ctx):
            await asyncio.sleep(0)
            ctx.on_package('Bounced',self.request())
            await asyncio.sleep(0)
            ctx.exit_event.set()
            await asyncio.Event().wait() # cancellation during owner shutdown
        ut=types.SimpleNamespace(TrackerGameContext=Host,server_loop=server_loop)
        result=await run_managed(CONFIG,ut)
        self.assertEqual(result,0)
        self.assertTrue(Host.last.shutdown_called)
        self.assertEqual(Host.last.generator_calls,1)
        self.assertEqual(len(Host.last.sent),1)

class RegistrationTests(unittest.TestCase):
    def test_hidden_component_only(self):
        fake=types.ModuleType('worlds.LauncherComponents')
        fake.components=[]
        fake.Type=types.SimpleNamespace(HIDDEN='hidden')
        def component(name,**kwargs):return types.SimpleNamespace(display_name=name,**kwargs)
        fake.Component=component
        previous=sys.modules.get('worlds.LauncherComponents')
        sys.modules['worlds.LauncherComponents']=fake
        try:
            register_worker();register_worker()
            self.assertEqual(len(fake.components),1)
            self.assertEqual(fake.components[0].display_name,WORKER_COMPONENT)
            self.assertEqual(fake.components[0].component_type,'hidden')
        finally:
            if previous is None:del sys.modules['worlds.LauncherComponents']
            else:sys.modules['worlds.LauncherComponents']=previous

if __name__=='__main__':unittest.main(verbosity=2)
