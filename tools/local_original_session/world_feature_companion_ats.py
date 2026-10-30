"""Optional ATS "나/동료" scope for the same saved character (LOCAL).

Design: game-core-prep/ATS_COMPANION_TOGGLE_DESIGN.md. Per permanent character
two ATSConfig wrappers are kept: ``self`` (direct play) and ``companion``
(this character acting as somebody's companion), plus the latest SELF
CharacterConfig wrapper (4ED6 f1). On the DLL's ``ats-select`` signal the
server supplies a full 4ED7 (hex SELF f1, hex chosen-scope f2) and publishes
``ats-apply`` with the same event/epoch. A 4ED6 Save while the companion scope
is shown stores its f2 as the companion setting; the account sidecar still
receives SELF f1 + SELF f2, so the companion value never leaks into it.

The saved companion setting becomes the member's AI policy through the
``companion_ai_policy`` fold (ats_config_codec.companion_policy). Removing
this module leaves ordinary settings saving and the companion default AI.

2차 (design 6장): the owner (e.g. a knight) edits a summoned member's
companion setting from the pet window "동료 설정" (``settings-load``). The
owner's own ATSConfig is kept aside (never written while editing), the
member's companion setting is sent as full 4ED7 (member f1 + member f2).
First edits clone the owner's f1 with inventory shortcut links emptied.
The owner's spell window temporarily lists the member's learned spells
(4E60 upsert/erase). A 4ED6 during the edit stores its f1/f2 as the member's
companion setting; the owner's row and account sidecar remain unchanged.
``ats-edit-close`` sends the owner's original 4ED7/4E60 back. Until the
DLL reports ``ats-edit-restored`` (or the client echoes the owner's own f2) a
late 4ED6 still counts as the member's. The edit is memory only: a
disconnect leaves the owner's saved setting as it was, and the next world
entry of that owner erases the member-only spells again (4E60 f2=false), since
the same client process keeps its spell map across reselection (the pending
erase is kept in the owner's ats-scopes row). While an edit
is open the ATS start request (4F36, Play) is consumed with a notice only: the
owner must not auto-hunt with the member's setting.

The independent ``ats-window-open/save`` path has its own memory-only edit
epoch and JSON view/delta/result files in the existing owned bridge directory.
It reads and patches only the member's companion_ats wrapper and never loads
or saves a native ATS model, owner wrapper, spell list, or account sidecar.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import struct
import tempfile
import time
from types import SimpleNamespace

from tools.local_entry_server import protobuf as pb
from tools.local_original_session import ats_config_codec as codec
from tools.local_original_session.world_bridge import need

SETTINGS_OPCODE = 0x4ED6
NOTI_OPCODE = 0x4ED7
SPELL_LIST_OPCODE = 0x4E60
NOTICE_OPCODE = 0x4EEA
ATS_START_OPCODE = 0x4F36  # CS_START_ATS_REQ (ATS_COMPANION_EVIDENCE.md)
EDIT_OPERATIONS = ('settings-load', 'ats-edit-close', 'ats-edit-restored')


def _ats_initialize(ctx):
    ctx._ats_scope = {}      # id(writer) -> 'self' | 'companion'
    ctx._ats_edit = {}       # id(writer) -> owner editing a member (2차, memory only)
    ctx._ats_events = []
    ctx._ats_policies = {}   # character id -> normalized policy (cache)
    ctx._ats_window_edits = {}  # independent JSON window; never replaces native ATS state
    ctx._ats_window_epoch = time.time_ns()
    ctx._ats_window_ui = {}
    # Same opt-in and profile restriction as the companion feature.
    ctx._ats_enabled = (os.environ.get('SL_COMPANION') == '1'
                        and 'manual-user-play' not in str(ctx.realm.store.path).lower())
    ctx._ats_store = {'schema': 1, 'characters': {}}
    if not ctx._ats_enabled:
        return
    # Fixed-client spell UI configuration is display metadata. Load it once;
    # an absent source leaves unsupported rows UNKNOWN instead of guessing icons.
    ui_path = Path(__file__).resolve().parents[2] / 'work/all_table_semantics/spell_token/spell-ui-joins.json'
    try:
        ui_rows = json.loads(ui_path.read_text(encoding='utf-8'))
        for ui in ui_rows:
            key, named = ui.get('spell_id'), ui.get('named_UI_configuration') or {}
            if (type(key) is int and key >= 0 and named.get('id') == key
                    and type(named.get('icon')) is int and isinstance(ui.get('name_KR'), str)
                    and key not in ctx._ats_window_ui):
                ctx._ats_window_ui[key] = dict(spell_row=key, name=ui['name_KR'], icon=named['icon'])
    except (OSError, ValueError, TypeError) as error:
        _ats_note(ctx, dict(event='window-ui-unknown', reason=str(error)[:96]))
    path = Path(ctx.realm.store.path).with_name('ats-scopes.json')
    ctx._ats_path = path
    if path.exists():
        payload = json.loads(path.read_text(encoding='utf-8'))
        need(payload.get('schema') == 1 and isinstance(payload.get('characters'), dict),
             'ATS_SCOPE_STORE_INVALID')
        ctx._ats_store = payload


def _ats_spell_entries(ctx):
    magic = getattr(ctx, '_world_magic', None)
    catalog = getattr(magic, 'catalog', None)
    spells = catalog if isinstance(catalog, dict) else getattr(ctx, '_companion_spells', None)
    if not spells:
        from tools.local_original_session.world_companion_classes import load_definitions
        spells = next(d.spells for d in load_definitions().classes.values() if d.spells.get('spells'))
    return spells['spells']


def _ats_spell_keys(ctx):
    return {s['classic_key']['value']: s['id'] for s in _ats_spell_entries(ctx)
            if isinstance(s.get('classic_key'), dict)}


def _ats_row(ctx, character_id):
    return ctx._ats_store['characters'].setdefault(str(character_id), {})


def _ats_save_store(ctx):
    from tools.local_original_session.world_companion import replace_file
    raw = json.dumps(ctx._ats_store, ensure_ascii=False, indent=2) + '\n'
    temporary = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=ctx._ats_path.parent,
                prefix=ctx._ats_path.name + '.', suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        replace_file(temporary, ctx._ats_path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def _ats_note(ctx, entry):
    ctx._ats_events = (ctx._ats_events + [entry])[-32:]


def _ats_fields(payload):
    with pb.parse_message(payload, schema={1: 2, 2: 2}, limits=pb.WireLimits()) as message:
        first = [bytes(f.value) for f in message.occurrences(1)]
        second = [bytes(f.value) for f in message.occurrences(2)]
    need(first, 'SETTINGS_REQUIRED_FIELD1')
    return first[-1], (second[-1] if second else None)


def _ats_same(left, right):
    """Same ATSConfig content (wrapper compression may differ)."""
    if left is None or right is None:
        return False
    try:
        # The loader rewrites unresolved item slot f5/f6 (loadable_ats), so an
        # echo differs from the stored bytes only there.
        return (codec.unwrap_blob(codec.loadable_ats(left))
                == codec.unwrap_blob(codec.loadable_ats(right)))
    except ValueError:
        return left == right


def _ats_keep_sidecar(ctx, writer, game, self_config, self_ats):
    """The account sidecar keeps SELF f1 + SELF f2 (when known), never a companion f2."""
    from tools.local_original_session import settings
    store = getattr(ctx.realm, 'settings', None)
    if store is None:
        return
    ctx.realm.bound_account(writer, game)
    body = pb.encode_bytes(1, self_config)
    if self_ats is not None:
        body += pb.encode_bytes(2, self_ats)
    store.save(settings.parse(body))


def _ats_settings_frame(ctx, writer, row, game, frame, operation_lock):
    """Observe each 4ED6; in companion scope keep its f2 out of the SELF save."""
    if not getattr(ctx, '_ats_enabled', False) or not ctx._world_bound(writer):
        return False
    uid = ctx._world_pcs[id(writer)][1]
    edit = getattr(ctx, '_ats_edit', {}).get(id(writer))
    try:
        self_config, ats = _ats_fields(bytes(frame.payload))
    except (ValueError, pb.WireError):
        return edit is not None  # no edit frame may reach the account sidecar
    if edit is not None:
        if ats is None:
            return True  # no f2 to attribute; f1 may still be the member's model
        if _ats_same(ats, edit['owner_ats']):
            # The client holds the owner's own setting (before the member's
            # 4ED7 was parsed, or after the restore): not a companion save.
            if edit['phase'] == 'restoring':
                ctx._ats_edit.pop(id(writer), None)
            return True  # even the restore echo may still carry member f1
        else:
            codec.unwrap_blob(ats)  # refuse a malformed companion setting
            member = edit['member']
            member_data = _ats_row(ctx, member)
            member_data['companion_config'] = self_config.hex()
            member_data['companion_ats'] = ats.hex()
            ctx._ats_policies.pop(member, None)
            _ats_save_store(ctx)
            _ats_note(ctx, dict(event='save', scope='member-edit', character=uid, member=member,
                                phase=edit['phase']))
            return True
    scope = ctx._ats_scope.get(id(writer), 'self')
    data = _ats_row(ctx, uid)
    data['self_config'] = self_config.hex()
    if scope == 'self' or ats is None:
        if ats is not None:
            data['self_ats'] = ats.hex()
        _ats_save_store(ctx)
        _ats_note(ctx, dict(event='save', scope='self', character=uid))
        return False  # ordinary account sidecar save continues unchanged
    codec.unwrap_blob(ats)  # refuse a malformed companion setting
    data['companion_ats'] = ats.hex()
    ctx._ats_policies.pop(uid, None)
    _ats_save_store(ctx)
    _ats_keep_sidecar(ctx, writer, game, self_config,
                      bytes.fromhex(data['self_ats']) if data.get('self_ats') else None)
    _ats_note(ctx, dict(event='save', scope='companion', character=uid))
    return True


async def _ats_frame(ctx, writer, row, game, frame, operation_lock):
    return _ats_settings_frame(ctx, writer, row, game, frame, operation_lock)


def _ats_wire(opcode, body):
    return struct.pack('<HH', len(body) + 6, opcode) + body + b'\0\0'


def _ats_noti(self_config: bytes, ats: bytes) -> bytes:
    body = pb.encode_bytes(1, codec.noti_field(self_config)) + pb.encode_bytes(2, codec.noti_field(codec.loadable_ats(ats)))
    return _ats_wire(NOTI_OPCODE, body)


def _ats_spell_frame(shown, hidden):
    """4E60 SpellInfo rows: f2=true upserts the shown keys, false erases the hidden ones."""
    rows = [(key, 1) for key in sorted(shown)] + [(key, 0) for key in sorted(set(hidden) - set(shown))]
    if not rows:
        return None
    return _ats_wire(SPELL_LIST_OPCODE, b''.join(
        pb.encode_bytes(1, pb.encode_uint32(1, key) + pb.encode_uint32(2, flag)) for key, flag in rows))


def _ats_notice(text):
    body = pb.encode_uint32(1, 12066) + pb.encode_bytes(2, text.encode('utf-8'))
    return _ats_wire(NOTICE_OPCODE, body)


def _ats_select(ctx, uid, scope):
    """Full 4ED7 for the chosen scope of this selected character, or a reason."""
    data = _ats_row(ctx, uid)
    if not data.get('self_config'):
        return None, 'SELF_CHARACTER_CONFIG_UNKNOWN'
    chosen = data.get('companion_ats' if scope == 'companion' else 'self_ats')
    if chosen is None and scope == 'companion':
        chosen = data.get('self_ats')  # first companion edit starts from SELF
    if chosen is None:
        return None, 'SCOPE_ATS_UNKNOWN'
    return _ats_noti(bytes.fromhex(data['self_config']), bytes.fromhex(chosen)), None


def _ats_request(command, meta, **values):
    return dict(dict(command=command, actor_uid=0, actor_generation=0, owner_uid=0, member_id=0,
                     hold=0, lawful_known=0, lawful=0, event_seq=meta.get('event_seq', 0),
                     ats_epoch=meta.get('ats_epoch', 0)), **values)


def _ats_ui_refused(ctx, writer, uid, signal, meta, result):
    """Bridge refusal hook, including disabled ATS and an expired actor mapping."""
    if signal.operation in ('ats-window-open', 'ats-window-save'):
        if not result.get('feedback_sent'):
            args = getattr(signal, 'args', ())
            member = int(args[0]) if args else 0
            epoch = int(args[1]) if signal.operation == 'ats-window-save' and len(args) > 1 else 0
            _ats_window_feedback(ctx, uid, member, epoch, meta, result)
        return
    if signal.operation not in ('settings-load', 'ats-select', 'ats-edit-close') or result.get('feedback_sent'):
        return
    reason = result.get('reason') or result.get('error', '')
    if result.get('status') == 'NO_OWNER' or reason == 'COMPANION_SIGNAL_CURRENT_ACTOR_REQUIRED':
        text = '설정할 동료가 현재 소환되어 있지 않습니다. 동료를 다시 소환한 뒤 눌러 주세요.'
    elif reason in ('SELF_CHARACTER_CONFIG_UNKNOWN', 'SCOPE_ATS_UNKNOWN'):
        text = '저장된 자동 사냥 설정이 없습니다. 설정을 한 번 저장한 뒤 다시 눌러 주세요.'
    elif result.get('status') == 'UNHANDLED':
        text = '현재 자동 사냥 동료 설정 기능을 사용할 수 없습니다.'
    else:
        text = ('자동 사냥 설정을 복원하는 중 오류가 발생했습니다. 설정 창을 다시 열어 주세요.'
                if signal.operation == 'ats-edit-close' else
                '자동 사냥 설정을 불러오는 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.')
    ctx.run_sync_hooks('companion_bridge_publish', uid or 0, 'ats-cancel', _ats_request('ats-cancel', meta))
    if uid is not None:
        ctx.world._queue(uid, _ats_notice(text))
        ctx.world._announce()
    result['feedback_sent'] = True


def _ats_owner_saved(ctx, uid):
    """(f1, f2) the owner's latest SELF wrappers: own 4ED6 rows, else the account sidecar."""
    data = ctx._ats_store['characters'].get(str(uid), {})
    first = bytes.fromhex(data['self_config']) if data.get('self_config') else None
    second = bytes.fromhex(data['self_ats']) if data.get('self_ats') else None
    store = getattr(ctx.realm, 'settings', None)
    if (first is None or second is None) and store is not None:
        try:
            raw = store.saved_raw()
            saved = _ats_fields(raw) if raw is not None else (None, None)
        except (OSError, ValueError, pb.WireError):
            saved = (None, None)
        first = first if first is not None else saved[0]
        second = second if second is not None else saved[1]
    return first, second


def _ats_learned(ctx, uid):
    """The owner's learned spell keys from the optional magic feature (empty without it)."""
    state = getattr(getattr(ctx, '_world_magic', None), 'states', {}).get(uid)
    return frozenset(getattr(state, 'learned', ()) or ())


def _ats_member_name(ctx, member):
    looks = getattr(ctx.world, 'companion_looks', {}).get(member) or {}
    name = looks.get('name')
    if isinstance(name, bytes):
        name = name.decode('utf-8', 'replace')
    return str(name) if name else str(member)


def _ats_edit_actor(ctx, uid, signal):
    """Shared current-owner/current-actor check for both ATS editing paths."""
    manager = getattr(ctx.world, 'companions', None)
    actor = next((rt for rt in (manager.active.values() if manager is not None else ())
                  if rt.owner_ref.uid == uid and rt.ref.uid & 0xFFFFFFFF == signal.actor_uid), None)
    need(actor is not None, 'COMPANION_SIGNAL_CURRENT_ACTOR_REQUIRED')
    return actor


def _ats_edit_start(ctx, writer, uid, signal, meta):
    actor = _ats_edit_actor(ctx, uid, signal)
    member = actor.character_id
    previous = ctx._ats_edit.get(id(writer))
    owner_config, owner_ats = _ats_owner_saved(ctx, uid)
    if previous is not None:
        owner_config = previous['owner_config']
        owner_ats = previous['owner_ats']  # the shown model is the member's: keep the first stash
    if owner_config is None:
        reason = 'SELF_CHARACTER_CONFIG_UNKNOWN'
        result = dict(status='REFUSED', reason=reason, member=member)
        _ats_ui_refused(ctx, writer, uid, signal, meta, result)
        _ats_note(ctx, dict(event='edit', character=uid, member=member, status=reason))
        return result
    row = ctx._ats_store['characters'].get(str(member), {})
    chosen = row.get('companion_ats') or row.get('self_ats')
    mate_ats = bytes.fromhex(chosen) if chosen else (owner_ats if owner_ats is not None else codec.wrap_blob(b''))
    mate_config = (bytes.fromhex(row['companion_config']) if row.get('companion_config')
                   else codec.companion_character_config(owner_config))
    owner_spells = _ats_learned(ctx, uid)
    mate_spells = frozenset(actor.record.learned_spells)
    ctx._ats_edit[id(writer)] = dict(member=member, owner_config=owner_config,
                                     owner_ats=owner_ats, phase='open', owner=uid,
                                     owner_spells=owner_spells, mate_spells=mate_spells)
    ctx._ats_scope[id(writer)] = 'self'  # the restore returns to the owner's SELF scope
    ctx.world._queue(uid, _ats_noti(mate_config, mate_ats))
    spells = _ats_spell_frame(mate_spells, owner_spells)
    if spells is not None:
        ctx.world._queue(uid, spells)
    ctx.world._announce()
    label = ('동료: ' + _ats_member_name(ctx, member)).encode('utf-8')[:120]
    ctx.run_sync_hooks('companion_bridge_publish', uid, 'ats-edit-apply', _ats_request(
        'ats-edit-apply', meta, member_id=member, label_hex=label.hex()))
    _ats_note(ctx, dict(event='edit', character=uid, member=member, status='EDIT_STARTED',
                        source='companion' if row.get('companion_ats') else 'member-self' if chosen else 'owner'))
    return dict(status='EDIT_STARTED', member=member)


def _ats_edit_close(ctx, writer, uid, meta):
    edit = ctx._ats_edit.get(id(writer))
    try:
        owner_config, saved_ats = _ats_owner_saved(ctx, uid)
        if edit is not None:
            owner_config = edit['owner_config']
        # Even a duplicate/stale close must produce a load: the DLL's restoring
        # flag clears only on the original 4302F0 observation of the owner's 4ED7.
        need(owner_config is not None, 'SELF_CHARACTER_CONFIG_UNKNOWN')
        owner_ats = edit['owner_ats'] if edit is not None else saved_ats
        owner_ats = owner_ats if owner_ats is not None else codec.wrap_blob(b'')
        ctx.world._queue(uid, _ats_noti(owner_config, owner_ats))
    except Exception as error:
        result = (dict(status='REFUSED', error=str(error)[:96]) if isinstance(error, ValueError)
                  else dict(status='FAILED', error=f'{type(error).__name__}: {error}'[:96]))
        # Without an owner load the DLL needs cancellation for this close event,
        # including when the ATS handler is called without the transport wrapper.
        _ats_ui_refused(ctx, writer, uid, SimpleNamespace(operation='ats-edit-close'), meta, result)
        return result
    owner_spells = edit['owner_spells'] if edit is not None else _ats_learned(ctx, uid)
    mate_spells = edit['mate_spells'] if edit is not None else ()
    spells = _ats_spell_frame(owner_spells, mate_spells)
    if spells is not None:
        ctx.world._queue(uid, spells)
    ctx.world._announce()
    if edit is None:
        _ats_note(ctx, dict(event='edit-close', character=uid, status='NO_EDIT', supplied=True))
        return dict(status='NO_EDIT', supplied=True)
    edit['phase'] = 'restoring'
    _ats_note(ctx, dict(event='edit-close', character=uid, member=edit['member']))
    return dict(status='RESTORING', member=edit['member'])


def _ats_window_directory(ctx):
    """Only the existing owned companion IPC directory can carry JSON data."""
    host = getattr(ctx, '_companion_bridge_host', None)  # explicit shared attach, not transport internals
    raw = getattr(host, 'directory', None) or os.environ.get('SL_COMPANION_BRIDGE_DIR')
    need(raw is not None, 'ATS_WINDOW_BRIDGE_DIRECTORY_REQUIRED')
    directory = Path(raw).resolve(strict=True)
    need(directory.is_dir(), 'ATS_WINDOW_BRIDGE_DIRECTORY_REQUIRED')
    return directory


def _ats_window_json(ctx, prefix, epoch, payload):
    directory = _ats_window_directory(ctx)
    name = f'companion-ats-{prefix}-{epoch}-{time.time_ns()}.json'
    raw = (json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(',', ':')) + '\n').encode('utf-8')
    # CREATE_NEW preserves earlier view/result evidence, even for repeated signals.
    with open(directory / name, 'xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return name


def _ats_window_spell_catalog(ctx):
    """Known learned/cast keys joined to this fixed client's UI spell rows."""
    result = {}
    ui_rows = getattr(ctx, '_ats_window_ui', {})
    for spell in _ats_spell_entries(ctx):
        key_info = spell.get('classic_key') or {}
        key = key_info.get('value')
        # The 41 later rows carry OFFICIAL_CLIENT_EXACT_ID_NAME rather than
        # CONFIRMED_RETAINED_UI_KEY; their key is also present in the fixed UI
        # join and native spell table. Both statuses require the UI id join.
        if (type(key) is not int or key < 0 or key_info.get('status') not in
                ('CONFIRMED_RETAINED_UI_KEY', 'OFFICIAL_CLIENT_EXACT_ID_NAME')):
            continue
        ui = ui_rows.get(key)
        if ui is None:
            ui = (spell.get('source_snapshot', {}).get('client_ui') or {})
            named = ui.get('named_UI_configuration') or {}
            if ui.get('spell_id') != key or named.get('id') != key:
                continue
            ui = dict(spell_row=key, name=ui.get('name_KR'), icon=named.get('icon'))
        if (type(ui.get('icon')) is int and ui['icon'] >= 0
                and isinstance(ui.get('name'), str) and key not in result):
            result[key] = ui
    return result


def _ats_window_learned(ctx, member):
    """The same live/cold MagicStore hook used by companion cast eligibility."""
    collect = getattr(ctx, 'collect_sync_hooks', None)
    values = (() if collect is None else collect('character_learned_spells', member))
    learned = next((value for value in values if value is not None), ())
    return tuple(sorted(key for key in set(learned) if type(key) is int and key >= 0))


def _ats_heal_kinds(ctx):
    # PlayerMagic builds rules[name].kind from this same runtime policy.
    from tools.local_original_session.world_magic import load_catalog, runtime_spell
    names = _ats_spell_keys(ctx)
    result = {}
    for source in load_catalog()['spells']:
        spell = runtime_spell(source)
        policy = spell.get('player_policy', {})
        name = spell['id']
        key = spell['classic_key']['value']
        if not policy.get('supported') or names.get(key) != name:
            continue
        if name in ('heal', 'extra_heal', 'greater_heal') and policy.get('kind') == 'heal':
            result[key] = 'hp'
        elif name in ('cure_poison', 'remove_curse') and policy.get('kind') == name:
            result[key] = 'status'
    return result


def _ats_heal_policy(ctx, row):
    saved = row.get('companion_heal', ())
    names = _ats_spell_keys(ctx)
    return [dict(kind='hp' if index < 4 else 'status',
                 spell=names.get(selected.get('spell_row')),
                 spell_row=selected.get('spell_row'),
                 **(dict(percent=selected.get('percent', 50)) if index < 4 else {}))
            for index in range(6)
            for selected in [saved[index] if index < len(saved) else {}]]


def _ats_window_slot(ctx, selected, spells=None):
    if selected.get('status') == 'empty':
        return None
    raw = selected.get('raw', {})
    if raw.get(1) == 2 and raw.get(4, 0) > 0:
        name = raw.get(7, b'')
        name = name.decode('utf-8', 'replace') if isinstance(name, bytes) else str(name)
        if not name:
            item = getattr(getattr(ctx.world, 'data', None), 'items', {}).get(raw[4])
            name = getattr(item, 'name_ko', '')
        return dict(template=raw[4], name=name)
    if raw.get(1) == 1 and type(raw.get(4)) is int and raw[4] >= 0:
        known = (spells or {}).get(raw[4])
        return dict(known) if known is not None else dict(
            spell_row=raw[4], name=None, icon=None, status='UNKNOWN')
    # Unknown saved rows stay visible without pretending to be a learned spell.
    return dict(spell_key=raw.get(4), spell=selected.get('spell'), status=selected.get('status'))


def _ats_window_view(ctx, member, epoch):
    """No fallback to member SELF or owner's ATS: absent companion save is empty."""
    row = ctx._ats_store['characters'].get(str(member), {})
    wrapper = bytes.fromhex(row['companion_ats']) if row.get('companion_ats') else None
    decoded = codec.decode_options(codec.unwrap_blob(wrapper)) if wrapper is not None else {}
    policy = codec.companion_policy(wrapper, _ats_spell_keys(ctx))
    spells = _ats_window_spell_catalog(ctx)
    learned = _ats_window_learned(ctx, member)
    view = dict(schema='companion-ats-view-v1', member_id=member, edit_epoch=epoch,
                name=_ats_member_name(ctx, member))
    heal_kinds = _ats_heal_kinds(ctx)
    view['learned_spells'] = [dict(spells[key], **(dict(heal_kind=heal_kinds[key])
        if key in heal_kinds else {})) for key in learned if key in spells]
    unknown = [key for key in learned if key not in spells]
    if unknown:
        view['learned_spells_unknown'] = unknown
    for kind, count in (('hp', 2), ('mp', 2), ('function', 6)):
        key = kind + '_slots'
        slots = policy['potion_' + kind]['slots'] if kind in ('hp', 'mp') else policy[key]
        view[key] = ([_ats_window_slot(ctx, slot) for slot in slots] + [None] * count)[:count]
    for key in ('hp_percent', 'mp_percent'):
        value = decoded.get(key)
        view[key] = value if isinstance(value, (float, int)) and 0 <= value <= 100 else None
    view['buff_slots'] = [_ats_window_slot(ctx, slot, spells) for slot in policy['buff_slots']]
    view['battle_slots'] = [dict(kind=row['kind'], index=row['index'],
        slot=_ats_window_slot(ctx, row, spells), **({key: row.get(key) for key in ('condition', 'value')}
        if row['kind'] == 'conditional' else {})) for row in policy['battle_slots']]
    view['heal_slots'] = [dict(kind=selected['kind'], slot=(None
        if selected['spell_row'] is None else _ats_window_slot(ctx,
            dict(raw={1: 1, 4: selected['spell_row']}), spells)),
        **(dict(percent=selected['percent']) if selected['kind'] == 'hp' else {}))
        for selected in _ats_heal_policy(ctx, row)]
    view['options'] = {key: policy[key] for key in ('scan_tiles', 'pickup_weight') if policy[key] is not None}
    return view


def _ats_window_session(ctx, writer, uid, signal):
    need(ctx._world_bound(writer) and ctx._world_pcs.get(id(writer)) == (writer, uid),
         'ATS_WINDOW_CURRENT_SESSION_REQUIRED')
    actor = _ats_edit_actor(ctx, uid, signal)
    need(actor.character_id == int(signal.args[0]) and actor.record.owner_character_id == uid,
         'ATS_WINDOW_CURRENT_MEMBER_REQUIRED')
    entities = getattr(ctx.world, 'entities', {})
    owner, entity = entities.get(uid), entities.get(actor.ref.uid)
    need(owner is not None and owner.ref == actor.owner_ref and entity is not None
         and entity.ref == actor.ref, 'ATS_WINDOW_CURRENT_ACTOR_REQUIRED')
    need(actor.character_id not in getattr(ctx.world, 'pcs', {}), 'COMPANION_MEMBER_SELECTED')
    registry = getattr(ctx.realm, 'registry', None)
    game = registry.resolve(writer) if registry is not None else None
    need(game is not None and ctx._world_ready(writer, game) is not None,
         'ATS_WINDOW_CURRENT_SESSION_REQUIRED')
    return actor, game


def _ats_window_check_learned(ctx, member, changes, wrapper=None):
    """Admit current learning and keep unmapped saved magic rows read-only."""
    if not any(key in changes for key in ('buff_slots', 'battle_slots', 'heal_slots')):
        return
    learned = frozenset(_ats_window_learned(ctx, member))
    known = _ats_window_spell_catalog(ctx)
    if 'heal_slots' in changes:
        heals = changes['heal_slots']
        need(type(heals) is list and len(heals) == 6, 'ATS_WINDOW_HEAL_SLOTS_REQUIRED')
        kinds = _ats_heal_kinds(ctx)
        for index, selected in enumerate(heals):
            need(type(selected) is dict and 'spell_row' in selected,
                 'ATS_WINDOW_HEAL_SLOT')
            if index < 4:
                percent = selected.get('percent')
                need(type(percent) is int and 10 <= percent <= 90 and percent % 10 == 0,
                     'ATS_WINDOW_HEAL_PERCENT')
            key = selected['spell_row']
            if key is None:
                continue
            need(type(key) is int and key in known, 'ATS_WINDOW_HEAL_SPELL_ROW_UNKNOWN')
            need(key in learned, 'ATS_WINDOW_HEAL_SPELL_NOT_LEARNED')
            need(kinds.get(key) == ('hp' if index < 4 else 'status'), 'ATS_WINDOW_HEAL_KIND')
    slots = changes.get('buff_slots', ())
    need(type(slots) in (list, tuple), 'ATS_WINDOW_SPELL_SLOTS_REQUIRED')
    battles = changes.get('battle_slots', ())
    need(type(battles) in (list, tuple), 'ATS_WINDOW_BATTLE_ROWS_REQUIRED')
    if wrapper is not None:
        original = codec.decode_options(codec.unwrap_blob(wrapper))

        def keep_unmapped(before, after):
            key = before.get(4) if isinstance(before, dict) else None
            if before.get(1) == 1 and type(key) is int and key >= 0 and key not in known:
                need(after == dict(spell_row=key, name=None, icon=None, status='UNKNOWN'),
                     'ATS_WINDOW_SPELL_READONLY')

        if 'buff_slots' in changes:
            for before, after in zip(original['buff_slots'], slots):
                keep_unmapped(before, after)
        if 'battle_slots' in changes:
            for before, after in zip(original['battle_slots'], battles):
                if type(after) is dict:
                    keep_unmapped(before['slot'], after.get('slot'))
    for row in battles:
        need(type(row) is dict, 'ATS_WINDOW_BATTLE_ROW')
        slots = (*slots, row.get('slot'))
    for slot in slots:
        if slot is None or type(slot) is not dict or 'spell_row' not in slot:
            continue  # codec checks malformed rows and unchanged item slots
        spell_row = slot['spell_row']
        if slot.get('status') == 'UNKNOWN':
            need(type(spell_row) is int and spell_row not in known,
                 'ATS_WINDOW_SPELL_ROW_UNKNOWN')
            continue  # codec checks exact marker against the original slot
        need(type(spell_row) is int and spell_row in known, 'ATS_WINDOW_SPELL_ROW_UNKNOWN')
        need(spell_row in learned, 'ATS_WINDOW_SPELL_NOT_LEARNED')


def _ats_window_feedback(ctx, uid, member, epoch, meta, result, view=None):
    """A committed save remains OK even if its file/post delivery fails."""
    payload = dict(schema='companion-ats-result-v1', member_id=member, edit_epoch=epoch,
                   status=result['status'], reason=result.get('reason', result.get('error', '')))
    if view is not None:
        payload['view'] = view
    try:
        name = _ats_window_json(ctx, 'result', epoch, payload)
        ctx.run_sync_hooks('companion_bridge_publish', uid or 0, 'ats-window-result', _ats_request(
            'ats-window-result', dict(meta, ats_epoch=epoch), member_id=member, result_file=name))
    except Exception as error:
        result['delivery_error'] = f'{type(error).__name__}: {error}'[:120]
    if uid is not None:
        text = ('동료 설정이 저장되었습니다.' if result['status'] == 'OK' else
                '동료 설정 요청이 거절되었습니다: ' + str(payload['reason'] or result['status']))
        ctx.world._queue(uid, _ats_notice(text))
        ctx.world._announce()
    result['feedback_sent'] = True
    return result


def _ats_window_signal(ctx, writer, uid, signal, meta):
    member = int(signal.args[0])
    epoch = int(signal.args[1]) if signal.operation == 'ats-window-save' else 0
    try:
        actor, game = _ats_window_session(ctx, writer, uid, signal)
        if signal.operation == 'ats-window-open':
            if not hasattr(ctx, '_ats_window_edits'):
                ctx._ats_window_edits, ctx._ats_window_epoch = {}, time.time_ns()
            # A current owned open invalidates the preceding window, including a failed load.
            ctx._ats_window_edits.pop(id(writer), None)
            ctx._ats_window_epoch += 1
            epoch = ctx._ats_window_epoch
            view = _ats_window_view(ctx, member, epoch)
            name = _ats_window_json(ctx, 'view', epoch, view)
            ctx._ats_window_edits[id(writer)] = dict(member=member, owner=uid, game=game,
                actor_ref=actor.ref, owner_ref=actor.owner_ref, epoch=epoch)
            ctx.run_sync_hooks('companion_bridge_publish', uid, 'ats-window-view', _ats_request(
                'ats-window-view', dict(meta, ats_epoch=epoch), member_id=member, view_file=name))
            _ats_note(ctx, dict(event='window-open', character=uid, member=member, epoch=epoch))
            return dict(status='SUPPLIED', member=member, edit_epoch=epoch, view_file=name)
        edit = getattr(ctx, '_ats_window_edits', {}).get(id(writer))
        need(edit is not None and edit['epoch'] == epoch, 'ATS_WINDOW_EDIT_EPOCH_MISMATCH')
        need(edit['owner'] == uid and edit['member'] == member and edit['game'] is game
             and edit['actor_ref'] == actor.ref and edit['owner_ref'] == actor.owner_ref,
             'ATS_WINDOW_EDIT_SESSION_MISMATCH')
        name = signal.args[2]
        need(re.fullmatch(r'companion-ats-delta-[1-9][0-9]*\.json', name) is not None,
             'ATS_WINDOW_DELTA_BASENAME_REQUIRED')
        directory = _ats_window_directory(ctx)
        path = (directory / name).resolve(strict=True)
        need(path.parent == directory, 'ATS_WINDOW_DELTA_DIRECTORY_REQUIRED')
        need(path.stat().st_size <= 65536, 'ATS_WINDOW_DELTA_SIZE')
        delta = json.loads(path.read_text(encoding='utf-8'))
        need(isinstance(delta, dict) and type(delta.get('member_id')) is int
             and type(delta.get('edit_epoch')) is int and delta['member_id'] == member
             and delta['edit_epoch'] == epoch, 'ATS_WINDOW_DELTA_IDENTITY_MISMATCH')
        changes = {key: value for key, value in delta.items() if key not in ('member_id', 'edit_epoch')}
        old = ctx._ats_store['characters'].get(str(member), {})
        wrapper = bytes.fromhex(old['companion_ats']) if old.get('companion_ats') else None
        _ats_window_check_learned(ctx, member, changes, wrapper)
        native_changes = {key: value for key, value in changes.items() if key != 'heal_slots'}
        updated = (wrapper if 'heal_slots' in changes and not native_changes
                   else codec.apply_window_changes(wrapper, native_changes))
        # Build only the companion row. Restore its in-memory predecessor if durable save fails.
        characters = ctx._ats_store['characters']
        existed = str(member) in characters
        replacement = dict(old)
        if updated is not None:
            replacement['companion_ats'] = updated.hex()
        if 'heal_slots' in changes:
            replacement['companion_heal'] = [dict(spell_row=selected['spell_row'],
                **(dict(percent=selected['percent']) if index < 4 else {}))
                for index, selected in enumerate(changes['heal_slots'])]
        characters[str(member)] = replacement
        try:
            _ats_save_store(ctx)
        except Exception:
            if existed:
                characters[str(member)] = old
            else:
                characters.pop(str(member), None)
            raise
        ctx._ats_policies.pop(member, None)
    except Exception as error:
        result = dict(status='REFUSED' if isinstance(error, ValueError) else 'FAILED',
                      reason=str(error)[:160], member=member, edit_epoch=epoch)
        return _ats_window_feedback(ctx, uid, member, epoch, meta, result)
    # The durable write has succeeded. A later view/publication failure must not relabel it as refused.
    result = dict(status='OK', saved=True, member=member, edit_epoch=epoch)
    try:
        view = _ats_window_view(ctx, member, epoch)
    except Exception as error:
        view = None
        result['delivery_error'] = f'{type(error).__name__}: {error}'[:120]
    _ats_note(ctx, dict(event='window-save', character=uid, member=member, epoch=epoch))
    return _ats_window_feedback(ctx, uid, member, epoch, meta, result, view)


def _ats_ui_signal(ctx, writer, uid, signal, meta=None):
    if not getattr(ctx, '_ats_enabled', False):
        return None
    meta = meta or {}
    if signal.operation in ('ats-window-open', 'ats-window-save'):
        return _ats_window_signal(ctx, writer, uid, signal, meta)
    if signal.operation == 'settings-load':
        return _ats_edit_start(ctx, writer, uid, signal, meta)
    if signal.operation == 'ats-edit-close':
        return _ats_edit_close(ctx, writer, uid, meta)
    if signal.operation == 'ats-edit-restored':
        edit = ctx._ats_edit.get(id(writer))
        if edit is None or edit['phase'] != 'restoring':
            return dict(status='NO_EDIT')
        ctx._ats_edit.pop(id(writer), None)
        _ats_note(ctx, dict(event='edit-restored', character=uid, member=edit['member']))
        return dict(status='RESTORED', member=edit['member'])
    if signal.operation != 'ats-select':
        return None
    scope = signal.args[0]
    frame, reason = _ats_select(ctx, uid, scope)
    if frame is None:
        _ats_note(ctx, dict(event='select', scope=scope, character=uid, status=reason))
        result = dict(status='REFUSED', reason=reason, scope=scope)
        _ats_ui_refused(ctx, writer, uid, signal, meta, result)
        return result
    ctx._ats_scope[id(writer)] = scope
    ctx.world._queue(uid, frame)
    ctx.world._announce()
    ctx.run_sync_hooks('companion_bridge_publish', uid, 'ats-apply', _ats_request('ats-apply', meta))
    _ats_note(ctx, dict(event='select', scope=scope, character=uid, status='SUPPLIED',
                        frame_bytes=len(frame)))
    return dict(status='SUPPLIED', scope=scope)


def _ats_policy(ctx, value, character_id):
    """companion_ai_policy fold: the member's saved companion-scope setting."""
    if value is not None or not getattr(ctx, '_ats_enabled', False):
        return value
    if character_id not in ctx._ats_policies:
        row = ctx._ats_store['characters'].get(str(character_id), {})
        raw = row.get('companion_ats')
        policy = codec.companion_policy(None, {})
        if raw is not None:
            try:
                policy = codec.companion_policy(bytes.fromhex(raw), _ats_spell_keys(ctx))
            except (ValueError, TypeError) as error:
                policy.update(status='invalid', issues=[str(error)[:96]])
        policy['heal_slots'] = _ats_heal_policy(ctx, row)
        if raw is None and 'companion_heal' in row:
            policy['status'] = 'valid'
        if policy['status'] == 'invalid' or policy['issues']:
            _ats_note(ctx, dict(event='policy', character=character_id,
                status=policy['status'], issues=policy['issues']))
        ctx._ats_policies[character_id] = policy
    return ctx._ats_policies[character_id]


def _ats_forget_edit(ctx, writer):
    """Drop an unfinished edit; remember the member-only spells it showed."""
    edit = ctx._ats_edit.pop(id(writer), None)  # never saved for the owner
    if edit is not None and edit.get('owner') is not None:
        left = set(edit['mate_spells']) - set(edit['owner_spells'])
        if left:  # kept in the owner's row: also survives a server restart
            data = _ats_row(ctx, edit['owner'])
            data['respell'] = sorted(set(data.get('respell', ())) | left)
            _ats_save_store(ctx)


async def _ats_after_leave(ctx, writer):
    ctx._ats_scope.pop(id(writer), None)  # every new login starts in SELF scope
    getattr(ctx, '_ats_window_edits', {}).pop(id(writer), None)
    _ats_forget_edit(ctx, writer)


async def _ats_after_enter(ctx, writer, row, game, operation_lock):
    """(Re)selection: an edit left open (reselect or reconnect) loses the member spells."""
    if not getattr(ctx, '_ats_enabled', False) or not ctx._world_bound(writer):
        return
    getattr(ctx, '_ats_window_edits', {}).pop(id(writer), None)
    _ats_forget_edit(ctx, writer)  # same writer reselection keeps no edit either
    uid = ctx._world_pcs[id(writer)][1]
    left = ctx._ats_store['characters'].get(str(uid), {}).pop('respell', None)
    if not left:
        return
    _ats_save_store(ctx)
    frame = _ats_spell_frame(_ats_learned(ctx, uid), left)
    if frame is not None:
        await ctx._world_send(writer, row, (frame,), operation_lock)
    _ats_note(ctx, dict(event='respell', character=uid, erased=sorted(set(left) - _ats_learned(ctx, uid))))


async def _ats_start_frame(ctx, writer, row, game, frame, operation_lock):
    """ATS Play while editing a member's setting: consumed with a notice, no ACK."""
    if not getattr(ctx, '_ats_enabled', False) or id(writer) not in getattr(ctx, '_ats_edit', {}):
        return False  # ordinary handling unchanged
    _ats_note(ctx, dict(event='start-refused', character=ctx._world_pcs.get(id(writer), (None, None))[1]))
    await ctx._world_send(writer, row, (_ats_notice('동료 설정을 편집하는 동안에는 자동 사냥을 시작할 수 없습니다.'),),
                          operation_lock)
    return True


def _ats_report(ctx, result):
    result['ats_companion_scope'] = dict(events=list(ctx._ats_events[-16:]),
                                         editing=len(ctx._ats_edit))


METHODS = (_ats_initialize, _ats_frame, _ats_start_frame, _ats_ui_signal, _ats_ui_refused, _ats_policy,
           _ats_after_enter, _ats_after_leave, _ats_report)
HOOKS = {'initialize': ('_ats_initialize',), 'companion_ui_signal': ('_ats_ui_signal',),
         'companion_ui_refused': ('_ats_ui_refused',),
         'companion_ai_policy': ('_ats_policy',), 'after_enter': ('_ats_after_enter',),
         'after_leave': ('_ats_after_leave',), 'report': ('_ats_report',)}
NONCRITICAL_HOOKS = ('report',)
FRAMES = {SETTINGS_OPCODE: ('_ats_frame',), ATS_START_OPCODE: ('_ats_start_frame',)}
OUTGOING_OPCODES = (NOTI_OPCODE, SPELL_LIST_OPCODE, NOTICE_OPCODE)
