"""Optional companion bridge DLL transport (LOCAL, SIGNALS.md).

Receives the DLL's LOCAL 4F02 body two ways: as a socket 4F02 frame carrying
the marker (decided before the ordinary pet/companion 4F02 handlers), or from
the owned run directory's ``companion-signal-<seq>.json/.bin`` sink when
``SL_COMPANION_BRIDGE_DIR`` names it. Each decoded signal is resolved to the
authenticated selected owner and handed to the registered
``companion_ui_signal`` subscribers (companion rows, ATS scope). Publications
from those features (``companion_bridge_publish``: map/unmap/model/ats-apply)
go to the DLL through companion_bridge_host; without a host they are kept as
HOST_UNATTACHED records only.

Removing this module leaves the server and the companion feature working; the
pet window keeps its original rows. No other feature's method/state is used.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import re
import struct

from tools.local_entry_server import protobuf as pb
from tools.local_original_session import companion_signals
from tools.local_original_session.world_bridge import need

DIRECTORY_ENV = 'SL_COMPANION_BRIDGE_DIR'
POLL_SECONDS = 0.2
_SIGNAL = re.compile(r'^companion-signal-(\d+)\.json$')
SIGNAL_SCHEMAS = ('companion-native-signal-v1', 'companion-native-item-signal-v2')
READ_ATTEMPTS = 3
PUBLISH_ATTEMPTS = 3
ATS_PENDING_OPERATIONS = ('settings-load', 'ats-select', 'ats-edit-close')


def _bridge_initialize(ctx):
    ctx._bridge_outbox = []
    ctx._bridge_signals = []
    ctx._bridge_errors = []
    ctx._bridge_seen = set()
    ctx._bridge_read_attempts = {}
    ctx._bridge_task = None
    ctx._bridge_host = None
    ctx._bridge_host_error = None
    ctx._bridge_pending = {}
    ctx._bridge_models = {}
    ctx._bridge_model_retried = set()


def _bridge_note(ctx, name, entry, limit=64):
    setattr(ctx, name, (getattr(ctx, name) + [entry])[-limit:])


def _bridge_directory(ctx):
    raw = os.environ.get(DIRECTORY_ENV, '')
    return Path(raw) if raw else None


def _bridge_host(ctx):
    host = getattr(ctx, '_companion_bridge_host', None)  # explicit attach (launcher/tests)
    if host is not None:
        return host
    if ctx._bridge_host is None:
        directory = _bridge_directory(ctx)
        if directory is None or not (directory / 'context.json').exists():
            return None
        try:
            from tools.local_original_session.companion_bridge_host import DirectoryHost
            ctx._bridge_host = DirectoryHost(directory)
        except (OSError, ValueError, KeyError) as error:
            ctx._bridge_host_error = f'{type(error).__name__}: {error}'[:120]
            return None
    return ctx._bridge_host


def _bridge_publish(ctx, uid, kind, payload):
    """companion_bridge_publish subscriber: request JSON or model file + post."""
    member = payload.get('member', payload.get('member_id', 0))
    key = (uid, kind, member, payload.get('event_seq', 0), payload.get('ats_epoch', 0))
    if kind in ('unmap', 'disable'):
        for old in tuple(ctx._bridge_pending):
            if old != key and old[0] == uid and (kind == 'disable' or old[2] == member):
                ctx._bridge_pending.pop(old, None)
        for seq, (owner, model) in tuple(ctx._bridge_models.items()):
            if owner == uid and (kind == 'disable' or model.get('member') == member):
                ctx._bridge_models.pop(seq, None)
        ctx._bridge_model_retried = {view for view in ctx._bridge_model_retried
                                    if not (view[0] == uid and (kind == 'disable' or view[1] == member))}
    elif kind == 'map':
        ctx._bridge_pending.pop((uid, 'unmap', member, 0, 0), None)
    pending = ctx._bridge_pending.get(key)
    if pending is not None and pending['payload'] == payload:
        return False  # only the next tick retries; exhaustion survives repeat saves
    if kind == 'model':
        for seq, (owner, model) in tuple(ctx._bridge_models.items()):
            if owner == uid and model.get('member') == member:
                ctx._bridge_models.pop(seq, None)  # replaced, even while the next post is pending
    pending = dict(uid=uid, kind=kind, payload=dict(payload), attempts=0)
    ctx._bridge_pending[key] = pending
    return _bridge_attempt(ctx, key, pending)


def _bridge_attempt(ctx, key, pending):
    uid, kind, payload = pending['uid'], pending['kind'], pending['payload']
    pending['attempts'] += 1
    host = _bridge_host(ctx)
    entry = dict(kind=kind, owner=uid, status='HOST_UNATTACHED', attempt=pending['attempts'])
    if kind == 'model':
        entry.update(member=payload.get('member'), revision=payload.get('revision'),
                     frame=payload['frame'])
    else:
        entry.update(request=dict(payload))
    if host is not None:
        try:
            if kind == 'model' and any(k[0] == uid and k[1] == 'map' and k[2] == payload.get('member')
                                       for k in ctx._bridge_pending):
                entry.update(status='POST_FAILED', stage='map')
                _bridge_note(ctx, '_bridge_outbox', entry, 32)
                return False
            if not getattr(host, 'installed', True):
                seq, posted = host.publish_request(dict(command='install'))
                host.installed = bool(posted)
                _bridge_note(ctx, '_bridge_outbox', dict(kind='install', owner=uid, seq=seq,
                             status='POSTED' if posted else 'POST_FAILED'), 32)
                if not posted:
                    entry.update(status='POST_FAILED', stage='install')
                    _bridge_note(ctx, '_bridge_outbox', entry, 32)
                    return False
            seq, posted = (host.publish_model(payload['frame']) if kind == 'model'
                           else host.publish_request(payload))
            entry.update(seq=seq, status='POSTED' if posted else 'POST_FAILED')
            if posted:
                ctx._bridge_pending.pop(key, None)
                if kind == 'model':
                    ctx._bridge_models[seq] = (uid, payload)
                ctx.run_sync_hooks('companion_bridge_posted', uid, kind, payload)
        except (OSError, ValueError) as error:
            entry.update(status='PUBLISH_FAILED', error=f'{type(error).__name__}: {error}'[:120])
    _bridge_note(ctx, '_bridge_outbox', entry, 32)
    return entry['status'] == 'POSTED'


def _bridge_tick(ctx, now):
    for key, pending in tuple(ctx._bridge_pending.items()):
        if pending['attempts'] < PUBLISH_ATTEMPTS:
            _bridge_attempt(ctx, key, pending)
    host = _bridge_host(ctx)
    if host is None or not hasattr(host, 'read_model_failures'):
        return
    for seq in host.read_model_failures():
        publication = ctx._bridge_models.pop(seq, None)
        if publication is None:
            continue
        uid, payload = publication
        view = (uid, payload.get('member'), tuple(payload.get('view_epochs', ())))
        if view in ctx._bridge_model_retried:
            continue
        ctx._bridge_model_retried.add(view)
        ctx.run_sync_hooks('companion_bridge_model_failed', uid, payload)


def _bridge_started(ctx):
    ctx.world.runtime.add_tick_hook(lambda now: _bridge_tick(ctx, now))


def _bridge_dispatch(ctx, writer, uid, signal, meta):
    """Under the world lock: first subscriber result wins; refusals recorded."""
    try:
        results = [r for r in ctx.collect_sync_hooks('companion_ui_signal', writer, uid, signal, meta)
                   if r is not None]
        result = results[0] if results else dict(status='UNHANDLED')
    except ValueError as error:
        result = dict(status='REFUSED', error=str(error)[:96])
    except Exception as error:
        if signal.operation not in ATS_PENDING_OPERATIONS:
            raise  # item transfer partial/commit failures keep their existing semantics
        result = dict(status='FAILED', error=f'{type(error).__name__}: {error}'[:96])
    if result.get('status') in ('REFUSED', 'UNHANDLED', 'FAILED', 'REJECTED', 'ERROR'):
        _bridge_refused(ctx, writer, uid, signal, meta, result)
    result = dict(result, operation=signal.operation, actor=signal.actor_uid,
                  transport=meta.get('transport'), event_seq=meta.get('event_seq'))
    _bridge_note(ctx, '_bridge_signals', result)
    return result


def _bridge_refused(ctx, writer, uid, signal, meta, result):
    """Let the owning feature undo pending UI state through its registered hook."""
    if not result.get('feedback_sent'):
        ctx.run_sync_hooks('companion_ui_refused', writer, uid, signal, meta, result)
    if signal.operation in ATS_PENDING_OPERATIONS and not result.get('feedback_sent'):
        # The ATS feature may be disabled/excluded. Cancellation belongs to the
        # transport too: the DLL is waiting for this exact event/epoch.
        request = dict(command='ats-cancel', event_seq=meta.get('event_seq', 0),
                       ats_epoch=meta.get('ats_epoch', 0))
        ctx.run_sync_hooks('companion_bridge_publish', uid or 0, 'ats-cancel', request)
        if uid is not None:
            text = ('현재 자동 사냥 동료 설정 기능을 사용할 수 없습니다.'
                    if result.get('status') == 'UNHANDLED' else
                    '자동 사냥 설정 요청을 처리할 수 없습니다. 창을 다시 열어 주세요.')
            _bridge_notice(ctx, uid, text)
        result['feedback_sent'] = True
    if uid is None or not signal.operation.startswith('item-'):
        return
    reason = result.get('reason') or result.get('error', '')
    messages = {
        'COMPANION_GIVE_UNEQUIP_FIRST': '주인에게 장착된 아이템은 먼저 장착을 해제한 뒤 동료에게 주세요.',
        'COMPANION_TAKE_UNEQUIP_FIRST': '동료에게 장착된 아이템은 먼저 장착을 해제한 뒤 가져오세요.',
        'COMPANION_GIVE_OWNED_QUANTITY_REQUIRED': '줄 아이템이 없거나 수량이 부족합니다.',
        'COMPANION_TAKE_OWNED_QUANTITY_REQUIRED': '가져올 아이템이 없거나 수량이 부족합니다.',
        'COMPANION_GIVE_NONSTACK_QUANTITY': '겹칠 수 없는 아이템은 한 개씩 주세요.',
        'COMPANION_TAKE_NONSTACK_QUANTITY': '겹칠 수 없는 아이템은 한 개씩 가져오세요.',
        'COMPANION_WEIGHT_CAPACITY': '동료가 무거워서 아이템을 더 받을 수 없습니다.',
        'COMPANION_TAKE_OWNER_WEIGHT_CAPACITY': '소지 무게가 초과되어 아이템을 가져올 수 없습니다.',
        'COMPANION_CLASS_CANNOT_EQUIP': '동료의 직업으로는 이 아이템을 장착할 수 없습니다.',
        'EQUIPMENT_TWO_HANDED_SHIELD_CONFLICT': '양손 무기와 방패는 동시에 장착할 수 없습니다. 먼저 장착을 해제해 주세요.',
        'EQUIPMENT_HANDEDNESS_UNKNOWN': '이 무기의 양손 착용 정보가 확인되지 않아 방패와 함께 장착할 수 없습니다.',
        'ITEM_USE_CURSED_EQUIPMENT_CANNOT_REMOVE': '저주받은 장비는 장착을 해제하거나 교체할 수 없습니다.',
        'COMPANION_EQUIPPABLE_ITEM_REQUIRED': '장착할 수 없는 아이템입니다.',
        'COMPANION_EQUIP_OWNED_ITEM_REQUIRED': '장착할 아이템이 동료의 가방에 없습니다.',
        'COMPANION_UNEQUIP_SLOT_MISMATCH': '장착 정보가 바뀌었습니다. 장비 창을 다시 열어 주세요.',
        'COMPANION_TRANSFER_RECOVERY_REQUIRED': '이전 아이템 이동을 복구 중입니다. 잠시 후 다시 시도해 주세요.',
        'COMPANION_SIGNAL_CURRENT_ACTOR_REQUIRED': '동료가 현재 소환되어 있지 않습니다.',
        'COMPANION_LIVING_ACTOR_REQUIRED': '동료가 사망한 상태에서는 아이템을 옮기거나 장착할 수 없습니다.',
        'COMPANION_MEMBER_SELECTED': '접속 중인 캐릭터의 아이템은 변경할 수 없습니다.',
        'COMPANION_SIGNAL_MEMBER_GENERATION_MISMATCH': '동료 정보가 바뀌었습니다. 창을 다시 열어 주세요.',
        'COMPANION_SIGNAL_VIEW_EPOCH_MISMATCH': '이전 동료 창의 요청입니다. 현재 창에서 다시 시도해 주세요.',
        'COMPANION_GIVE_KNOWN_ITEM_REQUIRED': '동료에게 줄 수 없는 아이템입니다.',
        'COMPANION_TAKE_KNOWN_ITEM_REQUIRED': '가져올 수 없는 아이템입니다.',
    }
    text = messages.get(reason, '동료 아이템 요청을 처리할 수 없습니다. 창을 다시 열어 주세요.')
    _bridge_notice(ctx, uid, text)


def _bridge_notice(ctx, uid, text):
    body = pb.encode_uint32(1, 12066) + pb.encode_bytes(2, text.encode('utf-8'))
    ctx.world._queue(uid, struct.pack('<HH', len(body) + 6, 0x4EEA) + body + b'\0\0')
    ctx.world._announce()


async def _bridge_frame(ctx, writer, row, game, frame, operation_lock):
    """Socket 4F02: LOCAL marker bodies are owned here and never fall through."""
    if not ctx._world_bound(writer) or ctx._world_ready(writer, game) is None:
        return False
    try:
        signal = companion_signals.decode_signal(bytes(frame.payload))
    except companion_signals.SignalError as error:
        if companion_signals.MARKER.encode() not in bytes(frame.payload):
            return False  # not ours: the ordinary path judges a malformed pet body
        _bridge_note(ctx, '_bridge_errors', dict(transport='SOCKET', error=str(error)[:96]), 16)
        return True
    if signal is None:
        return False
    uid = ctx._world_pcs[id(writer)][1]
    meta = dict(transport='SOCKET', event_seq=0, ats_epoch=0)

    def apply():
        need(ctx.realm.registry.resolve(writer) is game and ctx._world_bound(writer),
             'COMPANION_BRIDGE_CURRENT_OWNER_REQUIRED')
        _bridge_dispatch(ctx, writer, uid, signal, meta)
        return ctx.world.drain(uid)
    frames = await ctx.world.runtime.dispatch_now(apply)
    await ctx._world_send(writer, row, frames, operation_lock)
    return True


def _bridge_writer_for(ctx, signal):
    bound = list(ctx._world_pcs.values())
    if signal.actor_uid:
        for writer, uid in bound:
            manager = getattr(ctx.world, 'companions', None)
            if any(rt.owner_ref.uid == uid and rt.ref.uid & 0xFFFFFFFF == signal.actor_uid
                   for rt in (manager.active.values() if manager is not None else ())):
                return writer, uid
        return None
    return bound[0] if len(bound) == 1 else None


async def _bridge_ingest(ctx, directory):
    """Consume new signal files in sequence order (opt-in file IPC sink)."""
    try:
        names = sorted(((int(m.group(1)), name) for name in os.listdir(directory)
                        if (m := _SIGNAL.match(name))), key=lambda item: item[0])
    except OSError:
        return 0
    host = _bridge_host(ctx)
    handled = 0
    for seq, name in names:
        if seq in ctx._bridge_seen:
            continue
        path = directory / name
        try:
            meta = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            _bridge_read_failed(ctx, seq, error)
            continue
        try:
            need(isinstance(meta, dict), 'COMPANION_BRIDGE_SIGNAL_SCHEMA')
            need(meta.get('schema') in SIGNAL_SCHEMAS and meta.get('transport') == 'LOCAL_IPC',
                 'COMPANION_BRIDGE_SIGNAL_SCHEMA')
            if host is not None:
                need(meta.get('pid') == host.identity['pid'] and meta.get('birth') == host.identity['birth'],
                     'COMPANION_BRIDGE_SIGNAL_IDENTITY')
            body_name = str(meta.get('body_file', ''))
            need(re.fullmatch(r'companion-signal-\d+\.bin', Path(body_name).name) is not None,
                 'COMPANION_BRIDGE_SIGNAL_BODY')
            info = dict(transport='LOCAL_IPC', event_seq=int(meta.get('event_seq', seq) or 0),
                        ats_epoch=int(meta.get('ats_epoch', 0) or 0),
                        view_epoch=int(meta.get('view_epoch', 0) or 0), seq=seq)
            if meta.get('operation') == 'pet-window-open':
                # The DLL already emits this mapped identity. Only this
                # operation consumes it; ordinary ATS/item signals are unchanged.
                for key in ('native_actor_uid', 'actor_generation', 'owner_uid', 'member_id'):
                    info[key] = meta.get(key)
            need(all(0 <= info[key] < 1 << 64 for key in ('event_seq', 'ats_epoch', 'view_epoch')),
                 'COMPANION_BRIDGE_SIGNAL_EVENT')
        except (ValueError, TypeError) as error:
            ctx._bridge_seen.add(seq)
            ctx._bridge_read_attempts.pop(seq, None)
            _bridge_note(ctx, '_bridge_errors', dict(transport='LOCAL_IPC', seq=seq,
                                                     error=str(error)[:96]), 16)
            continue
        try:
            body = (directory / Path(body_name).name).read_bytes()
        except OSError as error:
            _bridge_read_failed(ctx, seq, error)
            continue
        # Decode/schema/identity failures are permanent. Never replay a decoded
        # operation after dispatch, even if its handler or cleanup fails.
        ctx._bridge_seen.add(seq)
        ctx._bridge_read_attempts.pop(seq, None)
        try:
            signal = companion_signals.decode_signal(body)
            need(signal is not None, 'COMPANION_BRIDGE_SIGNAL_MARKER')
        except ValueError as error:
            _bridge_note(ctx, '_bridge_errors', dict(transport='LOCAL_IPC', seq=seq,
                                                     error=str(error)[:96]), 16)
            continue
        target = _bridge_writer_for(ctx, signal)
        if target is None:
            def refuse():
                bound = list(ctx._world_pcs.values())
                writer, uid = bound[0] if len(bound) == 1 else (None, None)
                result = dict(status='NO_OWNER', operation=signal.operation, transport='LOCAL_IPC',
                              seq=seq, event_seq=info['event_seq'], ats_epoch=info['ats_epoch'])
                _bridge_refused(ctx, writer, uid, signal, info, result)
                _bridge_note(ctx, '_bridge_signals', result)
            await ctx.world.runtime.dispatch_now(refuse)
            continue
        writer, uid = target
        result = await ctx.world.runtime.dispatch_now(_bridge_dispatch, ctx, writer, uid, signal, info)
        if signal.operation == 'pet-window-open' and result.get('status') == 'OK':
            # Reuse the authenticated writer's ordinary serialized send path.
            # A queued response alone must not admit legacy 4F02 menu commands.
            row = next((row for rows in ctx._claims.values() for row in rows
                        if row['writer'] is writer), None)
            if row is not None:
                async with row['operation_lock']:
                    game = ctx.realm.registry.resolve(writer)
                    if (ctx._world_bound(writer) and ctx._world_ready(writer, game) is not None
                            and ctx.owner_current(writer, row, ctx.realm.service(writer).snapshot())):
                        await ctx._world_flush(writer, row, game, row['operation_lock'])
                        await ctx.world.runtime.dispatch_now(ctx.run_sync_hooks,
                            'companion_ui_delivered', writer, uid, signal, info)
        handled += 1
        for consumed in (path, directory / Path(meta['body_file']).name):
            try:
                consumed.unlink()
            except OSError:
                pass  # still recorded as seen; never replayed in this process
    return handled


def _bridge_read_failed(ctx, seq, error):
    attempts = ctx._bridge_read_attempts.get(seq, 0) + 1
    terminal = attempts >= READ_ATTEMPTS
    if terminal:
        ctx._bridge_seen.add(seq)
        ctx._bridge_read_attempts.pop(seq, None)
    else:
        ctx._bridge_read_attempts[seq] = attempts
    _bridge_note(ctx, '_bridge_errors', dict(transport='LOCAL_IPC', seq=seq, attempt=attempts,
                 terminal=terminal, error=f'{type(error).__name__}: {error}'[:96]), 16)


async def _bridge_poll(ctx):
    while True:
        await asyncio.sleep(POLL_SECONDS)
        directory = _bridge_directory(ctx)
        if directory is not None and ctx._world_pcs:
            try:
                await _bridge_ingest(ctx, directory)
            except Exception as error:  # keep the sink alive; report only
                _bridge_note(ctx, '_bridge_errors', dict(transport='LOCAL_IPC',
                             error=f'{type(error).__name__}: {error}'[:96]), 16)


async def _bridge_after_enter(ctx, writer, row, game, operation_lock):
    if _bridge_directory(ctx) is not None and (ctx._bridge_task is None or ctx._bridge_task.done()):
        ctx._bridge_task = asyncio.get_running_loop().create_task(_bridge_poll(ctx),
                                                                  name='companion-bridge-sink')


async def _bridge_stopped(ctx):
    task, ctx._bridge_task = getattr(ctx, '_bridge_task', None), None
    if task is not None:
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass


def _bridge_report(ctx, result):
    result['companion_bridge'] = dict(
        signals=list(ctx._bridge_signals[-16:]), errors=list(ctx._bridge_errors),
        outbox=[{k: v for k, v in e.items() if k != 'frame'} for e in ctx._bridge_outbox[-16:]],
        host_error=ctx._bridge_host_error)


METHODS = (_bridge_initialize, _bridge_publish, _bridge_frame, _bridge_after_enter,
           _bridge_stopped, _bridge_report, _bridge_started)
HOOKS = {'initialize': ('_bridge_initialize',),
         'runtime_started': ('_bridge_started',),
         'companion_bridge_publish': ('_bridge_publish',),
         'after_enter': ('_bridge_after_enter',),
         'runtime_stopped': ('_bridge_stopped',),
         'report': ('_bridge_report',)}
NONCRITICAL_HOOKS = ('report', 'companion_bridge_publish')
FRAMES = {0x4F02: ('_bridge_frame',)}  # companion_signals.OPCODE
FRAME_PRIORITY = -1  # LOCAL marker decided before pet (0), session (10) and companion 4F02
OUTGOING_OPCODES = (0x4EEA,)
