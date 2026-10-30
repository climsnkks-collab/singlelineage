"""Requested headless knight status scenario: saved fixture -> normal login -> real input."""
import time
from pathlib import Path


def install(module, Base, MemoryUi, world_grid_to_capture, probe, selected):
    kind = selected.removeprefix('knight_status_')
    module.STEP_SETS[selected] = (
        ('capture', 'status-before-onset'),
        ('status_wait', 'status-active-publication', True),
        ('capture', 'status-active-before-move'),
        ('private_input', 'status-blocked-move-click', dict(locator='status.move', action='left_click')),
        ('status_observe', 'status-blocked-movement-samples', 'blocked'),
        ('capture', 'status-active-after-move'),
        ('wait', 'status-held-render-gap', .5),
        ('capture', 'status-active-still-held'),
        ('status_wait', 'status-expiry-publication', False),
        ('capture', 'status-released-before-move'),
        ('private_input', 'status-released-move-click', dict(locator='status.move', action='left_click')),
        ('status_observe', 'status-released-movement', 'released'),
        ('capture', 'status-released-after-move'))

    if kind == 'poison':
        # Poison changes HP/color; it does not own a movement lock.
        module.STEP_SETS[selected] = (
            ('status_wait', 'status-poison-publication', True),
            ('capture', 'status-poison-active'),
            ('wait', 'status-poison-render-gap', 1),
            ('capture', 'status-poison-held'),
            ('status_wait', 'status-poison-expiry', False),
            ('capture', 'status-poison-cleared'))

    class StatusFeedbackSteps(Base):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            broker = self.manual.inventory_broker
            self.status_broker, self.status_packets = broker, []
            self.status_hooks = []
            self.status_samples = []
            original = broker._send
            async def send(writer, row, replies, **options):
                entries = []
                from tools.local_entry_server import protobuf as pb
                for wire in replies:
                    opcode = int.from_bytes(wire[2:4], 'little') if len(wire) >= 6 else None
                    if opcode not in (0x4eeb, 0x4f03, 0x4f05, 0x4e91, 0x4ee0, 0x4e61, 0x4ed5, 0x4eea):
                        continue
                    entry = dict(opcode=hex(opcode), monotonic_seconds=time.monotonic(), send_returned=False)
                    with pb.parse_message(wire[4:-2]) as body:
                        entry['fields'] = {str(f.number): f.value for f in body.fields if f.wire_type == 0}
                        entry['text'] = [bytes(f.value).decode('utf-8', errors='replace')[:180]
                                         for f in body.fields if f.wire_type == 2 and opcode != 0x4e91]
                    entries.append(entry)
                self.status_packets.extend(entries)
                result = await original(writer, row, replies, **options)
                for entry in entries:
                    entry['send_returned'] = True
                return result
            owned, saved = '_send' in vars(broker), vars(broker).get('_send')
            broker._send = send
            self.status_hooks.append((broker, '_send', original, send, owned, saved))

        def status_snapshot(self, *, native=False):
            current, _ = module.current_kit(self.manual)
            position = current[3]
            broker, uid = self.status_broker, position.uid
            now = broker._world.runtime.clock()
            engine = broker._world_magic
            effect = (engine.state(uid).poison if kind == 'poison' and engine.state(uid).poison
                      and engine.state(uid).poison['until'] > now else None) if kind == 'poison' else engine.status(uid, kind, now)
            entity = broker._world.entities.get(uid)
            out = dict(uid=uid, kind=kind, active=effect is not None,
                effect=None if effect is None else dict(effect), server_grid=[entity.x, entity.y],
                map_id=entity.map_id, scene=self.scene(), packets=list(self.status_packets),
                movement=dict(requests_received=current[2].requests_received,
                    corrections_prepared=current[2].corrections_prepared, committed=current[2].committed),
                magic_errors=list(getattr(broker, '_world_magic_errors', ())))
            if native:
                memory, _ = self.manual.consumer.reader.sample(include_input_state=False)
                out['native_world'] = memory.get('world', {})
                out['native_move'] = memory.get('move_state', {})
            return out

        def resolve_request(self, request):
            if request.get('locator') != 'status.move':
                return super().resolve_request(request)
            capture = self.last_capture_context
            if self.results[-1].get('kind') != 'capture' or self.results[-1].get('status') != 'OBSERVED':
                raise ValueError('STATUS_IMMEDIATELY_PRECEDING_CAPTURE_REQUIRED')
            snapshot = self.status_snapshot(native=True)
            owner = snapshot['server_grid']
            world = self.status_broker._world
            if not hasattr(self, 'status_target'):
                offsets = ((2, 2), (2, 0), (0, 2), (-2, -2))
                self.status_target = next(([owner[0]+dx, owner[1]+dy] for dx, dy in offsets
                    if world.terrain.can_stand(snapshot['map_id'], owner[0]+dx, owner[1]+dy) is True), None)
            if self.status_target is None:
                raise ValueError('STATUS_CURRENT_TERRAIN_MOVE_TARGET_UNKNOWN')
            ui = MemoryUi(self)
            director = ui.ptr(ui.base + 0x1807fd8)
            size = ui.vec(ui.ptr(director + 0x150) + 0x6c)
            point, facts = world_grid_to_capture(capture,
                dict(map_id=snapshot['map_id'], grid=owner),
                dict(map_id=snapshot['map_id'], grid=self.status_target), size, probe)
            ui.validate()
            self.status_baseline = snapshot
            self.status_samples = []
            request = dict(request)
            request.pop('locator')
            request.update(schema='local-original-input-request-v1', expected_scene='Land',
                sequence=getattr(getattr(self, 'private_inputs', None), 'last_sequence', 0)+1,
                x=point[0], y=point[1], coordinate_space='capture', png_size=capture['png_size'])
            return request, dict(facts, target=self.status_target, before=snapshot)

        async def tick(self):
            if self.done:
                return await super().tick()
            step = self.steps[self.index]
            if step[0] not in ('status_wait', 'status_observe'):
                return await super().tick()
            if self.started is None:
                self.started = time.monotonic()
            try:
                snapshot = self.status_snapshot(native=step[0] == 'status_observe')
                elapsed = time.monotonic()-self.started
                if step[0] == 'status_wait':
                    matches = snapshot['active'] is step[2]
                    if not matches and elapsed < 110:
                        return
                    self.finish(dict(status='OBSERVED' if matches else 'UNKNOWN',
                        reason=None if matches else 'STATUS_DEADLINE_NOT_OBSERVED', snapshot=snapshot,
                        prepared_start='FRESH_COPY_MAGIC_STORE_RESTORED_BY_NORMAL_LOGIN', formal_pass=False))
                    return
                if not self.status_samples or elapsed-self.status_samples[-1]['elapsed'] >= .25:
                    self.status_samples.append(dict(elapsed=elapsed, server_grid=snapshot['server_grid'],
                        native_grid=snapshot['native_world'].get('grid_words'),
                        transform=snapshot['native_move'].get('transform'),
                        controller=snapshot['native_move'].get('controller')))
                baseline = self.status_baseline
                if step[2] == 'blocked':
                    if elapsed < 2:
                        return
                    native_before = baseline['native_world'].get('grid_words')
                    stable = (snapshot['active'] and native_before is not None
                        and all(row['server_grid'] == baseline['server_grid']
                            and row['native_grid'] == native_before
                            and row['transform'].get('status') == 'OBSERVED'
                            and all(row['transform'].get(k) == baseline['native_move'].get('transform', {}).get(k)
                                    for k in ('current_grid', 'predicted_grid'))
                            for row in self.status_samples)
                        and snapshot['movement'] == baseline['movement'])
                    ok = stable
                else:
                    ok = (snapshot['server_grid'] != baseline['server_grid'] and not snapshot['active']
                        and snapshot['movement']['requests_received'] > baseline['movement']['requests_received']
                        and snapshot['movement']['committed'] > baseline['movement']['committed'])
                    if not ok and elapsed < 8:
                        return
                self.finish(dict(status='OBSERVED' if ok else 'UNKNOWN',
                    reason=None if ok else 'STATUS_NATIVE_OR_SERVER_MOVEMENT_NOT_OBSERVED',
                    before=baseline, after=snapshot, samples=self.status_samples,
                    ui_result='REQUIRES_CAPTURE_REVIEW', formal_pass=False))
            except Exception as error:
                self.finish(dict(status='UNKNOWN', reason=str(error)[:300], formal_pass=False))

        def close(self):
            try:
                return super().close()
            finally:
                for obj, name, original, hook, owned, saved in reversed(self.status_hooks):
                    if getattr(obj, name) is hook:
                        if owned:
                            setattr(obj, name, saved)
                        else:
                            delattr(obj, name)

    module.Steps = StatusFeedbackSteps
