"""Read-only UT result publisher used by the game-owned, windowless host.

TrackerGameContext supplies the actual upstream evaluation. This module only
encodes its result, pins requests to the owning game and coalesces replies.
"""
from __future__ import annotations
import asyncio
import logging
import re
import sys
import time
import uuid
from .TrackerMirror import PROTOCOL, VERSION, TAG, encode_snapshot, snapshot_rows


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
            super().__init__(*args, **kwargs)

        def make_gui(self):
            gui=super().make_gui()
            gui.base_title='SOH-EXTREME Universal Tracker '+VERSION+' for AP version'
            return gui

        def on_package(self, cmd, args):
            if cmd in ('RoomInfo','Connected','ConnectionRefused'):
                self._mirror_subscription=None
                self._mirror_last_state=None
                self._mirror_last_signature=None
                self._mirror_packet=None
            super().on_package(cmd,args)
            if cmd != 'Bounced' or self.game != 'SOH-EXTREME':return
            data=args.get('data')
            if not isinstance(data,dict) or data.get('soh_extreme_tracker') != PROTOCOL:return
            if data.get('kind') != 'request' or data.get('slot') != self.slot:return
            nonce=data.get('nonce');request=data.get('request')
            if not isinstance(nonce,str) or not re.fullmatch(r'[a-f0-9]{32}',nonce):return
            if self._managed_nonce is not None and nonce != self._managed_nonce:return
            if type(request) is not int or not 0 < request <= 0xffffffffffffffff:return
            now=time.monotonic()
            if now-self._mirror_last_request_time < 0.1:return
            self._mirror_last_request_time=now
            sub=self._mirror_subscription
            if sub and sub[0]==nonce and request<sub[1]:return
            self._mirror_subscription=(nonce,request)
            # Re-evaluate using UT itself on a game request. This also handles
            # snapshots requested before the first ReceivedItems update.
            self.updateTracker()

        def updateTracker(self):
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
                payload=encode_snapshot(nonce=nonce,request=request,revision=self._mirror_revision,
                    slot=self.slot,producer=self._mirror_producer,received=received,
                    active=active,checked=checked,rows=rows,
                    manual_count=len(self.tracker_core.manual_items),
                    ignored_count=len(self.tracker_core.ignored_locations))
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
            self._mirror_subscription=None
            self._mirror_packet=None
            self._mirror_last_state=None
            if self._mirror_sender is not None and not self._mirror_sender.done():
                self._mirror_sender.cancel()
            await super().disconnect(allow_autoreconnect)
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
