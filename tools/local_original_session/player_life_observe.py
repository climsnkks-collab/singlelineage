"""Own-player passive Action inputs inside the original retained 24-KiB query.

No getter/callback/Start/Next/Remove, packet, new sampler or code fallback.
Recovery authority remains unavailable until the original init/resource
contract has a source-bound current implementation; numeric fields alone
never mint RecoveryInputs.
"""
import hashlib
import json
import struct
import time
import copy

from tools.local_original_session import attack, attack_action_observe as actions
from tools.local_original_session import hp_status_observe as hp, move_state, observe

need = observe.need
BYTE_LIMIT = actions.BYTE_LIMIT
MIN_INTERVAL_NS = actions.MIN_INTERVAL_NS
ROOT = observe.ROOT
BASE = 'work/local_server_rea_20261016/run102_own_player_death_recovery/'
SOURCE_PINS = {
    BASE+'resource_input_delta/source-evidence.json': '1f8b09b986b54bd70a72d1f9a5cab3d92a57a8ec1c2e467cd4dc1050ca8278ed',
    BASE+'resource_input_delta/findings.md': '33b3918fe1a60a86467cee1f70c6831ffb3e28c36dd3f77ecb4dd41ebcfab55c',
    BASE+'implementation-conditions.md': '213b7b4ea107d00977bcff8b03a37a8d35958629096f13fecd83cf0525c5a30e',
    BASE+'worker_death/source-evidence.json': '264494872e1eb297bc456d5906e039c5acb97279b69c7478ec75c616644b7d3a',
    BASE+'worker_recovery/source-evidence.json': '3353f2c0da6cd5dca7d684bfafdcb0ab427259b695795327aa8c5d8ae8de227b',
}


def source_ready():
    for path, expected in SOURCE_PINS.items():
        raw = observe.ordinary(ROOT/path).read_bytes()
        need(0 < len(raw) <= 1048576 and hashlib.sha256(raw).hexdigest() == expected,
             'PLAYER_LIFE_SAVED_SOURCE_CHANGED')
    # Existing typed Action RTTI/owner and Actor/Map tables remain canonical.
    return actions._source()


class RecoveryInputs:
    """Exact issuing-service capability, never a caller-created numeric DTO."""
    __slots__ = ('_observer', '_writer', '_context', '_stage', '_receipt', '_f2', '_f3', '_record')

    def __init__(self, *args, **kwargs):
        raise TypeError('PLAYER_LIFE_SERVICE_ISSUED_INPUTS_REQUIRED')

    @property
    def f2(self): return self._f2

    @property
    def f3(self): return self._f3

    def require_current_locked(self, writer, context):
        return self._observer._require(self, writer, context)

    def require_stage_locked(self, writer, context, *, stage):
        row = self.require_current_locked(writer, context)
        need(stage == self._stage, 'PLAYER_LIFE_EXACT_STAGE_REQUIRED')
        return row

    def metadata(self):
        # Scalar diagnostics do not authorize a wire operation or a new life.
        return dict(stage=self._stage, f2=self.f2, f3=self.f3,
                    observed=copy.deepcopy(self._receipt))


class PlayerLifeObserver:
    def __init__(self, broker, reader):
        source_ready()
        self.broker, self.reader = broker, reader
        self.selected = hp.StatusHpObserver(broker, reader)
        self.layout = move_state.MoveState()
        self._inputs = self.before = None
        self._issued = []
        self._baseline = self._owners = self._candidate = None
        self._prepared = self._last_ns = self._last_completed = None
        self._preparing = False
        self.last_result = dict(status='UNKNOWN', reason='NOT_SAMPLED')

    @property
    def inputs(self): return self._inputs

    def _current(self, writer, context):
        from tools.local_original_session import player_life
        need(type(context) in (player_life.Context, player_life.AfterContext)
             and self.broker._player_life_observer is self,
             'PLAYER_LIFE_REGISTERED_CONTEXT_REQUIRED')
        row = context.require_current_locked(writer)
        selected = self.selected._selection(writer)
        need(selected[0] is row, 'PLAYER_LIFE_SELECTED_ROW_CHANGED')
        return selected

    async def prepare(self, writer, *, life_context, stage, now_ns):
        need(not self._preparing and self._prepared is None,
             'PLAYER_LIFE_QUERY_INFLIGHT')
        from tools.local_original_session import player_life
        need((stage == 'RESTORED') is (type(life_context) is player_life.AfterContext),
             'PLAYER_LIFE_AFTER_CONTEXT_READONLY_STAGE_REQUIRED')
        need(stage in ('PRE', 'DEAD', 'RECOVERY', 'RESTORED')
             and type(now_ns) is int and 0 <= now_ns < (1 << 63)
             and (self._last_ns is None or now_ns-self._last_ns >= MIN_INTERVAL_NS),
             'PLAYER_LIFE_EXPLICIT_STAGE_CADENCE_REQUIRED')
        self._last_ns, self._preparing = now_ns, True
        self._inputs = None
        try:
            initial = self._current(writer, life_context)
            for _ in range(2):
                need(await self.broker._movement_owner(writer, initial[0], initial[1]) is True,
                     'PLAYER_LIFE_CURRENT_NATIVE_OWNER_REQUIRED')
                actual = self._current(writer, life_context)
                need(attack._same_binding(initial[2], initial[3], actual[2], actual[3]),
                     'PLAYER_LIFE_SELECTION_CHANGED')
            self._prepared = writer, life_context, stage, now_ns, initial
        finally:
            self._preparing = False

    async def capture_locked(self, writer, context, *, stage, now_ns):
        from tools.local_original_session.observe import RetainedSceneReader
        need(type(self.reader) is RetainedSceneReader
             and type(self.reader).sample is RetainedSceneReader.sample,
             'PLAYER_LIFE_ORIGINAL_RETAINED_QUERY_REQUIRED')
        await self.prepare(writer, life_context=context, stage=stage, now_ns=now_ns)
        sampled, _count = self.reader.sample(include_input_state=False, player_life_observer=self)
        raw = sampled.get('player_life', {})
        need(raw.get('status') == 'OBSERVED', raw.get('reason') or 'PLAYER_LIFE_QUERY_UNKNOWN')
        need(raw.get('stable_double_read') is True
             and raw.get('resource_status') == 'OBSERVED_SOURCE_BOUND_INIT_METADATA',
             'PLAYER_LIFE_CURRENT_INIT_METADATA_REQUIRED')
        return self._issue(writer, context, stage, raw)

    def _require(self, cap, writer, context):
        need(type(cap) is RecoveryInputs and self.inputs is cap and cap._observer is self
             and any(cap._record is record for record in self._issued)
             and (cap._f2,cap._f3) == self._baseline
             and cap._writer is writer and cap._context is context,
             'PLAYER_LIFE_EXACT_ISSUED_INPUTS_REQUIRED')
        selected = self._current(writer, context)
        need(self._last_completed is not None
             and 0 <= time.monotonic_ns()-self._last_completed <= MIN_INTERVAL_NS,
             'PLAYER_LIFE_TYPED_OBSERVATION_EXPIRED')
        # No hidden typed read here. Current memory is scoped to the preceding
        # scheduled physical double-read, never an atomic/owning lease.
        return selected[0]

    def _issue(self, writer, context, stage, raw):
        private = self._pending_identity
        owners, candidate = private[0], private[1]
        if stage == 'PRE':
            need(self.before is None and raw['numeric_hp'] == 1,
                 'PLAYER_LIFE_PRE_HP_ONE_ONCE_REQUIRED')
            self._baseline = raw['current_f2'], raw['current_f3']
            self._owners, self._candidate = owners, candidate
        else:
            need(self.before is not None and owners == self._owners
                 and candidate == self._candidate,
                 'PLAYER_LIFE_PRE_INIT_OWNER_OR_METADATA_CHANGED')
        current = raw['action']
        if stage == 'DEAD':
            need(raw['numeric_hp'] == 0 and raw['flag46'] is False
                 and current.get('kind') == 'DeathAction'
                 and current.get('corpse_latch80') is True
                 and current.get('finished') is False,
                 'PLAYER_LIFE_DEAD_CURRENT_NOT_READY')
        elif stage == 'RESTORED':
            need(raw['numeric_hp'] == context.snapshot.current_hp == context.snapshot.maximum_hp
                 and raw['numeric_max_hp'] == context.snapshot.maximum_hp
                 and raw['flag46'] is True
                 and current.get('kind') in ('BreathAction','DefaultAction'),
                 'PLAYER_LIFE_RESTORED_CURRENT_NOT_READY')
        cap = object.__new__(RecoveryInputs)
        cap._observer, cap._writer, cap._context, cap._stage = self,writer,context,stage
        cap._receipt = copy.deepcopy(raw)
        cap._f2,cap._f3 = self._baseline
        cap._record = (cap,private,context,stage)
        self._issued.append(cap._record)
        self._inputs = cap
        if stage == 'PRE': self.before = cap
        return cap

    @staticmethod
    def _pairs(reads, obj, offset, maximum):
        begin,end = struct.unpack('<QQ', reads.read(obj+offset,16))
        need(begin == end == 0 or 0x10000 <= begin <= end <= 0x7fffffffffff
             and (begin|end)%8 == 0 and (end-begin)%16 == 0
             and (end-begin)//16 <= maximum, 'PLAYER_LIFE_PAIR_VECTOR_BOUND')
        result = []
        for at in range(begin,end,16):
            raw = reads.read(at,16)
            value = reads.pair(raw)
            result.append((value,struct.unpack('<QQ',raw)))
        return result

    @staticmethod
    def _sprite_record(reads, subsystem, bits):
        requested = struct.unpack('<i',struct.pack('<I',bits))[0]
        head = reads.pointer(subsystem+0x908,role='SPRITE_METADATA_MAP_HEAD')
        root = reads.pointer(head+8,role='SPRITE_METADATA_MAP_ROOT')
        def find(key):
            at,selected,seen = root,head,set()
            for _ in range(128):
                if reads.number(at+0x19,'<B',role='SPRITE_METADATA_NODE_NIL'):
                    break
                need(at not in seen,'PLAYER_LIFE_SPRITE_TREE_CYCLE')
                seen.add(at)
                found = reads.number(at+0x20,'<i',role='SPRITE_METADATA_SIGNED_KEY')
                if found >= key:
                    selected = at
                    at = reads.pointer(at,role='SPRITE_METADATA_LEFT')
                else:
                    at = reads.pointer(at+0x10,role='SPRITE_METADATA_RIGHT')
            else: raise ValueError('PLAYER_LIFE_SPRITE_TREE_QUERY_BOUND')
            if selected == head or reads.number(selected+0x19,'<B'):
                return None
            return selected if reads.number(selected+0x20,'<i') == key else None
        node = find(requested)
        resolved,fallback = requested,False
        if node is None:
            node,resolved,fallback = find(0x460),0x460,True
        need(node is not None,'PLAYER_LIFE_SPRITE_METADATA_FALLBACK_MISSING')
        record = node+0x28  #34A160 returns LEA of inline value, no payload dereference.
        original = reads.number(record,'<i',role='SPRITE_METADATA_RECORD0')
        alias = reads.number(record+0xc,'<i',role='SPRITE_METADATA_RECORDC')
        begin,end = struct.unpack('<QQ',reads.read(record+0x10,16,role='SPRITE_METADATA_VECTOR_HEADER'))
        need(begin == end == 0 or 0x10000 <= begin <= end <= 0x7fffffffffff
             and (begin|end)%8 == 0 and (end-begin)%0x28 == 0,
             'PLAYER_LIFE_SPRITE_METADATA_VECTOR_BOUND')
        scalar = dict(requested_u32=bits,requested_i32=requested,resolved_i32=resolved,
            fallback=fallback,node=node,record=record,record0_i32=original,
            recordC_i32=alias,normal_resource_id=alias if alias>0 else original,
            vector_begin=begin,vector_end=end,vector_count=(end-begin)//0x28)
        identity = (head,root,node,record,original,alias,begin,end,requested,resolved,fallback)
        return scalar,identity

    def _npc_current_action(self, reads, sampler, subsystem, actor_pairs, context, action_types):
        """Same-query diagnostic; first UID match and existing typed source only."""
        from tools.local_original_session import npc_observe
        monster, common, checks = npc_observe._source()
        npc_observe._registry_lookup_source()
        from tools.local_original_session import edge
        checks = checks + edge._lookup_contract()['code_checks']
        base, size = sampler.g['base'], sampler.g['size']
        for check in checks:
            need(hashlib.sha256(reads.read(base+check['rva'],check['length'],True)).hexdigest()
                 == check['sha256'], 'PLAYER_LIFE_NPC_SOURCE_CODE_CHANGED')
        actor = None
        vector_index = None
        for index,offset in enumerate((0x8a8,0x8c0,0x8d8)):
            pairs = actor_pairs if index == 0 else self._pairs(reads,subsystem,offset,512)
            for obj,_pair in pairs:
                vp = reads.pointer(obj)
                need(base <= vp <= base+size-16, 'NPC_OBSERVE_GETTER_TABLE_BOUNDS')
                need(struct.unpack('<Q',reads.read(vp+8,8,True))[0] == base+common['ID_getter_RVA'],
                     'NPC_OBSERVE_UID_GETTER_UNSUPPORTED')
                if reads.number(obj+common['Actor_ID_u64_offset'],'<Q') == context.source_uid:
                    actor,vector_index = obj,index
                    break  # First UID match; an unsupported actor must not be skipped.
            if actor is not None: break
        need(actor is not None, 'NPC_OBSERVE_UID_NOT_REGISTERED')
        need(reads.pointer(actor) == base+monster['rva']
             and reads.pointer(actor+common['Actor_self_pointer_offset']) == actor,
             'PLAYER_LIFE_NPC_EXACT_MONSTER_REQUIRED')
        reads.normalized_table(actor,monster);reads.rtti(monster)
        for check in monster['RTTI_graph_anchors']:
            need(hashlib.sha256(reads.read(base+check['rva'],check['length'],True)).hexdigest()
                 == check['sha256'], 'PLAYER_LIFE_NPC_HIERARCHY_CHANGED')
        components = self._pairs(reads,actor,0x20,128)
        found = [(obj,pair) for obj,pair in components
                 if reads.pointer(obj) == base+self.layout.tables['ActionComponent']['rva']]
        need(len(found) == 1, 'PLAYER_LIFE_NPC_UNIQUE_ACTION_COMPONENT_REQUIRED')
        component,_pair = found[0]
        reads.table(component,self.layout.tables['ActionComponent'])
        need(reads.pointer(component+8) == actor, 'PLAYER_LIFE_NPC_ACTION_OWNER_CHANGED')
        current = reads.pointer(component+0xc0,True,role='NPC_CURRENT_ACTION')
        out = dict(status='UNKNOWN',uid=context.source_uid,lookup_vector_index=vector_index,kind='unknown',present=bool(current),
                   current_npc_attack=False,source_contract_valid=False)
        if not current:
            return dict(out,kind='none',reason='NPC_CURRENT_ACTION_ABSENT')
        need(reads.pointer(current+8) == component, 'PLAYER_LIFE_NPC_CURRENT_ACTION_OWNER_CHANGED')
        vp = reads.pointer(current)
        row = next((row for row in action_types if vp == base+row['rva']),None)
        if row is None:
            quiet = self.layout.action_tables.get(vp-base)
            if quiet is None or quiet['kind'] not in ('BreathAction','DefaultAction'):
                return dict(out,reason='NPC_CURRENT_ACTION_TYPE_UNQUALIFIED')
            need(reads.read(vp,64,True) == struct.pack('<8Q',*(base+v for v in quiet['targets'])),
                 'PLAYER_LIFE_NPC_QUIET_CURRENT_TABLE_CHANGED')
            return dict(out,status='OBSERVED',kind=quiet['kind'],source_contract_valid=True)
        reads.table(current,row);reads.rtti(row)
        out.update(status='OBSERVED',kind=row['kind'],source_contract_valid=True,
                   finished=reads.number(current+0x24,'<B') != 0)
        if row['kind'] == 'AttackAction':
            source,target,effect = struct.unpack('<QQi',reads.read(current+0x80,20,
                role='NPC_ACTION_ATTACK_PAIR_EFFECT'))
            out.update(stored_attacker_uid=source,target_uid=target,raw_effect_i32=effect,
                       current_npc_attack=source == context.source_uid and target == context.target_uid)
        return out

    def collect(self, scene, world, proof, cache=None):
        result = dict(status='UNKNOWN', reason='NOT_SAMPLED',
            observation_scope='PASSIVE_READONLY_CURRENT_OWN_ACTION',
            typed_byte_limit=BYTE_LIMIT, max_samples_per_second=2,
            stable_double_read=False, source_contract_valid=False,
            snapshot_atomic=False, owning_lease=False, aba_excluded=False,
            start_observed=False, eligible_next_observed=False, ui='UNKNOWN',
            resource_status='NOT_OBSERVED', resource_payload='UNKNOWN',
            life_code_bytes_verified=False, typed_bytes_requested=0)
        prepared, self._prepared = self._prepared, None
        reads = None
        sampler = self.reader.sampler
        previous = sampler.bytes, sampler.read_limit
        sampler.bytes, sampler.read_limit = 0, 8192
        try:
            need(prepared is not None, 'PLAYER_LIFE_PREPARE_REQUIRED')
            writer, context, stage, now_ns, initial = prepared
            actual = self._current(writer, context)
            need(attack._same_binding(initial[2], initial[3], actual[2], actual[3]),
                 'PLAYER_LIFE_SELECTION_CHANGED')
            position = initial[1]
            result['query_context'] = dict(scene={key:scene.get(key) for key in
                ('status','reason','current','pending','root_ready')},world={key:world.get(key) for key in
                ('status','reason','stable_double_read','my_player_uid','map_resolved_i32')})
            need(scene.get('status') == 'OBSERVED' and scene.get('current') == 'Land'
                 and scene.get('pending') == 'none' and scene.get('root_ready') is True
                 and world.get('status') == 'OBSERVED' and world.get('stable_double_read') is True
                 and world.get('my_player_uid') == position.uid
                 and world.get('map_resolved_i32') == position.map_id,
                 'PLAYER_LIFE_STABLE_SELECTED_WORLD_REQUIRED')
            need(type(cache) is actions.SameQueryCache, 'PLAYER_LIFE_SAME_QUERY_CACHE_REQUIRED')
            cache.validate(self.reader, sampler, proof)
            reads = actions._Reads(sampler, cache)
            attack_type, damaged_type, death_type, _public = source_ready()
            tables, base = self.layout.tables, sampler.g['base']
            subs = [reads.pair(pair) for pair, vp in proof['route'][-2]
                    if vp == base+tables['ActorSubsystem']['rva']]
            need(len(subs) == 1, 'PLAYER_LIFE_UNIQUE_ACTOR_SUBSYSTEM_REQUIRED')
            reads.table(subs[0], tables['ActorSubsystem'])
            actor_pairs = self._pairs(reads,subs[0],0x8a8,512)
            own = [(actor,pair) for actor,pair in actor_pairs
                   if reads.pointer(actor) == base+tables['MyPlayer']['rva']]
            need(len(own) == 1, 'PLAYER_LIFE_UNIQUE_MYPLAYER_REQUIRED')
            actor,player_pair = own[0]
            reads.table(actor, tables['MyPlayer'])
            need(reads.number(actor+0x18, '<Q') == position.uid,
                 'PLAYER_LIFE_CURRENT_OWN_UID_CHANGED')
            components = self._pairs(reads,actor,0x20,128)
            found = [(obj,pair) for obj,pair in components
                     if reads.pointer(obj) == base+tables['ActionComponent']['rva']]
            need(len(found) == 1, 'PLAYER_LIFE_UNIQUE_ACTION_COMPONENT_REQUIRED')
            component,action_pair = found[0]
            reads.table(component, tables['ActionComponent'])
            need(reads.pointer(component+8) == actor, 'PLAYER_LIFE_ACTION_OWNER_CHANGED')
            f3 = reads.number(component+0x38, '<I', role='RECOVERY_CURRENT_ACTION38')
            f2 = reads.number(component+0x40, '<I', role='RECOVERY_CURRENT_ACTION40')
            effective = reads.number(component+0x3c, '<I', role='RECOVERY_CURRENT_ACTION3C')
            flags = reads.read(component+0x44, 12, role='RECOVERY_CURRENT_ACTION_FLAGS')
            current = reads.pointer(component+0xc0, True, role='RECOVERY_CURRENT_ACTION')
            need(current != 0,'PLAYER_LIFE_CURRENT_ACTION_REQUIRED')
            need(reads.pointer(current+8) == component,'PLAYER_LIFE_CURRENT_ACTION_OWNER_CHANGED')
            override = reads.number(current+0x30,'<i',role='CURRENT_ACTION_APPEARANCE_OVERRIDE')
            parameter = reads.number(current+0x34,'<i',role='CURRENT_ACTION_PARAMETER_OVERRIDE')
            action = dict(kind='none', present=False)
            if current:
                vp = reads.pointer(current)
                classified = next((row for row in (attack_type, damaged_type, death_type)
                                   if vp == base+row['rva']), None)
                action = dict(kind='unknown', present=True)
                quiet = self.layout.action_tables.get(vp-base)
                if quiet is not None and quiet['kind'] in ('BreathAction', 'DefaultAction'):
                    need(reads.read(vp, 64, True) == struct.pack('<8Q',
                         *(base+value for value in quiet['targets'])),
                         'PLAYER_LIFE_QUIET_CURRENT_TABLE_CHANGED')
                    action = dict(kind=quiet['kind'], present=True,
                        finished=(reads.number(current+0x24, '<B') != 0
                                  if quiet['kind'] == 'DefaultAction' else None))
                if classified is not None:
                    reads.table(current, classified); reads.rtti(classified)
                    need(reads.pointer(current+8) == component, 'PLAYER_LIFE_CURRENT_ACTION_OWNER_CHANGED')
                    action.update(kind=classified['kind'],
                        finished=reads.number(current+0x24, '<B') != 0)
                    if classified['kind'] == 'DeathAction':
                        action['corpse_latch80'] = reads.number(current+0x80, '<B') != 0
            need(action.get('kind') in ('DeathAction','AttackAction','DamagedAction','BreathAction','DefaultAction'),
                 'PLAYER_LIFE_CURRENT_ACTION_TYPE_UNQUALIFIED')
            requested = f3 if stage == 'PRE' else self._baseline[1]
            candidate,candidate_id = self._sprite_record(reads,subs[0],requested)
            effective_record,_effective_id = self._sprite_record(reads,subs[0],effective)
            sub_pairs = [struct.unpack('<QQ',pair) for pair,vp in proof['route'][-2]
                         if vp == base+tables['ActorSubsystem']['rva']]
            need(len(sub_pairs) == 1,'PLAYER_LIFE_UNIQUE_SUBSYSTEM_PAIR_REQUIRED')
            hp_table,_checks = hp._source()
            characters = [reads.pair(pair) for pair,vp in proof['route'][-2]
                          if vp == base+int(hp_table['vptr_rva'],16)]
            need(len(characters) == 1,'PLAYER_LIFE_UNIQUE_CHARACTER_REQUIRED')
            character = characters[0]
            need(reads.number(character+0x6d8,'<Q') == position.uid,'PLAYER_LIFE_CHARACTER_UID_CHANGED')
            expected = struct.pack('<5Q',*(base+int(v,16) for v in hp_table['methods']))
            need(reads.read(base+int(hp_table['vptr_rva'],16),40,True) == expected,
                 'PLAYER_LIFE_CHARACTER_TABLE_CHANGED')
            raw_hp = reads.read(character+0x750,24,role='CURRENT_OWN_HP_PAIR')
            numeric,numeric_max = hp.decode(raw_hp[:12]),hp.decode(raw_hp[12:])
            from tools.local_original_session import player_life
            npc_action = None
            if stage == 'DEAD' and self.broker._player_life.policy.label == player_life.NPC_POLICY_LABEL:
                npc_action = self._npc_current_action(reads,sampler,subs[0],actor_pairs,context,
                    (attack_type,damaged_type,death_type))
            owners = (player_pair,action_pair,sub_pairs[0])
            self._pending_identity = owners,candidate_id
            reads.verify()
            need(reads.physical(proof['state']+0x360,36) == proof['raw']
                 and sampler.route() == proof['route'], 'PLAYER_LIFE_ROOT_SCENE_CHANGED')
            actual = self._current(writer, context)
            need(attack._same_binding(initial[2], initial[3], actual[2], actual[3]),
                 'PLAYER_LIFE_SELECTION_CHANGED')
            result.update(status='OBSERVED', reason=None, stage=stage,
                uid=position.uid, map_id=position.map_id, sample_monotonic_ns=now_ns,
                current_f2=f2, current_f3=f3, current_effective3c=effective, action=action,
                action30_i32=override, action34_i32=parameter,
                candidate_pre=candidate,current_effective=effective_record,
                numeric_hp=numeric,numeric_max_hp=numeric_max,
                resource_status='OBSERVED_SOURCE_BOUND_INIT_METADATA',
                resource_payload='UNKNOWN',
                flag46=flags[2] != 0, flag47=flags[3] != 0,
                source_contract_valid=True, stable_double_read=not reads.count_drift,
                owning_count_changed=reads.count_drift)
            if npc_action is not None: result['npc_action'] = npc_action
            self._last_completed = time.monotonic_ns()
        except Exception as error:
            result['reason'] = observe.reason(error)
        finally:
            result['typed_bytes_requested'] = sampler.total
            sampler.bytes, sampler.read_limit = previous
            self.last_result = result
        return result


PREPARE_METHOD = PlayerLifeObserver.prepare
COLLECT_METHOD = PlayerLifeObserver.collect
