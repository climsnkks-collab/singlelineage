"""Explicit own-player life consumer configuration and original-button host.

The named production policy and fixture policy are separate explicit labels.
Ordinary positive HP,
Restart/Reselect, NPC Contact and item consumers keep their existing contracts.
"""
from tools.local_original_session import feature_config, player_life

need = feature_config.need


def configuration(config):
    need(type(config) is feature_config.Features
         and type(config.player_life_policy) is player_life.Policy,
         'PLAYER_LIFE_EXACT_EXPLICIT_POLICY_REQUIRED')
    policy = config.player_life_policy
    need(policy.label in ('TEST_LOCAL_POLICY',
         'EXPLICIT_LOCAL_OWN_PLAYER_HP1_DEAD_RESTART_MAX_SAME_GRID_V1'),
         'PLAYER_LIFE_EXPLICIT_LOCAL_POLICY_LABEL_REQUIRED')
    need(all(getattr(config, key) is None for key in (
        'hp_status_input', 'npc_player_hit_policy', 'npc_player_hit_repeated_policy',
        'npc_approach_hit_policy', 'restart_policy', 'npc_death_policy',
        'npc_remove_policy', 'npc_respawn_policy')),
        'PLAYER_LIFE_EXCLUSIVE_CONSUMER_REQUIRED')
    return policy


def broker_options(config):
    policy = configuration(config)
    from tools.local_original_session import hp_status, npc_player_hit, npc_hp
    need(len(config.spawns) == 1 and config.interval_ns is not None
         and config.attack_policy == feature_config.ATTACK_INTENT_POLICY
         and type(config.attack_hp_provider) is npc_hp.ExplicitInputs,
         'PLAYER_LIFE_CURRENT_PROJECTOR_DEPENDENCIES_REQUIRED')
    # The current backend has no separate query-only constructor. These actual
    # services include their original guarded send APIs, but this product never
    # selects single/repeated user actions or invokes their4E31 producers.
    return dict(player_life_policy=policy, hp_status_policy=hp_status.POLICY,
                npc_player_hit_policy=npc_player_hit.POLICY)


class PlayerHpOnePreparation:
    """One original positive status operation, then actual same-own HP1.

    The caller schedules sample_one_locked in the existing monitor's16KiB
    2Hz due turn. No memory values, Store fields or ordinary once records are
    changed here except through the existing public status producer.
    """
    def __init__(self, broker, reader):
        from tools.local_original_session import broker as bm, hp_status, hp_status_observe
        need(type(broker) is bm.PersistentBroker and type(broker._hp_status) is hp_status.Service
             and broker._hp_status is broker.realm._hp_status,
             'PLAYER_LIFE_PREPARATION_REAL_HP_SERVICE_REQUIRED')
        self.broker, self.reader, self.service = broker, reader, broker._hp_status
        self.observer = hp_status_observe.StatusHpObserver(broker, reader)
        self.before = self.after = self.operation = self.writer = self.row = None
        self.started_ns = self.drained_ns = None
        self.claimed = self.context_claimed = False
        self.phase = 'NOT_REQUESTED'
        self.observation = None

    def _current_locked(self, writer):
        import time
        need(writer is self.writer and self.phase not in ('FAILED', 'NOT_REQUESTED')
             and self.row['operation_lock'].locked()
             and 0 <= time.monotonic_ns()-self.started_ns < 15_000_000_000,
             'PLAYER_LIFE_PREPARATION_CURRENT_BOUND_REQUIRED')
        need(self.broker._hp_status is self.broker.realm._hp_status is self.service
             and self.service._checked(writer, locked=True)[3] is self.row,
             'PLAYER_LIFE_PREPARATION_SERVICE_OR_SELECTION_CHANGED')
        self.reader.validate()
        return self.service.current(writer)

    async def update_once(self, writer):
        import time
        from tools.local_original_session import hp_status
        need(not self.claimed, 'PLAYER_LIFE_PREPARATION_ONCE_REQUIRED')
        self.claimed = True
        self.writer = writer
        self.row = self.service._checked(writer)[3]
        self.started_ns = time.monotonic_ns()
        self.phase = 'PREPARING'
        try:
            async with self.row['operation_lock']:
                self.before = self._current_locked(writer)
                need(type(self.before) is hp_status.Snapshot
                     and 1 < self.before.current_hp <= self.before.maximum_hp,
                     'PLAYER_LIFE_PREPARATION_POSITIVE_CURRENT_GT_ONE_REQUIRED')
            # This is the only update route. Its original row lock is internal.
            await self.broker.update_hp_status(writer, current_hp=1,
                maximum_hp=self.before.maximum_hp, expected_snapshot=self.before,
                expected_revision=self.before.revision, policy=hp_status.POLICY)
            self.drained_ns = time.monotonic_ns()
            async with self.row['operation_lock']:
                self.after = self._current_locked(writer)
                self.operation = self.service._operations.get(id(writer))
                need(self.operation is not None and self.operation.phase == 'DRAINED'
                     and self.operation.result.before is self.before
                     and self.operation.result.after is self.after
                     and self.after.current_hp == 1
                     and self.after.maximum_hp == self.before.maximum_hp
                     and self.after.revision == self.before.revision+1
                     and {k:v for k,v in self.after.fields.items() if k != 10}
                         == {k:v for k,v in self.before.fields.items() if k != 10},
                     'PLAYER_LIFE_PREPARATION_ORIGINAL_DRAINED_RESULT_REQUIRED')
            self.phase = 'WAIT_ACTUAL_HP1'
        except BaseException:
            self.phase = 'FAILED'
            raise

    async def sample_one_locked(self, writer, *, now_ns):
        need(self.phase == 'WAIT_ACTUAL_HP1', 'PLAYER_LIFE_PREPARATION_HP1_STAGE_REQUIRED')
        try:
            need(self._current_locked(writer) is self.after,
                 'PLAYER_LIFE_PREPARATION_SNAPSHOT_CHANGED')
            raw = await self.observer.sample(writer, now_ns=now_ns)
            self.observation = raw
            need(self._current_locked(writer) is self.after,
                 'PLAYER_LIFE_PREPARATION_SNAPSHOT_CHANGED')
            need(raw.get('status') == 'OBSERVED'
                 and raw.get('source_contract_valid') is True
                 and raw.get('source_owner_revalidated') is True
                 and raw.get('stable_double_read') is True
                 and raw.get('snapshot_atomic') is False
                 and raw.get('uid') == self.after.target_uid
                 and raw.get('map_id') == self.after.map_id
                 and raw.get('sample_monotonic_ns') == now_ns
                 and now_ns >= self.drained_ns
                 and raw.get('typed_byte_limit') == 16384
                 and type(raw.get('typed_bytes_requested')) is int
                 and 0 <= raw['typed_bytes_requested'] <= 16384,
                 'PLAYER_LIFE_PREPARATION_ACTUAL_OWN_HP_QUERY_REQUIRED')
            if (raw.get('current_hp'),raw.get('max_hp')) == (self.before.current_hp,self.before.maximum_hp):
                return False  # Bounded original setter wait; producer is never repeated.
            need((raw.get('current_hp'),raw.get('max_hp')) == (1,self.after.maximum_hp),
                 'PLAYER_LIFE_PREPARATION_ACTUAL_HP1_REQUIRED')
            self.phase = 'ACTUAL_HP1_CONFIRMED'
            return True
        except BaseException:
            self.phase = 'FAILED'
            raise

    async def life_context_once(self, writer, *, policy):
        need(self.phase == 'ACTUAL_HP1_CONFIRMED' and not self.context_claimed,
             'PLAYER_LIFE_PREPARATION_ACTUAL_HP1_CONTEXT_ONCE_REQUIRED')
        self.context_claimed = True
        try:
            async with self.row['operation_lock']:
                need(self._current_locked(writer) is self.after
                     and self.service._operations.get(id(writer)) is self.operation,
                     'PLAYER_LIFE_PREPARATION_ORDINARY_ONCE_RECORD_CHANGED')
            context = await self.broker.player_life_context(writer, policy=policy)
            async with self.row['operation_lock']:
                need(context.require_current_locked(writer) is self.row
                     and context.snapshot is self.after
                     and self.service._operations.get(id(writer)) is self.operation,
                     'PLAYER_LIFE_PREPARATION_LIFE_CONTEXT_CONTINUITY_REQUIRED')
            self.phase = 'LIFE_CONTEXT_ISSUED'
            return context
        except BaseException:
            self.phase = 'FAILED'
            raise

    def metadata(self):
        def value(snapshot):
            return None if snapshot is None else dict(current=snapshot.current_hp,
                maximum=snapshot.maximum_hp, revision=snapshot.revision)
        return dict(status=self.phase, before=value(self.before), after=value(self.after),
            method='PUBLIC_POSITIVE_FULL_STATUS_ONCE', actual_own_hp1=self.observation is not None
                and self.phase in ('ACTUAL_HP1_CONFIRMED','LIFE_CONTEXT_ISSUED'),
            npc_attack='NOT_REQUESTED', automatic_retry=False)


DEATH_PROFILE = 'sibling-background-player-death-recovery-spawn'
DEAD_DLL_SHA = 'a91192f93a46349ee4de977cfc08d37171126812b87bb6d7982bb37e60b8e5d5'
DEAD_DLL_PATH = ('work/local_original_session/implementation-2/combat-hp-death/'
                 'player-death-recovery/native-dead-restart/native/own-login-bridge-dg49.dll')


class SourceDeadRestartRequests:
    """One original-button request in the existing global Native sequence.

    Native RETURNED is joined to the unique real body0 route/ACK. Neither
    signal is new-life authority; the empty body encodes no sequence/epoch.
    """
    def __init__(self, requests, broker):
        from tools.local_original_session import launcher, manual_move_commands as manual, broker as bm
        need(type(requests) is launcher.ManualMoveRequests
             and type(requests.consumer) is manual.ManualMoveCommands
             and type(broker) is bm.PersistentBroker,
             'PLAYER_LIFE_REAL_MANUAL_REQUESTS_REQUIRED')
        self.requests,self.consumer,self.broker = requests,requests.consumer,broker
        self.reader = self.consumer.reader
        self.claimed = self.completed = False
        self.request = self.result = self.context = self.writer = self.row = None
        self.receipt = self.receipt_identity = self.event_start = None
        self.settings_before = self.started_ns = None
        self.state = 'NOT_REQUESTED'

    def _current_locked(self):
        import time
        from tools.local_original_session import launcher, manual_move_commands as manual
        need(type(self.requests) is launcher.ManualMoveRequests
             and self.requests.consumer is self.consumer
             and type(self.consumer) is manual.ManualMoveCommands
             and not self.requests._resources_closed and not self.requests.closed
             and not self.requests._polling and not self.consumer._busy
             and self.requests._inventory_request is None and self.requests._inventory_wait is None
             and self.consumer._readonly_pending is None
             and self.requests.pending is False and self.consumer.pending is None
             and self.reader is self.consumer.reader,
             'PLAYER_LIFE_NATIVE_INGRESS_NOT_QUIESCENT')
        need(self.context.require_current_locked(self.writer) is self.row
             and 0 <= time.monotonic_ns()-self.started_ns < 15_000_000_000,
             'PLAYER_LIFE_NATIVE_CURRENT_CONTEXT_REQUIRED')
        current = self.consumer._current()  # Owner/selection only; no alive idle/Action-ready gate.
        need(current[0].broker is self.broker and current[0].writer is self.writer
             and current[1] is self.row and current[3].uid == self.context.target_uid
             and current[3].map_id == self.context.map_id,
             'PLAYER_LIFE_NATIVE_CURRENT_SELECTED_WRITER_REQUIRED')
        return current

    def publish_locked(self, writer, context, result):
        import time
        from tools.local_original_session import manual_move_commands as manual, launcher
        need(not self.claimed,'PLAYER_LIFE_NATIVE_ONCE_REQUIRED')
        self.claimed = True
        try:
            self.writer,self.context,self.result = writer,context,result
            self.row = context.require_current_locked(writer)
            self.started_ns = time.monotonic_ns()
            result.require_current_locked(writer)
            need(type(context.target_uid) is int and 0<context.target_uid<=0xffffffff
                 and type(context.map_id) is int and -(1<<31)<=context.map_id<(1<<31),
                 'PLAYER_LIFE_NATIVE_UID_MAP_BOUNDS_REQUIRED')
            need(type(self.reader.owner) is launcher.NativeOwner,
                 'PLAYER_LIFE_NATIVE_ACTUAL_OWNER_REQUIRED')
            expected_profile = DEATH_PROFILE
            if type(self) is not SourceDeadRestartRequests:
                from tools.local_original_session import npc_player_lethal_recovery_focused as lethal
                need(type(self) is lethal.SourceDeadRestartRequests,
                     'PLAYER_LIFE_NATIVE_EXACT_HOST_TYPE_REQUIRED')
                expected_profile = lethal.PROFILE
            need(self.reader.owner.product == expected_profile and not self.reader.owner.internal
                 and self.reader.owner.background is True, 'PLAYER_LIFE_NATIVE_EXACT_PRODUCT_REQUIRED')
            current = self._current_locked()
            hwnd = self.consumer._window(current)
            boundary,identity = current[5],current[6]
            need(identity['candidate_sha256'] == self.reader.owner.image_sha,
                 'PLAYER_LIFE_NATIVE_IMAGE_CANDIDATE_REQUIRED')
            # Share the existing monotonic Native counter. Public AddInventory may
            # already have consumed a higher public sequence; never start a new1.
            floor = max(self.consumer.sequence,self.requests.sequence)
            need(type(floor) is int and 0 <= floor < manual.MAX_SEQUENCE,
                 'PLAYER_LIFE_NATIVE_SEQUENCE_EXHAUSTED')
            if not self.consumer._reservation:
                import os
                need(not any(os.path.lexists(boundary/(name+'-request.json'))
                             or any(boundary.glob(name+'-result-*.json')) for name in
                             ('manual-move','attack-target','source-quit','source-restart','source-dead-restart')),
                     'PLAYER_LIFE_NATIVE_BOUNDARY_PREVIOUSLY_USED')
                manual._create_once(boundary/'manual-move-adapter-owner.json',
                    dict(schema='own-manual-move-adapter-owner-v1',**identity))
                self.consumer._reservation = True
            self.consumer.sequence = floor+1
            sequence = self.consumer.sequence
            self.request = dict(schema='own-source-dead-restart-request-v1',**identity,
                seq=sequence,command='SourceDeadRestart',phase='DeadRestart',
                own_uid=context.target_uid,map_id=context.map_id)
            self.event_start = self.broker.policy.events
            self.settings_before = self.broker.realm.settings.committed
            manual._create_once(boundary/('manual-move-adapter-claim-'+str(sequence)+'.json'),
                dict(schema='own-manual-move-adapter-claim-v1',**identity,
                     seq=sequence,queued_monotonic_ns=self.started_ns))
            manual._create_once(boundary/'source-dead-restart-request.json',self.request)
            user = self.reader.owner.native.u
            message = int(user.RegisterWindowMessageW('LC-Owned-Manual-SourceDeadRestart-v1'))
            need(0xc000 <= message <= 0xffff,'PLAYER_LIFE_NATIVE_MESSAGE_REQUIRED')
            current = self._current_locked()
            need(self.consumer._window(current) == hwnd,'PLAYER_LIFE_NATIVE_WINDOW_CHANGED')
            self.state = 'WRITE_ATTEMPTED'
            need(user.PostMessageW(hwnd,message,sequence,0),'PLAYER_LIFE_NATIVE_POST_UNKNOWN')
            self.state = 'PENDING'
        except BaseException:
            self.state = 'UNKNOWN'
            raise

    def poll_locked(self):
        from tools.local_original_session import commands
        if self.completed:return True
        current = self._current_locked()
        need(self.request is not None and self.consumer.sequence == self.request['seq'],
             'PLAYER_LIFE_NATIVE_SEQUENCE_CHANGED')
        path = current[5]/('source-dead-restart-result-'+str(self.request['seq'])+'.json')
        try:raw = commands._closed_health_json(path)
        except (FileNotFoundError,UnicodeError):return False
        except __import__('json').JSONDecodeError:return False
        if raw is None:return False
        expected = dict(self.request,schema='own-source-dead-restart-result-v1')
        need(set(raw) == set(expected)|{'status','reason','invoked'}
             and all(type(raw.get(k)) is type(v) and raw[k] == v for k,v in expected.items())
             and raw['status'] == 'RETURNED' and type(raw['reason']) is int and raw['reason'] == 0
             and raw['invoked'] is True,'PLAYER_LIFE_NATIVE_WHOLE_RET_NOT_RETURNED')
        stat = commands._ordinary(path).stat()
        identity = stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns
        need(stat.st_size <= 1024 and (self.receipt is None
             or self.receipt == raw and self.receipt_identity == identity),
             'PLAYER_LIFE_NATIVE_IMMUTABLE_RECEIPT_CHANGED')
        self.receipt,self.receipt_identity = dict(raw),identity
        events = list(self.broker.policy.log)
        offset = self.event_start-(self.broker.policy.events-len(events))
        need(0 <= offset <= len(events),'PLAYER_LIFE_NATIVE_EVENTS_DROPPED')
        received = [(index,event) for index,event in enumerate(events[offset:])
                    if event[0] == 'rx' and event[1] == self.row['peer']['endpoint_port']]
        dead = [(i,e) for i,e in received if e[2] == 0x4eec]
        need(all(e[3] == 10 for _i,e in dead), 'PLAYER_LIFE_NATIVE_BODY0_REQUIRED')
        settings = [(i,e) for i,e in received if e[2] == 0x4ed6]
        need(len(dead) <= 1 and len(settings) <= 1
             and (not settings or not dead or settings[0][0] < dead[0][0])
             and self.broker.realm.settings.committed == self.settings_before+len(settings),
             'PLAYER_LIFE_NATIVE_OPTIONAL_SETTINGS_CORRELATION_CHANGED')
        if not dead or self.result.metadata()['stage'] != 'ACK_DRAINED':return False
        self.result.require_current_locked(self.writer)
        self.completed = True
        self.state = 'NATIVE_RETURNED_REAL_REQUEST_ACK_DRAINED'
        return True

    def metadata(self):
        return dict(status=self.state,sequence=None if self.request is None else self.request['seq'],
            native_returned=self.receipt is not None,actual_request_ack=self.completed,
            delayed_body0_epoch_identifiable=False,automatic_retry=False,
            oldlife_bound=self.context is not None,source_ui='CURRENT_TYPED_BINDING_ORIGINAL_CALLBACK_GUARDS',
            modal_visibility_pixels='UNKNOWN')
