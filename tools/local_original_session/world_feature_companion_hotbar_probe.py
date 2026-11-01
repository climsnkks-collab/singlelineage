"""Optional companion hotbar commands; historical probe name retained.

Display-only SpellInfo never grants player learning. The companion consumer
owns costs, cooldowns, effects and persistence. No experimental environment flags.
"""
from __future__ import annotations
import struct
import time
from tools.local_entry_server import protobuf as pb

AVAILABLE, CAST, SETTINGS = 0x4E60, 0x4EE6, 0x4ED6

def _note(ctx, event, **fields):
    ctx._hotbar_probe_events.append(dict(event=event, at=time.time(), monotonic=time.monotonic(), **fields))
    del ctx._hotbar_probe_events[:-64]

def _learned(ctx, uid):
    return set(next((v for v in ctx.collect_sync_hooks('character_learned_spells', uid) if v is not None), ()))

def _wire(op, body):
    return struct.pack('<HH', len(body)+6, op)+body+b'\0\0'

def _list_frame(add, remove=()):
    return _wire(AVAILABLE, b''.join(pb.encode_bytes(1, pb.encode_uint32(1,key)+pb.encode_bool(2,flag)
        +(pb.encode_uint32(6,1) if flag else b''))
        for flag,keys in ((True,add),(False,remove)) for key in sorted(keys)))

def _commands(ctx):
    return next((value for value in ctx.collect_sync_hooks('companion_commands')
                 if value is not None), None)

def _members(ctx, uid, *, restoring=False):
    commands = _commands(ctx)
    return {} if commands is None else commands.members(uid, restoring=restoring)

def _publish(ctx, uid, keys):
    return ctx.chain_sync_hooks('companion_hotbar_publish', uid, keys)

def _sync(ctx, writer, uid, *, restoring=False):
    session = ctx._hotbar_probe_sessions.get(id(writer))
    if session is None or session['uid'] != uid:
        session = dict(uid=uid,keys=frozenset(),known=set(),published=False)
        ctx._hotbar_probe_sessions[id(writer)] = session
    members = _members(ctx,uid,restoring=restoring)
    keys, own = frozenset(members), _learned(ctx,uid)
    adopted = session['keys'] & own
    add, remove = keys-session['keys'], session['keys']-keys-own
    frames = []
    if add or remove:
        frames.append(_list_frame(add,remove))
        _note(ctx,'list-changed',uid=uid,added=sorted(add),removed=sorted(remove),members=members)
    if adopted:
        magic = next(value for value in ctx.collect_sync_hooks('magic_service') if value is not None)
        frames.append(_wire(AVAILABLE,b''.join(pb.encode_bytes(1,pb.encode_uint32(1,key)
            +pb.encode_bool(2,True)+pb.encode_uint32(6,magic.spell_mp(key))) for key in sorted(adopted))))
    if keys != session['keys'] or keys and not session['published']:
        session['published'] = _publish(ctx,uid,keys)
    session['keys'], session['members'] = keys, members
    session['known'].update(keys)
    return tuple(frames)

def _hotbar_probe_initialize(ctx):
    ctx._hotbar_probe_enabled, ctx._hotbar_probe_f6 = True, 1
    ctx._hotbar_probe_sessions, ctx._hotbar_probe_events = {}, []
    ctx._hotbar_command_wrappers = []

def _hotbar_command_started(ctx):
    commands = _commands(ctx)
    if commands is None or not commands.ready:
        return
    def ordered_send(base):
        async def send(writer,row,replies,**options):
            marker = next((i for i,w in enumerate(replies) if int.from_bytes(w[2:4],'little') == 0x4ED7
                or w == b'\x08\0\xef\x4e\x08\x09\0\0'),None)
            if marker is not None and id(writer) not in ctx._hotbar_probe_sessions:
                position = ctx.realm.service(writer).snapshot()
                if commands.character_class(position.uid) == 1:
                    frames = _sync(ctx,writer,position.uid,restoring=True)
                    if frames:
                        if marker:
                            await base(writer,row,replies[:marker],**options)
                        await ctx._world_send(writer,row,frames,options.get('operation_lock'))
                        _note(ctx,'before-shortcut-restore',uid=position.uid)
                        return await base(writer,row,replies[marker:],**options)
            return await base(writer,row,replies,**options)
        return send
    ctx._hotbar_command_wrappers.append(ctx.world.runtime_extensions.wrap('companion_hotbar',ctx.broker,'_send',ordered_send))
    ctx._hotbar_command_tick_entry = ctx.world.events.add('companion_hotbar','tick',
        lambda now:_hotbar_command_changed(ctx),priority=110)

def _hotbar_command_changed(ctx,*args):
    for writer,uid in tuple(ctx._world_pcs.values()):
        if ctx.world.combat.pcs[uid].profile.character_class != 1:
            continue
        if ctx.chain_sync_hooks('companion_hotbar_suspended', writer):
            continue
        frames = _sync(ctx,writer,uid)
        for wire in frames:
            ctx.world._queue(uid,wire)
        if frames:
            ctx.world._announce()

async def _hotbar_probe_enter(ctx,writer,row,game,operation_lock):
    if not ctx._world_bound(writer) or _commands(ctx) is None:
        return
    uid = ctx._world_pcs[id(writer)][1]
    if ctx.world.combat.pcs[uid].profile.character_class == 1:
        frames = await ctx.world.runtime.dispatch_now(_sync,ctx,writer,uid)
        await ctx._world_send(writer,row,frames,operation_lock)

def _hotbar_display_keys(ctx,uid):
    return frozenset(_members(ctx,uid))

def _decode(payload):
    with pb.parse_message(payload) as msg:
        keys,params = msg.occurrences(1),msg.occurrences(2)
        if len(keys)!=1 or keys[0].wire_type!=0 or len(params)>1 or len(msg.fields)!=1+len(params):
            raise ValueError('CAST_FIELDS')
        key,target,coords = keys[0].value,None,{}
        if params:
            with pb.parse_message(bytes(params[0].value)) as child:
                if any(f.number not in (1,3,4) or f.wire_type != 0 for f in child.fields):
                    raise ValueError('CAST_TARGET_FIELDS')
                if any(len(child.occurrences(n))>1 for n in (1,3,4)):
                    raise ValueError('CAST_DUPLICATE_TARGET')
                for f in child.fields:
                    if f.number==1:
                        target=f.value & 0xffffffff
                    else:
                        coords[f.number]=f.value
        return key,target,coords

def _command(ctx,uid,key,target_uid,coords):
    result = _commands(ctx).cast(uid, key, target_uid)
    if result['cast']:
        _note(ctx, 'cast-command', **result, coordinates=coords)
        return
    ctx.world._queue(uid,_wire(0x4EEA,pb.encode_uint32(1,12066)
        +pb.encode_bytes(2,result['message'].encode('utf-8'))))
    _note(ctx, 'command-refused', **result)

async def _hotbar_probe_frame(ctx,writer,row,game,frame,operation_lock):
    if (frame.opcode!=CAST or not ctx._world_bound(writer) or ctx._world_ready(writer,game) is None
            or _commands(ctx) is None):
        return False
    uid=ctx._world_pcs[id(writer)][1]
    session=ctx._hotbar_probe_sessions.get(id(writer))
    if session is None or session['uid']!=uid:
        return False
    try:
        with pb.parse_message(frame.payload) as msg:
            keys=msg.occurrences(1)
            if len(keys)!=1 or keys[0].wire_type!=0:
                return False
            key=keys[0].value
        if key in _learned(ctx,uid) or key not in session['known']:
            return False
        key,target,coords=_decode(frame.payload)
    except (ValueError,TypeError,pb.WireError):
        if 'key' not in locals() or key not in session['known']:
            return False
        target,coords=None,None
    def apply():
        if ctx.world.combat.pcs[uid].dead:
            return ()
        if coords is None:
            ctx.world._queue(uid,_wire(0x4EEA,pb.encode_uint32(1,12066)
                +pb.encode_bytes(2,'[LOCAL] 동료: 잘못된 마법 대상입니다.'.encode('utf-8'))))
        else:
            _command(ctx,uid,key,target,coords)
        return ctx.world.drain(uid)
    frames=await ctx.world.runtime.dispatch_now(apply)
    await ctx._world_send(writer,row,frames,operation_lock)
    return True

def _hotbar_probe_leave(ctx,writer):
    session = ctx._hotbar_probe_sessions.pop(id(writer),None)
    if session is not None and session['known']:
        _publish(ctx,session['uid'],())

def _hotbar_command_stopped(ctx):
    entry=getattr(ctx,'_hotbar_command_tick_entry',None)
    if entry is not None:
        ctx.world.events.remove('tick',entry)
    for handle in reversed(ctx._hotbar_command_wrappers):
        handle.close()

def _hotbar_probe_report(ctx,result):
    result['companion_hotbar_command']=dict(enabled=True,events=list(ctx._hotbar_probe_events),formal_pass=False)

METHODS=(_hotbar_probe_initialize,_hotbar_command_started,_hotbar_probe_enter,_hotbar_probe_frame,
    _hotbar_probe_leave,_hotbar_command_stopped,_hotbar_probe_report,_hotbar_command_changed,_hotbar_display_keys)
HOOKS={'initialize':('_hotbar_probe_initialize',),'runtime_started':('_hotbar_command_started',),
    'after_enter':('_hotbar_probe_enter',),'magic_learning_changed':('_hotbar_command_changed',),
    'companion_spell_display_keys':('_hotbar_display_keys',),'after_leave':('_hotbar_probe_leave',),
    'runtime_stopped':('_hotbar_command_stopped',),'report':('_hotbar_probe_report',)}
HOOK_PRIORITY={'after_enter':100,'magic_learning_changed':100,'runtime_started':100}
FRAMES={CAST:('_hotbar_probe_frame',)}
FRAME_PRIORITY=-10
OUTGOING_OPCODES=(AVAILABLE,0x4EEA)
