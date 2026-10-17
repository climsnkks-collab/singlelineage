"""Main-owned diagnostic coordinator. Only public command files; no UI APIs."""
import argparse
import asyncio
import copy
from contextlib import contextmanager
import json
from pathlib import Path
import sys
import threading
import time

from tools.local_original_session import launcher
from tools.local_original_session.commands import _atomic as _source_atomic, REQUEST_SCHEMA
from tools.local_original_session.ipc_files import read_shared_text

ipc_lock = threading.RLock()


def _atomic(path, row, limit):
    with ipc_lock:
        return _source_atomic(path, row, limit)


def read_text(path, limit=65536):
    with ipc_lock:
        return read_shared_text(path, limit)

parser = argparse.ArgumentParser()
parser.add_argument('run_name')
parser.add_argument('--scenario', choices=('login-hold', 'login-quit', 'world-move-hold',
                                          'world-quit', 'world-move-quit', 'world-probe-quit'),
                    default='login-hold')
parser.add_argument('--product', default='sibling-internal-command')
parser.add_argument('--dx', type=int, choices=(-1, 0, 1), default=1)
parser.add_argument('--dy', type=int, choices=(-1, 0, 1), default=0)
parser.add_argument('--probe-requested-edge', action='store_true')
parser.add_argument('--wait-action-ready', action='store_true')
parser.add_argument('--choose-clear-neighbor', action='store_true')
parser.add_argument('--hold-world-seconds', type=float, default=0)
parser.add_argument('--move-steps', type=int, choices=range(1, 33), default=1)
parser.add_argument('--idle-world-seconds', type=float, default=0)
args = parser.parse_args()
if not 0 <= args.hold_world_seconds <= 120:
    raise SystemExit('WORLD_HOLD_BOUND_REQUIRED')
if not 0 <= args.idle_world_seconds <= 120:
    raise SystemExit('WORLD_IDLE_BOUND_REQUIRED')
if args.scenario != 'world-move-quit' and (args.move_steps != 1 or args.idle_world_seconds != 0):
    raise SystemExit('MULTISTEP_IDLE_REQUIRES_WORLD_MOVE_QUIT')
if args.dx == 0 and args.dy == 0:
    raise SystemExit('NONZERO_GOAL_DELTA_REQUIRED')
if not args.run_name.replace('-', '').isalnum():
    raise SystemExit('INVALID_RUN_NAME')
root = launcher.ROOT
directory = root / 'work/local_original_session/runs' / args.run_name
done = threading.Event()
driver = dict(schema='internal-scenario-v1', scenario=args.scenario, requests=[],
              goal_delta=[args.dx, args.dy], probe_requested_edge=args.probe_requested_edge,
              wait_action_ready=args.wait_action_ready,
              choose_clear_neighbor=args.choose_clear_neighbor,
              hold_world_seconds=args.hold_world_seconds,
              move_steps=args.move_steps, idle_world_seconds=args.idle_world_seconds,
              screenshot_count=0, mouse_or_focus_api=False)


class RequestedEdgeProbe:
    """Coordinator-only observation before submission; never a command gate."""
    def __init__(self, directory):
        self.directory, self.thread_id = directory, threading.get_ident()
        self.edge, self.published, self.seen, self.error_type = None, None, set(), None
        self.neighbors_key = None

    def neighbors(self, owner, public):
        if self.edge is None or self.edge.reader.owner is not owner:
            return
        scene, world = public.get('memory', {}).get('scene', {}), public.get('memory', {}).get('world', {})
        move_state = public.get('memory', {}).get('move_state')
        rows = public.get('broker', {}).get('movement', {}).get('sessions', [])
        uid, map_id, grid = world.get('my_player_uid'), world.get('map_resolved_i32'), world.get('grid_words')
        if not (public.get('state') == 'RUNNING' and scene.get('status') == 'OBSERVED'
                and scene.get('current') == 'Land' and scene.get('pending') == 'none'
                and scene.get('root_ready') is True and world.get('status') == 'OBSERVED'
                and world.get('scene') == 'Land' and world.get('stable_double_read') is True
                and type(uid) is int and 0 < uid <= 0xffffffffffffffff
                and type(map_id) is int and 0 <= map_id <= 0x7fffffff
                and world.get('map_requested_i32') == map_id and type(grid) is list and len(grid) == 2
                and all(type(n) is int and 0 <= n <= 65535 for n in grid)
                and len(rows) == 1 and rows[0].get('fatal') is False and rows[0].get('closed') is False
                and rows[0].get('authority') == dict(uid=uid, map_id=map_id, grid=grid)
                and source_action_ready(move_state, 0)):
            return
        if threading.get_ident() != self.thread_id:
            return
        # Cache only for the current authority start, with one refresh when stale.
        # Revisited starts and an idle-to-ready transition must not reuse old tile reads.
        key = (uid, map_id, *grid)
        if self.neighbors_key is not None and self.neighbors_key[0] == key and time.monotonic() - self.neighbors_key[1] < 1.0:
            return
        self.neighbors_key = (key, time.monotonic())
        row = dict(scope='REQUESTED_NEIGHBOR_TILE_ONLY_NOT_CLIENT_SELECTION', uid=uid, map_id=map_id,
                   start_grid=list(grid), status='UNKNOWN', stable_double_read=False, directions=[])
        try:
            asyncio.get_running_loop()
            if owner.validate(owner.child) is not True:
                raise ValueError('NEIGHBOR_CURRENT_OWNER_REQUIRED')
            result = self.edge.tile_neighbors(uid, map_id, (grid[1] << 16) | grid[0])
            if (result.get('uid') != uid or result.get('map_id') != map_id
                    or result.get('start_grid') != grid or result.get('status') not in
                    ('OBSERVED', 'OBSERVED_PARTIAL', 'UNKNOWN')):
                raise ValueError('NEIGHBOR_RESULT_BINDING_REQUIRED')
            # The producer's bounded scalar contract exposes no addresses.
            for key in ('status', 'reason', 'stable_double_read', 'typed_bytes_requested',
                        'source_code_bytes_requested', 'unique_cells_read', 'unique_segments_read',
                        'byte_limit', 'source_code_bytes_planned', 'refused_read_bytes',
                        'shortfall_at_refused_read', 'required_total_bytes', 'total_shortfall_bytes',
                        'client_direction_selection', 'occupancy', 'full_passability'):
                if key in result: row[key] = result[key]
            directions = result.get('directions')
            if type(directions) is not list or len(directions) != 8:
                raise ValueError('NEIGHBOR_EIGHT_RESULTS_REQUIRED')
            for item in directions:
                row['directions'].append({key: item.get(key) for key in
                    ('direction', 'status', 'reason', 'grid_target', 'flags_u16', 'blocked')})
        except Exception as error:
            row.update(status='UNKNOWN', stable_double_read=False, directions=[],
                       error_type=type(error).__name__[:64])
        try:
            _atomic(self.directory / 'neighbors-probe.json', row, 8192)
        except Exception as error:
            self.error_type = type(error).__name__[:64]

    def probe(self, handler, request):
        sequence = request.get('sequence')
        if (request.get('command') != 'MoveGoal' or type(sequence) is not int
                or not 1 <= sequence <= 2147483647 or sequence in self.seen or len(self.seen) >= 32):
            return
        self.seen.add(sequence)
        row = dict(scope='REQUESTED_DIRECTION_READONLY_NOT_CLIENT_SELECTION', uid=None, map=None,
                   start_grid=None, target_grid=None, direction=None, result='UNKNOWN', metadata={})
        try:
            def need(value, reason):
                if not value: raise ValueError(reason)
            need(threading.get_ident() == self.thread_id, 'PROBE_MAIN_THREAD_REQUIRED')
            asyncio.get_running_loop()
            need(set(request) == {'schema', 'sequence', 'command', 'uid', 'x', 'y'}
                 and request['schema'] == REQUEST_SCHEMA and sequence > handler.last_sequence,
                 'PROBE_FRESH_REQUEST_REQUIRED')
            uid, target = request['uid'], [request['x'], request['y']]
            need(type(uid) is int and 0 < uid <= 0xffffffffffffffff
                 and all(type(n) is int and 0 <= n <= 65535 for n in target), 'PROBE_UID_GOAL_REQUIRED')
            row.update(uid=uid, target_grid=target)
            need(self.edge is not None and self.published is not None, 'PROBE_BINDING_UNKNOWN')
            owner, stamp, public = self.published
            need(owner is handler.owner and self.edge.reader.owner is owner
                 and 0 <= time.monotonic() - stamp <= 1.5, 'PROBE_FRESH_PUBLISHED_OWNER_REQUIRED')
            scene, world = public.get('memory', {}).get('scene', {}), public.get('memory', {}).get('world', {})
            need(public.get('state') == 'RUNNING' and scene.get('status') == 'OBSERVED'
                 and scene.get('current') == 'Land' and scene.get('pending') == 'none'
                 and scene.get('root_ready') is True and world.get('status') == 'OBSERVED'
                 and world.get('scene') == 'Land' and world.get('stable_double_read') is True,
                 'PROBE_FRESH_LAND_WORLD_REQUIRED')
            start, map_id = world.get('grid_words'), world.get('map_resolved_i32')
            need(type(start) is list and len(start) == 2
                 and all(type(n) is int and 0 <= n <= 65535 for n in start)
                 and world.get('my_player_uid') == uid and type(map_id) is int
                 and 0 <= map_id <= 0x7fffffff and world.get('map_requested_i32') == map_id,
                 'PROBE_WORLD_UID_MAP_GRID_REQUIRED')
            rows = public.get('broker', {}).get('movement', {}).get('sessions', [])
            need(len(rows) == 1 and rows[0].get('fatal') is False and rows[0].get('closed') is False
                 and rows[0].get('authority') == dict(uid=uid, map_id=map_id, grid=start),
                 'PROBE_BACKEND_AUTHORITY_REQUIRED')
            row.update(map=map_id, start_grid=list(start))
            directions = []
            for direction in range(8):
                try:
                    if self.edge.tile.map_step(start, direction)['grid_target'] == target:
                        directions.append(direction)
                except ValueError:
                    pass  # A boundary direction can be outside the original u16 grid.
            need(len(directions) == 1, 'PROBE_ADJACENT_DIRECTION_UNKNOWN')
            row['direction'] = directions[0]
            handler._identity()  # Existing retained primary identity/source guard.
            previous = self.edge.last_result
            try:
                result = self.edge(uid, map_id, (start[1] << 16) | start[0], row['direction'],
                                   (target[1] << 16) | target[0])
                metadata = self.edge.last_result
                reason = metadata.get('reason')
                row['metadata'] = dict(status=metadata.get('status') if metadata.get('status') in
                    ('CLEAR_EMPTY_SUBSET', 'CLEAR_OWN_SELF_SUBSET', 'BLOCKED_MASK1', 'UNKNOWN') else 'UNKNOWN',
                    reason=reason if type(reason) is str and len(reason) <= 96
                    and reason.replace('_', '').isalnum() else None,
                    typed_bytes_requested=metadata.get('typed_bytes_requested') if
                    type(metadata.get('typed_bytes_requested')) is int
                    and 0 <= metadata['typed_bytes_requested'] <= 32768 else None)
                row['result'] = (metadata.get('status') if result is True and metadata.get('status') in
                                 ('CLEAR_EMPTY_SUBSET', 'CLEAR_OWN_SELF_SUBSET') else
                                 'BLOCKED_MASK1' if result is False else 'UNKNOWN')
            finally:
                self.edge.last_result = previous
        except Exception as error:
            row['result'] = 'UNKNOWN'
            row['metadata'] = dict(error_type=type(error).__name__[:64])
            if type(error) is ValueError and len(error.args) == 1 and str(error.args[0]).startswith('PROBE_'):
                row['metadata']['reason'] = error.args[0]
        try:
            _atomic(self.directory / 'requested-edge-probe.json',
                    dict(sequence=sequence, requested_edge_probe=row), 4096)
        except Exception as error:
            self.error_type = type(error).__name__[:64]

    @contextmanager
    def installed(self, enabled, choose_clear=False):
        from tools.local_original_session import edge, commands, observe
        original_init, original_submit, original_publish = (edge.EdgeAdapter.__init__,
            commands.CommandRequests._submit, observe.SessionMonitor.publish)
        original_atomic = commands._atomic
        probe = self
        def edge_init(adapter, *args, **kwargs):
            original_init(adapter, *args, **kwargs)
            probe.edge = adapter
        def publish(monitor, public):
            # Force publication on each actual memory sample even when its fields
            # are unchanged; a file timestamp alone must not revive a cached sample.
            public['scenario_observation_sample'] = monitor.samples
            with ipc_lock:
                published = original_publish(monitor, public)
            if enabled:
                probe.published = (monitor.owner, time.monotonic(), copy.deepcopy({
                    'state': published.get('state'), 'memory': {key: published.get('memory', {}).get(key)
                        for key in ('scene', 'world')},
                    'broker': {'movement': published.get('broker', {}).get('movement')}}))
            if choose_clear:
                probe.neighbors(monitor.owner, published)
            return published
        def submit(handler, request, fingerprint):
            probe.probe(handler, request)
            return original_submit(handler, request, fingerprint)
        if enabled or choose_clear: edge.EdgeAdapter.__init__ = edge_init
        if enabled: commands.CommandRequests._submit = submit
        commands._atomic = _atomic
        observe.SessionMonitor.publish = publish
        try:
            yield self
        finally:
            edge.EdgeAdapter.__init__, commands.CommandRequests._submit = original_init, original_submit
            commands._atomic = original_atomic
            observe.SessionMonitor.publish = original_publish
            self.edge, self.published = None, None


def collect_edge_probe():
    probe = read(directory / 'requested-edge-probe.json')
    for item in driver['requests']:
        if item['sequence'] == probe.get('sequence') and 'requested_edge_probe' not in item:
            item['requested_edge_probe'] = probe.get('requested_edge_probe')


def grid_valid(value):
    return (type(value) is list and len(value) == 2
            and all(type(n) is int and 0 <= n <= 65535 for n in value))


def movement_counters_valid(snapshot):
    """Saturated/missing diagnostic counters cannot prove an event delta."""
    return (type(snapshot) is dict and all(type(snapshot.get(key)) is int
            and 0 <= snapshot[key] < (1 << 64) - 1
            for key in ('committed', 'requests_received', 'corrections_prepared'))
            and type(snapshot.get('memory_sample')) is int
            and 0 < snapshot['memory_sample'] < (1 << 64) - 1)


def movement_snapshot(status, status_age):
    """Fresh stable selected Land state. No renderer or busy-call claim."""
    scene = status.get('memory', {}).get('scene', {})
    world = status.get('memory', {}).get('world', {})
    move = status.get('memory', {}).get('move_state', {})
    rows = status.get('broker', {}).get('movement', {}).get('sessions', [])
    if not (0 <= status_age <= 1.5 and status.get('state') == 'RUNNING'
            and scene.get('status') == 'OBSERVED' and scene.get('current') == 'Land'
            and scene.get('pending') == 'none' and scene.get('root_ready') is True
            and world.get('status') == 'OBSERVED' and world.get('scene') == 'Land'
            and world.get('stable_double_read') is True and type(move) is dict
            and move.get('status') == 'OBSERVED' and move.get('stable_double_read') is True
            and move.get('source_contract_valid') is True
            and type(rows) is list and len(rows) == 1 and type(rows[0]) is dict):
        return None
    row = rows[0]
    authority, transform = row.get('authority', {}), move.get('transform', {})
    character = move.get('character_data', {})
    uid, map_id, grid = authority.get('uid'), authority.get('map_id'), authority.get('grid')
    if not (row.get('fatal') is False and row.get('closed') is False
            and type(row.get('connection_id')) is int and row['connection_id'] > 0
            and type(row.get('committed')) is int and row['committed'] >= 0
            and type(uid) is int and 0 < uid <= 0xffffffffffffffff
            and type(map_id) is int and 0 <= map_id <= 0x7fffffff and grid_valid(grid)
            and world.get('my_player_uid') == uid and move.get('actor_uid') == uid
            and character.get('status') == 'OBSERVED' and character.get('own_uid') == uid
            and character.get('own_uid_matches_actor') is True
            and world.get('map_requested_i32') == world.get('map_resolved_i32') == map_id
            and world.get('grid_words') == grid and transform.get('status') == 'OBSERVED'
            and transform.get('current_grid') == transform.get('predicted_grid') == grid
            and type(status.get('memory_samples')) is int and status['memory_samples'] > 0
            and status.get('scenario_observation_sample') == status['memory_samples']):
        return None
    snapshot = dict(connection_id=row['connection_id'], uid=uid, map_id=map_id, grid=list(grid),
                committed=row['committed'], requests_received=row.get('requests_received'),
                corrections_prepared=row.get('corrections_prepared'),
                memory_sample=status['memory_samples'], last_result=row.get('last_result'))
    snapshot['counter_evidence'] = 'OBSERVED_UNSATURATED' if movement_counters_valid(snapshot) else 'UNKNOWN'
    return snapshot


def move_returned(request, returned):
    return (type(request.get('sequence')) is int and request.get('command') == 'MoveGoal'
            and type(returned.get('sequence')) is int
            and returned['sequence'] == request['sequence']
            and returned.get('native_command') == 4 and returned.get('status') == 'RETURNED'
            and returned.get('invoked') is True)


def move_step_ready(status, request, returned, status_age):
    before, after = request.get('movement_before', {}), movement_snapshot(status, status_age)
    if not (movement_counters_valid(before) and movement_counters_valid(after)
            and move_returned(request, returned)):
        return False
    return (all(after.get(key) == before.get(key) for key in ('connection_id', 'uid', 'map_id'))
            and after['uid'] == request.get('uid')
            and after['grid'] == [request.get('x'), request.get('y')]
            and grid_valid(before.get('grid'))
            and max(abs(after['grid'][i] - before['grid'][i]) for i in range(2)) == 1
            and type(before.get('committed')) is int and after['committed'] == before['committed'] + 1
            and after['requests_received'] == before['requests_received'] + 1
            and after['corrections_prepared'] == before['corrections_prepared']
            and type(before.get('memory_sample')) is int and after['memory_sample'] > before['memory_sample'])


def requested_probe_outcome(status, request, returned, status_age):
    """Classify source-goal settling using received/prepared service counters.

    A prepared correction is not evidence of transport or client consumption.
    """
    before, after = request.get('movement_before', {}), movement_snapshot(status, status_age)
    if not (movement_counters_valid(before) and movement_counters_valid(after)
            and move_returned(request, returned)):
        return 'UNKNOWN'
    move = status['memory']['move_state']
    nav, controller = move.get('navigation', {}), move.get('controller', {})
    target = [request.get('x'), request.get('y')]
    settled = (all(after.get(key) == before.get(key) for key in
                ('connection_id', 'uid', 'map_id', 'grid', 'committed'))
            and after['uid'] == request.get('uid')
            and type(before.get('memory_sample')) is int and after['memory_sample'] > before['memory_sample']
            and grid_valid(target) and max(abs(target[i] - after['grid'][i]) for i in range(2)) == 1
            and nav.get('status') == 'OBSERVED' and nav.get('active') is False
            and nav.get('target_grid') == target and controller.get('status') == 'OBSERVED'
            and (controller.get('command_present') is False or
                 controller.get('command_present') is True and
                 controller.get('command_owner_uid') == after['uid'] and controller.get('goal_grid') == target))
    if not settled:
        return 'UNKNOWN'
    received = after['requests_received'] - before['requests_received']
    prepared = after['corrections_prepared'] - before['corrections_prepared']
    if received == prepared == 0:
        return 'CLIENT_GOAL_SETTLED_NO_CS'
    result = after.get('last_result')
    authority = dict(uid=after['uid'], map_id=after['map_id'], grid=after['grid'])
    if (received == prepared == 1 and type(result) is dict
            and result.get('accepted') is False and result.get('fatal') is False
            and result.get('reason') in ('STALE_START', 'DIRECTION_0_TO_7_REQUIRED', 'GRID_BOUNDARY',
                                          'EDGE_BLOCKED', 'EDGE_UNKNOWN')
            and type(result.get('reply_count')) is int and result['reply_count'] == 1
            and type(result.get('own_SC4E2C_count')) is int and result['own_SC4E2C_count'] == 0
            and result.get('authority') == authority):
        return 'SERVER_CORRECTION_PREPARED_POSITION_UNCHANGED'
    return 'UNKNOWN'


def requested_probe_quit_ready(status, request, returned, status_age):
    return requested_probe_outcome(status, request, returned, status_age) != 'UNKNOWN'


def idle_observe(previous, snapshot, now, seconds):
    """Consecutive fresh unchanged received/prepared/commit/position samples."""
    keys = ('connection_id', 'uid', 'map_id', 'grid', 'committed',
            'requests_received', 'corrections_prepared')
    if not movement_counters_valid(snapshot):
        return None, False
    if previous is None or any(previous['anchor'].get(key) != snapshot.get(key) for key in keys):
        previous = dict(anchor=snapshot, started=now, last_at=now, last_sample=snapshot['memory_sample'],
                        observations=1, elapsed_seconds=0, wire_activity='UNKNOWN',
                        cs4e2b_received_delta=0, corrections_prepared_delta=0,
                        correction_consumption='UNKNOWN')
    elif snapshot['memory_sample'] > previous['last_sample']:
        if now - previous['last_at'] > 1.5:
            return idle_observe(None, snapshot, now, seconds)
        previous = dict(previous, last_at=now, last_sample=snapshot['memory_sample'],
                        observations=previous['observations'] + 1,
                        elapsed_seconds=round(now - previous['started'], 6))
    return previous, (seconds == 0 or previous['observations'] >= 2
                      and previous['elapsed_seconds'] >= seconds and now - previous['last_at'] <= 1.5)


def source_action_ready(move_state, status_age):
    if type(move_state) is not dict:
        return False
    action = move_state.get('action', {})
    evaluated = action.get('busy_source_eval', {})
    return (0 <= status_age <= 1.5 and move_state.get('status') == 'OBSERVED'
        and move_state.get('stable_double_read') is True
        and move_state.get('source_contract_valid') is True
        and action.get('status') == 'OBSERVED' and evaluated.get('status') == 'EVALUATED'
        and evaluated.get('value') is False and evaluated.get('actual_call_observed') is False)


def neighbor_choice(probe, uid, map_id, grid, preferred, age):
    if (type(probe) is not dict or probe.get('scope') != 'REQUESTED_NEIGHBOR_TILE_ONLY_NOT_CLIENT_SELECTION'
            or probe.get('uid') != uid or probe.get('map_id') != map_id
            or probe.get('start_grid') != grid):
        return 'WAIT', None
    if not 0 <= age <= 1.5:
        return 'STALE', None
    if probe.get('status') not in ('OBSERVED', 'OBSERVED_PARTIAL') or probe.get('stable_double_read') is not True:
        return 'NO_CLEAR', None
    directions = probe.get('directions')
    if (type(directions) is not list or len(directions) != 8
            or not all(type(item.get('direction')) is int for item in directions)
            or {item.get('direction') for item in directions} != set(range(8))):
        return 'NO_CLEAR', None
    clear = [item for item in directions if item.get('status') == 'OBSERVED' and item.get('blocked') is False
             and type(item.get('grid_target')) is list and len(item['grid_target']) == 2
             and all(type(n) is int and 0 <= n <= 65535 for n in item['grid_target'])]
    if not clear:
        return 'NO_CLEAR', None
    clear.sort(key=lambda item: (item['grid_target'] != preferred, item['direction']))
    return 'SELECTED', clear[0]


def persist_driver():
    with ipc_lock:
        (directory / 'scenario.json').write_text(json.dumps(driver, indent=2), encoding='utf-8')


def read(path):
    try:
        return json.loads(read_text(path))
    except (OSError, ValueError):
        return {}

def quit_diagnostic_filename(sequence, product):
    """Product policy selects the diagnostic basename; context has no mode."""
    if type(sequence) is not int or not 1 <= sequence <= 2147483647 or type(product) is not dict:
        return None
    mode = product.get('command_result_mode')
    if mode is None:
        return 'command-result.json'
    if type(mode) is str and mode == 'immutable-sequence-v1':
        return 'command-result-' + str(sequence) + '.json'
    return None


def quit_diagnostic_metadata(sequence, context, native):
    """Only identity-bound quit telemetry; coordinator still owns command status."""
    if not (type(sequence) is int and 1 <= sequence <= 2147483647
            and type(context) is dict and context.get('schema') == 'own-key-invoke-primary-v1'
            and type(native) is dict and native.get('schema') == 'own-internal-command-result-v1'):
        return None
    pid, birth, candidate = (context.get(key) for key in ('pid', 'birth', 'candidate_sha256'))
    if not (type(pid) is int and 1 <= pid <= 0xffffffff
            and type(birth) is int and 1 <= birth <= 0xffffffffffffffff
            and type(candidate) is str and len(candidate) == 64
            and all(char in '0123456789abcdef' for char in candidate)
            and type(native.get('seq')) is int and native['seq'] == sequence
            and all(type(native.get(key)) is type(value) and native[key] == value
                    for key, value in (('pid', pid), ('birth', birth), ('candidate_sha256', candidate)))):
        return None
    return {key: value for key, value in native.items() if type(key) is str and key.startswith('quit_')}


def control():
    sent = set()
    collected = set()
    land_since = None
    idle = None
    try:
        while not done.wait(.1):
            collect_edge_probe()
            previous = read(directory / 'command.result.json')
            sequence = previous.get('sequence')
            if (previous.get('status') in ('RETURNED', 'REFUSED', 'UNSUPPORTED', 'UNKNOWN')
                    and previous.get('reason') != 'COMMAND_CLAIMED_NO_RETRY'
                    and sequence in {item['sequence'] for item in driver['requests']} and sequence not in collected):
                entry = {key: previous.get(key) for key in ('sequence', 'status', 'invoked', 'native_reason')}
                try:
                    boundary = Path(read_text(directory / 'boundary-path.txt', 1024).strip())
                    filename = quit_diagnostic_filename(sequence, launcher.PRODUCTS.get(args.product))
                    if filename is not None:
                        context, native = read(boundary / 'context.json'), read(boundary / filename)
                        metadata = quit_diagnostic_metadata(sequence, context, native)
                        if metadata is not None:
                            entry['native'] = metadata
                except OSError:
                    pass
                driver.setdefault('results', []).append(entry)
                collected.add(sequence)
                persist_driver()
            with ipc_lock:
                status = read(directory / 'status.json')
                status_age = time.time() - (directory / 'status.json').stat().st_mtime if status else float('inf')
            scene = status.get('memory', {}).get('scene', {})
            if not (scene.get('status') == 'OBSERVED' and scene.get('pending') == 'none'
                    and scene.get('root_ready') is True and status.get('state') == 'RUNNING'):
                idle = None
                continue
            world = status.get('memory', {}).get('world', {})
            move_state = status.get('memory', {}).get('move_state')
            if scene.get('current') == 'Land' and type(move_state) is dict:
                samples = driver.setdefault('move_samples', [])
                if len(samples) < 32 and (not samples or samples[-1]['state'] != move_state):
                    samples.append(dict(after_sequence=len(driver['requests']), state=move_state))
                    persist_driver()
            if scene.get('current') == 'Land' and world.get('status') == 'OBSERVED' and 'world_observed' not in driver:
                land_since = time.monotonic()
                driver['world_observed'] = {key: world.get(key) for key in (
                    'status', 'scene', 'my_player_uid', 'grid_words', 'map_requested_i32',
                    'map_resolved_i32', 'render_ready', 'stable_double_read')}
                persist_driver()
            try:
                boundary = Path(read_text(directory / 'boundary-path.txt', 1024).strip())
            except OSError:
                continue
            bridge = read(boundary / 'command-bridge.json')
            if not (bridge.get('ready') is True and bridge.get('background_guard_installed') is True
                    and bridge.get('protected_exports') == 18):
                continue
            command, uid, x, y, role = None, 0, 0, 0, None
            if scene.get('current') == 'Login' and not sent:
                command = 'Quit' if args.scenario == 'login-quit' else 'LoginOK'
            elif (scene.get('current') == 'CharacterSelect' and sent == {'LoginOK'}
                  and args.scenario.startswith('world-')):
                command = 'Select'
            elif (scene.get('current') == 'Land' and sent == {'LoginOK', 'Select'}
                  and args.scenario == 'world-quit'):
                if args.hold_world_seconds and (land_since is None or
                        time.monotonic() - land_since < args.hold_world_seconds):
                    continue
                command, role = 'Quit', 'QuitRequest'
            elif (scene.get('current') == 'Land' and sent in
                  ({'LoginOK', 'Select'}, {'LoginOK', 'Select', 'MoveGoal'})
                  and args.scenario in ('world-move-hold', 'world-move-quit', 'world-probe-quit')):
                moves = [item for item in driver['requests'] if item['command'] == 'MoveGoal']
                completed = driver.setdefault('move_steps_completed', [])
                snapshot = movement_snapshot(status, status_age)
                if snapshot is not None and not movement_counters_valid(snapshot):
                    observation = dict(status='UNKNOWN', reason='MOVEMENT_COUNTERS_MISSING_INVALID_OR_SATURATED',
                                       action='WAIT_NO_MOVEGOAL_OR_COMPLETION_CLAIM')
                    if driver.get('movement_event_observation') != observation:
                        driver['movement_event_observation'] = observation
                        persist_driver()
                    idle = None
                    continue
                returned = read(directory / 'command.result.json')
                if moves:
                    latest = moves[-1]
                    converged = move_step_ready(status, latest, returned, status_age)
                    probe_outcome = (requested_probe_outcome(status, latest, returned, status_age)
                                     if args.scenario == 'world-probe-quit' else 'UNKNOWN')
                    probe_settled = probe_outcome != 'UNKNOWN'
                    if not converged and not probe_settled:
                        idle = None
                        continue
                    if len(completed) < len(moves):
                        completed.append(dict(step=len(moves), sequence=latest['sequence'],
                            outcome='EXACT_TARGET_COMMIT_ONCE' if converged else
                                    probe_outcome,
                            before=latest['movement_before'], after=snapshot,
                            returned=dict(sequence=returned['sequence'], status=returned['status'],
                                          invoked=returned['invoked'], native_command=returned['native_command']),
                            requested_edge_probe=latest.get('requested_edge_probe'),
                            source_goal=dict(controller=move_state.get('controller'),
                                             navigation=move_state.get('navigation')),
                            wire_activity='UNKNOWN',
                            observation_scope='SAME_SERVICE_COUNTER_INTERVAL_BETWEEN_FRESH_OBSERVED_SAMPLES',
                            notes='No claim about later sends or official client block cause',
                            event_counter_scope='PER_SERVICE_RECEIVED_PREPARED_NOT_TRANSPORT_OR_CONSUMPTION',
                            correction_consumption='UNKNOWN'))
                        persist_driver()
                    if args.scenario == 'world-probe-quit':
                        command, role = 'Quit', 'QuitRequest'
                    elif args.scenario == 'world-move-hold':
                        continue
                    elif len(moves) >= args.move_steps:
                        idle, ready = idle_observe(idle, snapshot, time.monotonic(), args.idle_world_seconds)
                        # No further agent MoveGoal is queued during this window.
                        if not ready:
                            continue
                        driver['idle_world_observed'] = dict(idle,
                            scope='UNCHANGED_REQUESTS_CORRECTIONS_COMMIT_AUTHORITY_CURRENT_PREDICTED_SAMPLES',
                            requested_seconds=args.idle_world_seconds, agent_movegoal_requests=0,
                            opcode_4e2b_count='UNKNOWN')
                        command, role = 'Quit', 'QuitRequest'
                if command is None:
                    if snapshot is None:
                        continue
                    if (moves or args.wait_action_ready or args.choose_clear_neighbor) and not source_action_ready(move_state, status_age):
                        continue
                    target = [snapshot['grid'][0] + args.dx, snapshot['grid'][1] + args.dy]
                    if not grid_valid(target):
                        continue
                    if args.choose_clear_neighbor:
                        with ipc_lock:
                            probe = read(directory / 'neighbors-probe.json')
                            probe_age = time.time() - (directory / 'neighbors-probe.json').stat().st_mtime if probe else float('inf')
                        outcome, chosen = neighbor_choice(probe, snapshot['uid'], snapshot['map_id'],
                                                          snapshot['grid'], target, probe_age)
                        if outcome in ('WAIT', 'STALE'):
                            continue  # The retained observer can refresh this authority start.
                        driver.update(neighbor_probe=probe, neighbor_probe_outcome=outcome)
                        persist_driver()
                        if outcome == 'NO_CLEAR':
                            if args.scenario != 'world-probe-quit':
                                continue
                            driver['probe_outcome'] = 'NO_CLEAR_NEIGHBOR_NO_MOVE_SUBMITTED'
                            command, role = 'Quit', 'QuitRequest'
                        else:
                            target = chosen['grid_target']
                            driver['neighbor_probe_selected_direction'] = chosen['direction']
                    if command is None:
                        command, uid, x, y = 'MoveGoal', snapshot['uid'], *target
            elif scene.get('current') == 'Quit' and 'QuitRequest' in sent and 'QuitCredit' not in sent:
                command, role = 'Quit', 'QuitCredit'
            if command is None or launcher_command(command) not in bridge.get('supported_commands', []):
                continue
            previous = read(directory / 'command.result.json')
            if sent and not (previous.get('status') == 'RETURNED' and previous.get('invoked') is True
                    and previous.get('sequence') == driver['requests'][-1]['sequence']):
                continue
            sequence = len(driver['requests']) + 1
            request = dict(schema=REQUEST_SCHEMA, sequence=sequence, command=command, uid=uid, x=x, y=y)
            _atomic(directory / 'command.request.json', request, 1024)
            sent.add(role or command)
            driver['requests'].append(dict(sequence=sequence, command=command,
                                            uid=uid, x=x, y=y, role=role, observed_scene=scene['current']))
            if command == 'MoveGoal' and type(move_state) is dict:
                driver['requests'][-1]['movement_before'] = snapshot
                action = move_state.get('action', {})
                driver['requests'][-1]['pre_submit_action'] = dict(
                    scope='READONLY_SNAPSHOT_NOT_ACTUAL_CALL',
                    current=action.get('current'), queue_count=action.get('queue_count'),
                    queue_head=action.get('queue_head'), busy_source_eval=action.get('busy_source_eval'))
            persist_driver()
    except Exception as error:
        driver.update(error_type=type(error).__name__, error=str(error)[:100])

def launcher_command(name):
    return {'LoginOK': 1, 'Select': 2, 'Quit': 3, 'MoveGoal': 4}[name]

sys.argv = ['launcher', '--run', '--control-mode', 'internal', '--product', args.product,
            '--image', str(root / 'work/standalone_boot/current-unmodified-clone/LC.guard.exe'),
            '--expected-uuid', 'a1416ea8-d0e1-4b93-b622-c27752ef6b51',
            '--store', str(root / 'work/local_original_session/test-profile/characters.json'),
            '--run-directory', str(directory)]
thread = threading.Thread(target=control, name='owned-internal-scenario', daemon=True)
thread.start()
try:
    with RequestedEdgeProbe(directory).installed(args.probe_requested_edge, args.choose_clear_neighbor) as edge_probe:
        code = launcher.main()
finally:
    done.set()
    thread.join()
    collect_edge_probe()
    if 'edge_probe' in globals() and edge_probe.error_type is not None:
        driver['requested_edge_probe_error_type'] = edge_probe.error_type
    if directory.exists():
        persist_driver()
raise SystemExit(code)
