"""Server-configured Universal Tracker, Check Finder publisher, and hint bridge.

TrackerGameContext supplies the actual upstream evaluation. The separate hint
bridge relays server metadata and records only completed progression hints
through the supported AP hint command; it never grants or checks locations.
"""
from __future__ import annotations
import asyncio
import logging
import re
import sys
import time
import uuid
from .TrackerMirror import PROTOCOL, VERSION, TAG, encode_snapshot, snapshot_rows
from .HintBridge import HintBridge
from .TrackerBootstrap import install_slot_data_core
from .AmmoRefillRules import refill_mask, validate_observed_sources


def make_context_class(base):
    # Importing the AP world does not import UT or its GUI. Failure to install
    # tracker.apworld cannot prevent ordinary seed generation or SoH gameplay.
    class SohExtremeTrackerContext(base):
        tags = base.tags | {TAG}

        def __init__(self, *args, **kwargs):
            self._mirror_subscription = None
            self._managed_nonce = None
            self._mirror_producer = uuid.uuid4().hex
            self._mirror_revision = 0
            self._mirror_last_state = None
            self._mirror_last_signature = None
            self._mirror_packet = None
            self._mirror_sender = None
            self._mirror_last_request_time = 0.0
            self._mirror_live_shields = None
            self._mirror_live_time = None
            self._mirror_live_clock = None
            self._mirror_live_time_flags = 0
            self._reset_mirror_ammo()
            super().__init__(*args, **kwargs)
            install_slot_data_core(self)
            self._hint_bridge = HintBridge(self)

        def _reset_mirror_ammo(self):
            self._mirror_live_ammo = None
            self._mirror_live_ammo_owned = 0
            self._mirror_live_rupees = 0
            self._mirror_live_ammo_flags = 0
            self._mirror_live_ammo_state = 0
            self._mirror_live_age = None
            self._mirror_ammo_sources = ()
            self._mirror_ammo_cache = None

        def _reset_tracker_generation(self):
            # Connection loss can call CommonClient.reset_server_state without
            # calling UT.disconnect. Never keep a previous slot's world or
            # watcher alive while waiting for another Connected snapshot.
            watcher = getattr(self, "watcher_task", None)
            if watcher is not None and not watcher.done():
                watcher.cancel()
            self.watcher_task = None
            sender = getattr(self, "_mirror_sender", None)
            if sender is not None and not sender.done():
                sender.cancel()
            self._mirror_sender = None
            core = getattr(self, "tracker_core", None)
            if core is not None:
                core.disconnect()

        def reset_server_state(self):
            self._reset_tracker_generation()
            self._mirror_subscription = None
            self._mirror_last_state = None
            self._mirror_last_signature = None
            self._mirror_packet = None
            self._mirror_live_shields = None
            self._mirror_live_time = None
            self._mirror_live_clock = None
            self._mirror_live_time_flags = 0
            self._reset_mirror_ammo()
            if hasattr(self, "_hint_bridge"):
                self._hint_bridge.reset()
            super().reset_server_state()

        def run_generator(self):
            # The per-context bootstrap only initializes display settings here.
            # Actual UT generation starts once Connected supplies this slot's
            # resolved options, starting inventory, and entrance destinations.
            self.tracker_core.run_generator(None, None)
            self.use_split = self.tracker_core.use_split

        def make_gui(self):
            gui=super().make_gui()
            gui.base_title='SOH-EXTREME Universal Tracker '+VERSION+' for AP version'
            return gui

        def on_package(self, cmd, args):
            # CommonClient has already decoded the packet and updated its
            # authoritative metadata. Hints do not depend on UT evaluation.
            self._hint_bridge.on_package(cmd, args)
            if cmd in ('RoomInfo','Connected','ConnectionRefused'):
                self._reset_tracker_generation()
                self._mirror_subscription=None
                self._mirror_last_state=None
                self._mirror_last_signature=None
                self._mirror_packet=None
                self._mirror_live_shields=None
                self._mirror_live_time=None
                self._mirror_live_clock=None
                self._mirror_live_time_flags=0
                self._reset_mirror_ammo()
            super().on_package(cmd,args)
            if cmd != 'Bounced' or self.game != 'SOH-EXTREME':return
            data=args.get('data')
            if not isinstance(data,dict) or data.get('soh_extreme_tracker') != PROTOCOL:return
            if data.get('kind') in ('hint_request', 'hint_reveal'):
                self._hint_bridge.on_bounce(data)
                return
            if data.get('kind') != 'request' or data.get('slot') != self.slot:return
            nonce=data.get('nonce');request=data.get('request')
            if not isinstance(nonce,str) or not re.fullmatch(r'[a-f0-9]{32}',nonce):return
            if self._managed_nonce is not None and nonce != self._managed_nonce:return
            if type(request) is not int or not 0 < request <= 0xffffffffffffffff:return
            shields=data.get('live_shields')
            phase=data.get('live_time')
            clock=data.get('live_clock')
            time_flags=data.get('live_time_flags',0)
            if clock is not None and (type(clock) is not int or not 0 <= clock <= 0xffff or phase is None):return
            if type(time_flags) is not int or time_flags not in (0,1):return
            if phase is not None and (type(phase) is not int or phase not in (0,1)):return
            if self._managed_nonce is not None and (type(shields) is not int or not 0 <= shields <= 3):return
            ammo = None
            owned = rupees = ammo_flags = ammo_state = 0
            live_age = None
            sources = ()
            if data.get('ammo_protocol') is not None:
                if type(data.get('ammo_protocol')) is not int or data['ammo_protocol'] != 1:return
                # Only the game-owned process may assert live save inventory.
                if self._managed_nonce is None or clock is None:return
                ammo, owned = data.get('live_ammo'), data.get('live_ammo_owned')
                rupees, ammo_flags = data.get('live_rupees'), data.get('live_ammo_flags')
                ammo_state = data.get('live_ammo_state')
                live_age = data.get('live_age')
                if type(live_age) is not int or live_age not in (1, 2):return
                if type(ammo) is not int or not 0 <= ammo <= 31:return
                if type(owned) is not int or not 0 <= owned <= 31 or ammo & ~owned:return
                if type(rupees) is not int or not 0 <= rupees <= 0xffff:return
                if type(ammo_flags) is not int or not 0 <= ammo_flags <= 3:return
                if type(ammo_state) is not int or not 0 < ammo_state <= 0xffffffffffffffff:return
                try:sources = validate_observed_sources(data.get('ammo_sources', []))
                except ValueError:return
            now=time.monotonic()
            if now-self._mirror_last_request_time < 0.1:return
            self._mirror_last_request_time=now
            sub=self._mirror_subscription
            if sub and sub[0]==nonce and request<sub[1]:return
            self._mirror_subscription=(nonce,request)
            self._hint_bridge.on_bounce(data)
            # Only the game-owned worker accepts live equipment. Standalone UT
            # continues to show generation logic, including planned purchases.
            self._mirror_live_shields=shields if self._managed_nonce is not None else None
            self._mirror_live_time=phase if self._managed_nonce is not None else None
            self._mirror_live_clock=clock if self._managed_nonce is not None else None
            self._mirror_live_time_flags=time_flags if self._managed_nonce is not None else 0
            self._mirror_live_ammo = ammo
            self._mirror_live_ammo_owned = owned
            self._mirror_live_rupees = rupees
            self._mirror_live_ammo_flags = ammo_flags
            self._mirror_live_ammo_state = ammo_state
            self._mirror_live_age = live_age
            self._mirror_ammo_sources = sources
            # Re-evaluate using UT itself on a game request. This also handles
            # snapshots requested before the first ReceivedItems update.
            self.updateTracker()

        def updateTracker(self):
            world=self.tracker_core.get_current_world()
            if world is None and getattr(self.tracker_core, "_soh_slot_data_bootstrap", False):
                # GUI refreshes and requests may arrive before Connected. Keep
                # the waiting/slot-error page instead of UT's generic YAML
                # advice; no availability can be published without a world.
                result = self.tracker_core.updateTracker()
                self._mirror_last_state = result
                return result
            if world is not None:
                # UT builds a fresh CollectionState on every update, so removing
                # a shield also removes routes/events previously opened by it.
                world._extreme_live_shields=self._mirror_live_shields
                world._extreme_live_time=self._mirror_live_time
                world._extreme_live_clock=self._mirror_live_clock
                world._extreme_live_time_flags=self._mirror_live_time_flags
                world._extreme_live_ammo=self._mirror_live_ammo
            result=super().updateTracker()
            self._mirror_last_state=result
            if self._mirror_subscription and getattr(result,'state',None) is not None:
                self._publish_mirror(result)
            return result

        def _publish_mirror(self, result):
            if self.game!='SOH-EXTREME' or self.slot is None:return
            world=self.tracker_core.get_current_world()
            if world is None:return
            try:
                active=set(self.server_locations)
                checked=set(self.checked_locations) & active
                rows=snapshot_rows(self.tracker_core,result,world,active,checked)
                nonce,request=self._mirror_subscription
                self._mirror_revision+=1
                received=len(self.tracker_items_received)
                manual_count = len(self.tracker_core.manual_items)
                ignored_count = len(self.tracker_core.ignored_locations)
                refills = 0
                if self._mirror_live_ammo is not None and manual_count == 0 and ignored_count == 0:
                    # UT's rebuilt state and the same exact AP entrance graph
                    # supply refill reachability, even with the Finder closed.
                    # Cache by the native inventory/rupee/source token and all
                    # server facts which can change that proof.
                    clock = self._mirror_live_clock
                    clock_window = ((1 if 0x4555 <= clock < 0x5000 else 0)
                                    | (2 if 0xC000 < clock < 0xE000 else 0)
                                    | (4 if clock <= 0x3555 or clock > 0xD556 else 0)
                                    | (8 if 0x4555 <= clock < 0xB889 else 0))
                    key = (id(world), received, tuple(sorted(checked)),
                           self._mirror_live_ammo_state, self._mirror_live_time,
                           clock_window, self._mirror_live_time_flags, self._mirror_live_age,
                           self._mirror_ammo_sources)
                    if self._mirror_ammo_cache is not None and self._mirror_ammo_cache[0] == key:
                        refills = self._mirror_ammo_cache[1]
                    else:
                        try:
                            refills = refill_mask(world, result.state,
                                live_ammo=self._mirror_live_ammo, owned=self._mirror_live_ammo_owned,
                                rupees=self._mirror_live_rupees, flags=self._mirror_live_ammo_flags,
                                checked=checked, observed=self._mirror_ammo_sources, live_age=self._mirror_live_age)
                        except Exception:
                            # A failed source proof must leave gameplay protected
                            # and must not take down the ordinary Finder result.
                            logging.getLogger('Client').exception('SOH-EXTREME refill proof unavailable')
                            refills = 0
                        self._mirror_ammo_cache = (key, refills)
                else:
                    self._mirror_ammo_cache = None
                payload=encode_snapshot(nonce=nonce,request=request,revision=self._mirror_revision,
                    slot=self.slot,producer=self._mirror_producer,received=received,
                    active=active,checked=checked,rows=rows,
                    manual_count=manual_count,
                    ignored_count=ignored_count,
                    live_shields=self._mirror_live_shields,live_time=self._mirror_live_time,
                    live_clock=self._mirror_live_clock,live_time_flags=self._mirror_live_time_flags,
                    live_ammo=self._mirror_live_ammo, live_ammo_owned=self._mirror_live_ammo_owned,
                    live_rupees=self._mirror_live_rupees, live_ammo_flags=self._mirror_live_ammo_flags,
                    live_ammo_state=self._mirror_live_ammo_state, ammo_refills=refills)
            except (ValueError,KeyError,AttributeError,TypeError):
                logging.getLogger('Client').exception('SOH-EXTREME tracker mirror rejected an invalid snapshot')
                return
            # A single sender coalesces bursts from receipts/hints and prevents
            # old queued snapshots from overtaking new ones.
            self._mirror_packet={'cmd':'Bounce','slots':[self.slot],
                'data':{'soh_extreme_tracker':PROTOCOL,'kind':'snapshot','nonce':nonce,'payload':payload}}
            if self._mirror_sender is None or self._mirror_sender.done():
                self._mirror_sender=asyncio.create_task(self._send_mirror(),name='SOH tracker mirror')

        async def _send_mirror(self):
            try:
                while self._mirror_packet is not None:
                    packet=self._mirror_packet;self._mirror_packet=None
                    await self.send_msgs([packet])
            except Exception:
                logging.getLogger('Client').exception('SOH-EXTREME tracker mirror send failed')

        async def disconnect(self, allow_autoreconnect=False):
            await self._hint_bridge.close()
            self._mirror_subscription=None
            self._mirror_live_shields=None
            self._mirror_live_time=None
            self._mirror_live_clock=None
            self._mirror_live_time_flags=0
            self._reset_mirror_ammo()
            world=self.tracker_core.get_current_world()
            if world is not None:world._extreme_live_shields=None
            if world is not None:
                world._extreme_live_time=None
                world._extreme_live_clock=None
                world._extreme_live_time_flags=0
                world._extreme_live_ammo=None
            self._mirror_packet=None
            self._mirror_last_state=None
            if self._mirror_sender is not None and not self._mirror_sender.done():
                self._mirror_sender.cancel()
            await super().disconnect(allow_autoreconnect)

        async def shutdown(self):
            await self._hint_bridge.close()
            await super().shutdown()
    return SohExtremeTrackerContext


async def _main(args, ut):
    context_type=make_context_class(ut.TrackerGameContext)
    ctx=context_type(args.connect,args.password,print_count=False,print_list=False)
    ctx.auth=args.name
    ctx.server_task=asyncio.create_task(ut.server_loop(ctx),name='server loop')
    try:
        ctx.run_generator()
        if ut.gui_enabled and not getattr(args, "nogui", False):ctx.run_gui()
        ctx.run_cli()
        await ctx.exit_event.wait()
    finally:
        await ctx.shutdown()


def run(*args):
    try:
        from worlds.tracker import TrackerClient as ut
    except ImportError as e:
        from Utils import messagebox
        messagebox('Universal Tracker required',
            'Install tracker.apworld alongside soh_extreme.apworld, then restart Archipelago Launcher.\n'
            'SOH-EXTREME uses Universal Tracker itself; no alternate logic engine is bundled here.',error=True)
        raise RuntimeError('Universal Tracker is not available') from e
    parser=ut.get_base_parser(description='SOH-EXTREME Universal Tracker and in-game Check Finder')
    parser.add_argument('--name',default=None,help='Archipelago slot name')
    parser.add_argument('url',nargs='?',help='Archipelago connection URL')
    parsed=ut.handle_url_arg(parser.parse_args(list(args)))
    asyncio.run(_main(parsed,ut))


def launch(*args):
    from worlds.LauncherComponents import launch as launch_component
    launch_component(run,'SOH-EXTREME Universal Tracker',args)


def register_launcher():
    from .TrackerWorker import register_worker
    register_worker()

if __name__=='__main__':run(*sys.argv[1:])
