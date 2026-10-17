"""Source-only MoveGoal candidate; game execution blocked: focus unresolved."""
if __name__ == '__main__':
    raise SystemExit('BACKGROUND_LAUNCH_UNVERIFIED')

import ctypes as C
import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('_manual_move_baseline', Path(__file__).with_name('run_manual_baseline_scenario.py'))
baseline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(baseline)
launcher, need = baseline.launcher, baseline.need
PROFILE = 'sibling-manual-move-once-spawn'
DLL_SHA = 'a28f93a2d9c61ce1a8a8c165a640ebb9ab162e3626842415a0a86955da6674a5'
MOVE_RESULT_SUPERVISION_SECONDS = 15  # Tool observation bound, not a game timeout.


def noactivate_launch(native, parent_create, startup_type):
    """Existing STARTUPINFO wrapper shape, on the original/default desktop."""
    original = native.k.CreateProcessW
    def create(*args):
        need(len(args) == 10 and args[5] & 4 and not args[4], 'MANUAL_SUSPENDED_LAUNCH_REQUIRED')
        startup = C.cast(args[8], C.POINTER(startup_type)).contents
        need(startup.cb == C.sizeof(startup_type) and not startup.desktop, 'DEFAULT_DESKTOP_STARTUP_REQUIRED')
        startup.flags |= 1  # STARTF_USESHOWWINDOW
        startup.show = 4  # SW_SHOWNOACTIVATE; later game-internal focus remains UNKNOWN.
        return original(*args)
    native.k.CreateProcessW = create
    try: return parent_create()
    finally: native.k.CreateProcessW = original


class MoveScenario(baseline.Scenario):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        need(not self.confirm_window_close, 'NO_QUIT_ENTER_TRIAL_IN_MOVE_RUN')
        self.path = self.monitor.directory / 'manual-move-scenario.json'
        self.move = dict(status='NOT_REQUESTED', initial=None, target=None, actual=None, saved=None,
                         native_result='UNKNOWN', cs4e2b_seen=False, alive_rx=False, alive_tx=False)
        self.move_started = self.move_service = self.move_writer = self.move_before = None
        self.move_event_start = 0

    def summary(self):
        return dict(super().summary(), manual_move=self.move,
                    startup_show='SW_SHOWNOACTIVATE_DEFAULT_DESKTOP', later_game_focus='UNKNOWN')

    def current_position(self, row, broker):
        services = list(broker.realm._movement.values())
        need(len(services) == 1, 'ONE_SELECTED_MOVE_SERVICE_REQUIRED')
        writer, service, _connection_id = services[0]
        position = service.snapshot()
        scene = row.get('memory', {}).get('scene', {})
        world = row.get('memory', {}).get('world', {})
        move = row.get('memory', {}).get('move_state', {})
        grid = (position.word0, position.word1)
        known = (scene.get('status') == 'OBSERVED' and scene.get('current') == 'Land'
                 and scene.get('pending') == 'none' and scene.get('root_ready') is True
                 and world.get('status') == 'OBSERVED' and world.get('stable_double_read') is True
                 and world.get('my_player_uid') == position.uid
                 and world.get('map_requested_i32') == world.get('map_resolved_i32') == position.map_id
                 and baseline.grid_pair(world.get('grid_words')) == grid
                 and move.get('status') == 'OBSERVED' and move.get('stable_double_read') is True
                 and baseline.grid_pair(move.get('transform', {}).get('current_grid')) == grid
                 and baseline.grid_pair(move.get('transform', {}).get('predicted_grid')) == grid)
        return writer, service, position, known

    def submit_move(self, row, broker):
        from tools.local_original_session.edge import EdgeAdapter
        writer, service, position, known = self.current_position(row, broker)
        if not known: return
        motion = row['memory']['move_state']
        if not (motion.get('source_contract_valid') is True
                and motion.get('controller', {}).get('command_present') is False
                and motion.get('navigation', {}).get('active') is False): return
        edge = broker.realm.edge_passability
        need(type(edge) is EdgeAdapter and edge.reader is self.reader, 'CURRENT_RETAINED_EDGE_REQUIRED')
        self.reader.validate()
        self.move['initial'] = position.metadata()
        neighbors = edge.tile_neighbors(position.uid, position.map_id, position.packed)
        self.move['neighbor_status'] = neighbors.get('status')
        need(neighbors.get('status') in ('OBSERVED', 'OBSERVED_PARTIAL')
             and neighbors.get('stable_double_read') is True
             and neighbors.get('uid') == position.uid and neighbors.get('map_id') == position.map_id
             and baseline.grid_pair(neighbors.get('start_grid')) == (position.word0, position.word1),
             'FRESH_NEIGHBOR_UNKNOWN')
        choices = [item for item in neighbors.get('directions', [])
                   if item.get('status') == 'OBSERVED' and item.get('blocked') is False]
        need(bool(choices), 'NO_OBSERVED_CLEAR_NEIGHBOR')
        choice = choices[0]
        target = baseline.grid_pair(choice.get('grid_target'))
        need(target is not None and all(0 <= value <= 65535 for value in target)
             and max(abs(target[0] - position.word0), abs(target[1] - position.word1)) == 1,
             'ADJACENT_TARGET_REQUIRED')
        need(edge(position.uid, position.map_id, position.packed, choice['direction'],
                  (target[1] << 16) | target[0]) is True, 'CURRENT_CLEAR_OWNED_EDGE_REQUIRED')
        self.reader.validate()
        need(service.snapshot() == position and self.owner.validate(self.owner.child) is True,
             'MOVE_AUTHORITY_CHANGED')
        self.move.update(target=list(target), direction=choice['direction'], status='CLAIMED_NO_RETRY')
        self.move_service, self.move_writer = service, writer
        self.move_before = (service.requests_received, service.committed, service.corrections_prepared)
        self.move_event_start = broker.policy.events
        request = dict(schema='own-internal-command-v1', pid=self.owner.child.pid,
                       birth=int(self.owner.child.identity['birth']), candidate_sha256=baseline.IMAGE_SHA,
                       seq=1, command=4, uid=position.uid, x=target[0], y=target[1])
        baseline._atomic(self.owner.directory / 'manual-move-request.json', request, 512)
        self.stage, self.move_started = 'MOVE_WAIT', self.clock()
        self.actions.append(dict(command='MoveGoal', status='CLAIMED_NO_RETRY', invoked=None))
        self.save()
        hwnd, user = self.current_window(), self.owner.native.u
        user.RegisterWindowMessageW.argtypes, user.RegisterWindowMessageW.restype = (baseline.W.LPCWSTR,), baseline.W.UINT
        message = user.RegisterWindowMessageW('LC-Owned-Manual-Move-v1')
        need(0xc000 <= message <= 0xffff, 'MANUAL_MOVE_MESSAGE_REQUIRED')
        self.reader.validate()
        need(self.current_window() == hwnd, 'CURRENT_PRIMARY_WINDOW_CHANGED')
        need(user.PostMessageW(hwnd, message, 1, 0), 'MANUAL_MOVE_POST_FAILED')
        self.actions[-1]['status'] = 'POSTED_CALLBACK_UNKNOWN'
        self.reader.validate()
        need(self.current_window() == hwnd, 'CURRENT_PRIMARY_WINDOW_CHANGED')
        self.save()

    def collect_move(self, row, broker):
        events = list(broker.policy.log)
        fresh = events[max(0, self.move_event_start - (broker.policy.events - len(events))):]
        for key, direction, opcode in (('cs4e2b_seen', 'rx', 0x4e2b), ('alive_rx', 'rx', 0x4e2a), ('alive_tx', 'tx', 0x4f57)):
            self.move[key] |= any(e[0] == direction and e[2] == opcode for e in fresh)
        try: result = baseline._closed_health_json(self.owner.directory / 'manual-move-result-1.json')
        except FileNotFoundError: result = None
        except ValueError: result = None  # Closed partial/malformed publication remains UNKNOWN, never retried.
        if result is not None:
            expected = dict(schema='own-manual-move-result-v1', pid=self.owner.child.pid,
                            birth=int(self.owner.child.identity['birth']), candidate_sha256=baseline.IMAGE_SHA, seq=1, command=4)
            need(set(result) == set(expected) | {'status', 'reason', 'invoked'}
                 and all(type(result.get(k)) is type(v) and result[k] == v for k, v in expected.items())
                 and result.get('status') in ('RETURNED', 'REFUSED', 'UNKNOWN')
                 and type(result.get('reason')) is int and type(result.get('invoked')) is bool,
                 'MANUAL_MOVE_RESULT_IDENTITY_OR_SCHEMA')
            self.move['native_result'] = result['status']
            self.actions[-1].update(status=result['status'], invoked=result['invoked'])
        writer, service, position, known = self.current_position(row, broker)
        need(writer is self.move_writer and service is self.move_service, 'MOVE_SERVICE_CHANGED')
        self.move.update(actual=position.metadata(), actual_client_known=known,
                         counters=dict(received=service.requests_received, committed=service.committed,
                                       corrections_prepared=service.corrections_prepared))
        self.move['saved'] = broker.realm.positions.restore(position).metadata()
        if (known and self.move['native_result'] == 'RETURNED' and result is not None
                and result['invoked'] is True and result['reason'] == 0 and self.move['cs4e2b_seen']
                and position.uid == self.move['initial']['uid'] and position.map_id == self.move['initial']['map_id']
                and position.metadata()['grid'] == self.move['target'] and self.move['saved'] == position.metadata()
                and (service.requests_received, service.committed, service.corrections_prepared)
                    == (self.move_before[0] + 1, self.move_before[1] + 1, self.move_before[2])):
            self.move['status'], self.stage = 'MOVE_COMMITTED_AND_SAVED', 'MOVE_PROVEN'
        if self.stage == 'MOVE_PROVEN':
            if self.move['alive_rx'] and self.move['alive_tx']: self.stop.set()
        elif self.clock() - self.move_started >= MOVE_RESULT_SUPERVISION_SECONDS:
            self.move['status'], self.stage = 'MOVEMENT_OUTCOME_UNKNOWN', 'MOVE_UNKNOWN'
            self.stop.set()
        self.save()

    def tick(self, row, broker, state):
        if self.stage in ('LOGIN', 'WAIT_LOGIN', 'WAIT_SLOT', 'WAIT_LAND'):
            super().tick(row, broker, state)
            if self.stage == 'IDLE': self.stage = 'MOVE_READY'; self.save()
            return
        if state != 'RUNNING' or self.stop.is_set() or self.monitor.samples == self.last_sample: return
        self.last_sample = self.monitor.samples
        try:
            self.reader.validate()
            need(self.owner.validate(self.owner.child) is True, 'RETAINED_BASELINE_OWNER_LOST')
            if self.stage == 'MOVE_READY': self.submit_move(row, broker)
            elif self.stage in ('MOVE_WAIT', 'MOVE_PROVEN'): self.collect_move(row, broker)
        except Exception as error:
            self.error = launcher.safe_error_code(error) or type(error).__name__
            self.stage, self.move['status'] = 'MOVE_UNKNOWN', 'UNKNOWN_NO_RETRY'
            self.save(); self.stop.set()


def main():
    raise SystemExit('BACKGROUND_LAUNCH_UNVERIFIED')


if __name__ == '__main__': raise SystemExit(main())
