"""Existing headless scenario plus explicit private-desktop input requests.

POSTED on the default route is message delivery only. On the explicit GLFW
diagnostic route it means the native helper sequence completed. UI/server
observations stay separate; the target input is never retried.
"""
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

_selected_steps = next((arg.split('=', 1)[1] for arg in sys.argv[1:]
                        if arg.startswith('--steps=')), None)
if '--steps' in sys.argv:
    _selected_steps = sys.argv[sys.argv.index('--steps') + 1]
ATS_WINDOW_SCENARIO = _selected_steps in ('ats_window_open', 'ats_window_edit', 'ats_window_spell', 'ats_window_heal', 'ats_window_reset_dragoff')
# The environment is inherited by the owned child. Only this explicit scenario
# opts into the new window; older scenarios preserve their caller environment.
if ATS_WINDOW_SCENARIO:
    os.environ['COMPANION_ATS_WINDOW'] = '1'
PLAY_SMOKE_SCENARIO = _selected_steps in ('play_smoke', 'play_smoke_reconnect')
if PLAY_SMOKE_SCENARIO:
    os.environ.update(SL_EXPERIMENT_MAP='2', SL_EXPERIMENT_M5='1',
                     SL_COMPANION='1', SL_COMPANION_PET_UI='1',
                     SL_COMPANION_BRIDGE='1', COMPANION_ATS_WINDOW='1')

source = Path(r"C:\Users\Chansol\AppData\Local\Temp\claude\D--claude\0483de89-75e7-4b94-84b8-fb31fe00f575\scratchpad\verify_shots.py")
spec = importlib.util.spec_from_file_location("verify_shots_waitonly", source)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
module.STEP_SETS["waitonly"] = (("wait", "after_install", 45),)
module.STEP_SETS["pet_nocap"] = (("pet", "open_pet_window"),
                                  ("wait", "pet_settle", 5),
                                  ("wait", "after_pet", 10))
module.STEP_SETS["ats_capture"] = (("pet", "open_pet_window"),
                                     ("wait", "ats_settle", 6),
                                     ("capture", "ats-after-open"))
module.STEP_SETS["pet_after_capture"] = (("pet", "open_pet_window"),
                                          ("wait", "pet_settle", 3),
                                          ("capture", "pet-after-open"))
module.STEP_SETS["pet_after_capture_late"] = (("pet", "open_pet_window"),
                                               ("wait", "pet_settle", 7),
                                               ("capture", "pet-after-open-late"))
module.STEP_SETS["pet_click_movement"] = (("pet", "open_pet_window"),
                                           ("wait", "pet_settle", 3),
                                           ("capture", "pet-before-click"),
                                           ("click", "movement_row", (170, 520)),
                                           ("wait", "movement_settle", 2),
                                           ("capture", "pet-after-click"))
module.STEP_SETS["pet_focus_click"] = (("pet", "open_pet_window"),
                                        ("wait", "pet_settle", 3),
                                        ("raw", "focus_msgs", ((0x0006, 1, 0), (0x0007, 0, 0))),
                                        ("key", "tab", (0x09, 0x0F)),
                                        ("click", "movement_row", (170, 520)),
                                        ("wait", "movement_settle", 3))

# PNG point is Claude's visual estimate for row 7 (zero-based 6).
# Geometry comes from this run's immediately preceding capture, never an old run.
MOVEMENT_COORDINATE = dict(coordinate_space='capture', png_size=[2880, 2160],
    coordinate_basis='capture_to_client',
    row=6, point_basis='CLAUDE_VISUAL_ESTIMATE_NOT_NODE_OBSERVATION')
module.STEP_SETS['pet_private_movement'] = (
    ('pet', 'open_pet_window'), ('wait', 'pet_settle', 3),
    ('capture', 'pet-before-private-click'),
    ('private_input', 'movement_row_once', dict(
        schema='local-original-input-request-v1', action='left_click',
        x=230, y=518, expected_scene='Land', sequence=1), MOVEMENT_COORDINATE),
    ('server_observe', 'movement_server_arrival', 8),
    ('capture', 'pet-after-private-click'))

# InputPlan: use PNG coordinates with coordinate_space="capture",
# coordinate_basis="capture_to_client" and png_size=[2880,2160].
# Every action gets its own immediately preceding capture; drag points and wheel
# use the same conversion. The extra fields are removed before InputRequests.
# Click-only experiment: click_options={activate:bool, move_settle_ms:int,
# down_hold_ms:int} is also scenario metadata, not part of the strict v1 request.
# VERIFY_PRIVATE_CLICK_OPTIONS supplies the default for pet_private_movement or
# a plan. Per-entry click_options overrides it; {} selects the native message
# order with no synthetic activation or delays. Delays do not prove frame count.
default_click_options = json.loads(os.environ.get('VERIFY_PRIVATE_CLICK_OPTIONS', '{}'))
input_route = os.environ.get('VERIFY_INPUT_ROUTE', 'PRIVATE_DESKTOP_MESSAGES')
if input_route not in ('PRIVATE_DESKTOP_MESSAGES', 'GLFW_CALLBACK_INJECTION'):
    raise ValueError('INPUT_ROUTE_REQUIRED')
plan_path = os.environ.get('VERIFY_INPUT_PLAN', '')
if plan_path:
    plan = json.loads(Path(plan_path).read_text(encoding='utf-8-sig'))
    if isinstance(plan, dict):
        semantic_plan = plan
        plan = plan.get('requests', [])
    else:
        semantic_plan = {}
    if not isinstance(plan, list) or (not plan and not semantic_plan):
        raise ValueError('INPUT_PLAN_ARRAY_REQUIRED')
    plan_steps = [('pet', 'open_pet_window'), ('wait', 'pet_settle', 3)]
    for i, request in enumerate(plan):
        plan_steps.extend((('capture', f'before-private-input-{i + 1}'),
                           ('private_input', f'private_input_{i + 1}', request),
                           ('wait', f'private_input_settle_{i + 1}', 1)))
    module.STEP_SETS['private_input_plan'] = (*plan_steps, ('capture', 'after-private-input'))
else:
    semantic_plan = {}


COORDINATE_BASES = frozenset(('capture_to_client', 'world_grid_to_capture',
                              'corpse_grid_to_capture', 'node_to_capture'))


def require_capture_geometry(capture):
    """Accept only the established native-size PNG crop, without rescaling."""
    expected = dict(png_size=[2880, 2160], read_size=[3840, 2160],
                    crop=[480, 0, 2880, 2160], client_rect=[0, 0, 3840, 2160])
    if not isinstance(capture, dict) or any(capture.get(k) != v for k, v in expected.items()):
        raise ValueError('ESTABLISHED_CAPTURE_GEOMETRY_REQUIRED')


def require_coordinate_basis(request, evidence, resolved):
    """Validate point provenance before creating a strict InputRequests entry.

    A supplied plan may name an explicit capture point. It cannot claim that
    arbitrary coordinates came from a native node or either world equation.
    Those bases must be produced by the current locator resolver.
    """
    supplied = request.pop('coordinate_basis', None)
    if request.get('action') in ('key_press', 'type_text'):
        return evidence
    if resolved:
        sources = ((evidence or {}).get('locators')
                   if 'locators' in (evidence or {}) else [evidence])
        sources = [row for row in sources or [] if isinstance(row, dict)
                   and 'coordinate_basis' in row]
        expected = 2 if request.get('action') == 'left_drag' else 1
        if len(sources) != expected or any(row['coordinate_basis'] not in COORDINATE_BASES
                                            for row in sources):
            raise ValueError('INPUT_APPROVED_COORDINATE_BASIS_REQUIRED')
        if supplied is not None and any(row['coordinate_basis'] != supplied for row in sources):
            raise ValueError('INPUT_SUPPLIED_COORDINATE_BASIS_DISAGREES_WITH_LOCATOR')
        return evidence
    basis = supplied if supplied is not None else (evidence or {}).get('coordinate_basis')
    if basis != 'capture_to_client':
        raise ValueError('INPUT_EXPLICIT_CAPTURE_COORDINATE_BASIS_REQUIRED')
    return dict(evidence or {}, coordinate_basis=basis,
                point_basis='EXPLICIT_CAPTURE_POINT; TARGET_EFFECT_UNVERIFIED')


def node_to_capture(capture, scene_bounds, scene_size, require_capture=True):
    """Use the established scene_bounds center and aspect-fit presentation."""
    import math
    require_capture_geometry(capture)
    width, height = scene_size
    edges = [scene_bounds[key] for key in ('left', 'bottom', 'right', 'top')]
    if (not all(math.isfinite(n) for n in [width, height, *edges])
            or width <= 0 or height <= 0
            or edges[2] < edges[0] or edges[3] < edges[1]):
        raise ValueError('UI_SCENE_BOUNDS_OR_SIZE_UNKNOWN')
    dw, dh = capture['read_size']
    cx, cy, cw, ch = capture['crop']
    scale = min(dw / width, dh / height)
    def project(x, y):
        return [x * scale + (dw - width * scale) / 2 - cx,
                (height - y) * scale + (dh - height * scale) / 2 - (dh - cy - ch)]
    point = [round(n) for n in project((edges[0] + edges[2]) / 2,
                                      (edges[1] + edges[3]) / 2)]
    corners = [project(edges[0], edges[1]), project(edges[2], edges[3])]
    rect = [min(p[0] for p in corners), min(p[1] for p in corners),
            max(p[0] for p in corners), max(p[1] for p in corners)]
    if require_capture and not (0 <= point[0] < cw and 0 <= point[1] < ch):
        raise ValueError('UI_INFERRED_POINT_OUTSIDE_CAPTURE')
    return point, dict(scene_bounds=scene_bounds, scene_size=list(scene_size),
                       capture_rect=rect, coordinate_basis='node_to_capture')


def paced_drag_events(events, action):
    # The installed DLL consumes delay_ms before each event on its UI timer.
    # Distinct points alone do not let a drag cross an update/render turn.
    if action == 'left_drag':
        for event in events[1:]:
            event['delay_ms'] = 40
    return events


# Keep the durable dispatcher and all owner/scene/geometry checks in the shared
# adapter. Only this diagnostic scenario changes its native event pacing.
from tools.local_original_session.input import GlfwCallbackInput


class ScenarioGlfwCallbackInput(GlfwCallbackInput):
    def _events(self, action, geometry, parameters):
        if ((_selected_steps == 'pet_window_toggle' or PLAY_SMOKE_SCENARIO) and action == 'key_press'
                and parameters.get('key') == 'Ctrl+E'):
            return [dict(type='key', key=key, scancode=scan, action=pressed,
                         mods=mods, delay_ms=40)
                    for key, scan, pressed, mods in ((341, 0x1d, 1, 2),
                        (69, 0x12, 1, 2), (69, 0x12, 0, 2), (341, 0x1d, 0, 0))]
        if ATS_WINDOW_SCENARIO and action == 'key_press' and parameters.get('key') == 'Alt+W':
            # Original help documents Alt-W settings. Use the same owned GLFW
            # callback adapter, not an ATS handler or a manager show call.
            return [dict(type='key', key=key, scancode=scan, action=pressed,
                         mods=mods, delay_ms=40)
                    for key, scan, pressed, mods in ((342, 0x38, 1, 4),
                        (87, 0x11, 1, 4), (87, 0x11, 0, 4), (342, 0x38, 0, 0))]
        return paced_drag_events(super()._events(action, geometry, parameters), action)


# Keep the successful harness capture implementation after module.Steps is
# replaced with the scenario class at the end of this file.
EstablishedCaptureSteps = module.Steps


class PrivateSteps(module.Steps):
    def close(self):
        try:
            super().close()
        finally:
            # The imported harness writes only after an IDLE-stage poll. A
            # login/scene timeout can therefore finish with no shots file at
            # all. Preserve partial results at the existing cleanup boundary,
            # without running or claiming any unattempted input.
            scenario = self.scenario
            stage = getattr(scenario, 'stage', None)
            reason = (None if self.done else
                      'SCENARIO_NOT_IDLE_AT_CLOSE' if stage != 'IDLE' else
                      'STEPS_INCOMPLETE_AT_CLOSE')
            shop_server_errors = getattr(self, 'shop_new_server_errors', None)
            if shop_server_errors:
                reason = shop_server_errors[0]
            summary = dict(results=self.results, done=self.done,
                stage=stage, scenario_error=getattr(scenario, 'error', None),
                reason=reason, next_step=None if self.done else self.steps[self.index][1],
                remaining_steps=[s[1] for s in self.steps[self.index:]],
                last_memory=dict(getattr(getattr(scenario, 'monitor', None), 'last_memory', {}) or {}),
                log=module.LOG[-50:])
            if shop_server_errors:
                summary['new_server_errors'] = shop_server_errors
            self.directory.mkdir(parents=True, exist_ok=True)
            (self.directory / 'verify-shots.json').write_text(
                json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
            if not self.done:
                module.log('STEPS_INCOMPLETE', reason, 'stage', stage,
                           'next_step', summary['next_step'])

    def target(self):
        scenario, owner = self.scenario, self.scenario.owner
        scenario.background_desktop()
        target = dict(identity=dict(pid=owner.child.pid,
                                    birth=int(owner.child.identity['birth']),
                                    candidate_sha256=owner.image_sha),
                      hwnd=scenario.current_window(), ui_thread=owner.child.tid)
        if getattr(self, 'input_geometry', None) is not None:
            target['expected_geometry'] = self.input_geometry
        self.last_input_target = target
        return target

    def read_crop(self):
        # Same typed Director/view chain used by original_screenshot.py:477.
        import struct
        import math
        current, _ = module.current_kit(self.manual)
        reader = self.manual.consumer.reader
        reader.validate()
        base = reader.sampler.g['base']
        def read(at, size, image=False):
            raw = reader.backend.read(at, size, base if image else None)
            if type(raw) is not bytes or len(raw) != size:
                raise ValueError('INPUT_CAPTURE_VIEW_READ_PARTIAL')
            return raw
        director = struct.unpack('<Q', read(base + 0x1807fd8, 8, True))[0]
        if struct.unpack('<Q', read(director, 8))[0] != base + 0x1237f90:
            raise ValueError('INPUT_CAPTURE_DIRECTOR_TYPE')
        view = struct.unpack('<Q', read(director + 0x100, 8))[0]
        if struct.unpack('<Q', read(view, 8))[0] != base + 0x123a7d8:
            raise ValueError('INPUT_CAPTURE_VIEW_TYPE')
        raw = read(view + 0x20, 16)
        values = struct.unpack('<ffff', raw)
        if not all(math.isfinite(n) and 0 <= n < 2147483648 for n in values):
            raise ValueError('INPUT_CAPTURE_RECTANGLE')
        if read(view + 0x20, 16) != raw:
            raise ValueError('INPUT_CAPTURE_VIEW_CHANGED')
        reader.validate()
        return [int(n) for n in values]

    def geometry(self):
        target = self.target()
        return self.scenario.background_desktop().observe_client_geometry(
            self.scenario.owner, target['identity'], target['hwnd'], target['ui_thread'])

    async def do_capture(self, name):
        if not any(step[0] == 'private_input' for step in self.steps):
            return await super().do_capture(name)
        import shutil
        from dataclasses import asdict
        if self.capture is None:
            if self.busy():
                return
            self.last_capture_context = None
            self.capture_start = (self.read_crop(), self.geometry())
            self.capture = module.KitScreenshotObserver(self.manual)
            if not self.capture.request():
                reason = self.capture.observation().get('reason')
                self.capture.close(); self.capture = None
                raise ValueError('CAPTURE_REQUEST_REFUSED:' + str(reason))
            self.cap_started = time.monotonic()
            return
        await self.capture.sample()
        row = self.capture.collect()
        if row.get('status') == 'OBSERVED':
            crop, geo = self.capture_start
            after = self.geometry()
            keys = ('pid', 'birth', 'candidate_sha256', 'hwnd', 'ui_thread',
                    'client_rect', 'window_dpi', 'window_awareness')
            if crop != self.read_crop() or any(geo[k] != after[k] for k in keys):
                raise ValueError('INPUT_CAPTURE_GEOMETRY_CHANGED')
            destination = self.directory / (name + '.png')
            shutil.copyfile(row['image_path'], destination)
            native = self.capture.capture_observation()
            if native is not None:
                context = asdict(native.geometry)
                context.update(pid=native.pid, birth=native.birth,
                               candidate_sha256=native.candidate_sha256)
                # JSON-shaped lists for both native and host observations.
                context = json.loads(json.dumps(context))
                context['relation'] = ('OBSERVED_DEFAULT_CLIENT_DRAWABLE_V6'
                    if context['read_fbo'] == 0 else 'FBO_PRESENTATION_UNKNOWN')
            else:
                # v5 has no read-FBO metadata. This is an explicit inference,
                # never a measured default FBO or a proven presentation map.
                context = dict(geo, crop=crop, read_size=geo['client_rect'][2:],
                    read_fbo=None, relation='INFERRED_DEFAULT_CLIENT_DRAWABLE_V5',
                    limitation='V5_DOES_NOT_REPORT_READ_FBO_OR_PRESENTATION_TRANSFORM')
            context.update(png_size=[row['width'], row['height']], png=str(destination))
            self.last_capture_context = context
            self.capture.close(); self.capture = None
            self.finish(dict(status='OBSERVED', png=str(destination), width=row['width'],
                             height=row['height'], coordinate_capture=context))
            return
        if row.get('cleanup_required') or time.monotonic() - self.cap_started > 20:
            self.capture.close(); self.capture = None
            self.finish(dict(status='CAPTURE_FAILED', row={k: row.get(k) for k in
                             ('status', 'reason', 'cleanup_required', 'direct_stage')}))

    def scene(self):
        return dict(self.scenario.monitor.last_memory)

    def server_signals(self):
        current, _ = module.current_kit(self.manual)
        return [dict(row) for row in getattr(current[0].broker, '_bridge_signals', ())]

    async def tick(self):
        if self.done or self.steps[self.index][0] not in ('private_input', 'server_observe'):
            return await super().tick()
        step = self.steps[self.index]
        if self.started is None:
            self.started = time.monotonic()
        if step[0] == 'server_observe':
            try:
                before = getattr(self, 'signals_before_input', [])
                rows = [row for row in self.server_signals() if row not in before
                        and row.get('operation') in ('movement-hold', 'movement-follow')
                        and row.get('actor') == getattr(self, 'input_actor', None)]
                current, _ = module.current_kit(self.manual)
                boundary = current[5]
                callbacks = [str(path) for path in sorted(boundary.glob('companion-pet-click-*.json'))
                             if str(path) not in getattr(self, 'callbacks_before_input', ())]
                if rows or time.monotonic() - self.started >= step[2]:
                    reason = None if rows else ('NO_NEW_MOVEMENT_SIGNAL_BY_DEADLINE' if callbacks
                                               else 'NO_NATIVE_CALLBACK_OR_MOVEMENT_SIGNAL_BY_DEADLINE')
                    self.finish(dict(status='OBSERVED' if rows else 'UNKNOWN',
                        ui_result='UNKNOWN', server_signals=rows, server_signal_count=len(rows),
                        native_callback_files=callbacks, target_actor=getattr(self, 'input_actor', None),
                        reason=reason))
            except Exception as error:
                self.finish(dict(status='UNKNOWN', ui_result='UNKNOWN',
                                 reason='SERVER_OBSERVATION_FAILED:' + str(error)[:200]))
            return
        if self.busy():
            return
        # This branch deliberately bypasses Steps.tick's catch-and-retry loop.
        # InputRequests durably claims the sequence before any input dispatch.
        evidence = step[3] if len(step) > 3 else None
        geometry = None
        target = None
        self.input_geometry = None
        try:
            from tools.local_original_session.input import PrivateInput, InputRequests
            self.signals_before_input = self.server_signals()
            current, _ = module.current_kit(self.manual)
            self.callbacks_before_input = [str(path) for path in current[5].glob('companion-pet-click-*.json')]
            opened = next((row for row in reversed(self.results) if row.get('kind') == 'pet'), {})
            target_uid = opened.get('reply', {}).get('target_uid')
            self.input_actor = target_uid & 0xffffffff if type(target_uid) is int else None
            from tools.local_original_session.input import capture_to_client
            request = dict(step[2])
            resolved = 'locator' in request
            if resolved:
                request, evidence = self.resolve_request(request)
            evidence = require_coordinate_basis(request, evidence, resolved)
            click_options = request.pop('click_options', default_click_options)
            options = dict(observation_scene=self.scene, observation_target=self.target,
                           click_options=click_options)
            adapter = (ScenarioGlfwCallbackInput(self.scenario.owner, current[5], enabled=True, **options)
                       if input_route == 'GLFW_CALLBACK_INJECTION'
                       else PrivateInput(self.scenario.owner, **options))
            if not hasattr(self, 'private_inputs'):
                self.private_inputs = InputRequests(self.directory, adapter)
            else:
                # Keep the durable claim/sequence state across plan entries,
                # while each entry gets its own options (no option inheritance).
                self.private_inputs.mouse = adapter
            space = request.pop('coordinate_space', (evidence or {}).get('coordinate_space', 'client'))
            png_size = request.pop('png_size', (evidence or {}).get('png_size'))
            if request.get('action') not in ('key_press', 'type_text') and space != 'capture':
                raise ValueError('INPUT_CAPTURE_COORDINATES_REQUIRED')
            if space == 'capture':
                capture = getattr(self, 'last_capture_context', None)
                require_capture_geometry(capture)
                geometry = self.geometry()
                if not capture or png_size != capture['png_size']:
                    raise ValueError('INPUT_CAPTURE_PNG_SIZE_CHANGED_OR_MISSING')
                if self.read_crop() != capture['crop']:
                    raise ValueError('INPUT_CAPTURE_VIEW_CHANGED')
                request, converted = capture_to_client(request, capture, geometry)
                evidence = dict(evidence or {}, **converted)
                self.input_geometry = geometry
            elif space != 'client':
                raise ValueError('INPUT_COORDINATE_SPACE_REQUIRED')
            # Check again at dispatch, after locator/capture work. No await
            # occurs between this check and publishing the native request.
            if (getattr(self, 'resurrect_scenario', False)
                    and step[1] == 'resurrect-corpse-click' and self.resurrection_scroll_arrived()):
                self.finish(dict(status='SKIPPED', reason='RESURRECTION_SCROLL_CS0960_ALREADY_RECEIVED',
                                 automatic_retry=False, ui_result='UNKNOWN'))
                return
            if (getattr(self, 'spell_cast', False) and step[1].startswith('spell-cast-knight-attack')
                    and self.cast_attack_attempts[:-1] and any(
                        self.cast_attack_evidence()[key] for key in ('pc_attacks', 'target_hp_drops'))):
                self.finish(dict(status='SKIPPED', reason='SPELL_CAST_PRIOR_ATTACK_ARRIVED_BEFORE_RETRY',
                                 automatic_retry=False, ui_result='UNKNOWN'))
                return
            temporary = self.directory / 'input.request.tmp'
            with temporary.open('x', encoding='ascii') as stream:
                json.dump(request, stream, separators=(',', ':'), ensure_ascii=True)
            os.replace(temporary, self.private_inputs.request)
            outcome = await self.private_inputs.poll_async()
            if outcome is None:
                raise ValueError('INPUT_REQUEST_NO_NEW_RESULT')
            self.finish(dict(status=outcome['status'], input_result=outcome,
                ui_result='UNKNOWN', request=request, native_geometry=geometry,
                input_target=getattr(self, 'last_input_target', target), coordinate_evidence=evidence,
                signals_before=self.signals_before_input))
        except Exception as error:
            self.finish(dict(status='REFUSED', ui_result='UNKNOWN', automatic_retry=False,
                reason=str(error)[:300], native_geometry=geometry,
                coordinate_evidence=getattr(error, 'coordinate_evidence', evidence)))




# Named scenarios use fresh memory geometry, followed by the existing durable
# InputRequests dispatcher. The opt-in GLFW route invokes native input helpers;
# the default route queues private desktop messages. Neither proves UI effects.
# Optional object InputPlan: {"locators": {"semantic.name": {"capture_sha256":
# "...", "png_size": [w,h], "point": [x,y]}}}. Bindings are accepted only for
# the immediately preceding capture. Array InputPlans use the metadata above.
PET_NAMES = ('Targeting', 'AttackStance', 'DefendStance', 'Spread', 'Alert', 'Gather', 'Dismiss')


def scenario_action(name, locator, action='left_click', observe=None, **extra):
    request = dict(schema='local-original-input-request-v1', action=action,
                   expected_scene='Land', locator=locator, **extra)
    result = [('capture', 'before-' + name), ('private_input', name, request),
              ('wait', name + '-settle', 1), ('capture', 'after-' + name)]
    if observe:
        result.append(('scenario_observe', name + '-observe', observe))
    return result


def scenario_steps(name):
    if name == 'talkscroll_teleport_capture':
        # Start on map1 in an owned test-save copy to exercise a same-map trip.
        # The row handler below adds an immediate effect capture only here.
        return (('scenario_prepare', 'talkscroll-preconditions', 'talkscroll'),
                ('capture', 'before-talkscroll-inventory'),
                ('scenario_inventory', 'ensure-talkscroll-inventory'),
                ('capture', 'before-talkscroll-scroll-check-0'),
                ('scenario_talkscroll_scroll', 'talkscroll-scroll-check-0'),
                *scenario_action('talkscroll-double-click', 'self_bag.talkscroll',
                                 'left_double_click'),
                ('scenario_talkscroll_row', 'talkscroll-teleport-capture-row'))
    if name == 'talkscroll_open':
        return (('scenario_prepare', 'talkscroll-preconditions', 'talkscroll'),
                ('capture', 'before-talkscroll-inventory'),
                ('scenario_inventory', 'ensure-talkscroll-inventory'),
                ('capture', 'before-talkscroll-scroll-check-0'),
                ('scenario_talkscroll_scroll', 'talkscroll-scroll-check-0'),
                *scenario_action('talkscroll-double-click', 'self_bag.talkscroll',
                                 'left_double_click'),
                ('scenario_talkscroll_row', 'talkscroll-first-hunting-row'))
    if name == 'resurrect_scroll':
        # No pet window/query: the selected member is a corpse. Borrow the
        # same self-bag locator as give/equip, opening through the native HUD
        # bag button only when the knight inventory is not already shown.
        return (('scenario_prepare', 'resurrect-preconditions', 'resurrect'),
                ('capture', 'before-resurrect-inventory'),
                ('scenario_inventory', 'ensure-resurrect-inventory'),
                *scenario_action('resurrect-scroll-double-click', 'self_bag.resurrect_scroll',
                                 'left_double_click'),
                *scenario_action('resurrect-corpse-click', 'world.dead_companion'),
                ('scenario_observe', 'resurrect-result', dict(resurrect=True)))
    steps = [('pet', 'open_pet_window'), ('wait', 'pet_settle', 3),
             ('scenario_prepare', 'companion-preconditions')]
    def add(label, locator, action='left_click', observe=None, **extra):
        steps.extend(scenario_action(label, locator, action, observe, **extra))
    def row(index, label, operation):
        add(label, 'pet.' + PET_NAMES[index], observe=dict(operation=operation, row=index))
    if name == 'ats_window_open':
        steps.append(('scenario_prepare', 'ats-window-baseline', 'ats_window'))
        add('companion-settings-open', 'pet.Spread', observe=dict(ats_window='companion'))
        add('knight-settings-open', 'companion_ats', 'key_press',
            dict(ats_window='knight-replaces-companion'), key='Alt+W')
        add('companion-settings-reopen-over-knight', 'pet.Spread',
            observe=dict(ats_window='companion-replaces-knight'))
        add('companion-settings-close', 'companion_ats.close',
            observe=dict(ats_window='companion-closed'))
        add('knight-settings-reopen', 'pet', 'key_press',
            dict(ats_window='knight-reopened'), key='Alt+W')
        add('knight-settings-close', 'ats.window_close', observe=dict(ats_window='closed'))
        steps.append(('scenario_observe', 'knight-ats-preserved-after-close', dict(ats_window='saved')))
        add('companion-settings-reopen', 'pet.Spread', observe=dict(ats_window='reopened'))
        add('companion-settings-escape', 'companion_ats', 'key_press',
            dict(ats_window='escaped'), key='Escape')
        steps.append(('scenario_observe', 'knight-ats-preserved-final', dict(ats_window='saved-final')))
    elif name == 'ats_window_edit':
        steps.append(('scenario_prepare', 'ats-window-edit-baseline', 'ats_window_edit'))
        # Let the product place ATS around the already visible native Bag.
        row(4, 'companion-bag-open', 'bag-open-take')
        add('companion-settings-open', 'pet.Spread', observe=dict(ats_window_edit='opened'))
        steps.append(('scenario_prepare', 'companion-red-potion', 'companion_potion'))
        add('companion-hp-slot2-drag', ['companion_bag.potion', 'companion_ats.hp_slot2'],
            'left_drag', dict(ats_window_edit='dragged'))
        add('companion-hp-percent-focus', 'companion_ats.hp_percent')
        steps.append(('scenario_ats_clear', 'companion-hp-percent-clear'))
        add('companion-hp-percent-enter', 'companion_ats', 'type_text',
            dict(ats_window_edit='draft'), text='60')
        add('companion-settings-save', 'companion_ats.save', observe=dict(ats_window_edit='saved'))
        add('companion-bag-close', 'companion_bag.close', observe=dict(hidden='companion_bag'))
        add('companion-settings-close', 'companion_ats.close', observe=dict(ats_window_edit='closed'))
        add('companion-settings-reopen', 'pet.Spread', observe=dict(ats_window_edit='reopened'))
        add('companion-settings-final-close', 'companion_ats.close', observe=dict(ats_window_edit='final'))
    elif name == 'ats_window_spell':
        steps.append(('scenario_prepare', 'ats-window-spell-baseline', 'ats_window_spell'))
        add('companion-settings-open', 'pet.Spread')
        add('companion-spell-open', 'companion_ats.spell_open')
        steps.extend((('wait', 'companion-spell-delayed-sample', 1.5),
                      ('scenario_observe', 'companion-spell-open-observe',
                       dict(ats_window_spell='opened'))))
        add('companion-spell-close', 'companion_spell.close',
            observe=dict(ats_window_spell='closed'))
        add('companion-spell-reopen', 'companion_ats.spell_open')
        steps.extend((('wait', 'companion-spell-reopen-delayed-sample', 1.5),
                      ('scenario_observe', 'companion-spell-reopen-observe',
                       dict(ats_window_spell='reopened'))))
        add('companion-spell-to-buff', ['companion_spell.learned_buff', 'companion_ats.buff_spell'],
            'left_drag', dict(ats_window_spell='buff-draft'))
        add('companion-combat-tab', 'companion_ats.combat_tab')
        add('companion-spell-to-battle', ['companion_spell.learned_battle', 'companion_ats.battle_spell'],
            'left_drag', dict(ats_window_spell='battle-draft'))
        add('companion-spell-to-conditional',
            ['companion_spell.learned_conditional', 'companion_ats.conditional_spell'],
            'left_drag', dict(ats_window_spell='conditional-draft'))
        add('companion-settings-save', 'companion_ats.save',
            observe=dict(ats_window_spell='saved'))
        add('companion-spell-final-close', 'companion_spell.close')
        add('companion-settings-close', 'companion_ats.close')
        add('companion-settings-reopen', 'pet.Spread',
            observe=dict(ats_window_spell='reopened-saved'))
        add('companion-settings-final-close', 'companion_ats.close')
    elif name == 'ats_window_reset_dragoff':
        steps.append(('scenario_prepare', 'ats-reset-dragoff-baseline', 'ats_window_reset_dragoff'))
        add('ats-clear-settings-open', 'pet.Spread')
        add('ats-clear-spell-open', 'companion_ats.spell_open')
        steps.extend((('wait', 'ats-clear-spell-population', 1.5),
                      ('scenario_observe', 'ats-clear-opened', dict(ats_window_clear='opened'))))
        add('ats-clear-buff-seed', ['companion_spell.learned_buff', 'companion_ats.buff_spell'],
            'left_drag', dict(ats_window_clear='buff-seeded'))
        # Seed other tabs through native input so preservation cannot pass on
        # empty fixture rows. Return to Buff: Reset applies to that tab only.
        add('ats-clear-battle-tab', 'companion_ats.combat_tab')
        add('ats-clear-battle-seed', ['companion_spell.learned_battle', 'companion_ats.battle_spell'],
            'left_drag')
        add('ats-clear-conditional-seed',
            ['companion_spell.learned_conditional', 'companion_ats.conditional_spell'], 'left_drag')
        add('ats-clear-heal-seed-tab', 'companion_ats.heal_tab')
        add('ats-clear-heal-seed', ['companion_spell.learned_hp', 'companion_ats.heal_hp'], 'left_drag')
        add('ats-clear-buff-return', 'companion_ats.buff_tab')
        # Commit before Reset so its Save must produce a real Buff delta.
        add('ats-clear-seed-save', 'companion_ats.save', observe=dict(ats_window_clear='seed-saved'))
        add('ats-clear-reset', 'companion_ats.reset', observe=dict(ats_window_clear='reset-draft'))
        add('ats-clear-reset-save', 'companion_ats.save', observe=dict(ats_window_clear='reset-saved'))
        add('ats-clear-buff-refill', ['companion_spell.learned_buff', 'companion_ats.buff_spell'],
            'left_drag', dict(ats_window_clear='buff-refilled'))
        add('ats-clear-buff-dragoff', ['companion_ats.buff_spell', 'pet.AttackStance'],
            'left_drag', dict(ats_window_clear='buff-empty'))
        add('ats-clear-heal-tab', 'companion_ats.heal_tab')
        add('ats-clear-heal-fill', ['companion_spell.learned_hp', 'companion_ats.heal_hp'],
            'left_drag', dict(ats_window_clear='heal-filled'))
        add('ats-clear-heal-dragoff', ['companion_ats.heal_hp', 'pet.AttackStance'],
            'left_drag', dict(ats_window_clear='heal-empty'))
        steps.extend((('wait', 'ats-clear-heal-render-settle', .25),
                      ('capture', 'ats-clear-heal-dragoff-confirmed'),
                      ('scenario_observe', 'ats-clear-heal-confirmed-native',
                       dict(ats_native_clear_probe='confirmed'))))
        add('ats-clear-spell-close', 'companion_spell.close')
        add('ats-clear-settings-close', 'companion_ats.close')
    elif name == 'ats_window_heal':
        steps.append(('scenario_prepare', 'ats-window-heal-baseline', 'ats_window_heal'))
        add('companion-heal-settings-open', 'pet.Spread')
        add('companion-heal-tab', 'companion_ats.heal_tab',
            observe=dict(ats_window_heal='opened'))
        # The spell button belongs to Buff. Open it there, then return to Help.
        add('companion-heal-buff-tab', 'companion_ats.buff_tab')
        add('companion-heal-spell-open', 'companion_ats.spell_open')
        steps.append(('wait', 'companion-heal-spell-population', 1.5))
        add('companion-heal-return-tab', 'companion_ats.heal_tab',
            observe=dict(ats_window_heal='spell-opened'))
        add('companion-heal-hp-drag', ['companion_spell.learned_hp', 'companion_ats.heal_hp'],
            'left_drag', dict(ats_window_heal='hp-draft'))
        add('companion-heal-kind-refused', ['companion_spell.learned_hp', 'companion_ats.heal_status'],
            'left_drag', dict(ats_window_heal='kind-refused'))
        add('companion-heal-status-drag', ['companion_spell.learned_status', 'companion_ats.heal_status'],
            'left_drag', dict(ats_window_heal='status-draft'))
        add('companion-heal-percent-menu', 'companion_ats.heal_percent_menu',
            observe=dict(ats_window_heal='menu-opened'))
        add('companion-heal-percent30', 'companion_ats.heal_percent30',
            observe=dict(ats_window_heal='percent-draft'))
        add('companion-heal-save', 'companion_ats.save', observe=dict(ats_window_heal='saved'))
        add('companion-heal-spell-close', 'companion_spell.close')
        add('companion-heal-settings-close', 'companion_ats.close',
            observe=dict(ats_window_heal='closed'))
        steps.append(('scenario_prepare', 'companion-heal-reopen-baseline', 'ats_window_heal_reopen'))
        add('companion-heal-settings-reopen', 'pet.Spread')
        add('companion-heal-reopen-tab', 'companion_ats.heal_tab',
            observe=dict(ats_window_heal='reopened'))
        add('companion-heal-final-close', 'companion_ats.close',
            observe=dict(ats_window_heal='final'))
    elif name == 'pet_rows_click':
        steps.append(('scenario_observe', 'attack-target-skipped', dict(skip='TARGET_REQUIRES_LIVING_WORLD_TARGET')))
        # Original rows 1/2 use native pet mode packets, not LOCAL bridge signals.
        row(1, 'attack-stance', None); row(2, 'defend-stance', None)
        row(3, 'settings-row', 'settings-load')
        add('settings-close', 'ats.close', observe=dict(hidden='ats'))
        row(4, 'bag-row', 'bag-open-take')
        add('bag-close', 'companion_bag.close', observe=dict(hidden='companion_bag'))
        row(5, 'equipment-row', 'equipment-open')
        add('equipment-close', 'companion_equipment.close', observe=dict(hidden='companion_equipment'))
        row(6, 'movement-row', ('movement-hold', 'movement-follow'))
    elif name == 'bag_drag_give':
        row(4, 'bag-open', 'bag-open-take')
        steps.append(('scenario_prepare', 'potion-stack', 'potion'))
        add('give-drag', ['self_bag.potion', 'companion_bag.drop'], 'left_drag',
            dict(quantity_popup=True))
        add('give-quantity-focus', 'quantity')
        add('give-quantity', 'quantity', 'key_press', key='1')
        add('give-confirm', 'quantity', 'key_press', dict(operation='item-give', transfer=1), key='Enter')
        add('take-drag', ['companion_bag.potion', 'self_bag.drop'], 'left_drag',
            dict(quantity_popup_or_signal='item-take'))
        # A single remaining potion transfers without a quantity popup.
        steps.append(('scenario_quantity', 'take-quantity-if-needed'))
        steps.append(('scenario_observe', 'take-result', dict(operation='item-take', transfer=-1)))
    elif name == 'bag_close_wheel':
        row(4, 'bag-open', 'bag-open-take')
        add('wheel-down', 'companion_bag.drop', 'mouse_wheel', dict(scroll=True), delta=-120)
        add('wheel-up', 'companion_bag.drop', 'mouse_wheel', dict(scroll=True), delta=120)
        add('close-button', 'companion_bag.close', observe=dict(hidden='companion_bag'))
        row(4, 'bag-reopen', 'bag-open-take')
        add('escape', 'companion_bag', 'key_press', dict(hidden='companion_bag'), key='Escape')
    elif name == 'equip_dblclick':
        # Gear/ATS overlap the pet rows; open the central bag before either.
        row(4, 'bag-open', 'bag-open-take')
        row(5, 'equipment-open', 'equipment-open')
        steps.append(('scenario_prepare', 'equipped-item', 'equipment'))
        add('unequip-double-click', 'companion_equipment.equipped', 'left_double_click',
            dict(operation='item-unequip', equipped=False))
        add('equip-double-click', 'companion_bag.equipment_item', 'left_double_click',
            dict(operation='item-equip', equipped=True))
    elif name in ('ats_edit_save', 'equip_after_ats'):
        row(4, 'bag-open', 'bag-open-take')
        row(3, 'settings-open', 'settings-load')
        steps.append(('scenario_prepare', 'potion-stack', 'companion_potion'))
        add('recovery-buff-tab', 'ats.buff_tab')
        add('recovery-slot-drag', ['companion_bag.potion', 'ats.recovery'], 'left_drag')
        add('settings-save', 'ats.save', observe=dict(ats_saved=True))
        add('settings-close', 'ats.close', observe=dict(hidden='ats'))
        row(3, 'settings-reopen', 'settings-load')
        steps.append(('scenario_observe', 'member-ats-reopen', dict(ats_saved=True, reopened=True)))
        if name == 'equip_after_ats':
            add('settings-reopen-close', 'ats.close', observe=dict(hidden='ats'))
            row(5, 'equipment-after-ats-open', 'equipment-open')
            add('equipment-after-ats-close', 'companion_equipment.close',
                observe=dict(hidden='companion_equipment'))
    return tuple(steps)


for scenario_name in ('ats_window_open', 'ats_window_edit', 'ats_window_spell', 'ats_window_heal', 'ats_window_reset_dragoff', 'pet_rows_click', 'bag_drag_give', 'bag_close_wheel', 'equip_dblclick', 'ats_edit_save',
                      'equip_after_ats', 'resurrect_scroll', 'talkscroll_open',
                      'talkscroll_teleport_capture'):
    module.STEP_SETS[scenario_name] = scenario_steps(scenario_name)


# Explicit scoped replay for the observed healing-slot stale rendered child.
# Reuses the established opening, learned-row input and close sequence.
if (_selected_steps == 'ats_window_reset_dragoff'
        and os.environ.get('VERIFY_ATS_HEAL_CLEAR_PROBE') == '1'):
    _full_clear_steps = module.STEP_SETS[_selected_steps]
    _clear_prefix = _full_clear_steps[:next(i for i, step in enumerate(_full_clear_steps)
        if step[1] == 'before-ats-clear-buff-seed')]
    module.STEP_SETS[_selected_steps] = (*_clear_prefix,
        *scenario_action('ats-clear-heal-tab', 'companion_ats.heal_tab'),
        *scenario_action('ats-clear-heal-fill', ['companion_spell.learned_hp', 'companion_ats.heal_hp'],
            'left_drag', dict(ats_native_clear_probe='filled')),
        *scenario_action('ats-clear-heal-dragoff', ['companion_ats.heal_hp', 'pet.AttackStance'],
            'left_drag', dict(ats_native_clear_probe='cleared')),
        *scenario_action('ats-clear-spell-close', 'companion_spell.close'),
        *scenario_action('ats-clear-settings-close', 'companion_ats.close'))


def capture_pet_point(capture, locator, error):
    """Same-action PNG fallback for the authored seven command rows."""
    require_capture_geometry(capture)
    import hashlib
    from PIL import Image
    reason = getattr(error, 'reason', str(error))
    role, _, control = locator.partition('.')
    if role != 'pet' or control not in PET_NAMES:
        raise error
    raw = Path(capture['png']).read_bytes()
    import io
    with Image.open(io.BytesIO(raw)) as image:
        if list(image.size) != capture['png_size']:
            raise ValueError('INPUT_CAPTURE_PNG_SIZE_CHANGED_OR_MISSING')
        pixels = image.crop((60, 165, 450, 565)).convert('RGB')
        bands = []
        for y in range(pixels.height):
            xs = [x for x in range(pixels.width)
                  if (lambda r, g, b: r >= 130 and g >= 120 and b <= 130
                      and min(r, g) > b * 1.3)(*pixels.getpixel((x, y)))]
            if len(xs) >= 5:
                if not bands or y - bands[-1][-1][0] > 4:
                    bands.append([])
                bands[-1].append((y, min(xs), max(xs)))
    boxes = [[60 + min(row[1] for row in band), 165 + band[0][0],
              60 + max(row[2] for row in band), 165 + band[-1][0]] for band in bands]
    centers = [(box[1] + box[3]) / 2 for box in boxes]
    first = next((y for y in centers if 185 <= y <= 235), 208)
    last = next((y for y in reversed(centers) if 485 <= y <= 555), 518)
    index = PET_NAMES.index(control)
    # Native command labels can merge/split into extra glyph bands. First/last
    # rows define all seven spacings without requiring seven OCR-like hits.
    y = first + (last-first)*index/6
    x = 230
    return [round(x), round(y)], dict(
        locator=locator, coordinate_basis='capture_to_client',
        point_basis='SAME_CAPTURE_KNOWN_PET_ROW_LAYOUT',
        capture_sha256=hashlib.sha256(raw).hexdigest(), png=capture['png'],
        png_size=capture['png_size'], row=index, row_boxes=boxes,
        first_last_row_centers=[first, last],
        node_geometry_failure=reason, ui_result='UNKNOWN',
        limitation='PNG_ROW_SPACING_AND_AUTHORED_ORDER_DO_NOT_PROVE_NODE_IDENTITY_OR_UI_EFFECT')


def capture_close_point(capture, locator, error):
    """Locate the authored Close label in this action's PNG, without UI PASS."""
    require_capture_geometry(capture)
    import hashlib
    from PIL import Image
    import io
    role, _, control = locator.partition('.')
    # Bags have a top-LEFT Close extension; Pet/ATS have it at top right.
    # These are label regions, not the right edge of the inventory cell grid.
    regions = dict(ats=(870, 12, 970, 65), pet=(870, 12, 970, 65),
                   companion_bag=(1220, 12, 1320, 65),
                   self_bag=(2040, 12, 2140, 65))
    if control != 'close' or role not in regions:
        raise error
    raw = Path(capture['png']).read_bytes()
    left, top, right, bottom = regions[role]
    with Image.open(io.BytesIO(raw)) as image:
        if list(image.size) != capture['png_size']:
            raise ValueError('INPUT_CAPTURE_PNG_SIZE_CHANGED_OR_MISSING')
        pixels = image.convert('RGB')
        label = [(x, y) for y in range(top, bottom) for x in range(left, right)
                 if (lambda r, g, b: min(r, g, b) >= 170 and max(r, g, b)-min(r, g, b) <= 45)
                 (*pixels.getpixel((x, y))) ]
    box = ([min(x for x, _ in label), min(y for _, y in label),
            max(x for x, _ in label), max(y for _, y in label)]
           if label else [left, top, right, bottom])
    point = [round((box[0]+box[2])/2), round((box[1]+box[3])/2)]
    return point, dict(locator=locator, coordinate_basis='capture_to_client',
        point_basis='SAME_CAPTURE_CLOSE_LABEL',
        capture_sha256=hashlib.sha256(raw).hexdigest(), png=capture['png'],
        png_size=capture['png_size'], label_region=list(regions[role]), label_box=box,
        node_geometry_failure=getattr(error, 'reason', str(error)), ui_result='UNKNOWN',
        limitation='PNG_LABEL_REGION_DOES_NOT_PROVE_NODE_IDENTITY_OR_CLOSE_EFFECT')


def capture_bag_point(capture, locator, error, steps):
    """Infer current inventory cells from the same action's screenshot.

    The established two-window layout has companion left of knight, each with
    four columns/eight rows. Points stay in the established native-size PNG;
    capture_to_client supplies the crop offset once.
    """
    require_capture_geometry(capture)
    import hashlib
    from PIL import Image
    import io
    role, _, control = locator.partition('.')
    if role not in ('self_bag', 'companion_bag') or control not in ('potion', 'equipment_item', 'resurrect_scroll', 'talkscroll', 'drop'):
        raise error
    raw = Path(capture['png']).read_bytes()
    with Image.open(io.BytesIO(raw)) as image:
        if list(image.size) != capture['png_size']:
            raise ValueError('INPUT_CAPTURE_PNG_SIZE_CHANGED_OR_MISSING')
        pixels = image.convert('RGB')
        # Grid bounds from the preserved original InventoryScene screenshot.
        # Each action samples its own PNG icons; no old capture is replayed.
        left = 2190 if role == 'self_bag' else 1376
        top, cell = 80, 140
        scores = []
        for index in range(32):
            x, y = left + (index % 4)*cell, top + (index // 4)*cell
            icon = pixels.crop((x+24, y+12, x+116, y+108))
            scores.append(sum(r >= 100 and r > g*1.5 and r > b*1.35
                              for r, g, b in icon.getdata()))
    if control in ('potion', 'equipment_item', 'resurrect_scroll', 'talkscroll'):
        uid = (65577 if control == 'talkscroll' else 65570 if control == 'resurrect_scroll' else
               steps.potion_uid(role) if control == 'potion' else steps.equipment_uid)
        if control == 'potion':
            steps.last_potion_uids[role] = uid
        rows = (module.inv.validate_kit_frame(steps.broker()._inventory_current_frame)
                if control in ('resurrect_scroll', 'talkscroll') else steps.frames()[0 if role == 'self_bag' else 1])
        native_index = next(i for i, row in enumerate(rows) if row.identifier == uid)
        if control == 'resurrect_scroll' and not 0 <= native_index < 32:
            raise ValueError('RESURRECTION_SCROLL_OUTSIDE_VISIBLE_GRID')
        if control == 'talkscroll':
            visible = steps.talkscroll_visible_slot(capture)
            if not visible['visible']:
                raise ValueError('TALKSCROLL_SLOT_NOT_CURRENTLY_VISIBLE:' + visible['reason'])
            index = visible['grid_cell']
        else:
            index = (max(range(32), key=scores.__getitem__)
                     if control == 'potion' and max(scores) >= 20 else native_index)
    else:
        # Drop on an empty lower cell inside the receiving grid, avoiding the
        # center occupied-item cell and the frame/scrollbar hit regions.
        uid, index = None, 31
    x, y = left + (index % 4 + .5)*cell, top + (index // 4 + .5)*cell
    return [round(x), round(y)], dict(
        locator=locator, coordinate_basis='capture_to_client',
        point_basis='SAME_CAPTURE_INVENTORY_GRID',
        capture_sha256=hashlib.sha256(raw).hexdigest(), png=capture['png'],
        png_size=capture['png_size'], grid_cell=index, item_uid=uid,
        **({'visible_slot': visible, 'absolute_inventory_index': native_index}
           if control == 'talkscroll' else {}),
        red_icon_scores=scores, node_geometry_failure=getattr(error, 'reason', str(error)),
        ui_result='UNKNOWN', limitation='PNG_GRID_AND_ICON_INFERENCE_DO_NOT_PROVE_ITEM_IDENTITY_OR_UI_EFFECT')


def ats_recovery_target(wrapper):
    """Choose a different recovery cell from the starting saved selection."""
    import struct
    import zlib
    from tools.local_original_session.ats_config_codec import decode_options, unwrap_blob

    slots = []
    if wrapper:
        try:
            slots = decode_options(unwrap_blob(bytes.fromhex(wrapper)))['hp_slots']
        except (ValueError, TypeError, struct.error, zlib.error):
            # Selection is a best-effort input choice, not another prerequisite.
            # The existing post-save companion_ats comparison remains decisive.
            pass
    def occupied(index):
        # Empty native item rows retain kind=2 but use f4=-1.
        return (index < len(slots) and slots[index].get(1, 0) != 0
                and slots[index].get(4, -1) != -1)
    # Same 2880x2160 control layout as the existing HP1 hit point; HP2/MP1
    # centers were checked in glfw12's before-recovery-slot-drag.png.
    if occupied(0):
        if occupied(1):
            return 'Root.Buff.01.Slot02.Item01', (516, 250)
        return 'Root.Buff.01.Slot01.Item02', (250, 250)
    return 'Root.Buff.01.Slot01.Item01', (108, 250)


def capture_control_point(capture, locator, error, steps):
    """Use the current PNG and the visually checked original control layout.

    Reference PNGs are 2880x2160. The current action's own capture supplies
    size/hash and the existing adapter supplies its current crop/client map.
    These hit points remain visual inferences, never a node or effect PASS.
    """
    require_capture_geometry(capture)
    import hashlib
    from PIL import Image
    points = {'quantity': (1296, 1930), 'ats.buff_tab': (115, 54),
              # verify_shots.py disc/disc2/disc3/disc4 bag_icon: PNG units,
              # before its old fixed crop/DPI conversion. Use our fresh map.
              'hud.bag_icon': (2530, 2100),
              # The buff area is the >> control at the upper right of the
              # 2880x2160 reconnect capture; hover exposes native remaining time.
              'hud.buff_hover': (2810, 40),
              'ats.recovery': getattr(steps, 'ats_recovery_target', ats_recovery_target(None))[1],
              'ats.save': (834, 1246)}
    if locator == 'companion_equipment.equipped':
        state = steps.broker()._companion_inventory.states[steps.member_id]
        if steps.equipment_uid == state.weapon_uid:
            points[locator] = (370, 730)
    if locator not in points:
        raise error
    raw = Path(capture['png']).read_bytes()
    import io
    with Image.open(io.BytesIO(raw)) as image:
        w, h = image.size
        if [w, h] != capture['png_size']:
            raise ValueError('INPUT_CAPTURE_PNG_SIZE_CHANGED_OR_MISSING')
    x, y = points[locator]
    return [round(x), round(y)], dict(
        locator=locator, coordinate_basis='capture_to_client',
        point_basis='SAME_CAPTURE_KNOWN_CONTROL_LAYOUT',
        capture_sha256=hashlib.sha256(raw).hexdigest(), png=capture['png'],
        png_size=[w, h], reference_png_size=[2880, 2160],
        reference_png_point=[x, y],
        reference_control=('HUD_INVENTORY_BUTTON' if locator == 'hud.bag_icon' else
                           'HUD_CHAT_QUANTITY_INPUT_STRIP' if locator == 'quantity' else
                           'COMPANION_WEAPON_SLOT' if locator.startswith('companion_equipment') else
                           'ATS_RECOVERY_TAB_CONTROL'),
        node_geometry_failure=getattr(error, 'reason', str(error)), ui_result='UNKNOWN',
        limitation='VISUALLY_CHECKED_CONTROL_LAYOUT_DOES_NOT_PROVE_NODE_IDENTITY_OR_UI_EFFECT')


def corpse_grid_to_capture(capture, knight, companion, scene_size):
    """Preserve the separately approved corpse equation; never use NPC body anchors."""
    import math
    require_capture_geometry(capture)
    width, height = scene_size
    if not all(math.isfinite(n) and n > 0 for n in (width, height)):
        raise ValueError('RESURRECTION_SCENE_SIZE_UNKNOWN')
    if knight[0] != companion[0]:
        raise ValueError('RESURRECTION_SAME_MAP_REQUIRED')
    dx, dy = companion[1]-knight[1], companion[2]-knight[2]
    # Original basis: work/source_play_slice/rules/review2/README.md:17 and
    # rules/projection-oracle.tsv. The old host camera/offsets are not reused.
    x, y = width/2 + 48*(dx+dy), height/2 - 24*(dx-dy)
    dw, dh = capture['read_size']
    cx, cy, cw, ch = capture['crop']
    point = [round(x*dw/width-cx), round(y*dh/height-(dh-cy-ch))]
    if not 0 <= point[0] < cw or not 0 <= point[1] < ch:
        raise ValueError('RESURRECTION_TARGET_OUTSIDE_CAPTURE')
    return point


class MemoryUi:
    """Bounded passive borrow of this run's UI list and source-owned nodes.

    Hierarchy/string offsets and child-role slots reuse owned_ui_binding.hpp.
    Node position/size/scale reuse companion3_native_nopatch.hpp and HP observer.
    The anchor/axis-aligned scene-to-drawable map below is explicitly inferred;
    its use never produces UI PASS or proves a native presentation transform.
    """
    def __init__(self, steps):
        import struct
        self.struct, self.steps = struct, steps
        self.reader = steps.manual.consumer.reader
        self.reader.validate()
        shared = self.reader.sampler
        # RetainedSceneReader leaves bytes == total after its scene/world/input
        # tick. Reusing that sampler's route() spends the UI allowance against
        # an already exhausted leaf counter. Keep an independent route sample
        # with the original sampler's contract/caps; never reset shared state.
        self.sampler = type(shared)(self.reader.backend, shared.c, shared.g)
        self.sampler.bytes = 0
        self.base = self.sampler.g['base']
        self.reads = {}
        route = self.sampler.route()
        self.manager = self.sampler.unique(route[-1], 'UI')
        if self.ptr(self.manager) != self.base + 0x1182c50:
            raise ValueError('UI_MANAGER_TYPE_UNKNOWN')

    def read(self, at, size):
        if not 0x10000 <= at <= 0x7fffffffffff - size or not 0 < size <= 4096:
            raise ValueError('UI_READ_BOUND')
        key = (at, size)
        if key not in self.reads:
            if sum(len(v) for v in self.reads.values()) + size > 262144:
                raise ValueError('UI_READ_BUDGET')
            value = self.reader.backend.read(at, size, self.base if self.base <= at < self.base + self.sampler.g['size'] else None)
            if type(value) is not bytes or len(value) != size:
                raise ValueError('UI_READ_PARTIAL')
            self.reads[key] = value
        return self.reads[key]

    def ptr(self, at):
        return self.struct.unpack('<Q', self.read(at, 8))[0]

    def vec(self, at):
        import math
        value = self.struct.unpack('<ff', self.read(at, 8))
        if not all(math.isfinite(n) and abs(n) < 100000 for n in value):
            raise ValueError('UI_GEOMETRY_NONFINITE')
        return value

    def string(self, at):
        raw = self.read(at, 32)
        size, capacity = self.struct.unpack_from('<QQ', raw, 16)
        if size > 128 or capacity < size:
            raise ValueError('UI_NAME_BOUND')
        return (raw[:size] if capacity < 16 else self.read(self.struct.unpack_from('<Q', raw)[0], size)).decode('utf-8') if size else ''

    def named_layout(self, name, offset=0x388):
        # Reuse the existing bounded exact-key MSVC unordered_map reader.
        from tools.local_original_session.hp_status_observe import _HudRead
        proxy = type('UiReader', (), dict(g=self.sampler.g, read=lambda _, at, size, image=False: self.read(at, size)))()
        entry = _HudRead(proxy).find(self.manager + offset, name.encode('ascii'))
        return self.ptr(entry + 0x30) if entry else None

    def layouts(self):
        head, count = self.ptr(self.manager + 0x350), self.ptr(self.manager + 0x358)
        if count > 64:
            raise ValueError('UI_LAYOUT_COUNT_BOUND')
        node, result = self.ptr(head), []
        for _ in range(count):
            if node == head:
                break
            result.append(self.ptr(node + 0x30)); node = self.ptr(node)
        return result

    def layout(self, role):
        if role == 'pet':
            # TickPetApply/FindPetLayoutRaw maps the first pet-vtable entry,
            # then retires other views. Do not pick a later actor-matching
            # stale layout that the currently mapped DLL does not own.
            current = next((p for p in self.layouts()
                            if self.ptr(p) == self.base + 0x122b6c0), None)
            matches = [current] if current and self.ptr(current + 0xb8) == self.steps.actor_uid else []
        elif role == 'quantity':
            layout = self.named_layout('HudChatLayout', 0x348)
            if not layout or self.ptr(layout) != self.base + 0x121d2d0:
                raise ValueError('QUANTITY_HUD_LAYOUT_REQUIRED')
            helper = self.ptr(layout + 0x150)
            if not helper or not self.ptr(helper + 0x1c0):
                raise ValueError('QUANTITY_ACTIVE_CALLBACK_REQUIRED')
            matches = [layout]
        else:
            name = {'ats': 'ATSLayout', 'companion_ats': 'SLCompATS', 'companion_spell': 'SLCompSpell',
                    'self_bag': 'InventoryLayout',
                    'self_equipment': 'CharacterInfoLayout',
                    'companion_bag': 'SLCompBag', 'companion_equipment': 'SLCompGear'}[role]
            value = self.named_layout(name)
            matches = [value] if value else []
        if len(matches) != 1:
            raise ValueError('UI_LAYOUT_NOT_UNIQUE:' + role + ':' + str(len(matches)))
        return matches[0]

    def visible(self, node):
        # Evaluate only an exact, simple original visibility getter, never call it.
        code = self.read(self.ptr(self.ptr(node) + 0x150), 8)
        if code[:3] == b'\x0f\xb6\x81' and code[7] == 0xc3:
            offset = self.struct.unpack_from('<i', code, 3)[0]
        elif code[:3] == b'\x0f\xb6\x41' and code[4] == 0xc3:
            offset = code[3]
        elif code[:2] == b'\x8a\x81' and code[6] == 0xc3:
            offset = self.struct.unpack_from('<i', code, 2)[0]
        elif code[:2] == b'\x8a\x41' and code[3] == 0xc3:
            offset = code[2]
        else:
            raise ValueError('UI_VISIBILITY_GETTER_UNSUPPORTED')
        if not 0 <= offset < 0x400:
            raise ValueError('UI_VISIBILITY_OFFSET_BOUND')
        return self.read(node + offset, 1) == b'\x01'

    def children(self, node):
        table = self.ptr(node)
        if self.ptr(table + 0x1f8) != self.base + 0x1498e0:
            return []
        first, last = self.ptr(node + 0x178), self.ptr(node + 0x180)
        if last < first or (last - first) % 8 or last - first > 4096:
            raise ValueError('UI_CHILD_VECTOR_BOUND')
        return [self.ptr(at) for at in range(first, last, 8)]

    def spell_children(self, node):
        # Original SpellLayout can hold visible rows below a Cocos node whose
        # getter differs from children(). The existing native FindSlotNode
        # walks +178/+180; accept that vector only when every child points back.
        try:
            first, last = self.ptr(node + 0x178), self.ptr(node + 0x180)
            if first == last:
                return []
            if first < 0x10000 or last < first or (last - first) % 8 or last - first > 4096:
                return []
            children = [self.ptr(at) for at in range(first, last, 8)]
            return children if all(child and self.ptr(child + 0x190) == node
                                   for child in children) else []
        except (ValueError, OSError):
            return []

    def shown(self, node):
        # Local visible bits alone include children of hidden duplicate panels.
        seen = set()
        while node:
            if node in seen or len(seen) >= 24:
                return False
            seen.add(node)
            if not self.visible(node):
                return False
            node = self.ptr(node + 0x190)
        return True

    def path(self, root, path):
        nodes = [root]
        parts = path.split('.')
        if parts[0] in ('Root', self.string(root + 0x1a8)):
            # layout+30 is the owning window node; the authored Root can be
            # that node OR a nested child. Native Lookup starts at this owner.
            nodes += [p for p in self.children(root) if self.string(p + 0x1a8) == parts[0]]
            parts = parts[1:]
        for part in parts:
            matches = [p for node in nodes for p in self.children(node)
                       if self.string(p + 0x1a8) == part]
            if len(matches) > 1:
                shown = [p for p in matches if self.shown(p)]
                if shown:
                    matches = shown
            if not matches:
                raise ValueError('UI_NODE_NOT_UNIQUE:' + path + ':' + part)
            # Carry duplicate ancestors forward: a later path component can
            # distinguish the current panel from a same-named decoration.
            nodes = list(dict.fromkeys(matches))
        # Keep only visible descendants of this step's selected layout. Same
        # names in another/hidden authored panel are not this window's button.
        nodes = [node for node in nodes if self.shown(node) and self.descendant(node, root)]
        if len(nodes) != 1:
            raise ValueError('UI_NODE_NOT_UNIQUE:' + path + ':' + path.split('.')[-1])
        return nodes[0]

    def descendant(self, node, root):
        seen = set()
        while node and node not in seen and len(seen) < 24:
            if node == root:
                return True
            seen.add(node)
            node = self.ptr(node + 0x190)
        return False

    def slot(self, layout, role, item_uid):
        grid = self.ptr(layout + 0xb8)
        offset = 0x158 if 'equipment' in role else 0xec8
        first, last = self.ptr(grid + offset), self.ptr(grid + offset + 8)
        if last < first or (last-first) % 8 or last-first > 8192:
            raise ValueError('UI_SLOT_VECTOR_BOUND')
        matches = []
        for at in range(first, last, 8):
            node = self.ptr(at)
            metadata = self.ptr(node + 0x808) if node else 0
            if metadata and self.ptr(metadata) == item_uid:
                matches.append(node)
        root = self.ptr(layout + 0x30)
        matches = [node for node in matches if self.shown(node) and self.descendant(node, root)]
        if len(matches) != 1:
            raise ValueError('UI_ITEM_SLOT_NOT_UNIQUE:' + role)
        return matches[0]

    def spell_slot(self, layout, role, control):
        root = self.ptr(layout + 0x30)
        if _selected_steps in ('ats_window_spell', 'ats_window_heal', 'ats_window_reset_dragoff') and role == 'companion_spell' \
                and control.startswith('learned_'):
            # The DLL recorded the displayed slots of this owned spell window.
            # A tree scan can find duplicate SlotNodes for the same spell row.
            population = self.steps.ats_spell_open_result(self.steps.ats_window_delivery())
            if (not population or population.get('layout') != layout
                    or population.get('root') != root):
                raise ValueError('ATS_SPELL_CURRENT_DRAG_POPULATION_REQUIRED')
            target = self.steps.ats_spell_rows[control.split('learned_', 1)[1]]
            matches = [entry for entry in self.steps.ats_spell_population_rows(population)
                       if entry.get('spell_row') == target and entry.get('visible') is True]
            if len(matches) != 1:
                raise ValueError('ATS_SPELL_CURRENT_VISIBLE_DRAG_ROW_REQUIRED')
            entry = matches[0]
            node, panel, metadata = (entry.get(key) for key in ('node', 'panel', 'metadata'))
            if (not all(type(value) is int and value > 0 for value in (node, panel, metadata))
                    or self.ptr(node) != self.base + 0x1232f30
                    or self.ptr(node + 0x830) != panel or self.ptr(node + 0x808) != metadata
                    or not self.descendant(node, root) or not self.descendant(panel, root)
                    or not self.shown(panel)
                    or self.struct.unpack('<i', self.read(metadata + 8, 4))[0] != 1
                    or self.struct.unpack('<i', self.read(metadata, 4))[0] != target
                    or self.struct.unpack('<i', self.read(metadata + 0xc, 4))[0] != entry.get('icon')):
                raise ValueError('ATS_SPELL_RECORDED_SLOT_NOT_CURRENT')
            return node
        if _selected_steps in ('ats_window_heal', 'ats_window_reset_dragoff') and role == 'companion_ats' \
                and control in ('heal_hp', 'heal_status'):
            index = 0 if control == 'heal_hp' else 4
            return self.heal_slot(layout, index)
        if _selected_steps in ('ats_window_spell', 'ats_window_reset_dragoff') and role == 'companion_ats' \
                and control in ('buff_spell', 'battle_spell', 'conditional_spell'):
            # glfw73: the 18 BehaviorSlot roots under ListView+CE0 have empty
            # names. Select the actual child-vector cell, never its path text.
            if control == 'buff_spell':
                area = self.path(root, 'Root.Buff.03.ListView_Slot')
                inner = self.ptr(area + 0xce0)
                if not inner or not self.descendant(inner, root):
                    raise ValueError('COMPANION_ATS_SPELL_TARGET_MISSING:buff_spell:INNER')
                cells = self.children(inner)
                index, count = 0, 18
            else:
                kind = 'sequence' if control == 'battle_spell' else 'conditional'
                entry = self.steps.ats_spell_before['battle_slots'][
                    self.steps.ats_spell_battle_targets[kind]]
                index = entry['index']
                if type(index) is not int or not 0 <= index < 8:
                    raise ValueError('COMPANION_ATS_SPELL_TARGET_MISSING:' + control + ':INDEX')
                if control == 'battle_spell':
                    area = self.path(root, 'Root.Combat.01.Slot01')
                    cells, count = self.children(area), 8
                else:
                    area = self.path(root, f'Root.Combat.02.Slot_{index + 1:02d}.Slot')
                    cells, index, count = self.children(area), 0, 1
            if len(cells) != count or len(set(cells)) != count:
                raise ValueError('COMPANION_ATS_SPELL_TARGET_MISSING:' + control + ':CHILDREN')
            node = cells[index]
            panels = self.children(node)
            if (self.ptr(node) != self.base + 0x1232f30
                    or not self.descendant(node, area) or not self.shown(node)
                    or len(panels) != 1 or self.ptr(node + 0x830) != panels[0]
                    or self.ptr(panels[0]) != self.base + 0x1244cb8
                    or self.string(panels[0] + 0x1a8) != 'Panel_Slot'
                    or not self.descendant(panels[0], root) or not self.shown(panels[0])
                    or any(value <= 0 for value in self.vec(panels[0] + 0x6c))):
                raise ValueError('COMPANION_ATS_SPELL_TARGET_MISSING:' + control + ':PANEL')
            return node
        area = (root if control.startswith('learned_') else self.path(root, {
                'buff_spell': 'Root.Buff.03.ListView_Slot',
                'battle_spell': 'Root.Combat.01.Slot01.Item_0',
                'conditional_spell': 'Root.Combat.02.Slot_01.Slot.FileNode_1'}[control]))
        pending, seen, slots = [area], set(), []
        while pending:
            node = pending.pop()
            if len(seen) >= 512:
                raise ValueError('SPELL_SLOT_TREE_BOUND')
            if node in seen:
                continue
            seen.add(node)
            children = self.children(node)
            if role == 'companion_ats' and control == 'buff_spell' and node == area:
                # ListView::addChild attaches BehaviorSlot rows to its inner
                # container. That container need not appear in the child list.
                inner = self.ptr(area + 0xce0)
                if inner and inner not in children and self.descendant(inner, root):
                    children.append(inner)
            pending.extend(children)
            # SpellSlot.csb's SlotNode root is named "Node"; Panel_Slot is
            # its child. B07310 casts that root (TD 16895C0, vptr 1232F30)
            # before B042D0 supplies metadata. Names do not identify slots.
            try:
                if role == 'companion_ats':
                    if self.string(node + 0x1a8) != 'Node':
                        continue
                elif self.ptr(node) != self.base + 0x1232f30:
                    continue
                if not self.shown(node):
                    continue
                panel = self.ptr(node + 0x830)
                if (not panel or not self.descendant(panel, node)
                        or not self.descendant(panel, root)
                        or (role == 'companion_ats'
                            and self.string(panel + 0x1a8) != 'Panel_Slot')):
                    continue
                metadata = self.ptr(node + 0x808)
                if control.startswith('learned_'):
                    if not metadata or self.struct.unpack('<i', self.read(metadata + 8, 4))[0] != 1:
                        continue
                    row = self.struct.unpack('<i', self.read(metadata, 4))[0]
                    if row != self.steps.ats_spell_rows[control.split('_', 1)[1]]:
                        continue
            except ValueError:
                continue
            slots.append(node)
        if control.startswith('learned_') and len(slots) != 1:
            raise ValueError('LEARNED_SPELL_NATIVE_SLOT_NOT_UNIQUE')
        if not control.startswith('learned_') and not slots:
            raise ValueError('COMPANION_ATS_SPELL_TARGET_MISSING:' + control)
        if control == 'buff_spell':
            container = self.ptr(area + 0xce0)
            def buff_slot_order(node):
                # Selection order within the shared native container only;
                # this does not project a point or supply an input coordinate.
                for _ in range(8):
                    if not node:
                        break
                    parent = self.ptr(node + 0x190)
                    if parent in (area, container):
                        x, y = self.vec(node + 0x3c)
                        return -y, x
                    node = parent
                raise ValueError('ATS_BUFF_GRID_ANCESTOR_REQUIRED')
            slots.sort(key=buff_slot_order)
        return slots[0]

    def spell_rows(self, layout):
        root = self.ptr(layout + 0x30)
        original = self.ptr(layout) == self.base + 0x12341c8
        pending, seen, rows = [root], set(), []
        while pending:
            node = pending.pop()
            if node in seen or len(seen) >= 512:
                raise ValueError('SPELL_DISPLAY_TREE_BOUND')
            seen.add(node)
            pending.extend(self.spell_children(node) if original else self.children(node))
            # Read SlotNode+808, not the similarly named visual child.
            if self.ptr(node) != self.base + 0x1232f30 or not self.shown(node):
                continue
            try:
                panel = self.ptr(node + 0x830)
                metadata = self.ptr(node + 0x808)
                if not panel or not metadata or not self.descendant(panel, root):
                    continue
                kind = self.struct.unpack('<i', self.read(metadata + 8, 4))[0]
                row = self.struct.unpack('<i', self.read(metadata, 4))[0]
                icon = self.struct.unpack('<i', self.read(metadata + 0xc, 4))[0]
                name = self.string(metadata + 0x30)
            except ValueError:
                continue
            rows.append(dict(node=node, metadata=metadata, kind=kind, spell_row=row,
                             icon=icon, name=name))
        return rows

    def heal_slot(self, layout, index):
        root = self.ptr(layout + 0x30)
        area = self.path(root, f'Root.Help.02.Slot_{index + 1:02d}.Slot.FileNode_1')
        pending, slots = [area], []
        while pending:
            node = pending.pop()
            if self.ptr(node) == self.base + 0x1232f30:
                slots.append(node)
            else:
                pending.extend(self.children(node))
        if len(slots) != 1 or not self.shown(slots[0]):
            raise ValueError('ATS_HEAL_CURRENT_TARGET_SLOT_REQUIRED:' + str(index))
        return slots[0]

    def heal_percent_options(self, root):
        layout = self.layout('companion_ats')
        menu = self.path(root, 'Root.Help.02.Slot_01.Pulldown_Menu.Sub_Menu.ListView')
        inner = self.ptr(menu + 0xce0)
        if not inner or not self.descendant(inner, root):
            raise ValueError('ATS_HEAL_MENU_CURRENT_INNER_REQUIRED')
        options = []
        for panel in self.children(inner):
            if not self.shown(panel):
                continue
            # Lent panels have duplicate names. Use the live button bounds.
            button = self.path(panel, 'Button_225')
            _, facts = self.node_point(button, 'companion_ats.heal_percent_option', layout)
            options.append(dict(panel=panel, button=button,
                                scene_bounds=facts['scene_bounds']))
        return sorted(options, key=lambda option: -option['scene_bounds']['top'])

    def point(self, locator):
        role, _, control = locator.partition('.')
        layout = self.layout(role)
        root = self.ptr(layout + 0x30)
        paths = dict(close='Root.Bottom.Bt_Quit' if role == 'ats' else 'Root.Bt_Close',
                     window_close='Root.Bt_Close',
                     save='Root.Bottom.Bt_Save', reset='Root.Bottom.Bt_Reset', buff_tab='Root.Tab.Bt_Buff',
                     combat_tab='Root.Tab.Bt_Combat', heal_tab='Root.Tab.Bt_Help',
                     heal_percent_menu='Root.Help.02.Slot_01.Pulldown_Menu.Bt_Pdn',
                     spell_open='Root.Bt',
                     hp_slot2='Root.Buff.01.Slot01.Item02',
                     hp_percent='Root.Buff.01.HPTextField.TextField_23',
                     recovery=getattr(self.steps, 'ats_recovery_target',
                         (semantic_plan.get('recovery_node_path', 'Root.Buff.01.Slot01.Item01'), None))[0])
        if role == 'pet':
            node = self.path(root, 'Root.Pet_Main.ListviewScroll.ListView.' + control)
        elif control in ('potion', 'equipment_item', 'equipped', 'resurrect_scroll', 'talkscroll'):
            item = (65577 if control == 'talkscroll' else 65570 if control == 'resurrect_scroll' else
                    self.steps.potion_uid(role) if control == 'potion' else self.steps.equipment_uid)
            if control == 'potion':
                self.steps.last_potion_uids[role] = item
            node = self.slot(layout, role, item)
            if control in ('potion', 'equipment_item', 'resurrect_scroll', 'talkscroll') and role in ('self_bag', 'companion_bag'):
                # Virtualized Slot nodes can have size=(0,0): their origin is
                # not the center of the visible item. Preserve the native UID
                # lookup, but use this action's PNG grid/icon for the hit point.
                self.validate()
                point, facts = capture_bag_point(self.steps.last_capture_context, locator,
                    ValueError('VIRTUAL_INVENTORY_SLOT_CENTER_FROM_CAPTURE'), self.steps)
                return point, dict(facts, layout=layout, node=node)
            if control == 'equipped':
                state = self.steps.broker()._companion_inventory.states[self.steps.member_id]
                if item == state.weapon_uid:
                    self.validate()
                    point, facts = capture_control_point(self.steps.last_capture_context, locator,
                        ValueError('WEAPON_SLOT_CENTER_FROM_CAPTURE'), self.steps)
                    return point, dict(facts, layout=layout, node=node)
        elif control == 'drop':
            node = self.ptr(layout + 0xb8)
            if role in ('self_bag', 'companion_bag'):
                self.validate()
                point, facts = capture_bag_point(self.steps.last_capture_context, locator,
                    ValueError('INVENTORY_EMPTY_DROP_CELL_FROM_CAPTURE'), self.steps)
                return point, dict(facts, layout=layout, node=node)
        elif control in ('learned_buff', 'learned_battle', 'learned_conditional',
                         'learned_hp', 'learned_status', 'heal_hp', 'heal_status',
                         'buff_spell', 'battle_spell', 'conditional_spell'):
            node = self.spell_slot(layout, role, control)
            panel = self.ptr(node + 0x830)
            if not panel:
                raise ValueError('SPELL_SLOT_PANEL_REQUIRED:' + locator)
            node = panel
        elif role == 'companion_ats' and control == 'heal_percent30':
            node = self.heal_percent_options(root)[2]['button']
        elif role == 'quantity':
            helper = self.ptr(layout + 0x150)
            node = self.ptr(self.ptr(helper + 0x28) + 0x730)
        else:
            node = self.path(root, paths[control]) if control else root
        if role == 'companion_ats' and control == 'hp_slot2':
            # The authored SlotNode has size (0, 0): its origin is the corner
            # of the real 62x62 hit area. Native 95E010 uses Panel_Slot +830.
            panel = self.ptr(node + 0x830)
            if not panel:
                raise ValueError('ATS_WINDOW_PANEL_SLOT_REQUIRED')
            node = panel
        point, facts = self.node_point(node, locator, layout)
        if ATS_WINDOW_SCENARIO and locator in ('companion_ats.close', 'ats.window_close'):
            # Simultaneously open ATS windows have independent roots. The
            # close point must come from this registry's current child node.
            facts.update(owned_window_registry='SLCompATS' if role == 'companion_ats' else 'ATSLayout',
                         owned_window_root=root, node_path=paths[control])
        return point, facts

    def node_point(self, node, locator, layout, require_capture=True):
        # Produce scene_bounds from the established window hierarchy. The
        # single node_to_capture path owns scene-to-capture presentation.
        chain, seen = [], set()
        current = node
        while current:
            if current in seen or len(chain) >= 24:
                raise ValueError('UI_PARENT_CHAIN_BOUND')
            seen.add(current)
            if not self.visible(current):
                raise ValueError('UI_NODE_HIDDEN:' + locator)
            chain.append(dict(node=current, position=self.vec(current + 0x3c),
                              scale=self.vec(current + 0x30), size=self.vec(current + 0x6c),
                              anchor=self.vec(current + 0x64)))
            current = self.ptr(current + 0x190)
        # Nodes use the DLL-known window root hierarchy (+30 owner,
        # +190 parents, +3C position, +6C size; native B5A1D0 excludes ancestor).
        # The terminal scene's anchor is not another window-local transform.
        # Controls share the successful close button's window-to-scene basis.
        # Applying the terminal scene's anchor a second time can put
        # an on-screen control's inferred point outside the capture.
        corners = [[0., 0.], list(chain[0]['size'])]
        for entry in chain[:-1]:
            if not all(0 <= n <= 1 for n in entry['anchor']) or not all(0 < n <= 16 for n in entry['scale']):
                raise ValueError('UI_INFERRED_AXIS_ALIGNED_GEOMETRY_UNSUPPORTED')
            for corner in corners:
                for axis in (0, 1):
                    corner[axis] = ((corner[axis]-entry['anchor'][axis]*entry['size'][axis])
                                    *entry['scale'][axis]+entry['position'][axis])
        width, height = chain[-1]['size']
        capture = self.steps.last_capture_context
        if width <= 0 or height <= 0:
            raise ValueError('UI_SCENE_CONTENT_SIZE_UNKNOWN')
        bounds = dict(left=min(p[0] for p in corners), bottom=min(p[1] for p in corners),
                      right=max(p[0] for p in corners), top=max(p[1] for p in corners), visible=True)
        point, facts = node_to_capture(capture, bounds, [width, height], require_capture)
        self.validate()
        return point, dict(facts, locator=locator, node=node, layout=layout, chain=chain,
            route_typed_bytes=self.sampler.bytes,
            ui_result='UNKNOWN', limitation='ANCHOR_OFFSET_AND_SCENE_PRESENTATION_TRANSFORM_INFERRED')

    def validate(self):
        for (at, size), before in self.reads.items():
            after = self.reader.backend.read(at, size, self.base if self.base <= at < self.base + self.sampler.g['size'] else None)
            if after != before:
                raise ValueError('UI_MEMORY_CHANGED_DURING_GEOMETRY')
        self.reader.validate()

class CompanionScenarioSteps(PrivateSteps):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.named_scenario = any(s[0] == 'scenario_prepare' for s in self.steps)
        self.blocked = None
        self.action_observations = {}
        self.last_potion_uids = {}
        self.resurrect_scenario = any(s[1] == 'resurrect-preconditions' for s in self.steps)
        self.talkscroll_scenario = any(s[1] == 'talkscroll-preconditions' for s in self.steps)

    def finish(self, row):
        kind = self.steps[self.index][0]
        name = self.steps[self.index][1]
        optional_quantity_focus = kind == 'private_input' and name in (
            'give-quantity-focus', 'take-quantity-focus')
        if optional_quantity_focus and row.get('status') not in ('OBSERVED', 'POSTED'):
            # The native quantity strip may already own keyboard focus. Keep
            # this click's actual refusal, but still send the one digit/Enter.
            row = dict(row, continue_quantity_keys=True)
        if self.resurrect_scenario:
            # Preserve state/errors even if native input or a prerequisite failed.
            row = dict(row, resurrection_observation=self.resurrection_snapshot())
        super().finish(row)
        if not self.named_scenario:
            return
        success = row.get('status') in ('OBSERVED', 'POSTED', 'WAITED', 'SKIPPED')
        if kind == 'pet':
            success = row.get('status') == 'REPLIED' and row.get('reply', {}).get('status') not in (None, 'UNKNOWN', 'REFUSED')
        if not success and not optional_quantity_focus and self.blocked is None:
            self.blocked = dict(step=name, status=row.get('status'), reason=row.get('reason'))

    def broker(self):
        return module.current_kit(self.manual)[0][0].broker

    def frames(self):
        broker = self.broker()
        return (module.inv.validate_kit_frame(broker._inventory_current_frame),
                module.inv.validate_kit_frame(broker._companion_inventory.frames[self.member_id]))

    def self_bag_visibility(self):
        ui = MemoryUi(self)
        layout = ui.named_layout('InventoryLayout')
        shown = bool(layout and ui.shown(ui.ptr(layout + 0x30)))
        ui.validate()
        return dict(layout=layout, shown=shown)

    def resurrection_snapshot(self):
        result = dict(scroll_uid=65570, scroll_template=28)
        try:
            broker = self.broker()
            result['companion_errors'] = list(getattr(broker, '_companion_errors', ()))
            result['companion_error_params'] = list(getattr(broker, '_companion_error_params', ()))
            result['companion_untargeted_params'] = list(getattr(broker, '_companion_untargeted_params', ()))
            result['raw_item_uses'] = [dict(r) for r in getattr(self, 'resurrection_raw_uses', ())]
            current = module.current_kit(self.manual)[0]
            owner_uid = current[3].uid
            actors = [a for a in broker._world.companions.active.values()
                      if a.owner_ref.uid == owner_uid
                      and (not hasattr(self, 'actor_uid') or a.ref.uid == self.actor_uid)]
            if len(actors) != 1:
                result['actor_reason'] = 'OWNED_COMPANION_NOT_UNIQUE_OR_RETIRED'
            else:
                actor = actors[0]
                result.update(actor=actor.ref.uid, member=actor.record.character_id,
                              alive=actor.record.alive, hp=actor.record.hp)
                # kill() retains the corpse by UID while invalidating its old
                # live ref. Match the server's retained-corpse lookup; living
                # actors and the owner still require their current generation.
                dead = actor.record.alive is False
                entity = (broker._world.entities.get(actor.ref.uid) if dead else
                          broker._world.entities.resolve(actor.ref))
                owner = broker._world.entities.resolve(actor.owner_ref)
                result.update(actor_ref_generation=actor.ref.generation,
                              entity_generation=entity.generation if entity is not None else None,
                              entity_lookup='RETAINED_CORPSE_UID' if dead else 'CURRENT_ACTOR_REF')
                if entity is None:
                    result['actor_reason'] = ('RETAINED_CORPSE_ENTITY_MISSING' if dead else
                                              'CURRENT_COMPANION_ENTITY_REF_MISSING_OR_STALE')
                elif owner is None:
                    result['actor_reason'] = 'CURRENT_OWNER_ENTITY_REF_MISSING_OR_STALE'
                elif not owner.alive:
                    result['actor_reason'] = 'CURRENT_LIVING_OWNER_REQUIRED'
                elif entity.alive != actor.record.alive:
                    result['actor_reason'] = 'COMPANION_RECORD_ENTITY_LIFE_MISMATCH'
                else:
                    result.update(companion_position=[entity.map_id, entity.x, entity.y],
                                  knight_position=[owner.map_id, owner.x, owner.y])
        except Exception as error:
            result['observation_error'] = str(error)[:300]
        # Inventory cost remains observable when the corpse has been retired.
        try:
            rows = module.inv.validate_kit_frame(self.broker()._inventory_current_frame)
            scrolls = [r for r in rows if r.identifier == 65570]
            if scrolls and (len(scrolls) != 1 or scrolls[0].template_bits != 28):
                raise ValueError('RESURRECTION_SCROLL_UID_TEMPLATE_MISMATCH')
            result['scroll_quantity'] = dict(scrolls[0].raw_fields).get(4, 0) if scrolls else 0
        except Exception as error:
            result['scroll_observation_error'] = str(error)[:300]
        try:
            saved_path = Path(self.broker()._companion_store.path)
            result['companion_json'] = dict(path=str(saved_path), status='UNKNOWN')
            if saved_path.stat().st_size > 1048576:
                raise ValueError('COMPANION_JSON_OBSERVATION_SIZE_BOUND')
            saved = json.loads(saved_path.read_text(encoding='utf-8'))
            if saved.get('schema') != 1 or not isinstance(saved.get('records'), list):
                raise ValueError('COMPANION_JSON_SCHEMA_REQUIRED')
            member = result.get('member', getattr(self, 'member_id', None))
            matches = [r for r in saved['records'] if r.get('character_id') == member]
            if len(matches) != 1:
                raise ValueError('COMPANION_JSON_MEMBER_NOT_UNIQUE')
            row = matches[0]
            result['companion_json'].update(status='OBSERVED', member=member,
                alive=row.get('alive'), hp=row.get('hp'), owner_character_id=row.get('owner_character_id'))
        except Exception as error:
            result.setdefault('companion_json', dict(status='UNKNOWN'))['reason'] = str(error)[:300]
        return result

    def install_resurrection_probe(self):
        # Observe actual decoded CS0960 bytes. Never manufacture params or alter
        # dispatch. Scope to this broker and UID; restore at original close.
        from tools.local_original_session import world_bridge
        original, broker = world_bridge._item_use_probe, self.broker()
        self.resurrection_raw_uses = []
        def probe(observed_broker, frame):
            record = original(observed_broker, frame)
            if observed_broker is broker:
                try:
                    pb = world_bridge.ack.realm.pb
                    with pb.parse_message(frame.payload, limits=pb.WireLimits(
                            max_body=4096, max_fields=8, max_field_bytes=2048)) as outer:
                        uid, params = outer.occurrences(1), outer.occurrences(2)
                        if len(uid) != 1 or uid[0].wire_type != 0 or uid[0].value != 65570:
                            return record
                        # Receipt alone cancels the follow-up corpse click,
                        # including a malformed/missing nested params message.
                        observation = dict(opcode='0x0960', item_uid=65570,
                                           raw_params_hex=None, params=[])
                        self.resurrection_raw_uses.append(observation)
                        self.resurrection_raw_uses[:] = self.resurrection_raw_uses[-16:]
                        if len(params) != 1 or params[0].wire_type != 2:
                            raise ValueError('RESURRECTION_SCROLL_PARAMS_MISSING_OR_MALFORMED')
                        raw = bytes(params[0].value)
                    # Save raw bytes even when the nested message is malformed.
                    observation['raw_params_hex'] = raw.hex()
                    record['raw_params_hex'] = raw.hex()
                    with pb.parse_message(raw, limits=pb.WireLimits(
                            max_body=2048, max_fields=16, max_field_bytes=256)) as nested:
                        observation['params'] = [dict(number=f.number, wire_type=f.wire_type,
                            value=f.value if isinstance(f.value, int) else bytes(f.value).hex())
                            for f in nested.fields]
                except Exception as error:
                    self.resurrection_raw_uses.append(dict(observation_error=str(error)[:200]))
            return record
        self.resurrection_probe = (world_bridge, original, probe)
        world_bridge._item_use_probe = probe

    def resurrection_scroll_arrived(self):
        return any(r.get('opcode') == '0x0960' and r.get('item_uid') == 65570
                   for r in getattr(self, 'resurrection_raw_uses', ()))

    def close(self):
        try:
            if self.resurrect_scenario:
                self.results.append(dict(kind='resurrection_close_observe', name='resurrect-close',
                    resurrection_observation=self.resurrection_snapshot(), ui_result='UNKNOWN'))
            super().close()
        finally:
            installed = getattr(self, 'talkscroll_send_probe', None)
            if installed:
                broker, probe, owned, saved = installed
                if broker._world_send is probe:
                    if owned:
                        broker._world_send = saved
                    else:
                        delattr(broker, '_world_send')
            installed = getattr(self, 'resurrection_probe', None)
            if installed:
                bridge, original, probe = installed
                if bridge._item_use_probe is probe:
                    bridge._item_use_probe = original

    def resurrection_point(self, capture):
        before = self.resurrection_snapshot()
        if before.get('actor_reason'):
            raise ValueError(before['actor_reason'])
        if before.get('actor') != self.actor_uid or before.get('alive') is not False:
            raise ValueError('CURRENT_DEAD_COMPANION_REQUIRED_FOR_CLICK')
        companion, knight = before['companion_position'], before['knight_position']
        if companion[0] != knight[0]:
            raise ValueError('RESURRECTION_SAME_MAP_REQUIRED')
        ui = MemoryUi(self)
        director = ui.ptr(ui.base + 0x1807fd8)
        if ui.ptr(director) != ui.base + 0x1237f90:
            raise ValueError('RESURRECTION_DIRECTOR_TYPE_UNKNOWN')
        # Existing original entry_point.hpp SCENE_READ uses Director+150;
        # run104_drop_camera_parent_contract traces getter 1D442B to this field.
        # Node+6c content size is the same passive convention as MemoryUi.point.
        scene = ui.ptr(director + 0x150)
        size = ui.vec(scene + 0x6c)
        point = corpse_grid_to_capture(capture, knight, companion, size)
        ui.validate()
        after = self.resurrection_snapshot()
        if any(before.get(k) != after.get(k) for k in ('actor', 'alive', 'companion_position', 'knight_position')):
            raise ValueError('RESURRECTION_ACTORS_CHANGED_DURING_GEOMETRY')
        return point, dict(locator='world.dead_companion', actor=self.actor_uid,
            knight_position=knight, companion_position=companion, scene_size=list(size),
            coordinate_basis='corpse_grid_to_capture',
            projection_basis='original projection-oracle.tsv: dx=(48,24), dy=(48,-24), bottom-up',
            ui_result='UNKNOWN', limitation='KNIGHT_AT_SCENE_CENTER_CAMERA_SCALE_AND_CORPSE_HITBOX_UNVERIFIED')

    def worn(self):
        state = self.broker()._companion_inventory.states[self.member_id]
        return {uid for _, uid in state.slots} | ({state.weapon_uid} if state.weapon_uid else set())

    def potion_uid(self, role):
        rows = self.frames()[0 if role.startswith('self') else 1]
        selected = [r.identifier for r in rows if r.template_bits == 14 and dict(r.raw_fields).get(4, 0) > 0]
        if len(selected) != 1:
            raise ValueError('POTION_SLOT_NOT_UNIQUE:' + role)
        return selected[0]

    def totals(self):
        return [sum(dict(r.raw_fields).get(4, 0) for r in rows if r.template_bits == 14) for rows in self.frames()]

    def resolve_request(self, request):
        import hashlib
        request = dict(request)
        locator = request.pop('locator')
        capture = getattr(self, 'last_capture_context', None)
        if not capture or self.results[-1].get('kind') != 'capture' or self.results[-1].get('status') != 'OBSERVED':
            raise ValueError('INPUT_IMMEDIATELY_PRECEDING_CAPTURE_REQUIRED')
        self.last_action_capture = dict(capture)
        self.last_action_signals = self.server_signals()
        self.last_action_callbacks = self.callback_rows()
        self.last_action_drops = self.drop_rows()
        self.last_action_ats = list(getattr(self.broker(), '_ats_events', ()))
        self.last_action_pet_mode = self.broker()._companion_pet_modes.get(self.actor_uid)
        request['sequence'] = getattr(getattr(self, 'private_inputs', None), 'last_sequence', 0) + 1
        request.update(coordinate_space='capture', png_size=capture['png_size'])
        if request['action'] in ('key_press', 'type_text'):
            # Quantity has already been proved by its current native drop event.
            # ESC flows through InputRequests and is durably refused if the
            # installed desktop adapter still supports only digits and Enter.
            # The HUD-chat quantity strip can already own focus; a refused
            # optional focus click must not prevent its digit/Enter sequence.
            # Typing 1 assumes the strip starts empty/selects its initial text;
            # the exact one-item inventory delta below must confirm that assumption.
            self.last_action_layouts = {}
            if locator == 'quantity':
                # quantity_open() already observed the preceding native drop
                # and its active strip. Keys have no point geometry to infer.
                pass
            else:
                memory = MemoryUi(self)
                layout = memory.layout(locator)
                if not memory.visible(memory.ptr(layout + 0x30)):
                    raise ValueError('KEY_TARGET_WINDOW_HIDDEN:' + locator)
                memory.validate()
                self.last_action_layouts[locator] = layout
            return request, dict(locator=locator, capture=capture)
        memory = None
        evidence = []
        self.last_action_layouts = {}
        def point(name):
            nonlocal memory
            bound = semantic_plan.get('locators', {}).get(name)
            if _selected_steps in ('ats_window_heal', 'ats_window_reset_dragoff'):
                bound = None  # This scenario uses live scene bounds for every control.
            if ATS_WINDOW_SCENARIO and name in ('companion_ats.close', 'ats.window_close',
                                                 'companion_spell.close'):
                bound = None  # Always resolve this live window's own close node.
            if name == 'ats.recovery' and hasattr(self, 'ats_recovery_target'):
                bound = None  # These scenarios choose from the starting saved ATS.
            if _selected_steps == 'ats_window_spell' and name in (
                    'companion_spell.learned_buff', 'companion_spell.learned_battle',
                    'companion_spell.learned_conditional', 'companion_ats.buff_spell',
                    'companion_ats.battle_spell', 'companion_ats.conditional_spell'):
                bound = None  # Spell drags use this owned window's scene bounds.
            if bound:
                digest = hashlib.sha256(Path(capture['png']).read_bytes()).hexdigest()
                if bound.get('capture_sha256') != digest or bound.get('png_size') != capture['png_size']:
                    raise ValueError('SEMANTIC_LOCATOR_SAME_CAPTURE_REQUIRED:' + name)
                value = bound.get('point')
                if type(value) is not list or len(value) != 2 or not all(type(n) is int for n in value):
                    raise ValueError('SEMANTIC_LOCATOR_POINT_REQUIRED')
                evidence.append(dict(locator=name, coordinate_basis='capture_to_client',
                    point_basis='EXPLICIT_SAME_CAPTURE_BINDING', capture_sha256=digest))
                return value
            if name == 'world.dead_companion':
                value, facts = self.resurrection_point(capture)
                evidence.append(facts)
                return value
            if name == 'hud.bag_icon':
                value, facts = capture_control_point(capture, name,
                    ValueError('ESTABLISHED_HUD_BAG_ICON_CAPTURE_POINT'), self)
                evidence.append(facts)
                return value
            if self.resurrect_scenario and name == 'self_bag.resurrect_scroll':
                if not self.self_bag_visibility()['shown']:
                    raise ValueError('RESURRECTION_SELF_BAG_NOT_SHOWN')
            if name == 'self_bag.talkscroll' and not self.self_bag_visibility()['shown']:
                raise ValueError('TALKSCROLL_SELF_BAG_NOT_SHOWN')
            try:
                if memory is None:
                    memory = MemoryUi(self)
                value, facts = memory.point(name)
                if _selected_steps in ('ats_window_spell', 'ats_window_heal', 'ats_window_reset_dragoff') and 'scene_bounds' in facts:
                    value, facts = self.ats_spell_drag_point(memory, name, facts)
            except Exception as error:
                if (_selected_steps == 'ats_window_spell'
                        and name in ('companion_ats.buff_spell', 'companion_ats.battle_spell',
                                     'companion_ats.conditional_spell')
                        and str(error).startswith('COMPANION_ATS_SPELL_TARGET_MISSING:')):
                    self.ats_spell_missing_target_tree(name, error)
                if name.split('.')[0] in ('companion_ats', 'companion_spell') or name == 'ats.window_close':
                    # Existing ATS PNG fallbacks address the knight window.
                    # Never borrow those points for the separate CSB wrapper.
                    raise ValueError('ATS_WINDOW_NATIVE_NODE_REQUIRED:' + str(error)) from error
                if name.endswith('.close'):
                    value, facts = capture_close_point(capture, name, error)
                    if memory is not None:
                        try:
                            facts['layout'] = memory.layout(name.split('.')[0])
                        except Exception:
                            # Layout identity is optional fallback evidence;
                            # a failed lookup must not undo the PNG hit point.
                            pass
                elif name.split('.')[0] in ('self_bag', 'companion_bag'):
                    value, facts = capture_bag_point(capture, name, error, self)
                elif name == 'quantity' or name.split('.')[0] in ('ats', 'companion_equipment'):
                    value, facts = capture_control_point(capture, name, error, self)
                else:
                    value, facts = capture_pet_point(capture, name, error)
                # Failed partial node reads are not a geometry proof to replay.
                memory = None
                self.manual.consumer.reader.validate()
            if facts.get('layout'):
                self.last_action_layouts[name.split('.')[0]] = facts['layout']
            evidence.append(facts); return value
        if request['action'] == 'left_drag':
            first, last = [point(name) for name in locator]
            if (_selected_steps == 'ats_window_reset_dragoff'
                    and locator[0] in ('companion_ats.buff_spell', 'companion_ats.heal_hp')):
                if memory is None:
                    memory = MemoryUi(self)
                layout = memory.layout('companion_ats')
                _, bounds = memory.node_point(memory.ptr(layout + 0x30),
                    'companion_ats.window_bounds', layout, require_capture=False)
                rect = bounds['capture_rect']
                outside = not (rect[0] <= last[0] < rect[2] and rect[1] <= last[1] < rect[3])
                evidence.append(dict(outside_ats_window=outside, target_point=last,
                                     ats_capture_rect=rect))
                if not outside:
                    raise ValueError('ATS_DRAG_OFF_EXISTING_PET_NODE_NOT_OUTSIDE_CURRENT_ATS')
            if locator == ['companion_bag.potion', 'companion_ats.hp_slot2']:
                # Bounds are read in this same capture's live node hierarchy.
                # The ATS editor may intentionally cover the pet window. Only
                # the source bag can hide this target during the real drag.
                if memory is None:
                    memory = MemoryUi(self)
                windows = []
                for role in ('companion_bag',):
                    layout = memory.layout(role)
                    root = memory.ptr(layout + 0x30)
                    shown = memory.shown(root)
                    facts = dict(role=role, layout=layout, root=root, shown=shown)
                    if shown:
                        _, bounds = memory.node_point(root, role + '.window_bounds',
                                                      layout, require_capture=False)
                        rect = bounds['capture_rect']
                        intersects = rect[0] <= last[0] < rect[2] and rect[1] <= last[1] < rect[3]
                        facts.update(capture_rect=rect, target_intersects=intersects,
                                     coordinate_basis=bounds['coordinate_basis'])
                    windows.append(facts)
                evidence.append(dict(target_point=last, visibility_windows=windows,
                                     z_order='UNKNOWN', visibility_basis='LIVE_NATIVE_WINDOW_BOUNDS_SEPARATION'))
                memory.validate()
                if any(window.get('target_intersects') for window in windows):
                    error = ValueError('ATS_EDIT_TARGET_INTERSECTS_VISIBLE_WINDOW:' +
                                       ','.join(window['role'] for window in windows if window.get('target_intersects')))
                    error.coordinate_evidence = dict(locators=evidence, capture=capture,
                                                     presentation_result='UNKNOWN')
                    raise error
            request['points'] = [[round(first[0]+(last[0]-first[0])*i/10),
                                  round(first[1]+(last[1]-first[1])*i/10)] for i in range(11)]
            evidence.append(dict(drag_points=11,
                native_event_delay_ms=40 if input_route == 'GLFW_CALLBACK_INJECTION' else None,
                frame_count='UNKNOWN', timing_basis=('DLL_DELAY_MS_BEFORE_EACH_EVENT'
                    if input_route == 'GLFW_CALLBACK_INJECTION' else 'PRIVATE_DESKTOP_MESSAGE_ORDER')))
        else:
            request['x'], request['y'] = point(locator)
        if memory is not None:
            memory.validate()
        return request, dict(locators=evidence, presentation_result='UNKNOWN')

    def callback_rows(self):
        boundary = module.current_kit(self.manual)[0][5]
        return self.json_rows(boundary, 'companion-pet-click-*.json')

    def drop_rows(self):
        boundary = module.current_kit(self.manual)[0][5]
        return self.json_rows(boundary, 'companion-result-drop-*.json')

    @staticmethod
    def json_rows(directory, pattern):
        rows = []
        for path in sorted(directory.glob(pattern)):
            if path.stat().st_size > 4096:
                continue
            try:
                rows.append(dict(json.loads(path.read_text(encoding='utf-8')), evidence_file=str(path)))
            except (ValueError, OSError):
                continue
        return rows

    def quantity_open(self):
        rows = [r for r in self.drop_rows() if r not in self.last_action_drops]
        event = any(r.get('reason') == 'QUANTITY_OPENED' and r.get('stage') == 'drop' for r in rows)
        if not event:
            return False
        ui = MemoryUi(self)
        layout = ui.layout('quantity')
        helper = ui.ptr(layout + 0x150)
        widget = ui.ptr(ui.ptr(helper + 0x28) + 0x730)
        visible = ui.visible(widget)
        ui.validate()
        return visible

    def prepare(self, mode=None):
        if mode == 'ats_window_reset_dragoff':
            baseline = self.prepare('ats_window_spell')
            self.ats_clear_stages = {}
            self.ats_clear_events = list(getattr(self.broker(), '_ats_events', ()))
            self.ats_clear_deltas = {str(path) for path in
                                     self.ats_window_directory().glob('companion-ats-delta-*.json')}
            return dict(baseline, scope='EXISTING_TEST_COPY; NATIVE_RESET_AND_SLOT_DRAG_OFF')
        if mode == 'ats_window_heal_reopen':
            # ats_spell_view selects exactly one new opening; reset only its
            # event baseline, retaining the first opening's evidence on disk.
            self.ats_spell_events_before = list(getattr(self.broker(), '_ats_events', ()))
            return dict(status='OBSERVED', scope='NEXT_WINDOW_OPEN_EVENT_BASELINE_ONLY')
        if mode == 'ats_window_heal':
            baseline = self.prepare('ats_window')
            from tools.local_original_session import world_feature_companion_ats as ats
            broker = self.broker()
            magic, store = broker._world_magic, broker._world_magic_store
            keys = {name: key for key, name in ats._ats_spell_keys(broker).items()
                    if name in ('heal', 'cure_poison')}
            if set(keys) != {'heal', 'cure_poison'} or store is None:
                raise ValueError('ATS_HEAL_MAGIC_SAVE_AND_HEAL_CURE_KEYS_REQUIRED')
            state = magic.states.get(self.member_id)
            saved = store.rows.get(self.member_id)
            learned_before = sorted(state.learned if state is not None else
                                    (() if saved is None else saved['learned']))
            learned = sorted(set(learned_before) | set(keys.values()))
            if state is not None:
                proposed = magic.snapshot(self.member_id, broker._world.runtime.clock(), learned=learned)
            elif saved is not None:
                proposed = dict(saved, learned=learned)
            else:
                proposed = dict(uid=self.member_id, learned=learned, buffs=[],
                                reuse_remaining=0.0, saved_at=time.time())
            # The existing run wrapper creates a fresh profile copy before the
            # game starts. Synthetic setup uses the product's durable APIs;
            # it is not a book-learning or normal gameplay claim.
            store.save(proposed)
            if state is not None:
                state.learned = set(learned)
            empty = [dict(spell_row=None, **(dict(percent=50) if i < 4 else {})) for i in range(6)]
            member = broker._ats_store['characters'].setdefault(str(self.member_id), {})
            member['companion_heal'] = empty
            ats._ats_save_store(broker)
            broker._ats_policies.pop(self.member_id, None)
            self.ats_spell_events_before = list(getattr(broker, '_ats_events', ()))
            self.ats_heal_events_before = list(self.ats_spell_events_before)
            self.ats_spell_rows = dict(hp=keys['heal'], status=keys['cure_poison'])
            self.ats_heal_before = self.ats_heal_snapshot()
            self.ats_heal_stages = {}
            self.ats_heal_drag_sequence = 0
            return dict(baseline, preparation='SYNTHETIC_TEST_PREPARATION',
                        magic_file=str(store.path), ats_file=str(self.ats_window_path),
                        learned_before=learned_before, learned_after=learned,
                        selected_spell_rows=self.ats_spell_rows, companion_heal=empty,
                        scope='FRESH_WRAPPER_TEST_COPY_ONLY; NO_BOOK_LEARNING_CLAIM')
        if mode == 'ats_window_spell':
            baseline = self.prepare('ats_window')
            self.ats_spell_before = self.ats_spell_snapshot('before')
            if not self.ats_spell_before['buff_slots'] or not self.ats_spell_before['battle_slots']:
                raise ValueError('ATS_SPELL_EXISTING_BUFF_AND_BATTLE_ROWS_REQUIRED;_CREATION_UNKNOWN')
            buff = self.ats_spell_before['buff_slots'][0]
            self.ats_spell_battle_targets = {}
            for i, entry in enumerate(self.ats_spell_before['battle_slots']):
                if entry['kind'] in ('sequence', 'conditional') and entry['index'] == 0:
                    self.ats_spell_battle_targets[entry['kind']] = i
            if set(self.ats_spell_battle_targets) != {'sequence', 'conditional'}:
                raise ValueError('ATS_SPELL_EXISTING_SEQUENCE_AND_CONDITIONAL_ROWS_REQUIRED')
            battle = [self.ats_spell_before['battle_slots'][self.ats_spell_battle_targets[k]].get('slot', {})
                      for k in ('sequence', 'conditional')]
            if buff.get(1) not in (None, 0, 1) or any(slot.get(1) not in (None, 0, 1) for slot in battle):
                raise ValueError('ATS_SPELL_FIRST_TARGET_ITEM_OR_UNRESOLVED_READ_ONLY')
            self.ats_spell_events_before = list(getattr(self.broker(), '_ats_events', ()))
            self.ats_spell_rows = {}
            self.ats_spell_stages = {}
            return dict(baseline, companion_before=self.ats_spell_before,
                        scope='EXISTING_COMPANION_SPELL_ROWS_ONLY')
        if mode == 'ats_window_edit':
            baseline = self.prepare('ats_window')
            self.ats_edit_before = self.ats_edit_snapshot('before')
            if self.ats_edit_before['hp_percent'] == 60 and self.ats_edit_before['hp_slot2'] == 14:
                raise ValueError('ATS_EDIT_START_ALREADY_HP60_SLOT2_TEMPLATE14')
            self.ats_edit_events_before = list(getattr(self.broker(), '_ats_events', ()))
            self.ats_edit_stages = {}
            return dict(baseline, companion_before=self.ats_edit_before)
        if mode == 'ats_window':
            if not ATS_WINDOW_SCENARIO or input_route != 'GLFW_CALLBACK_INJECTION':
                raise ValueError('ATS_WINDOW_REQUIRES_EXPLICIT_SCENARIO_AND_GLFW_CALLBACK_INJECTION')
            self.ats_window_owner_uid = module.current_kit(self.manual)[0][3].uid
            self.ats_window_path = Path(self.broker()._ats_path)
            self.ats_window_before = self.ats_window_snapshot('before')
            facts = self.ats_window_visibility()
            if facts['knight']['shown'] or facts['companion']['shown']:
                raise ValueError('ATS_WINDOW_START_REQUIRES_BOTH_WINDOWS_CLOSED')
            self.ats_window_observed = {}
            return dict(status='OBSERVED', before=self.ats_window_before,
                        windows=facts, scope='EXISTING_KNIGHT_ATS_FIELDS_AND_CLOSED_WINDOWS')
        if mode == 'talkscroll':
            if input_route != 'GLFW_CALLBACK_INJECTION':
                raise ValueError('TALKSCROLL_REQUIRES_GLFW_CALLBACK_INJECTION')
            before = self.talkscroll_snapshot()
            if before['scroll_quantity'] <= 0 or before['raw_item_type'] != 133:
                raise ValueError('OWNED_TALKSCROLL_TEMPLATE12163_UID65577_RAW133_REQUIRED')
            self.talkscroll_before = before
            self.actor_uid = before['position']['uid']
            return dict(status='OBSERVED', before=before, scope='CURRENT_KNIGHT_SCROLL_AND_POSITION_ONLY')
        if mode == 'resurrect':
            if input_route != 'GLFW_CALLBACK_INJECTION':
                raise ValueError('RESURRECT_SCROLL_REQUIRES_GLFW_CALLBACK_INJECTION')
            self.install_resurrection_probe()
            before = self.resurrection_snapshot()
            self.resurrection_before = before
            if before.get('actor_reason'):
                raise ValueError(before['actor_reason'])
            if before.get('actor') is None or before.get('alive') is not False or before.get('hp') != 0:
                raise ValueError('CURRENT_DEAD_OWNED_COMPANION_REQUIRED')
            if 'companion_position' not in before or 'knight_position' not in before:
                raise ValueError('CURRENT_CORPSE_AND_OWNER_POSITIONS_REQUIRED')
            if before.get('scroll_quantity', 0) <= 0:
                raise ValueError('OWNED_RESURRECTION_SCROLL_TEMPLATE28_UID65570_REQUIRED')
            self.actor_uid, self.member_id = before['actor'], before['member']
            self.input_actor = self.actor_uid & 0xffffffff
            return dict(status='OBSERVED', before=before,
                        scope='SERVER_CORPSE_AND_SCROLL_PRECONDITIONS_ONLY')
        if mode is None:
            opened = next(r for r in reversed(self.results) if r.get('kind') == 'pet')
            self.actor_uid = opened['reply']['target_uid']
            # Context.world delegates to PersistentBroker._world; current_kit
            # gives us the broker itself, not the feature Context facade.
            active = self.broker()._world.companions.active
            actors = [a for a in active.values() if a.ref.uid == self.actor_uid]
            if len(actors) != 1:
                raise ValueError('CURRENT_COMPANION_ACTOR_REQUIRED')
            self.member_id = actors[0].character_id
            self.input_actor = self.actor_uid & 0xffffffff
            needs_transfer = any(s[0] == 'scenario_observe' and s[2].get('transfer') for s in self.steps)
            self.start_totals = self.totals() if needs_transfer else None
            needs_ats = any(s[0] == 'scenario_observe' and s[2].get('ats_saved') for s in self.steps)
            if needs_ats:
                self.ats_path = Path(self.broker()._ats_path)
                self.ats_before = json.loads(self.ats_path.read_text(encoding='utf-8')) if self.ats_path.exists() else dict(schema=1, characters={})
                member_ats = self.ats_before.get('characters', {}).get(str(self.member_id), {})
                self.ats_recovery_target = ats_recovery_target(member_ats.get('companion_ats'))
                self.ats_events_before_edit = list(getattr(self.broker(), '_ats_events', ()))
            return dict(status='OBSERVED', actor=self.actor_uid, member=self.member_id,
                        initial_potion_totals=self.start_totals,
                        coordinate_limitation='AUTOMATIC_AXIS_ALIGNED_TRANSFORM_IS_INFERRED_UI_UNKNOWN')
        if mode in ('potion', 'companion_potion'):
            role = 'companion_bag' if mode == 'companion_potion' else 'self_bag'
            uid = self.potion_uid(role)
            rows = self.frames()[1 if role == 'companion_bag' else 0]
            row = next(r for r in rows if r.identifier == uid)
            # Native source metadata+D4 also must say unequipped. Potion14 is
            # the same template used by the existing companion give/take test.
            required = 1 if self.start_totals is not None else 0
            if dict(row.raw_fields).get(4, 0) <= required:
                raise ValueError('UNEQUIPPED_POTION_STACK_GT1_REQUIRED' if required else 'UNEQUIPPED_POTION_REQUIRED')
            ui = MemoryUi(self)
            node = ui.slot(ui.layout(role), role, uid)
            metadata = ui.ptr(node + 0x808)
            if ui.read(metadata + 0xd4, 1) != b'\0':
                raise ValueError('SOURCE_ITEM_EQUIPPED')
            ui.validate()
            return dict(status='OBSERVED', item=uid, template=14, quantity=dict(row.raw_fields)[4], unequipped=True)
        worn = sorted(self.worn())
        if not worn:
            raise ValueError('COMPANION_EQUIPPED_ITEM_REQUIRED')
        state = self.broker()._companion_inventory.states[self.member_id]
        # The saved equipment capture gives the weapon cell an unambiguous
        # fallback. Keep the existing choice when no weapon is currently worn.
        self.equipment_uid = state.weapon_uid or worn[0]
        return dict(status='OBSERVED', item=self.equipment_uid, equipped=True)

    def ats_edit_snapshot(self, label):
        from tools.local_original_session import ats_config_codec as codec
        stored = json.loads(self.ats_window_path.read_text(encoding='utf-8'))
        member = stored['characters'].get(str(self.member_id), {})
        wrapper = member.get('companion_ats')
        decoded = (codec.decode_options(codec.unwrap_blob(bytes.fromhex(wrapper)))
                   if wrapper else dict(hp_slots=[], hp_percent=None))
        slots = decoded['hp_slots']
        slot2 = slots[1] if len(slots) > 1 else {}
        return dict(member=self.member_id, companion_ats=wrapper,
                    hp_percent=decoded['hp_percent'],
                    hp_slot2=slot2[4] if slot2.get(1) == 2 and slot2.get(4, 0) > 0 else None,
                    owner=self.ats_window_snapshot('edit-' + label))

    def ats_native_clear_snapshot(self, stage):
        ui = MemoryUi(self)
        layout = ui.layout('companion_ats')
        slot = ui.heal_slot(layout, 0)
        cached = {hex(offset): ui.ptr(slot + offset)
                  for offset in (0x808, 0x810, 0x820, 0x828, 0x830, 0x838, 0x840)}
        pending, seen, nodes = [(slot, 0)], set(), []
        while pending:
            node, depth = pending.pop()
            if node in seen:
                continue
            seen.add(node)
            row = dict(node=node, name=ui.string(node + 0x1a8),
                parent=ui.ptr(node + 0x190), vptr_rva=ui.ptr(node)-ui.base,
                visible=ui.visible(node), shown=ui.shown(node),
                position=list(ui.vec(node + 0x3c)), size=list(ui.vec(node + 0x6c)),
                cached_as=[key for key, value in cached.items() if value == node])
            try:
                _, geometry = ui.node_point(node, 'companion_ats.heal_hp', layout, require_capture=False)
                row['scene_bounds'] = geometry['scene_bounds']
            except ValueError as error:
                row['scene_bounds_reason'] = str(error)[:120]
            children = ui.spell_children(node)
            row['children'] = children
            nodes.append(row)
            if depth < 6:
                pending.extend((child, depth+1) for child in children)
        ui.validate()
        result = dict(status='OBSERVED', stage=stage, layout=layout,
            slot=slot, cached=cached, nodes=nodes,
            capture=self.last_capture_context, formal_pass=False,
            ui_result='REQUIRES_CAPTURE_REVIEW; PASSIVE_CURRENT_SLOT_CHILD_IDENTITY')
        result['tree_file'] = self.shop_write('heal-clear-native-' + stage, result)
        return result

    def observe_ats_clear(self, stage):
        if self.blocked is not None:
            return dict(status='UNKNOWN', stage=stage, reason='FAILED_PREREQUISITE',
                        first_failure=self.blocked, automatic_retry=False)
        if stage == 'opened':
            result = self.observe_ats_spell('opened')
            if result['status'] != 'OBSERVED':
                return result
            hp = next((row for row in self.ats_spell_view_rows[:32]
                       if row.get('heal_kind') == 'hp' and type(row.get('spell_row')) is int), None)
            if hp is None:
                return dict(result, status='UNKNOWN',
                            reason='ATS_CLEAR_CURRENT_FIRST_PAGE_LEARNED_HP_SPELL_REQUIRED')
            self.ats_spell_rows['hp'] = hp['spell_row']
            self.ats_clear_stages[stage] = True
            return dict(result, selected_hp_spell_row=hp['spell_row'])
        previous = {'buff-seeded': 'opened', 'seed-saved': 'buff-seeded',
                    'reset-draft': 'seed-saved', 'reset-saved': 'reset-draft',
                    'buff-refilled': 'reset-saved', 'buff-empty': 'buff-refilled',
                    'heal-filled': 'buff-empty', 'heal-empty': 'heal-filled'}[stage]
        ui = MemoryUi(self)
        layout = ui.layout('companion_ats')
        control = 'heal_hp' if stage.startswith('heal-') else 'buff_spell'
        slot = ui.spell_slot(layout, 'companion_ats', control)
        metadata = ui.ptr(slot + 0x808)
        kind = ui.struct.unpack('<i', ui.read(metadata + 8, 4))[0] if metadata else None
        row = ui.struct.unpack('<i', ui.read(metadata, 4))[0] if metadata else None
        ui.validate()
        filled = stage in ('buff-seeded', 'seed-saved', 'buff-refilled', 'heal-filled')
        selected = self.ats_spell_rows['hp' if control == 'heal_hp' else 'buff']
        native_matches = (kind == 1 and row == selected) if filled else metadata == 0
        ok = previous in self.ats_clear_stages and native_matches
        after = self.ats_spell_snapshot('clear-' + stage)
        from tools.local_original_session import ats_config_codec as codec
        decoded = codec.decode_options(codec.unwrap_blob(bytes.fromhex(after['companion_ats'])))
        stored_member = json.loads(self.ats_window_path.read_text(encoding='utf-8'))[
            'characters'][str(self.member_id)]
        heals_after = stored_member.get('companion_heal', [])
        self_ats_same = after['owner']['self_ats'] == self.ats_spell_before['owner']['self_ats']
        ok = ok and self_ats_same
        result = dict(stage=stage, native_target_slot=slot, native_payload=metadata,
                      native_kind=kind, native_spell_row=row, expected_filled=filled,
                      native_slot_matches=native_matches, png=self.last_capture_context['png'],
                      ui_result='UNKNOWN', action_status='UNKNOWN; NOT_PUBLISHED',
                      knight_self_ats_unchanged=self_ats_same,
                      knight_self_config_drift=self.ats_config_drift(
                          self.ats_spell_before['owner']['self_config'], after['owner']['self_config']))
        if stage in ('seed-saved', 'reset-saved'):
            view, _ = self.ats_spell_view()
            epoch = view['edit_epoch']
            saves = [event for event in list(getattr(self.broker(), '_ats_events', ()))[len(self.ats_clear_events):]
                     if event.get('event') == 'window-save'
                     and event.get('member') == self.member_id and event.get('epoch') == epoch]
            deltas = []
            for path in self.ats_window_directory().glob('companion-ats-delta-*.json'):
                if str(path) in self.ats_clear_deltas or path.stat().st_size > 65536:
                    continue
                delta = json.loads(path.read_text(encoding='utf-8'))
                if delta.get('member_id') == self.member_id and delta.get('edit_epoch') == epoch:
                    deltas.append(dict(delta, evidence_file=str(path)))
            buff = after['buff_slots'][0] if after['buff_slots'] else {}
            if stage == 'seed-saved':
                saved_matches = buff.get(1) == 1 and buff.get(4) == selected
                delta_matches = len(deltas) == 1 and bool(deltas[0].get('buff_slots'))
                delta_slot = deltas[0]['buff_slots'][0] if delta_matches else None
                delta_matches = isinstance(delta_slot, dict) and delta_slot.get('spell_row') == selected
                battle_seeded = all(
                    slot.get(1) == 1 and slot.get(4) == self.ats_spell_rows[spell]
                    for kind, spell in (('sequence', 'battle'), ('conditional', 'conditional'))
                    for slot in (after['battle_slots'][self.ats_spell_battle_targets[kind]].get('slot', {}),))
                heal_seeded = bool(heals_after) and heals_after[0].get('spell_row') == self.ats_spell_rows['hp']
                saved_matches = saved_matches and battle_seeded and heal_seeded
                result.update(battle_preservation_seed_saved=battle_seeded,
                              heal_preservation_seed_saved=heal_seeded)
                self.ats_clear_preserved_battle = after['battle_slots']
                self.ats_clear_preserved_heal = heals_after
            else:
                # A full buff array is serialized on Reset. Preserve explicitly
                # read-only entries while requiring every editable spell empty.
                saved_matches = buff.get(1) in (None, 0) and buff.get(4, -1) == -1
                entries = deltas[0].get('buff_slots') if len(deltas) == 1 else None
                delta_matches = (isinstance(entries, list) and bool(entries)
                                 and entries[0] is None
                                 and all(entry is None or (isinstance(entry, dict)
                                     and entry.get('status') is not None) for entry in entries))
                draft = dict(view, **(deltas[0] if len(deltas) == 1 else {}))
                editable_empty = lambda entry: entry is None or (isinstance(entry, dict)
                    and entry.get('status') is not None)
                registrations_empty = all(all(entry is None for entry in draft.get(key, []))
                    for key in ('hp_slots', 'mp_slots', 'function_slots'))
                registrations_empty = registrations_empty and all(
                    editable_empty(entry) for entry in draft.get('buff_slots', []))
                percentages_reset = all(draft.get(key) == 80 and decoded.get(key) == 80
                                        for key in ('hp_percent', 'mp_percent'))
                def saved_empty(entry):
                    return (not entry or entry.get(1, 0) == 0
                            or entry.get(1) in (1, 2) and entry.get(4) == -1)
                saved_buff_tab_empty = all(all(saved_empty(entry) for entry in decoded[key])
                    for key in ('hp_slots', 'mp_slots', 'function_slots'))
                saved_buff_tab_empty = saved_buff_tab_empty and isinstance(entries, list) and (
                    len(entries) == len(decoded['buff_slots']) and all(
                        saved_empty(saved_entry) if selection is None else
                        saved_entry == self.ats_spell_before['buff_slots'][index]
                        for index, (saved_entry, selection) in enumerate(zip(decoded['buff_slots'], entries))))
                battle_preserved = after['battle_slots'] == self.ats_clear_preserved_battle
                heal_preserved = heals_after == self.ats_clear_preserved_heal
                delta_matches = delta_matches and registrations_empty and percentages_reset
                saved_matches = (saved_matches and saved_buff_tab_empty
                                 and battle_preserved and heal_preserved)
                result.update(reset_buff_registration_draft_empty_in_save_delta=registrations_empty,
                              reset_buff_saved_registrations_empty=saved_buff_tab_empty,
                              reset_hp_mp_percent80=percentages_reset,
                              reset_battle_selections_preserved=battle_preserved,
                              reset_heal_selections_preserved=heal_preserved)
            ok = ok and bool(saves) and saved_matches and delta_matches
            result.update(saved=after, window_save_events=saves, save_deltas=deltas,
                          saved_slot_matches=saved_matches, save_delta_matches=delta_matches)
            if ok:
                self.ats_clear_events = list(getattr(self.broker(), '_ats_events', ()))
                self.ats_clear_deltas.update(delta['evidence_file'] for delta in deltas)
                if stage == 'reset-saved':
                    self.ats_clear_reset_saved = after['companion_ats']
        elif stage in ('buff-refilled', 'buff-empty', 'heal-filled', 'heal-empty'):
            unchanged = after['companion_ats'] == self.ats_clear_reset_saved
            ok = ok and unchanged
            result['stored_ats_unchanged_during_draft'] = unchanged
        if ok:
            self.ats_clear_stages[stage] = True
        if stage.startswith('heal-'):
            result['native_drawable_snapshot'] = self.ats_native_clear_snapshot(stage)
        return dict(result, status='OBSERVED' if ok else 'UNKNOWN',
                    reason=None if ok else 'ATS_RESET_OR_SLOT_DRAG_OFF_NOT_OBSERVED',
                    scope='SELECTED_NATIVE_SLOT; RESET_SAVE_DELTA_AND_DURABLE_STORE; PNG_HUMAN_REVIEW_REQUIRED')

    def ats_heal_snapshot(self):
        stored = json.loads(self.ats_window_path.read_text(encoding='utf-8'))
        row = stored['characters'].get(str(self.member_id), {})
        return dict(companion_heal=row.get('companion_heal'),
                    companion_ats=row.get('companion_ats'),
                    owner=self.ats_window_snapshot('heal'))

    def ats_heal_display(self, include_menu=False):
        ui = MemoryUi(self)
        layout = ui.layout('companion_ats')
        root = ui.ptr(layout + 0x30)
        tabs = []
        for name in ('Bt_Buff', 'Bt_Combat', 'Bt_Help', 'Bt_Option'):
            button = ui.path(root, 'Root.Tab.' + name)
            _, facts = ui.node_point(button, 'companion_ats.' + name, layout)
            tabs.append(dict(name=name, scene_bounds=facts['scene_bounds']))
        tabs.sort(key=lambda tab: tab['scene_bounds']['left'])
        slots = []
        for index in range(6):
            slot = ui.heal_slot(layout, index)
            panel = ui.ptr(slot + 0x830)
            _, facts = ui.node_point(panel, 'companion_ats.heal_' + str(index), layout)
            slots.append(dict(index=index, node=slot, scene_bounds=facts['scene_bounds']))
        menu = ui.heal_percent_options(root) if include_menu else None
        pulldown = ui.path(root, 'Root.Help.02.Slot_01.Pulldown_Menu')
        submenus = [node for node in ui.children(pulldown) if ui.string(node + 0x1a8) == 'Sub_Menu']
        if len(submenus) != 1:
            raise ValueError('ATS_HEAL_CURRENT_SUBMENU_REQUIRED')
        menu_shown = ui.shown(submenus[0])
        ui.validate()
        return dict(layout=layout, root=root, tabs=tabs, slots=slots, menu=menu,
                    menu_shown=menu_shown)

    def observe_ats_heal(self, stage):
        if self.blocked is not None:
            return dict(status='UNKNOWN', stage=stage, reason='FAILED_PREREQUISITE',
                        first_failure=self.blocked, automatic_retry=False)
        previous = dict(**{'spell-opened': 'opened', 'hp-draft': 'spell-opened',
                          'kind-refused': 'hp-draft', 'status-draft': 'kind-refused',
                          'menu-opened': 'status-draft', 'percent-draft': 'menu-opened'},
                        saved='percent-draft', closed='saved', reopened='closed', final='reopened').get(stage)
        ok = previous is None or previous in self.ats_heal_stages
        stored = self.ats_heal_snapshot()
        visibility = self.ats_window_visibility()
        closed = stage in ('closed', 'final')
        ok = ok and visibility['companion']['shown'] != closed and not visibility['knight']['shown']
        result = dict(stage=stage, stored=stored, windows=visibility,
                      png=self.last_capture_context['png'], ui_result='UNKNOWN',
                      preparation='SYNTHETIC_TEST_PREPARATION',
                      knight_self_config_drift=self.ats_config_drift(
                          self.ats_heal_before['owner']['self_config'], stored['owner']['self_config']))
        display = None
        if not closed:
            display = self.ats_heal_display(include_menu=stage == 'menu-opened')
            result['display'] = display
            ok = ok and [tab['name'] for tab in display['tabs']] == [
                'Bt_Buff', 'Bt_Combat', 'Bt_Help', 'Bt_Option']
        if stage in ('opened', 'reopened'):
            view, filename = self.ats_spell_view()
            heal = view.get('heal_slots', [])
            result.update(server_view_file=filename, heal_slots=heal)
            expected = (self.ats_heal_before['companion_heal'] if stage == 'opened'
                        else self.ats_heal_expected)
            expected_view = [dict(kind='hp' if index < 4 else 'status',
                                  slot=row['spell_row'], **(dict(percent=row['percent']) if index < 4 else {}))
                             for index, row in enumerate(expected)]
            actual_view = [dict(kind=row.get('kind'), slot=(row.get('slot') or {}).get('spell_row'),
                                **(dict(percent=row.get('percent')) if index < 4 else {}))
                           for index, row in enumerate(heal)]
            ok = ok and actual_view == expected_view
            if stage == 'opened':
                learned = view.get('learned_spells', [])
                ok = ok and all(any(spell.get('spell_row') == self.ats_spell_rows[kind]
                                    and spell.get('heal_kind') == kind for spell in learned[:32])
                                for kind in ('hp', 'status'))
                self.ats_heal_learned = learned
                result['learned_spells'] = learned
        if stage == 'spell-opened':
            delivery = self.ats_window_delivery()
            population = self.ats_spell_open_result(delivery)
            ui = MemoryUi(self)
            layout = ui.layout('companion_spell')
            root = ui.ptr(layout + 0x30)
            check = self.ats_spell_population_check(self.ats_heal_learned, population or {})
            ok = ok and bool(population and population.get('layout') == layout
                             and population.get('root') == root
                             and population.get('status') == 'ATS_WINDOW_COMPANION_SPELL_OPENED'
                             and ui.shown(root) and check['matches'])
            ui.validate()
            result.update(native_view_results=delivery,
                          native_spell_population=({key: value for key, value in population.items()
                              if key not in ('native_spell_rows', 'dll_spell_rows', 'knight_spell_comparison')}
                              if population else None), native_spell_rows=check['rows'],
                          spell_population_matches=check['matches'])
        if stage in ('hp-draft', 'kind-refused', 'status-draft'):
            index = 0 if stage == 'hp-draft' else 4
            kind = 'status' if stage == 'status-draft' else 'hp'
            drags = [row for row in self.json_rows(self.ats_window_directory(), 'companion-spell-dll-drag-*.json')
                     if row.get('schema') == 'companion-spell-dll-drag-v1'
                     and type(row.get('sequence')) is int
                     and row['sequence'] > self.ats_heal_drag_sequence]
            drags.sort(key=lambda row: row['sequence'])
            expected_status = ('ATS_WINDOW_SPELL_KIND_REFUSED' if stage == 'kind-refused'
                               else 'ATS_WINDOW_SPELL_DRAFT_CHANGED')
            ok = ok and len(drags) == 1 and all(
                row.get('status') == expected_status and row.get('target') == 'HEAL'
                and row.get('target_index') == index
                and row.get('spell_row') == self.ats_spell_rows[kind] for row in drags)
            if drags:
                self.ats_heal_drag_sequence = drags[-1]['sequence']
            result['drag_results'] = drags
        if stage == 'menu-opened':
            ok = ok and display['menu_shown'] and len(display['menu']) == 9
        if stage == 'percent-draft':
            ok = ok and not display['menu_shown']
            self.ats_heal_expected = [dict(spell_row=(self.ats_spell_rows['hp'] if index == 0 else
                self.ats_spell_rows['status'] if index == 4 else None),
                **(dict(percent=30 if index == 0 else 50) if index < 4 else {})) for index in range(6)]
        if stage in ('opened', 'spell-opened', 'hp-draft', 'kind-refused', 'status-draft',
                     'menu-opened', 'percent-draft'):
            unchanged = all(stored[key] == self.ats_heal_before[key]
                            for key in ('companion_heal', 'companion_ats'))
            unchanged = unchanged and stored['owner']['self_ats'] == self.ats_heal_before['owner']['self_ats']
            ok = ok and unchanged
            result['store_unchanged_before_save'] = unchanged
        if stage in ('saved', 'closed', 'reopened', 'final'):
            saves = [row for row in getattr(self.broker(), '_ats_events', ())
                     if row not in self.ats_heal_events_before and row.get('event') == 'window-save'
                     and row.get('member') == self.member_id]
            ok = ok and stored['companion_heal'] == self.ats_heal_expected and bool(saves)
            ok = ok and stored['owner']['self_ats'] == self.ats_heal_before['owner']['self_ats']
            result.update(expected_companion_heal=self.ats_heal_expected, window_save_events=saves)
        if ok:
            self.ats_heal_stages[stage] = True
        return dict(result, status='OBSERVED' if ok else 'UNKNOWN',
                    reason=None if ok else 'ATS_HEAL_STAGE_NOT_OBSERVED',
                    scope='SYNTHETIC_FIXTURE; STORE_VIEW_DRAG_JSON_AND_NATIVE_GEOMETRY; PNG_HUMAN_REVIEW_REQUIRED')

    def ats_spell_snapshot(self, label):
        from tools.local_original_session import ats_config_codec as codec
        stored = json.loads(self.ats_window_path.read_text(encoding='utf-8'))
        row = stored['characters'].get(str(self.member_id), {})
        wrapper = row.get('companion_ats')
        decoded = codec.decode_options(codec.unwrap_blob(bytes.fromhex(wrapper))) if wrapper else {}
        return dict(member=self.member_id, companion_ats=wrapper,
                    buff_slots=decoded.get('buff_slots', []),
                    battle_slots=decoded.get('battle_slots', []),
                    owner=self.ats_window_snapshot('spell-' + label))

    def ats_window_directory(self):
        # Match the publisher's explicit host/environment contract. The normal
        # transport caches its host as _bridge_host, not _companion_bridge_host.
        host = getattr(self.broker(), '_companion_bridge_host', None)
        raw = getattr(host, 'directory', None) or os.environ.get('SL_COMPANION_BRIDGE_DIR')
        if not raw:
            raise ValueError('ATS_SPELL_OWNED_BRIDGE_DIRECTORY_REQUIRED')
        directory = Path(raw).resolve(strict=True)
        boundary = Path(module.current_kit(self.manual)[0][5]).resolve(strict=True)
        if directory != boundary:
            raise ValueError('ATS_WINDOW_BRIDGE_DIRECTORY_NOT_CURRENT_OWNED_RUN')
        return directory

    def ats_window_delivery(self):
        # Read the existing publication/reply evidence; a visible empty window
        # does not mean the DLL accepted its server view.
        opens = [row for row in getattr(self.broker(), '_ats_events', ())
                 if row.get('event') == 'window-open' and row.get('member') == self.member_id
                 and row.get('character') == self.ats_window_owner_uid]
        if not opens:
            return []
        directory = self.ats_window_directory()
        requests = [row for row in self.json_rows(directory, 'companion-request-*.json')
                    if row.get('command') == 'ats-window-view'
                    and row.get('ats_epoch') == opens[-1]['epoch']
                    and row.get('member_id') == self.member_id]
        replies = []
        for request in requests:
            for reply in self.json_rows(directory, 'companion-result-%s.json' % request['seq']):
                if (reply.get('schema') == 'own-companion-result-v1'
                        and all(reply.get(key) == request.get(key) for key in
                                ('pid', 'birth', 'candidate_sha256', 'seq', 'command'))):
                    replies.append(dict(status=reply.get('status'), seq=reply['seq'],
                                        edit_epoch=request['ats_epoch'],
                                        evidence_file=reply['evidence_file'],
                                        request_file=request['evidence_file']))
        return replies

    def ats_spell_open_result(self, delivery):
        # The button runs after the view request's reply. Read its actual
        # callback result, bound to that request's owned process and epoch.
        self.ats_spell_open_samples = []
        if not delivery:
            return None
        request = json.loads(Path(delivery[-1]['request_file']).read_text(encoding='utf-8'))
        records = []
        for path in self.ats_window_directory().glob('companion-ats-spell-open-*.json'):
            if path.stat().st_size > 1048576:
                continue
            try:
                record = json.loads(path.read_text(encoding='utf-8'))
            except (ValueError, OSError):
                continue
            counter = record.get('counter')
            if (record.get('schema') == 'companion-ats-spell-open-v1'
                    and type(counter) is int and counter > 0
                    and path.name == f'companion-ats-spell-open-{counter}.json'
                    and all(record.get(key) == request.get(key)
                            for key in ('pid', 'birth', 'candidate_sha256', 'member_id'))
                    and record.get('actor_uid') == self.actor_uid
                    and record.get('edit_epoch') == request.get('ats_epoch')):
                records.append(dict(record, evidence_file=str(path)))
        self.ats_spell_open_samples = sorted(records, key=lambda record: record['counter'])
        return self.ats_spell_open_samples[-1] if records else None

    def ats_spell_view(self):
        opens = [row for row in getattr(self.broker(), '_ats_events', ())
                 if row not in self.ats_spell_events_before and row.get('event') == 'window-open'
                 and row.get('member') == self.member_id]
        if len(opens) != 1:
            raise ValueError('ATS_SPELL_EXACT_OPEN_EVENT_REQUIRED')
        epoch = opens[0]['epoch']
        directory = self.ats_window_directory()
        files = list(directory.glob(f'companion-ats-view-{epoch}-*.json'))
        if len(files) != 1:
            raise ValueError('ATS_SPELL_EXACT_SERVER_VIEW_REQUIRED')
        view = json.loads(files[0].read_text(encoding='utf-8'))
        if view.get('schema') != 'companion-ats-view-v1' or view.get('member_id') != self.member_id \
                or view.get('edit_epoch') != epoch:
            raise ValueError('ATS_SPELL_SERVER_VIEW_IDENTITY_MISMATCH')
        return view, str(files[0])

    @staticmethod
    def ats_spell_population_rows(population):
        rows = population.get('native_spell_rows')
        if not isinstance(rows, list):
            rows = population.get('dll_spell_rows', [])
        return rows if isinstance(rows, list) else []

    @staticmethod
    def ats_spell_bounds_valid(bounds):
        import math
        return (isinstance(bounds, dict) and bounds.get('visible') is True
                and all(type(bounds.get(key)) in (int, float) and math.isfinite(bounds[key])
                        for key in ('left', 'bottom', 'right', 'top'))
                and bounds['left'] < bounds['right'] and bounds['bottom'] < bounds['top'])

    @classmethod
    def ats_spell_population_check(cls, learned, population):
        rows = cls.ats_spell_population_rows(population)
        expected = [(entry['spell_row'], entry['icon']) for entry in learned[:32]]
        # The DLL reports the first page's actual native slots; filled_count
        # describes the full learned model, not the length of this sample.
        displayed = [entry for entry in rows if entry.get('visible') is True]
        observed = [(entry.get('spell_row'), entry.get('icon')) for entry in displayed]
        viewport = population.get('spell_list_geometry', {}).get('scene_bounds')
        geometry_ok = cls.ats_spell_bounds_valid(viewport)
        summaries = []
        for index, entry in enumerate(displayed):
            panel = entry.get('panel_geometry', {}).get('scene_bounds')
            icon = entry.get('icon_geometry', {}).get('scene_bounds')
            valid = cls.ats_spell_bounds_valid(panel) and cls.ats_spell_bounds_valid(icon)
            if valid and geometry_ok:
                valid = (viewport['left'] <= panel['left'] < panel['right'] <= viewport['right']
                         and viewport['bottom'] <= panel['bottom'] < panel['top'] <= viewport['top']
                         and panel['left'] <= icon['left'] < icon['right'] <= panel['right']
                         and panel['bottom'] <= icon['bottom'] < icon['top'] <= panel['top'])
            geometry_ok = geometry_ok and valid
            # Preserve the observed order and hit bounds without copying large
            # ancestor/render diagnostic arrays into every scenario result.
            summaries.append(dict(spell_row=entry.get('spell_row'), icon=entry.get('icon'),
                                  kind=entry.get('kind'), node=entry.get('node'),
                                  metadata=entry.get('metadata'), panel=entry.get('panel'),
                                  visible=entry.get('visible'), scene_bounds=panel,
                                  icon_scene_bounds=icon))
            if valid:
                first = displayed[0].get('panel_geometry', {}).get('scene_bounds', {})
                if cls.ats_spell_bounds_valid(first):
                    cell_width = first['right'] - first['left']
                    cell_height = first['top'] - first['bottom']
                    left = first['left'] + (index % 4) * cell_width
                    top = first['top'] - (index // 4) * cell_height
                    geometry_ok = geometry_ok and all(abs(panel[key] - value) <= 0.1
                        for key, value in (('left', left), ('right', left + cell_width),
                                           ('top', top), ('bottom', top - cell_height)))
        pairs = [(entry.get('spell_row'), entry.get('icon')) for entry in rows]
        model = [(entry['spell_row'], entry['icon']) for entry in learned]
        matches = (population.get('requested_count') == len(learned)
                   and population.get('filled_count') == len(learned)
                   and population.get('displayed_count') == len(expected)
                   and population.get('visible') is True and population.get('page') == 0
                   and len(rows) in (len(expected), len(learned))
                   and pairs == model[:len(rows)] and observed == expected and geometry_ok
                   and all(entry.get('kind') == 1 and entry.get('vptr_rva') == 0x1232f30
                           and entry.get('camera_mask') == 2 and entry.get('icon_camera_mask') == 2
                           for entry in rows))
        return dict(matches=bool(matches), rows=summaries, expected=expected)

    @classmethod
    def ats_spell_geometry_signature(cls, population):
        return dict(layout=population.get('layout'), root=population.get('root'),
                    grid=[population.get(key) for key in
                          ('spell_list_geometry', 'spell_list_inner_geometry', 'slot_frame_geometry')],
                    rows=[{key: entry.get(key) for key in
                           ('node', 'metadata', 'spell_row', 'icon', 'visible', 'page',
                            'slot_geometry', 'panel_geometry', 'icon_geometry')}
                          for entry in cls.ats_spell_population_rows(population)])

    def ats_spell_drag_point(self, ui, locator, facts):
        bounds = facts['scene_bounds']
        if locator.startswith('companion_spell.learned_'):
            population = self.ats_spell_open_result(self.ats_window_delivery())
            layout = ui.layout('companion_spell')
            if (not population or population.get('layout') != layout
                    or population.get('root') != ui.ptr(layout + 0x30)):
                raise ValueError('ATS_SPELL_CURRENT_DRAG_POPULATION_REQUIRED')
            target = self.ats_spell_rows[locator.split('learned_', 1)[1]]
            matches = [entry for entry in self.ats_spell_population_rows(population)
                       if entry.get('spell_row') == target and entry.get('visible') is True
                       and entry.get('panel') == facts['node']]
            if len(matches) != 1:
                raise ValueError('ATS_SPELL_CURRENT_VISIBLE_DRAG_ROW_REQUIRED')
            native = matches[0].get('panel_geometry', {}).get('scene_bounds')
            if not self.ats_spell_bounds_valid(native) or any(
                    abs(bounds[key] - native[key]) > 0.1
                    for key in ('left', 'bottom', 'right', 'top')):
                raise ValueError('ATS_SPELL_LIVE_AND_DLL_SCENE_BOUNDS_DIFFER')
            bounds = native
            facts.update(spell_row=target, population_file=population['evidence_file'])
        if not self.ats_spell_bounds_valid(bounds):
            raise ValueError('ATS_SPELL_VISIBLE_DRAG_SCENE_BOUNDS_REQUIRED')
        point, converted = node_to_capture(self.last_capture_context, bounds, facts['scene_size'])
        return point, dict(facts, **converted, ui_result='UNKNOWN')

    def ats_spell_missing_target_tree(self, locator, error):
        stage = {'buff_spell': 'buff-draft', 'battle_spell': 'battle-draft',
                 'conditional_spell': 'conditional-draft'}[locator.partition('.')[2]]
        trigger = dict(stage=stage, locator=locator, first_failure=str(error),
                       input_sent=False)
        label = 'companion-ats-tree-' + stage
        try:
            ui = MemoryUi(self)  # The failed slot search may have spent its read budget.
            layout = ui.layout('companion_ats')
            self.shop_tree(label, owned_layout=layout, trigger=trigger)
        except Exception as dump_error:
            self.shop_write(label, dict(status='UNKNOWN', trigger=trigger,
                                        reason=str(dump_error)[:240]))
        try:
            knight = ui.named_layout('ATSLayout')
            if knight and ui.shown(ui.ptr(knight + 0x30)):
                self.shop_tree('knight-ats-tree-' + stage, owned_layout=knight,
                               trigger=dict(trigger, comparison='ORIGINAL_KNIGHT_ATS_SHOWN'))
        except ValueError:
            pass  # The companion failure and its dump remain the first result.

    def observe_ats_spell(self, stage):
        if self.blocked is not None:
            # Continue captures, but do not resolve absent target nodes or read
            # selections that the failed opening observation never produced.
            return dict(status='UNKNOWN', stage=stage, reason='FAILED_PREREQUISITE',
                        first_failure=self.blocked, automatic_retry=False, ui_result='UNKNOWN')
        delivery = self.ats_window_delivery()
        population = self.ats_spell_open_result(delivery)
        refused = next((row['status'] for row in delivery
                        if str(row.get('status', '')).startswith('ATS_WINDOW_SPELL_')), None)
        if population and population.get('status') != 'ATS_WINDOW_COMPANION_SPELL_OPENED':
            refused = population.get('status') or 'ATS_SPELL_OPEN_RESULT_INVALID'
        ui = MemoryUi(self)
        spell = ui.named_layout('SLCompSpell')
        spell_root = ui.ptr(spell + 0x30) if spell else None
        shown = bool(spell_root and ui.shown(spell_root))
        ats = ui.layout('companion_ats')
        ats_root = ui.ptr(ats + 0x30)
        ats_shown = ui.shown(ats_root)
        ui.validate()
        expected = stage not in ('closed', 'reopened-saved')
        ok = shown == expected and ats_shown and self.blocked is None
        result = dict(stage=stage, companion_spell_layout=spell, companion_spell_shown=shown,
                      companion_ats_layout=ats, companion_ats_shown=ats_shown,
                      png=self.last_capture_context['png'], ui_result='UNKNOWN',
                      native_view_results=delivery)
        if population:
            result['native_spell_population'] = {key: value for key, value in population.items()
                                                 if key not in ('native_spell_rows', 'dll_spell_rows',
                                                                'knight_spell_comparison')}
        if refused or (expected and not shown):
            # An absent spell layout has no root or native rows to inspect.
            # Preserve the DLL refusal when one explains the empty capture.
            return dict(result, status='UNKNOWN',
                        reason=refused or 'COMPANION_SPELL_LAYOUT_NOT_SHOWN',
                        scope='NATIVE_LAYOUT_AND_DLL_VIEW_RESULT; SPELL_ROWS_NOT_VERIFIED')
        if expected and (not population or population.get('layout') != spell
                         or population.get('root') != spell_root):
            return dict(result, status='UNKNOWN', reason='ATS_SPELL_CURRENT_OPEN_RESULT_NOT_OBSERVED',
                        scope='NATIVE_LAYOUT_ONLY; SPELL_POPULATION_NOT_VERIFIED')
        if stage == 'opened':
            view, filename = self.ats_spell_view()
            learned = view.get('learned_spells', [])
            if type(learned) is not list or not learned:
                raise ValueError('ATS_SPELL_CURRENT_LEARNED_LIST_REQUIRED')
            before = self.ats_spell_before
            def row_of(slot):
                return slot.get(4) if isinstance(slot, dict) and slot.get(1) == 1 else None
            existing = (row_of(before['buff_slots'][0]),
                        *(row_of(before['battle_slots'][self.ats_spell_battle_targets[k]].get('slot', {}))
                          for k in ('sequence', 'conditional')))
            self.ats_spell_rows = {}
            for target, old in zip(('buff', 'battle', 'conditional'), existing):
                choice = next((spell for spell in learned[:32] if type(spell.get('spell_row')) is int
                               and spell['spell_row'] != old), None)
                if choice is None:
                    raise ValueError('ATS_SPELL_LEARNED_DISTINCT_FROM_' + target.upper() + '_REQUIRED')
                self.ats_spell_rows[target] = choice['spell_row']
            self.ats_spell_view_file = filename
            self.ats_spell_view_rows = learned
            check = self.ats_spell_population_check(learned, population)
            samples = self.ats_spell_open_samples
            initial = next((sample for sample in reversed(samples)
                            if sample['counter'] < population['counter']
                            and sample.get('sample_phase') == 'OPEN'
                            and sample.get('layout') == spell and sample.get('root') == spell_root), None)
            stable = bool(initial and population.get('sample_phase') == 'AFTER_1500MS'
                          and self.ats_spell_population_check(learned, initial)['matches']
                          and self.ats_spell_geometry_signature(initial)
                          == self.ats_spell_geometry_signature(population))
            ok = ok and check['matches'] and stable
            result.update(server_view_file=filename, learned_spells=learned,
                          selected_spell_rows=self.ats_spell_rows,
                          native_spell_rows=check['rows'], first_page_expected=check['expected'],
                          spell_population_matches=check['matches'], spell_grid_stable=stable,
                          spell_grid_initial_file=initial.get('evidence_file') if initial else None,
                          spell_grid_delayed_file=population.get('evidence_file'),
                          spell_placement_status=population.get('placement', {}).get('status'),
                          first_buff_before=existing[0], first_battle_before=existing[1],
                          first_conditional_before=existing[2])
        if stage == 'reopened':
            check = self.ats_spell_population_check(self.ats_spell_view_rows, population)
            initial = next((sample for sample in reversed(self.ats_spell_open_samples)
                            if sample['counter'] < population['counter']
                            and sample.get('sample_phase') == 'OPEN'
                            and sample.get('layout') == spell and sample.get('root') == spell_root), None)
            stable = bool(initial and population.get('sample_phase') == 'AFTER_1500MS'
                          and self.ats_spell_population_check(self.ats_spell_view_rows, initial)['matches']
                          and self.ats_spell_geometry_signature(initial)
                          == self.ats_spell_geometry_signature(population))
            ok = ok and check['matches'] and stable
            result.update(spell_population_matches=check['matches'], spell_grid_stable=stable,
                          native_spell_rows=check['rows'])
        if stage in ('buff-draft', 'battle-draft', 'conditional-draft'):
            control = {'buff-draft': 'buff_spell', 'battle-draft': 'battle_spell',
                       'conditional-draft': 'conditional_spell'}[stage]
            slot = ui.spell_slot(ats, 'companion_ats', control)
            metadata = ui.ptr(slot + 0x808)
            kind = ui.struct.unpack('<i', ui.read(metadata + 8, 4))[0] if metadata else None
            row = ui.struct.unpack('<i', ui.read(metadata, 4))[0] if metadata else None
            ui.validate()
            target = {'buff-draft': 'buff', 'battle-draft': 'battle',
                      'conditional-draft': 'conditional'}[stage]
            ok = ok and kind == 1 and row == self.ats_spell_rows[target]
            result.update(native_target_slot=slot, native_kind=kind, native_spell_row=row,
                          selected_spell_row=self.ats_spell_rows[target])
        if stage in ('saved', 'reopened-saved'):
            after = self.ats_spell_snapshot(stage)
            before = self.ats_spell_before
            buff = after['buff_slots'][0] if after['buff_slots'] else {}
            battle = [after['battle_slots'][self.ats_spell_battle_targets[k]].get('slot', {})
                      for k in ('sequence', 'conditional')]
            buff_match = buff.get(1) == 1 and buff.get(4) == self.ats_spell_rows['buff']
            battle_match = all(slot.get(1) == 1 and slot.get(4) == self.ats_spell_rows[target]
                               for slot, target in zip(battle, ('battle', 'conditional')))
            self_ats_same = before['owner']['self_ats'] == after['owner']['self_ats']
            saves = [row for row in getattr(self.broker(), '_ats_events', ())
                     if row not in self.ats_spell_events_before and row.get('event') == 'window-save'
                     and row.get('member') == self.member_id]
            ok = ok and buff_match and battle_match and self_ats_same and bool(saves)
            result.update(saved=after, buff_spell_saved=buff_match,
                          battle_spell_saved=battle[0].get(1) == 1 and battle[0].get(4) == self.ats_spell_rows['battle'],
                          conditional_spell_saved=battle[1].get(1) == 1 and battle[1].get(4) == self.ats_spell_rows['conditional'],
                          knight_self_ats_unchanged=self_ats_same,
                          window_save_events=saves,
                          knight_self_config_drift=self.ats_config_drift(
                              before['owner']['self_config'], after['owner']['self_config']))
        if ok:
            self.ats_spell_stages[stage] = True
        return dict(result, status='OBSERVED' if ok else 'UNKNOWN',
                    reason=None if ok else 'ATS_SPELL_WINDOW_OR_SAVE_NOT_OBSERVED',
                    scope='NATIVE_WINDOW_VISIBILITY_AND_SERVER_SPELL_ROWS; PNG_VISUAL_REVIEW_REQUIRED')

    def ats_edit_display(self):
        ui = MemoryUi(self)
        layout = ui.layout('companion_ats')
        root = ui.ptr(layout + 0x30)
        field = ui.path(root, 'Root.Buff.01.HPTextField.TextField_23')
        renderer = ui.ptr(field + 0x700)
        interface = renderer + 0x340 if renderer else 0
        if not interface or ui.ptr(ui.ptr(interface) + 0x10) != ui.base + 0xc56a20:
            raise ValueError('ATS_EDIT_TEXTFIELD_STRING_GETTER_UNKNOWN')
        text = ui.string(renderer + 0x830)
        slot = ui.path(root, 'Root.Buff.01.Slot01.Item02')
        metadata = ui.ptr(slot + 0x808)
        template = None
        if metadata:
            kind = ui.struct.unpack('<i', ui.read(metadata + 8, 4))[0]
            if kind != 2:
                raise ValueError('ATS_EDIT_HP_SLOT2_NON_ITEM_METADATA')
            template = ui.struct.unpack('<i', ui.read(metadata + 0x20, 4))[0]
        ui.validate()
        return dict(layout=layout, root=root, hp_field=field, hp_renderer=renderer,
                    hp_percent_text=text, hp_slot2_node=slot, hp_slot2_metadata=metadata,
                    hp_slot2=template, text_basis='VALIDATED_C56A20_RENDERER_STRING32_AT_830',
                    slot_basis='NATIVE_SLOT_808_ITEM_METADATA_TEMPLATE_20')

    def observe_ats_edit(self, stage):
        facts = self.ats_window_visibility()
        closed = stage in ('closed', 'final')
        visible = not facts['knight']['shown'] and facts['companion']['shown'] != closed
        stages = self.ats_edit_stages
        previous = dict(dragged='opened', draft='dragged', saved='draft',
                        closed='saved', reopened='closed', final='reopened').get(stage)
        ok = visible and self.blocked is None and (previous is None or previous in stages)
        result = dict(windows=facts, png=self.last_capture_context['png'],
                      ui_result='UNKNOWN', scope='NATIVE_READBACK_AND_SERVER_SAVE; PNG_REQUIRES_VISUAL_REVIEW')
        delivery = self.ats_window_delivery()
        result['native_view_results'] = delivery
        # Missing spell targets only blank those slots (the DLL still renders the
        # rest); the item/HP edit verdict below is decided by the native display.
        refused = any(row.get('status') == 'ATS_WINDOW_SPELL_TARGETS_UNAVAILABLE' for row in delivery)
        result['spell_targets_unavailable'] = refused
        if not closed:
            display = self.ats_edit_display()
            result['native_display'] = display
            if stage == 'opened':
                self.ats_edit_initial_display = display
                hp = self.ats_edit_before['hp_percent']
                expected_text = '' if hp is None else str(int(hp)) if int(hp) == hp else str(hp)
                result['expected_native_display'] = dict(hp_percent_text=expected_text,
                                                        hp_slot2=self.ats_edit_before['hp_slot2'])
                ok = ok and display['hp_percent_text'] == expected_text
                ok = ok and display['hp_slot2'] == self.ats_edit_before['hp_slot2']
            if stage in ('dragged', 'draft', 'saved', 'reopened'):
                ok = ok and display['hp_slot2'] == 14
            if stage in ('draft', 'saved', 'reopened'):
                ok = ok and display['hp_percent_text'] == '60'
        if stage in ('saved', 'reopened', 'final'):
            after = self.ats_edit_snapshot(stage)
            before = self.ats_edit_before
            self_ats_unchanged = before['owner']['self_ats'] == after['owner']['self_ats']
            config_drift = self.ats_config_drift(before['owner']['self_config'],
                                                 after['owner']['self_config'])
            unchanged = self_ats_unchanged and not config_drift['raw_changed']
            saves = [row for row in getattr(self.broker(), '_ats_events', ())
                     if row not in self.ats_edit_events_before
                     and row.get('event') == 'window-save' and row.get('member') == self.member_id
                     and row.get('character') == self.ats_window_owner_uid]
            changed = after['companion_ats'] != before['companion_ats']
            # The original client's independent autosave can update its
            # CharacterConfig while this window is open. Report that drift;
            # this verdict covers the requested companion values and SELF ATS.
            ok = ok and self_ats_unchanged and changed and bool(saves) and after['hp_percent'] == 60 and after['hp_slot2'] == 14
            result.update(saved=after, knight_self_fields_unchanged=unchanged,
                          knight_self_ats_unchanged=self_ats_unchanged,
                          knight_self_config_drift=config_drift,
                          preservation_scope='SELF_ATS_BYTES; SELF_CONFIG_DRIFT_REPORTED_SEPARATELY',
                          companion_ats_changed=changed, window_save_events=saves)
        if ok:
            stages[stage] = True
        return dict(result, status='OBSERVED' if ok else 'UNKNOWN',
                    first_failure=self.blocked, required_prior_stage=previous,
                    reason=None if ok else 'ATS_EDIT_EXPECTED_NATIVE_DISPLAY_OR_SAVED_STATE_NOT_OBSERVED')

    @staticmethod
    def ats_config_drift(before, after):
        from collections import Counter
        from tools.local_original_session import ats_config_codec as codec
        result = dict(raw_changed=before != after)
        if before == after:
            return result
        try:
            old = codec.fields(codec.unwrap_blob(bytes.fromhex(before)))
            new = codec.fields(codec.unwrap_blob(bytes.fromhex(after)))
            keys = set((n, w) for n, w, _ in old + new)
            changed = sorted(n for n, w in keys
                             if [v for nn, ww, v in old if (nn, ww) == (n, w)]
                             != [v for nn, ww, v in new if (nn, ww) == (n, w)])
            result['changed_top_fields'] = sorted(set(changed))
            for field in (2, 3):
                def values(rows):
                    return [v for n, w, message in rows if (n, w) == (1, 2)
                            for nn, ww, v in codec.fields(message) if (nn, ww) == (field, 0)]
                left, right = Counter(values(old)), Counter(values(new))
                result['f1_f%d_varints' % field] = dict(
                    added=list((right-left).elements()), removed=list((left-right).elements()))
            result['classification'] = 'CHARACTER_CONFIG_DRIFT; FIELD_SEMANTICS_NOT_ASSUMED'
        except (ValueError, TypeError) as error:
            result['decode_reason'] = str(error)[:160]
        return result

    def ats_window_snapshot(self, label):
        # Missing data is UNKNOWN through the enclosing scenario exception
        # path. Comparing two absent keys must never become preservation PASS.
        stored = json.loads(self.ats_window_path.read_text(encoding='utf-8'))
        if stored.get('schema') != 1 or type(stored.get('characters')) is not dict:
            raise ValueError('ATS_WINDOW_SCOPE_STORE_INVALID')
        row = stored['characters'].get(str(self.ats_window_owner_uid))
        if type(row) is not dict or any(type(row.get(k)) is not str or not row[k]
                                       for k in ('self_config', 'self_ats')):
            raise ValueError('ATS_WINDOW_EXISTING_KNIGHT_SELF_CONFIG_AND_SELF_ATS_REQUIRED')
        snapshot = dict(character=self.ats_window_owner_uid,
                        self_config=row['self_config'], self_ats=row['self_ats'],
                        source=str(self.ats_window_path))
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / ('ats-window-' + label + '-snapshot.json')
        path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding='utf-8')
        return dict(snapshot, snapshot_file=str(path))

    def ats_window_visibility(self):
        ui = MemoryUi(self)
        facts = {}
        for role, key in (('knight', 'ATSLayout'), ('companion', 'SLCompATS')):
            layout = ui.named_layout(key)
            root = ui.ptr(layout + 0x30) if layout else None
            facts[role] = dict(registry_key=key, layout=layout, root=root,
                               shown=bool(root and ui.shown(root)))
        ui.validate()
        if (facts['knight']['layout'] and facts['companion']['layout']
                and (facts['knight']['layout'] == facts['companion']['layout']
                     or facts['knight']['root'] == facts['companion']['root'])):
            raise ValueError('ATS_WINDOW_KNIGHT_AND_COMPANION_NOT_DISTINCT')
        return facts

    def observe_ats_window(self, stage):
        if stage in ('saved', 'saved-final'):
            if not hasattr(self, 'ats_window_saved_snapshots'):
                self.ats_window_saved_snapshots = {}
            if stage not in self.ats_window_saved_snapshots:
                self.ats_window_saved_snapshots[stage] = self.ats_window_snapshot(
                    'after-close' if stage == 'saved' else 'after-escape')
            after = self.ats_window_saved_snapshots[stage]
            before = self.ats_window_before
            unchanged = all(before[k] == after[k] for k in ('self_config', 'self_ats'))
            required = ['companion', 'knight-replaces-companion', 'companion-replaces-knight',
                        'companion-closed', 'knight-reopened', 'closed']
            if stage == 'saved-final':
                required += ['reopened', 'escaped']
            missing = [s for s in required if s not in getattr(self, 'ats_window_observed', {})]
            ok = unchanged and not missing and self.blocked is None
            return dict(status='OBSERVED' if ok else 'UNKNOWN', before=before,
                after=after, knight_self_fields_unchanged=unchanged, ui_result='UNKNOWN',
                missing_visibility_stages=missing, first_failure=self.blocked,
                reason=(None if ok else 'KNIGHT_ATS_FIELDS_CHANGED' if not unchanged else
                        'ATS_WINDOW_SEQUENCE_INCOMPLETE'),
                scope='EXISTING_SERVER_ATS_SCOPES_KNIGHT_SELF_CONFIG_AND_SELF_ATS_ONLY')
        facts = self.ats_window_visibility()
        expected = {'companion': (False, True), 'knight-replaces-companion': (True, False),
                    'companion-replaces-knight': (False, True), 'companion-closed': (False, False),
                    'knight-reopened': (True, False), 'closed': (False, False),
                    'reopened': (False, True), 'escaped': (False, False)}[stage]
        actual = tuple(facts[role]['shown'] for role in ('knight', 'companion'))
        observed = getattr(self, 'ats_window_observed', {})
        predecessors = {'knight-replaces-companion': 'companion',
                        'companion-replaces-knight': 'knight-replaces-companion',
                        'companion-closed': 'companion-replaces-knight',
                        'knight-reopened': 'companion-closed', 'closed': 'knight-reopened',
                        'reopened': 'closed', 'escaped': 'reopened'}
        previous = predecessors.get(stage)
        ok = actual == expected and (previous is None or previous in observed)
        if ok:
            observed[stage] = facts
        return dict(status='OBSERVED' if ok else 'UNKNOWN', windows=facts,
            expected_shown=dict(zip(('knight', 'companion'), expected)),
            mutual_exclusion_observed=not all(actual),
            prior_observed_stage=previous, png=self.last_capture_context['png'],
            ui_result='UNKNOWN', automatic_retry=False,
            reason=None if ok else 'ATS_WINDOW_VISIBILITY_TRANSITION_NOT_OBSERVED',
            scope='DISTINCT_NATIVE_REGISTRY_ROOT_VISIBILITY; PNG_REQUIRES_VISUAL_REVIEW')

    def talkscroll_snapshot(self):
        current, _ = module.current_kit(self.manual)
        broker = current[0].broker
        rows = module.inv.validate_kit_frame(broker._inventory_current_frame)
        scroll = next((r for r in rows if r.identifier == 65577), None)
        if scroll is None or scroll.template_bits != 12163:
            raise ValueError('TALKSCROLL_UID_TEMPLATE_MISMATCH')
        position = broker.realm.service(current[0].writer).snapshot()
        return dict(scroll_uid=65577, scroll_template=12163,
            scroll_quantity=dict(scroll.raw_fields).get(4, 0), raw_item_type=dict(scroll.raw_fields).get(5),
            position=dict(uid=position.uid, map_id=position.map_id, x=position.word0, y=position.word1),
            server_errors=list(getattr(broker, '_world_handler_errors', ())))

    def talkscroll_visible_slot(self, capture):
        """Locate the live UID's rendered cell, including native scroll transforms.

        Slot nodes themselves can have zero size. A nonzero drawable descendant
        supplies the center; its parent chain includes the current scroll offset.
        Absolute inventory order and wheel count never supply a visual row.
        """
        require_capture_geometry(capture)
        memory = MemoryUi(self)
        layout = memory.layout('self_bag')
        try:
            slot = memory.slot(layout, 'self_bag', 65577)
        except ValueError as error:
            if str(error) != 'UI_ITEM_SLOT_NOT_UNIQUE:self_bag':
                raise
            memory.validate()
            return dict(visible=False, reason='UID_NOT_BOUND_TO_SHOWN_NATIVE_SLOT',
                        layout=layout, item_uid=65577)
        candidates, visited, pending = [], set(), [(slot, 0)]
        while pending:
            node, depth = pending.pop()
            if node in visited:
                continue
            visited.add(node)
            if len(visited) > 128:
                raise ValueError('TALKSCROLL_SLOT_DESCENDANT_BOUND')
            if not memory.shown(node):
                continue
            size = memory.vec(node + 0x6c)
            if all(n > 0 for n in size):
                point, facts = memory.node_point(node, 'self_bag.talkscroll_drawable',
                                                layout, require_capture=False)
                rect = facts['capture_rect']
                width, height = rect[2]-rect[0], rect[3]-rect[1]
                # Exclude small count text and decorations spanning many cells.
                if 35 <= width <= 175 and 35 <= height <= 175:
                    x, y = point
                    column, row = int((x-2190)//140), int((y-80)//140)
                    if (0 <= column < 4 and 0 <= row < 8
                            and abs(x-(2190+(column+.5)*140)) <= 56
                            and abs(y-(80+(row+.5)*140)) <= 56):
                        candidates.append(dict(grid_cell=row*4+column, point=point,
                                               node=node, geometry=facts))
            if depth < 4:
                pending.extend((child, depth+1) for child in memory.children(node))
        memory.validate()
        cells = {row['grid_cell'] for row in candidates}
        result = dict(visible=len(cells) == 1, item_uid=65577, layout=layout, slot=slot,
            selection_basis='LIVE_UID_SLOT_DRAWABLE_PARENT_CHAIN_WITH_CURRENT_SCROLL',
            candidates=candidates, ui_result='UNKNOWN',
            limitation='NATIVE_GEOMETRY_INFERENCE_REQUIRES_PNG_VISUAL_REVIEW')
        if len(cells) == 1:
            result.update(grid_cell=next(iter(cells)), reason=None)
        else:
            result['reason'] = ('DRAWABLE_NOT_IN_VISIBLE_CAPTURE_GRID' if not cells else
                                'DRAWABLES_DISAGREE_ON_VISIBLE_CELL')
        if not cells:
            # The original inventory virtualizes cells. In glfw26, UID65577
            # was bound even when its zero-size slot's drawable failed the
            # generic geometry filter. Measure THIS run's rendered row shift
            # instead of treating each wheel as a guaranteed row or replaying
            # a coordinate from a previous run.
            mapped = self.talkscroll_capture_slot(capture)
            result['capture_row_mapping'] = mapped
            if mapped.get('visible'):
                result.update(visible=True, grid_cell=mapped['grid_cell'], reason=None,
                    selection_basis='LIVE_UID_BINDING_AND_SAME_RUN_CAPTURE_ROW_SHIFT')
        return result

    def talkscroll_capture_slot(self, capture):
        require_capture_geometry(capture)
        from PIL import Image, ImageChops, ImageStat
        import hashlib
        rows = module.inv.validate_kit_frame(self.broker()._inventory_current_frame)
        order = [r.identifier for r in rows]
        absolute = order.index(65577)
        raw = Path(capture['png']).read_bytes()
        import io
        with Image.open(io.BytesIO(raw)) as image:
            if list(image.size) != capture['png_size']:
                raise ValueError('INPUT_CAPTURE_PNG_SIZE_CHANGED_OR_MISSING')
            pixels = image.convert('RGB')
            # Exclude borders/count text. Keep the icons and their opaque
            # backgrounds so native scrolling can be measured from the PNG.
            cells = [pixels.crop((2190+(i%4)*140+24, 80+(i//4)*140+16,
                                  2190+(i%4)*140+116, 80+(i//4)*140+108)).resize((23, 23))
                     for i in range(32)]
        baseline = getattr(self, 'talkscroll_grid_baseline', None)
        common = dict(item_uid=65577, absolute_inventory_index=absolute,
            inventory_count=len(order), png=capture['png'],
            capture_sha256=hashlib.sha256(raw).hexdigest(), ui_result='UNKNOWN')
        if baseline is None:
            self.talkscroll_grid_baseline = dict(cells=cells, order=order,
                png=capture['png'], capture_sha256=common['capture_sha256'])
            return dict(common, visible=False, reason='INITIAL_GRID_ROW_SHIFT_REFERENCE_RECORDED',
                initial_top_assumption='FRESH_INVENTORY_OPEN_AT_TOP; FRAME_ORDER_MATCHES_GLFW26_VISUAL_REVIEW')
        if order != baseline['order']:
            return dict(common, visible=False, reason='INVENTORY_ORDER_CHANGED_SINCE_GRID_REFERENCE')
        scores = []
        # At most two wheels are issued. Search more than two rows because a
        # callback delta is not a measured number of native scroll rows.
        for shift in range(6):
            differences = [sum(ImageStat.Stat(ImageChops.difference(
                cells[i], baseline['cells'][i+shift*4])).mean)/3
                for i in range(32-shift*4)]
            scores.append(dict(row_shift=shift, mean_rgb_error=sum(differences)/len(differences),
                               compared_cells=len(differences)))
        scores.sort(key=lambda r: r['mean_rgb_error'])
        best = scores[0]
        unique = (best['mean_rgb_error'] <= 12
                  and scores[1]['mean_rgb_error']-best['mean_rgb_error'] >= 3)
        cell = absolute-best['row_shift']*4
        visible = unique and 0 <= cell < 32
        return dict(common, visible=visible, grid_cell=cell if visible else None,
            measured_row_shift=best['row_shift'] if unique else None,
            row_shift_scores=scores, baseline_png=baseline['png'],
            baseline_sha256=baseline['capture_sha256'],
            reason=None if visible else 'CAPTURE_ROW_SHIFT_AMBIGUOUS_OR_TARGET_OUTSIDE_GRID',
            selection_basis='CURRENT_PNG_ICON_ROW_MATCH_TO_INITIAL_PNG_PLUS_CURRENT_FRAME_ORDER',
            reference_evidence='GLFW26_INDEX34_LAST_OF35; WHEEL2_VISUAL_CELL26; NATIVE_VIRTUALIZED_UID_BINDING',
            limitation='INITIAL_TOP_AND_FRAME_VISUAL_ORDER_INFERRED; CLICK_EFFECT_REQUIRES_SERVER_OBSERVATION')

    def scroll_talkscroll(self):
        capture = getattr(self, 'last_capture_context', None)
        if not capture or self.results[-1].get('status') != 'OBSERVED':
            return dict(status='UNKNOWN', reason='TALKSCROLL_SCROLL_CAPTURE_REQUIRED')
        if not self.self_bag_visibility()['shown']:
            return dict(status='UNKNOWN', reason='TALKSCROLL_SELF_BAG_NOT_SHOWN')
        visible = self.talkscroll_visible_slot(capture)
        count = getattr(self, 'talkscroll_wheel_count', 0)
        if visible['visible']:
            return dict(status='OBSERVED', visible_slot=visible, wheel_count=count,
                        png=capture['png'], ui_result='UNKNOWN')
        if count >= 2 or visible['reason'] == 'DRAWABLES_DISAGREE_ON_VISIBLE_CELL':
            return dict(status='UNKNOWN', reason='TALKSCROLL_VISIBLE_SLOT_NOT_ESTABLISHED',
                        visible_slot=visible, wheel_count=count, png=capture['png'])
        self.talkscroll_wheel_count = count + 1
        label = 'talkscroll-inventory-wheel-%d' % (count+1)
        # Same capture -> GLFW mouse_wheel -> settle -> capture path as
        # bag_close_wheel; native input determines the actual scroll distance.
        inserts = scenario_action(label, 'self_bag.drop', 'mouse_wheel', delta=-120)
        inserts.append(('scenario_talkscroll_scroll', 'talkscroll-scroll-check-%d' % (count+1)))
        self.steps[self.index+1:self.index+1] = inserts
        return dict(status='OBSERVED', action='SCHEDULED_NATIVE_WHEEL', delta=-120,
                    visible_slot=visible, wheel_count=count, png=capture['png'],
                    ui_result='UNKNOWN')

    def talkscroll_row_evidence(self, capture):
        """Bind the visually reviewed glfw29 row only when this PNG matches it."""
        require_capture_geometry(capture)
        import hashlib
        import io
        from PIL import Image, ImageChops, ImageStat
        reference = Path(__file__).resolve().parent.parent / 'runs' / (
            'glfw29-talkscroll_open-claude-20261030/after-talkscroll-double-click.png')
        reference_raw = reference.read_bytes()
        expected = '478c3d3118e6dfb6ce701e1bedf56e5b6b5331f12e7504cd2ed4747c5f3cdc4f'
        if hashlib.sha256(reference_raw).hexdigest() != expected:
            raise ValueError('TALKSCROLL_REVIEWED_REFERENCE_CHANGED')
        raw = Path(capture['png']).read_bytes()
        with Image.open(io.BytesIO(reference_raw)) as source, Image.open(io.BytesIO(raw)) as current:
            if source.size != (2880, 2160) or list(current.size) != capture['png_size']:
                raise ValueError('TALKSCROLL_ROW_CAPTURE_DIMENSIONS_UNKNOWN')
            source = source.convert('RGB')
            current = current.convert('RGB')
            comparisons = []
            # Title + village/hunting separator + first two hunting rows:
            # a row-shaped patch alone cannot establish which list is open.
            for box in ([55, 80, 790, 145], [55, 880, 790, 1075]):
                difference = ImageChops.difference(source.crop(box), current.crop(box))
                comparisons.append(dict(reference_box=box,
                    mean_rgb_error=sum(ImageStat.Stat(difference).mean)/3))
        if any(r['mean_rgb_error'] > 6 for r in comparisons):
            return None
        return dict(row='first_hunting', text='말하는섬 던전 1층',
            point=[270, 1000],
            png_size=capture['png_size'], capture_sha256=hashlib.sha256(raw).hexdigest(),
            visual_evidence='REVIEWED_GLFW29_TITLE_AND_FIRST_HUNTING_CONTEXT_MATCH_CURRENT_PNG',
            reference_png=str(reference), reference_sha256=expected,
            reference_point=[270, 1000], comparisons=comparisons,
            point_basis='REVIEWED_ROW_CENTER_SCALED_TO_CURRENT_CAPTURE; SAME_CAPTURE_GEOMETRY')

    def install_talkscroll_send_probe(self):
        if getattr(self, 'talkscroll_send_probe', None):
            return
        from tools.local_original_session.world_feature_talkscroll import _talkscroll_unavailable_notice
        broker = self.broker()
        writer = module.current_kit(self.manual)[0][0].writer
        original, owned = broker._world_send, '_world_send' in vars(broker)
        saved = vars(broker).get('_world_send')
        expected = _talkscroll_unavailable_notice()
        self.talkscroll_notices = []

        async def send(target_writer, row, frames, operation_lock):
            observation = None
            if target_writer is writer and any(frame == expected for frame in frames):
                observation = dict(opcode='0x4EEA', message_code=12066,
                    text='현재 서버에서 지원하지 않는 목적지이거나 이동할 수 없는 위치입니다.',
                    status='UNKNOWN', send_returned=False, requested_monotonic_seconds=time.monotonic(),
                    scope='EXACT_REFUSAL_FRAME_IN_WORLD_SEND; NATIVE_DISPLAY_UNKNOWN')
                self.talkscroll_notices.append(observation)
            try:
                result = await original(target_writer, row, frames, operation_lock)
            except BaseException as error:
                if observation is not None:
                    observation.update(reason=type(error).__name__ + ':' + str(error)[:200])
                raise
            if observation is not None:
                # _world_send awaits the product send's writer.write/drain.
                # This is transport completion, not proof of client rendering.
                observation.update(status='OBSERVED', send_returned=True,
                    completed_monotonic_seconds=time.monotonic())
            return result

        broker._world_send = send
        self.talkscroll_send_probe = (broker, send, owned, saved)

    def talkscroll_row(self):
        # A point must identify the FIRST hunting destination in this exact
        # list PNG. Explicit reviewer evidence still overrides the glfw29
        # visual match; both paths bind the current PNG hash and dimensions.
        import hashlib
        capture = getattr(self, 'last_capture_context', None)
        result = dict(status='UNKNOWN', row_result='UNKNOWN', ui_result='UNKNOWN',
            reason='FIRST_HUNTING_ROW_NOT_LOCATED_IN_SCREENSHOT', automatic_retry=False,
            capture_only=True, capture=capture, server=self.talkscroll_snapshot())
        if not capture or self.results[-1].get('status') != 'OBSERVED':
            return result
        bound = semantic_plan.get('locators', {}).get('talkscroll.first_hunting_row')
        path = os.environ.get('VERIFY_TALKSCROLL_ROW_EVIDENCE', '')
        if path:
            bound = json.loads(Path(path).read_text(encoding='utf-8-sig'))
        if not bound:
            bound = self.talkscroll_row_evidence(capture)
            if not bound:
                return result
        digest = hashlib.sha256(Path(capture['png']).read_bytes()).hexdigest()
        point = bound.get('point')
        if (bound.get('capture_sha256') != digest or bound.get('png_size') != capture['png_size']
                or bound.get('row') != 'first_hunting' or not bound.get('visual_evidence')
                or type(point) is not list or len(point) != 2
                or not all(type(n) is int and 0 <= n < capture['png_size'][i] for i, n in enumerate(point))):
            return dict(result, reason='SAME_CAPTURE_FIRST_HUNTING_ROW_EVIDENCE_REQUIRED')
        request = dict(schema='local-original-input-request-v1', action='left_click',
            expected_scene='Land', coordinate_space='capture', png_size=capture['png_size'],
            coordinate_basis='capture_to_client',
            x=point[0], y=point[1],
            sequence=getattr(getattr(self, 'private_inputs', None), 'last_sequence', 0)+1)
        self.talkscroll_selection_before = self.talkscroll_snapshot()
        self.install_talkscroll_send_probe()
        # Reuse THIS capture and its geometry, not a fresh capture with an old
        # binding. do_private_input performs current-owner/geometry checks.
        steps = [('private_input', 'talkscroll-first-hunting-click', request)]
        if _selected_steps == 'talkscroll_teleport_capture':
            steps.append(('capture', 'talkscroll-teleport-effect-immediate'))
        steps.extend((('wait', 'talkscroll-first-hunting-settle', 1),
                      ('capture', 'after-talkscroll-first-hunting-click'),
                      ('scenario_observe', 'talkscroll-position-result',
                       dict(talkscroll_position=True))))
        self.steps[self.index+1:self.index+1] = steps
        return dict(result, status='OBSERVED', row_result='LOCATED', reason=None,
                    capture_only=False, row_evidence=bound)

    def observe(self, condition):
        if condition.get('ats_native_clear_probe'):
            return self.ats_native_clear_snapshot(condition['ats_native_clear_probe'])
        if condition.get('ats_window_clear'):
            return self.observe_ats_clear(condition['ats_window_clear'])
        if condition.get('ats_window_heal'):
            return self.observe_ats_heal(condition['ats_window_heal'])
        if condition.get('ats_window_spell'):
            return self.observe_ats_spell(condition['ats_window_spell'])
        if condition.get('ats_window_edit'):
            return self.observe_ats_edit(condition['ats_window_edit'])
        if condition.get('ats_window'):
            return self.observe_ats_window(condition['ats_window'])
        if condition.get('talkscroll_position'):
            before, after = self.talkscroll_selection_before, self.talkscroll_snapshot()
            changed = before['position'] != after['position']
            click = next((r for r in reversed(self.results)
                          if r.get('step') == 'talkscroll-first-hunting-click'), {})
            posted = click.get('status') == 'POSTED'
            notices = list(getattr(self, 'talkscroll_notices', ()))
            sent = any(r['send_returned'] for r in notices)
            # The broker retains only eight handler errors. Preserve the new
            # suffix without treating a pre-click refusal as this click's
            # decision; an identical full ring remains ambiguous.
            prior, current = before['server_errors'], after['server_errors']
            overlap = max((n for n in range(min(len(prior), len(current))+1)
                           if n == 0 or prior[-n:] == current[:n]), default=0)
            new_errors = current[overlap:]
            refused = sent  # exact current-selection 4EEA notice + send return
            observed = posted and (changed or refused)
            return dict(status='OBSERVED' if observed else 'UNKNOWN', before=before, after=after,
                row_input_status=click.get('status', 'UNKNOWN'), server_position_changed=changed,
                refusal_notice_send='OBSERVED' if sent else 'UNKNOWN', refusal_notices=notices,
                new_server_errors=new_errors,
                destination_unavailable_decision=('OBSERVED' if
                    'TALKSCROLL_DESTINATION_UNAVAILABLE' in new_errors else 'UNKNOWN'),
                result=('SERVER_POSITION_CHANGED' if posted and changed else
                        'SERVER_REFUSAL_NOTICE_SENT' if posted and refused else 'UNKNOWN'),
                reason=None if observed else 'ROW_CLICK_POSITION_CHANGE_OR_REFUSAL_SEND_NOT_OBSERVED',
                ui_result='UNKNOWN',
                scope='SCREENSHOT_BOUND_ROW_INPUT_AND_SERVER_POSITION_OR_REFUSAL_TRANSPORT_ONLY')
        if condition.get('self_bag_shown'):
            facts = self.self_bag_visibility()
            return dict(status='OBSERVED' if facts['shown'] else 'UNKNOWN',
                        ui_result='UNKNOWN', automatic_retry=False, **facts,
                        reason=None if facts['shown'] else 'SELF_INVENTORY_NOT_SHOWN',
                        scope='NATIVE_INVENTORY_LAYOUT_VISIBILITY_ONLY')
        if condition.get('resurrect'):
            before = getattr(self, 'resurrection_before', {})
            after = self.resurrection_snapshot()
            decrease = (before.get('scroll_quantity', 0) - after['scroll_quantity']
                        if 'scroll_quantity' in after else None)
            revived = (before.get('alive') is False and after.get('alive') is True
                       and after.get('hp', 0) > 0 and after.get('companion_json', {}).get('alive') is True)
            return dict(status='OBSERVED' if revived and decrease == 1 else 'UNKNOWN',
                        ui_result='UNKNOWN', automatic_retry=False, before=before, after=after,
                        scroll_quantity_decrease=decrease, companion_errors=after.get('companion_errors', []),
                        companion_error_params=after.get('companion_error_params', []),
                        companion_untargeted_params=after.get('companion_untargeted_params', []),
                        raw_item_uses=after.get('raw_item_uses', []),
                        reason=None if revived and decrease == 1 else 'RESURRECTION_OR_SCROLL_COST_NOT_OBSERVED',
                        scope='SERVER_LIFE_HP_AND_SCROLL_COST_ONLY')
        if 'skip' in condition:
            return dict(status='SKIPPED', reason=condition['skip'], ui_result='UNKNOWN')
        result = dict(status='UNKNOWN', ui_result='UNKNOWN', automatic_retry=False)
        if condition.get('hidden'):
            ui = MemoryUi(self)
            try:
                layout = ui.layout(condition['hidden'])
                hidden = not ui.visible(ui.ptr(layout + 0x30))
            except ValueError as error:
                # A retired companion layout can leave the owner registry.
                # Absence alone cannot prove the original close callback ran.
                role = condition['hidden']
                key = {'ats': 'ATSLayout', 'companion_bag': 'SLCompBag', 'companion_equipment': 'SLCompGear'}[role]
                absent = ui.named_layout(key) is None
                was_registered = role in getattr(self, 'last_action_layouts', {})
                ui.validate()
                if absent and was_registered:
                    result.update(status='OBSERVED', native_registry_retired=True,
                        scope='PREVIOUSLY_OBSERVED_LAYOUT_REMOVED_FROM_CURRENT_REGISTRY',
                        png=self.last_capture_context['png'])
                else:
                    result['reason'] = str(error)
                return result
            ui.validate()
            result.update(status='OBSERVED' if hidden else 'UNKNOWN', native_root_hidden=hidden,
                          scope='CURRENT_NATIVE_VISIBILITY_ONLY', png=self.last_capture_context['png'])
        elif condition.get('scroll'):
            from PIL import Image, ImageChops
            before, after = self.last_action_capture['png'], self.last_capture_context['png']
            with Image.open(before) as a, Image.open(after) as b:
                changed = ImageChops.difference(a.convert('RGB'), b.convert('RGB')).getbbox()
            result.update(status='OBSERVED', capture_comparison=dict(before=before, after=after,
                          changed_bbox=changed), scroll_result='UNKNOWN',
                          limitation='PIXEL_DIFFERENCE_DOES_NOT_PROVE_SCROLL_OR_NO_SCROLL')
        elif condition.get('quantity_popup') or condition.get('quantity_popup_or_signal'):
            popup = self.quantity_open()
            operation = condition.get('quantity_popup_or_signal')
            arrived = any(r not in self.last_action_signals and r.get('operation') == operation
                          and r.get('actor') == self.input_actor and r.get('status') == 'OK' for r in self.server_signals()) if operation else False
            self.reverse_popup = popup
            # Preserve the drag baseline for optional quantity/Enter and result.
            self.transfer_signals_before = list(self.last_action_signals)
            result.update(status='OBSERVED' if popup or arrived else 'UNKNOWN',
                          quantity_popup_native_event=popup, immediate_transfer=arrived,
                          native_drop_results=[r for r in self.drop_rows() if r not in self.last_action_drops])
        elif condition.get('ats_saved'):
            stored = json.loads(self.ats_path.read_text(encoding='utf-8'))
            before = self.ats_before.get('characters', {})
            after = stored.get('characters', {})
            member = after.get(str(self.member_id), {})
            changed = bool(member.get('companion_ats')) and member.get('companion_ats') != before.get(str(self.member_id), {}).get('companion_ats')
            owner_changes = {k for k in set(before) | set(after) if k != str(self.member_id)
                and any(before.get(k, {}).get(field) != after.get(k, {}).get(field)
                        for field in ('self_ats', 'companion_ats', 'self_config'))}
            saves = [r for r in getattr(self.broker(), '_ats_events', ()) if r.get('event') == 'save'
                     and r.get('scope') == 'member-edit' and r.get('member') == self.member_id
                     and r not in getattr(self, 'ats_events_before_edit', ())]
            reopened = not condition.get('reopened') or any(r not in self.last_action_signals
                and r.get('operation') == 'settings-load' and r.get('member') == self.member_id
                and r.get('status') == 'EDIT_STARTED' for r in self.server_signals())
            result.update(status='OBSERVED' if changed and saves and not owner_changes and reopened else 'UNKNOWN',
                          member_companion_ats_changed=changed, other_character_ats_fields_changed=sorted(owner_changes),
                          member_save_events=saves, reopened_member_edit=reopened,
                          ats_scopes=str(self.ats_path), saved_scope='MEMBER_COMPANION_ATS_ONLY')
        else:
            operation = condition.get('operation')
            accepted = set(operation if isinstance(operation, (tuple, list)) else [operation])
            baseline = self.transfer_signals_before if condition.get('transfer') == -1 else self.last_action_signals
            rows = [r for r in self.server_signals() if r not in baseline and r.get('actor') == self.input_actor
                    and r.get('operation') in accepted]
            callbacks = [r for r in self.callback_rows() if r not in self.last_action_callbacks
                         and r.get('row') == condition.get('row') and r.get('actor') == self.actor_uid]
            ok = any(r.get('status') in ('OK', 'EDIT_STARTED') for r in rows)
            if operation is None:
                # Original stance rows do not produce ReportPetClick or bridge
                # events: require the live server's mode record to match.
                modes = self.broker()._companion_pet_modes.get(self.actor_uid)
                wanted = 2 if condition['row'] == 1 else 3
                was = self.last_action_pet_mode
                ok = modes == wanted and modes != was
                result.update(native_pet_mode=modes, previous_mode=was, expected_mode=wanted,
                    limitation='CACHED_MODE_WITHOUT_TRANSITION_IS_NOT_NEW_ARRIVAL')
            if condition.get('transfer'):
                expected_item = self.last_potion_uids.get('self_bag' if condition['transfer'] == 1 else 'companion_bag')
                ok = ok and any(r.get('item') == expected_item and r.get('status') == 'OK' for r in rows)
                totals = self.totals(); direction = condition['transfer']
                wanted = [self.start_totals[0]-1, self.start_totals[1]+1] if direction == 1 else self.start_totals
                ok = ok and totals == wanted
                result.update(potion_totals=totals, expected_totals=wanted)
            if 'equipped' in condition:
                actual = self.equipment_uid in self.worn()
                ok = ok and actual == condition['equipped'] and any(r.get('item') == self.equipment_uid for r in rows)
                result.update(item=self.equipment_uid, equipped=actual)
            result.update(status='OBSERVED' if ok else 'UNKNOWN', server_signals=rows,
                          native_callback_rows=callbacks, scope='SERVER_STATE_AND_ARRIVAL_ONLY')
        if result['status'] == 'UNKNOWN' and not result.get('reason'):
            result['reason'] = 'EXPECTED_OBSERVATION_NOT_PRESENT'
        return result

    async def tick(self):
        if not self.named_scenario or self.done:
            return await super().tick()
        step = self.steps[self.index]
        if (self.resurrect_scenario and step[0] == 'private_input'
                and step[1] == 'resurrect-corpse-click' and self.resurrection_scroll_arrived()):
            self.finish(dict(status='SKIPPED', reason='RESURRECTION_SCROLL_CS0960_ALREADY_RECEIVED',
                             automatic_retry=False, ui_result='UNKNOWN'))
            return
        if self.blocked and not ((self.resurrect_scenario or self.talkscroll_scenario or ATS_WINDOW_SCENARIO)
                                 and step[0] in ('capture', 'scenario_observe')):
            self.finish(dict(status='SKIPPED', reason='FAILED_PREREQUISITE', prerequisite=self.blocked,
                             automatic_retry=False, ui_result='UNKNOWN'))
            return
        try:
            if step[0] == 'scenario_prepare':
                self.finish(self.prepare(step[2] if len(step) > 2 else None)); return
            if step[0] == 'scenario_ats_clear':
                # Replace observed percent digits through actual focused
                # TextField keys. Never write native text/draft from the harness.
                text = self.ats_edit_display()['hp_percent_text']
                if len(text) > 3 or text and (not text.isascii() or not text.isdigit() or int(text) > 100):
                    raise ValueError('ATS_EDIT_NATIVE_PERCENT_TEXT_NOT_EMPTY_OR_INTEGER_0_TO_100')
                inserts = []
                for key in ('Right',) * len(text) + ('Backspace',) * len(text):
                    inserts.extend(scenario_action('companion-hp-clear-%d' % len(inserts),
                                                   'companion_ats', 'key_press', key=key))
                self.steps[self.index+1:self.index+1] = inserts
                self.finish(dict(status='OBSERVED', action='SCHEDULED_REAL_TEXTFIELD_KEYS',
                                 ui_result='UNKNOWN')); return
            if step[0] == 'scenario_inventory':
                facts = self.self_bag_visibility()
                if not facts['shown']:
                    inserts = scenario_action(('talkscroll' if self.talkscroll_scenario else 'resurrect') + '-inventory-open', 'hud.bag_icon',
                        observe=dict(self_bag_shown=True))
                    self.steps[self.index+1:self.index+1] = inserts
                self.finish(dict(status='OBSERVED', **facts,
                    action='ALREADY_SHOWN' if facts['shown'] else 'SCHEDULED_NATIVE_HUD_CLICK',
                    ui_result='UNKNOWN')); return
            if step[0] == 'scenario_talkscroll_row':
                self.finish(self.talkscroll_row()); return
            if step[0] == 'scenario_talkscroll_scroll':
                self.finish(self.scroll_talkscroll()); return
            if step[0] == 'scenario_quantity':
                if self.reverse_popup:
                    inserts = scenario_action('take-quantity-focus', 'quantity')
                    inserts += scenario_action('take-quantity', 'quantity', 'key_press', key='1')
                    inserts += scenario_action('take-confirm', 'quantity', 'key_press', key='Enter')
                    self.steps[self.index+1:self.index+1] = inserts
                self.finish(dict(status='OBSERVED', quantity_popup=self.reverse_popup)); return
            if step[0] == 'scenario_observe':
                row = self.observe(step[2])
                # Wait for server/save observations, never repeat an input.
                if self.started is None:
                    self.started = time.monotonic()
                if row['status'] == 'UNKNOWN' and time.monotonic()-self.started < 8:
                    return
                self.finish(row); return
            if self.started is None:
                self.started = time.monotonic()
            if step[0] == 'capture':
                await self.do_capture(step[1])
            elif step[0] == 'pet':
                await self.do_post(step[0], step[1], step)
            else:
                await super().tick()
        except Exception as error:
            if self.capture is not None:
                self.capture.close(); self.capture = None
            self.finish(dict(status='UNKNOWN', reason=str(error)[:300], automatic_retry=False, ui_result='UNKNOWN'))


module.STEP_SETS['potion_effect'] = (('potion_effect', 'companion-potion-effect'),)


class PotionEffectSteps(CompanionScenarioSteps):
    """Capture first, then lower test companion HP once; observe normal ATS."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.potion_effect = any(s[0] == 'potion_effect' for s in self.steps)
        if not self.potion_effect:
            return
        self.effect_created = time.monotonic()
        self.effect_created_wall = time.time()
        self.effect_started = None
        self.effect_interval, self.effect_duration = .25, 6.0
        self.effect_capture_started = None
        self.effect_trigger = None
        self.effect_next = None
        self.effect_frames, self.effect_queues, self.effect_uses = [], [], []
        self.effect_errors, self.effect_samples = [], []
        self.effect_initial = None
        self.effect_terminal = False
        self.effect_hooks = []
        self.effect_capture_step = None
        self.effect_first_capture_timeout = 20.0
        self.install_effect_observers()

    def effect_error(self, where, error):
        self.effect_errors.append(dict(where=where, reason=str(error)[:240],
                                       elapsed=time.monotonic()-self.effect_created))
        del self.effect_errors[:-32]

    def effect_state(self, actor=None):
        broker = self.manual.inventory_broker
        world = broker._world
        if actor is None:
            actors = list(world.companions.active.values())
            if len(actors) != 1:
                return dict(status='UNKNOWN', reason='ACTIVE_COMPANION_NOT_UNIQUE')
            actor = actors[0]
        entity, owner = world.entities.resolve(actor.ref), world.entities.resolve(actor.owner_ref)
        service = broker._companion_inventory
        rows = module.inv.validate_kit_frame(service.frames[actor.character_id])
        stacks = [dict(uid=r.identifier, quantity=dict(r.raw_fields).get(4, 0))
                  for r in rows if r.template_bits == 14]
        owner_state = world.combat.pcs.get(actor.owner_ref.uid)
        return dict(status='OBSERVED', actor=actor.ref.uid, member=actor.character_id,
            owner_uid=actor.owner_ref.uid, hp=actor.record.hp, max_hp=actor.record.max_hp,
            owner_class_id=getattr(getattr(owner_state, 'profile', None), 'character_class', None),
            alive=actor.record.alive, potion_template=14, potion_quantity=sum(r['quantity'] for r in stacks),
            potion_stacks=stacks, current_entity=entity is not None, current_owner=owner is not None,
            owner_alive=owner is not None and owner.alive,
            owner_is_pc=actor.owner_ref.uid in world.pcs,
            owner_known=actor.ref.uid in world.visibility.known.get(actor.owner_ref.uid, ()),
            companion_position=None if entity is None else [entity.map_id, entity.x, entity.y],
            owner_position=None if owner is None else [owner.map_id, owner.x, owner.y])

    async def lower_effect_hp(self, fallback=None):
        # This is an explicit development trigger in the copied test profile,
        # never a fabricated hit or potion call. A bounded failed PNG wait is
        # explicit fallback evidence, not a fabricated pre-trigger screenshot.
        first = next((r for r in self.effect_frames if r.get('status') == 'OBSERVED'), None)
        self.effect_trigger = dict(status='UNKNOWN',
            first_capture_png=None if first is None else first['png'],
            first_capture_completed_elapsed=None if first is None else first['completed_elapsed'],
            capture_wait_fallback=fallback,
            scope=('TEST_COPY_RECORD_HP_LOWERING_AFTER_FIRST_OBSERVED_PNG' if first else
                   'TEST_COPY_RECORD_HP_LOWERING_AFTER_BOUNDED_CAPTURE_WAIT'))
        broker = self.manual.inventory_broker
        world = broker._world
        def apply():
            actors = list(world.companions.active.values())
            if len(actors) != 1:
                raise ValueError('ACTIVE_COMPANION_NOT_UNIQUE_AT_HP_TRIGGER')
            actor = actors[0]
            before = self.effect_state(actor)
            if (not before['alive'] or not before['current_entity'] or not before['owner_alive']
                    or actor.character_id in world.combat.pcs):
                raise ValueError('LIVING_AUTONOMOUS_COMPANION_HP_AUTHORITY_REQUIRED')
            target = max(1, actor.record.max_hp*30//100)
            if target >= actor.record.hp:
                raise ValueError('COMPANION_HP_NOT_ABOVE_30_PERCENT_TARGET')
            if broker._companion_party is None or broker._companion_store is None:
                raise ValueError('COMPANION_PRODUCT_PARTY_AND_STORE_REQUIRED')
            self.effect_started = time.monotonic()
            self.effect_trigger.update(before=before, target_hp=target,
                monotonic_seconds=self.effect_started, unix_seconds=time.time(),
                elapsed=self.effect_started-self.effect_created, status='MUTATED_SAVE_UNCONFIRMED')
            actor.record.hp = target
            # Product save commits the record and invokes its party.sync().
            # The companion's character ID must not have a PC HP authority
            # which would overwrite this autonomous record inside save.
            broker._companion_save(actor.owner_ref.uid)
            after = self.effect_state(actor)
            self.effect_trigger.update(after=after, product_save_returned=True,
                party_sync_route='_companion_save -> _companion_party.sync',
                status='OBSERVED' if after['hp'] == target else 'UNKNOWN')
            if after['hp'] != target:
                raise ValueError('COMPANION_HP_TRIGGER_OVERWRITTEN_DURING_PRODUCT_SAVE')
        await world.runtime.dispatch_now(apply)

    def effect_crops(self, destination):
        from PIL import Image
        crops = {}
        with Image.open(destination) as image:
            width, height = image.size
            # Broad QA regions retain both the party list and the nearby
            # companion's overhead bar. The full PNG remains authoritative;
            # region selection does not locate or prove either HP bar.
            for name, region in (('party-top-left', (0, 0, .35, .35)),
                                 ('companion-world-area', (.15, .12, .85, .80))):
                box = [round(region[i]*(width if i % 2 == 0 else height)) for i in range(4)]
                path = destination.with_name(destination.stem + '-' + name + '.png')
                image.crop(box).save(path)
                crops[name] = dict(png=str(path), box=box,
                    basis='BROAD_SCREENSHOT_QA_REGION_HP_BAR_VISIBILITY_UNKNOWN')
        return crops

    def install_effect_observers(self):
        # Steps is constructed by feature_factory before owner.resume(). The
        # screenshot and passive probes therefore do not wait for harness IDLE.
        from tools.local_original_session import launcher, world_companion_inventory
        world = self.manual.inventory_broker._world
        original_queue = world._queue
        had_queue = '_queue' in vars(world)
        saved_queue = vars(world).get('_queue')

        def queue(recipient, frame):
            before = len(world.outbox.get(recipient, ()))
            result = original_queue(recipient, frame)
            queued_at, queued_wall = time.monotonic(), time.time()
            if self.done or (self.effect_started is not None
                            and time.monotonic()-self.effect_started >= self.effect_duration):
                return result
            try:
                if len(frame) >= 6 and int.from_bytes(frame[2:4], 'little') == 0x4ed8:
                    from tools.local_entry_server import protobuf as pb
                    if int.from_bytes(frame[:2], 'little') != len(frame) or frame[-2:] != b'\0\0':
                        raise ValueError('EFFECT_FRAME_ENVELOPE_UNKNOWN')
                    with pb.parse_message(frame[4:-2]) as body:
                        uid, gfx = body.occurrences(1), body.occurrences(2)
                        if (len(uid) != 1 or len(gfx) != 1
                                or uid[0].wire_type != 0 or gfx[0].wire_type != 0):
                            raise ValueError('EFFECT_FRAME_UID_GFX_UNKNOWN')
                        target, graphic = uid[0].value, gfx[0].value
                    queued = world.outbox.get(recipient, ())
                    actor = world.companions.get_actor(target)
                    self.effect_queues.append(dict(opcode='0x4ED8', recipient_uid=recipient,
                        monotonic_seconds=queued_at, unix_seconds=queued_wall,
                        source_world_identity=id(world),
                        target_uid=target, gfx=graphic, elapsed=queued_at-self.effect_created,
                        capture_window_elapsed=(None if self.effect_started is None else
                                                time.monotonic()-self.effect_started),
                        actual_append=len(queued) == before+1 and queued[-1] is frame,
                        owner_uid=None if actor is None else actor.owner_ref.uid,
                        recipient_is_owner=actor is not None and recipient == actor.owner_ref.uid,
                        recipient_is_pc=recipient in world.pcs, scope='ACTUAL_WORLD_OUTBOX_APPEND_ONLY'))
                    del self.effect_queues[:-128]
            except Exception as error:
                self.effect_error('queue-observation', error)
            return result

        world._queue = queue
        self.effect_hooks.append((world, '_queue', original_queue, queue, had_queue, saved_queue))
        cls = world_companion_inventory.CompanionInventory
        original_potion = cls.potion

        def potion(service, actor, now):
            scoped = (service.ctx.world is world and not self.done
                      and (self.effect_started is None
                           or time.monotonic()-self.effect_started < self.effect_duration))
            before = None
            if scoped:
                try:
                    before = self.effect_state(actor)
                except Exception as error:
                    self.effect_error('potion-before', error)
            # Preserve normal call, return, exception and packet dispatch.
            drink_at, drink_wall = time.monotonic(), time.time()
            result = original_potion(service, actor, now)
            if scoped and result:
                try:
                    self.effect_uses.append(dict(before=before, after=self.effect_state(actor),
                        server_clock=now, elapsed=drink_at-self.effect_created,
                        monotonic_seconds=drink_at, unix_seconds=drink_wall,
                        completed_monotonic_seconds=time.monotonic(),
                        timestamp_basis='REAL_POTION_CALL_ENTRY_SUCCESS_RECORDED_ON_RETURN',
                        capture_window_elapsed=(None if self.effect_started is None else
                                                time.monotonic()-self.effect_started),
                        inventory_events=[dict(r) for r in service.events[-2:]],
                        scope='REAL_POTION_CALL_BEFORE_AFTER'))
                    del self.effect_uses[:-64]
                except Exception as error:
                    self.effect_error('potion-after', error)
            return result

        cls.potion = potion
        self.effect_hooks.append((cls, 'potion', original_potion, potion, True, original_potion))
        original_poll = launcher.ProductFeatures.poll

        async def poll(features, *args, **kwargs):
            row = await original_poll(features, *args, **kwargs)
            if getattr(features, 'manual', None) is self.manual and not self.done:
                await self.effect_tick()
            return row

        launcher.ProductFeatures.poll = poll
        self.effect_hooks.append((launcher.ProductFeatures, 'poll', original_poll, poll, True, original_poll))

    def effect_summary(self):
        good = [r for r in self.effect_uses if r.get('before') and r.get('after')
                and r['before'].get('alive') is True and r['after'].get('hp', 0) > r['before'].get('hp', 0)
                and r['before'].get('potion_quantity', 0)-r['after'].get('potion_quantity', 0) == 1]
        queues = [q for q in self.effect_queues if q['actual_append'] and q['gfx'] == 189
                  and q['recipient_is_owner'] and q['recipient_is_pc']
                  and any(q['target_uid'] == r['after']['actor']
                          and q['recipient_uid'] == r['after']['owner_uid'] for r in good)]
        frames = [r for r in self.effect_frames if r.get('status') == 'OBSERVED']
        # Login-time uses are retained, but only post-trigger uses qualify for
        # this capture experiment's result.
        good = [r for r in good if self.effect_trigger is not None
                and r['monotonic_seconds'] >= self.effect_trigger.get('monotonic_seconds', float('inf'))]
        post_frames = [r for r in frames if self.effect_trigger is not None
                       and r['actual_request_monotonic_seconds'] >= self.effect_trigger.get(
                           'monotonic_seconds', float('inf'))]
        queues = [q for q in queues if any(q['target_uid'] == r['after']['actor']
                  and r['monotonic_seconds'] <= q['monotonic_seconds'] <= r['completed_monotonic_seconds']
                  for r in good)]
        observed = bool(good and queues and self.effect_trigger.get('status') == 'OBSERVED')
        return dict(status='OBSERVED' if observed and post_frames else 'UNKNOWN', ui_result='UNKNOWN',
            automatic_retry=False, initial=self.effect_initial, potion_uses=list(self.effect_uses),
            hp_trigger=self.effect_trigger, full_initial_hp_allowed=True,
            observation_started_unix_seconds=self.effect_created_wall,
            observation_started_monotonic_seconds=self.effect_created,
            queued_effects=list(self.effect_queues), frames=list(self.effect_frames),
            samples=list(self.effect_samples), observation_errors=list(self.effect_errors),
            hp_and_red14_cost_observed=bool(good), owner_directed_target_gfx189_queued=bool(queues),
            requested_interval_seconds=self.effect_interval, requested_window_seconds=self.effect_duration,
            capture_window_started_elapsed=(None if self.effect_started is None else
                                            self.effect_started-self.effect_created),
            capture_window_basis='SIX_SECONDS_FROM_HP_TRIGGER_AFTER_PNG_OR_CAPTURE_WAIT_TIMEOUT',
            first_capture_wait_timeout_seconds=self.effect_first_capture_timeout,
            observed_frame_count=len(frames),
            post_trigger_frame_count=len(post_frames),
            actual_request_span_seconds=(None if not frames else
                frames[-1]['actual_request_elapsed']-frames[0]['actual_request_elapsed']),
            queue_preceded_first_capture_request=(None if not queues or not frames else
                min(q['elapsed'] for q in queues) < frames[0]['actual_request_elapsed']),
            scope='SERVER_HP_RED14_COST_AND_ACTUAL_4ED8_QUEUE; PNG_EFFECT_REQUIRES_VISUAL_REVIEW',
            limitations=['OWNER_KNOWN_SET_IS_NOT_PIXEL_APPEARANCE_PROOF',
                'ESTABLISHED_CAPTURE_STEP_OBSERVER_CADENCE_AND_NATIVE_PNG_LATENCY_REMAIN',
                'REQUESTED_250MS_IS_NOT_PROOF_OF_ACHIEVED_FRAME_CADENCE',
                'TEST_RECORD_HP_TRIGGER_IS_DEVELOPMENT_SETUP_NOT_A_NORMAL_DAMAGE_PASS',
                'CROP_REGIONS_AND_SERVER_HP_DO_NOT_PROVE_EITHER_HP_BAR_RENDERED'],
            reason=(None if observed and post_frames else 'POST_TRIGGER_SCREENSHOT_NOT_OBSERVED' if observed else
                    'HP_COST_OR_OWNER_EFFECT_QUEUE_NOT_OBSERVED'))

    async def poll_established_capture(self, capture_step):
        # glfw26 potion_effect's exact request/busy/sample/wait/timeout route.
        # A request refusal closes only this attempt; the caller keeps the
        # real schedule and records the failure before a later capture slot.
        try:
            await capture_step.do_capture(capture_step.steps[0][1])
        except Exception as error:
            if capture_step.capture is not None:
                capture_step.capture.close()
                capture_step.capture = None
            capture_step.finish(dict(status='CAPTURE_FAILED', reason=str(error)[:240]))
        self.capture = capture_step.capture

    async def effect_tick(self):
        if self.done:
            return
        now = time.monotonic()
        try:
            state = self.effect_state()
            memory = dict(getattr(self.scenario.monitor, 'last_memory', {}) or {})
            sample = dict(elapsed=now-self.effect_created, state=state,
                          scene=memory, harness_stage=self.scenario.stage)
            if (not self.effect_samples or now-self.effect_created-self.effect_samples[-1]['elapsed'] >= .25):
                self.effect_samples.append(sample)
                del self.effect_samples[:-128]
            if self.effect_capture_started is None:
                # Successful kind=capture scenarios begin at harness IDLE.
                # monitor.last_memory has no nested scene dictionary here.
                if self.scenario.stage != 'IDLE':
                    if now-self.effect_created >= 90:
                        self.finish(self.effect_summary())
                    return
                self.effect_initial = dict(state, elapsed=now-self.effect_created,
                                           source='BEFORE_FIRST_CAPTURE_STEP')
                self.effect_capture_started = self.effect_next = now
            if (self.effect_trigger is None
                    and now-self.effect_capture_started >= self.effect_first_capture_timeout):
                await self.lower_effect_hp(dict(reason='FIRST_PNG_CAPTURE_WAIT_TIMEOUT',
                    waited_seconds=now-self.effect_capture_started,
                    timeout_seconds=self.effect_first_capture_timeout,
                    capture_pending=self.capture is not None,
                    completed_capture_attempts=len(self.effect_frames)))
                self.effect_next = self.effect_started
            if self.effect_capture_step is not None:
                capture_step = self.effect_capture_step
                # Reuse the established capture step, including its normal
                # KitScreenshotObserver, busy checks, timeout and cleanup.
                # No observer bytecode/global policy is cloned or patched.
                attempting = capture_step.capture is None and not capture_step.busy()
                if attempting and 'actual_request_elapsed' not in self.effect_frame:
                    requested = time.monotonic()
                    previous = next((r for r in reversed(self.effect_frames)
                                     if 'actual_request_monotonic_seconds' in r), None)
                    self.effect_frame.update(actual_request_elapsed=requested-self.effect_created,
                        actual_request_monotonic_seconds=requested,
                        actual_request_unix_seconds=time.time(),
                        actual_request_gap_seconds=(None if previous is None else
                            requested-previous['actual_request_monotonic_seconds']))
                await self.poll_established_capture(capture_step)
                if capture_step.done:
                    row = capture_step.results[-1]
                    self.results.extend(capture_step.results)
                    self.effect_frame.update(row,
                        status='OBSERVED' if row.get('status') == 'OBSERVED' else 'UNKNOWN',
                        completed_elapsed=time.monotonic()-self.effect_created,
                        completed_monotonic_seconds=time.monotonic(),
                        completed_unix_seconds=time.time(),
                        serial_slot_released=self.consumer._readonly_pending is None)
                    if row.get('status') == 'OBSERVED':
                        try:
                            self.effect_frame['crops'] = self.effect_crops(Path(row['png']))
                        except Exception as error:
                            self.effect_error('capture-crops', error)
                    self.effect_frames.append(self.effect_frame)
                    self.effect_capture_step = None
                    if not self.effect_frame['serial_slot_released']:
                        # Keep observing the real potion/queue after timeout;
                        # a retained reservation simply blocks new captures.
                        self.effect_frame['reason'] = 'CAPTURE_SERIAL_SLOT_NOT_RELEASED'
                    if row.get('status') == 'OBSERVED' and self.effect_trigger is None:
                        await self.lower_effect_hp()
                        self.effect_next = self.effect_started
            now = time.monotonic()
            if (self.effect_terminal or self.effect_started is not None
                    and now-self.effect_started >= self.effect_duration
                    or self.effect_started is None and now-self.effect_created >= 90):
                if self.effect_capture_step is not None:
                    self.effect_frame.update(status='UNKNOWN', reason='WINDOW_ENDED_CAPTURE_INCOMPLETE',
                        completed_elapsed=now-self.effect_created)
                    self.effect_frames.append(self.effect_frame)
                self.finish(self.effect_summary())
                return
            if self.effect_capture_step is not None or now < self.effect_next or self.busy():
                return
            # Retain the requested .25s schedule, skip missed slots, and report
            # actual request timestamps. Native capture latency can be longer.
            origin = self.effect_started if self.effect_started is not None else self.effect_capture_started
            slot = int((now-origin)/self.effect_interval)
            due = origin + slot*self.effect_interval
            self.effect_next = due+self.effect_interval
            self.effect_frame = dict(slot=slot, requested_elapsed=due-self.effect_created,
                lateness_seconds=now-due, harness_stage=self.scenario.stage, state_at_request=state,
                capture_route='ESTABLISHED_KIND_CAPTURE_STEP')
            name = 'potion-effect-%03d' % (len(self.effect_frames)+1)
            self.effect_capture_step = EstablishedCaptureSteps(self.manual, self.directory, (('capture', name),))
            self.effect_capture_step.scenario = self.scenario
        except Exception as error:
            self.effect_error('early-poll', error)
            if self.effect_trigger is not None:
                self.effect_terminal = True  # preserve partial mutation/save, never retry it
            if self.capture is not None:
                self.capture.close()
                self.capture = None
                self.effect_terminal = True
            if self.effect_terminal or time.monotonic()-self.effect_created >= 90:
                self.finish(self.effect_summary())

    async def tick(self):
        if self.potion_effect:
            return await self.effect_tick()
        return await super().tick()

    def close(self):
        if not self.potion_effect:
            return super().close()
        try:
            if (self.effect_capture_step is not None and hasattr(self, 'effect_frame')
                    and self.effect_frame not in self.effect_frames):
                self.effect_frame.update(status='UNKNOWN', reason='CLOSE_WITH_CAPTURE_INCOMPLETE',
                    completed_elapsed=time.monotonic()-self.effect_created)
                self.effect_frames.append(self.effect_frame)
            self.results.append(dict(kind='potion_effect_close_observe', **self.effect_summary()))
            return super().close()
        finally:
            for target, name, original, wrapper, owned, saved in reversed(self.effect_hooks):
                if getattr(target, name) is wrapper:
                    if owned:
                        setattr(target, name, saved)
                    else:
                        delattr(target, name)


module.STEP_SETS['hp_bar'] = (('hp_bar', 'companion-hp-bar'),)


class HpBarSteps(PotionEffectSteps):
    """Development HP projection capture; leave the potion-effect path intact."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hp_bar = any(s[0] == 'hp_bar' for s in self.steps)
        if not self.hp_bar:
            return
        self.effect_created = time.monotonic()
        self.effect_frames, self.effect_errors = [], []
        self.hp_queues, self.hp_mutations, self.hp_hooks = [], [], []
        self.hp_original = None
        self.hp_restore_required = False
        self.hp_restore_result = None
        self.hp_suppress_potion = False
        self.hp_phase, self.hp_phase_started = 'baseline', None
        self.hp_capture = None
        self.hp_next = None
        self.hp_interval = .25
        self.hp_baseline_timeout = 30.0
        self.install_hp_observers()

    def hp_stamp(self):
        now = time.monotonic()
        return dict(monotonic_seconds=now, unix_seconds=time.time(),
                    elapsed=now-self.effect_created)

    def install_hp_observers(self):
        from tools.local_original_session import launcher, world_companion_inventory
        world = self.manual.inventory_broker._world
        original_queue = world._queue
        owned = '_queue' in vars(world)
        saved = vars(world).get('_queue')

        def queue(recipient, frame):
            before = len(world.outbox.get(recipient, ()))
            result = original_queue(recipient, frame)
            stamp = self.hp_stamp()
            try:
                if len(frame) >= 6 and int.from_bytes(frame[2:4], 'little') == 0x08a3:
                    from tools.local_entry_server import protobuf as pb
                    if int.from_bytes(frame[:2], 'little') != len(frame) or frame[-2:] != b'\0\0':
                        raise ValueError('HP_STATUS_FRAME_ENVELOPE_UNKNOWN')
                    statuses = []
                    with pb.parse_message(frame[4:-2]) as body:
                        for nested in body.occurrences(1):
                            if nested.wire_type != 2:
                                raise ValueError('HP_STATUS_MEMBER_WIRE_UNKNOWN')
                            with pb.parse_message(nested.value) as member:
                                fields = [member.occurrences(i) for i in (1, 3, 4)]
                                if (any(len(v) != 1 for v in fields)
                                        or [v[0].wire_type for v in fields] != [2, 0, 0]):
                                    raise ValueError('HP_STATUS_MEMBER_FIELDS_UNKNOWN')
                                statuses.append(dict(name=bytes(fields[0][0].value).decode('utf-8'),
                                    hp_percent=fields[1][0].value, mp_percent=fields[2][0].value))
                    queued = world.outbox.get(recipient, ())
                    self.hp_queues.append(dict(stamp, opcode='0x08A3', recipient_uid=recipient,
                        phase=self.hp_phase, statuses=statuses, source_world_identity=id(world),
                        actual_append=len(queued) == before+1 and queued[-1] is frame,
                        scope='ACTUAL_WORLD_OUTBOX_APPEND_ONLY'))
                    del self.hp_queues[:-128]
            except Exception as error:
                self.effect_error('hp-queue-observation', error)
            return result

        world._queue = queue
        self.hp_hooks.append((world, '_queue', queue, owned, saved))
        cls = world_companion_inventory.CompanionInventory
        original_potion = cls.potion

        def potion(service, actor, now):
            original = self.hp_original
            if (self.hp_suppress_potion and original is not None
                    and service.ctx.world is world and actor is original['actor_object']):
                return False
            return original_potion(service, actor, now)

        cls.potion = potion
        self.hp_hooks.append((cls, 'potion', potion, True, original_potion))
        original_poll = launcher.ProductFeatures.poll

        async def poll(features, *args, **kwargs):
            row = await original_poll(features, *args, **kwargs)
            if getattr(features, 'manual', None) is self.manual and not self.done:
                await self.hp_tick()
            return row

        launcher.ProductFeatures.poll = poll
        self.hp_hooks.append((launcher.ProductFeatures, 'poll', poll, True, original_poll))

    def hp_change(self, restore=False, reason='capture-phase'):
        broker = self.manual.inventory_broker
        world = broker._world
        row = dict(self.hp_stamp(), operation='restore' if restore else 'lower', reason=reason,
                   status='UNKNOWN', product_save_returned=False)
        self.hp_mutations.append(row)
        if restore:
            if not self.hp_restore_required:
                return
            original = self.hp_original
            actor = original['actor_object']
            # Do not mutate a replacement actor/record belonging to another lifetime.
            if (world.companions.records.get(actor.character_id) is not original['record_object']
                    or world.companions.active.get(actor.character_id) is not actor
                    or not actor.record.alive or world.entities.resolve(actor.ref) is None
                    or actor.character_id in world.combat.pcs):
                raise ValueError('HP_RESTORE_ORIGINAL_COMPANION_LIFETIME_NOT_CURRENT')
            target = original['hp']
        else:
            actors = list(world.companions.active.values())
            if len(actors) != 1:
                raise ValueError('HP_BAR_ACTIVE_COMPANION_NOT_UNIQUE')
            actor = actors[0]
            before = self.effect_state(actor)
            if (not before['alive'] or not before['current_entity'] or not before['owner_alive']
                    or actor.character_id in world.combat.pcs
                    or broker._companion_party is None or broker._companion_store is None):
                raise ValueError('HP_BAR_LIVING_AUTONOMOUS_COMPANION_PRODUCT_AUTHORITY_REQUIRED')
            target = max(1, actor.record.max_hp*30//100)
            if actor.record.hp <= target:
                raise ValueError('HP_BAR_INITIAL_HP_NOT_ABOVE_30_PERCENT')
            self.hp_original = dict(actor_object=actor, record_object=actor.record,
                hp=actor.record.hp, max_hp=actor.record.max_hp, member=actor.character_id,
                actor=actor.ref.uid, owner_uid=actor.owner_ref.uid,
                name=broker._companion_rows[actor.character_id]['name'])
            self.hp_suppress_potion = True
        row.update(before=self.effect_state(actor), target_hp=target,
            target_percent=broker._companion_party.percent(target, actor.record.max_hp))
        # Claim before mutation/save: a save exception still requires restoration.
        self.hp_restore_required = True
        self.hp_phase = 'restored' if restore else 'low'
        self.hp_phase_started = time.monotonic()
        row.update(mutation_monotonic_seconds=self.hp_phase_started,
                   mutation_unix_seconds=time.time(), status='MUTATED_SAVE_UNCONFIRMED')
        actor.record.hp = target
        broker._companion_save(actor.owner_ref.uid)
        row.update(after=self.effect_state(actor), product_save_returned=True,
            completed=self.hp_stamp(), party_sync_route='_companion_save -> _companion_party.sync')
        if actor.record.hp != target:
            raise ValueError('HP_BAR_PRODUCT_SAVE_OVERWROTE_TARGET')
        row['status'] = 'OBSERVED'
        if restore:
            self.hp_restore_required = False
            self.hp_restore_result = row

    async def hp_restore(self, reason):
        if self.hp_restore_required:
            await self.manual.inventory_broker._world.runtime.dispatch_now(
                self.hp_change, True, reason)

    def hp_summary(self):
        original = self.hp_original
        frames = [r for r in self.effect_frames if r.get('status') == 'OBSERVED']
        queues = [q for q in self.hp_queues if q['actual_append'] and original is not None
                  and q['recipient_uid'] == original['owner_uid']
                  and any(r['name'] == original['name'] for r in q['statuses'])]
        changes = {r['operation']: r for r in self.hp_mutations if r.get('status') == 'OBSERVED'}
        def queued(phase, operation):
            change = changes.get(operation)
            return change is not None and any(q['phase'] == phase
                and q['monotonic_seconds'] >= change['mutation_monotonic_seconds']
                and any(r['name'] == original['name'] and r['hp_percent'] == change['target_percent']
                        for r in q['statuses']) for q in queues)
        low = queued('low', 'lower')
        restored = queued('restored', 'restore')
        def captured(phase):
            change = changes.get('lower' if phase == 'low' else 'restore')
            return change is not None and any(
                r.get('phase_at_request') == phase and r.get('phase_at_completion') == phase
                and r.get('state_at_request', {}).get('hp') == change['target_hp']
                and r.get('state_at_completion', {}).get('hp') == change['target_hp'] for r in frames)
        ok = (low and restored and self.hp_restore_result is not None
              and captured('low') and captured('restored'))
        return dict(status='OBSERVED' if ok else 'UNKNOWN', ui_result='UNKNOWN',
            reason=None if ok else 'HP_MUTATION_QUEUE_OR_PHASE_CAPTURE_NOT_OBSERVED',
            original=None if original is None else {k: v for k, v in original.items() if not k.endswith('_object')},
            mutations=self.hp_mutations, restore_required=self.hp_restore_required,
            restore_result=self.hp_restore_result, queued_statuses=self.hp_queues,
            frames=self.effect_frames, observation_errors=self.effect_errors,
            baseline_capture_wait_timeout_seconds=self.hp_baseline_timeout,
            baseline_capture_wait_basis='FROM_HARNESS_IDLE; HP_MUTATION_REQUIRES_OBSERVED_PNG',
            requested_interval_seconds=self.hp_interval,
            requested_low_window_seconds=3.0, requested_restored_window_seconds=2.0,
            potion_suppression='ONLY_EXACT_COMPANION_INVENTORY_POTION_CALL; ATS_UNCHANGED',
            scope='DEVELOPMENT_HP_RECORD_AND_PRODUCT_SAVE_PARTY_SYNC; PNG_REQUIRES_VISUAL_REVIEW',
            limitations=['250MS_REQUEST_SCHEDULE_DOES_NOT_PROVE_250MS_CAPTURE_CADENCE',
                '08A3_QUEUE_DOES_NOT_PROVE_NATIVE_CONSUMPTION_OR_HP_BAR_PIXELS'])

    async def hp_tick(self):
        if self.done:
            return
        try:
            now = time.monotonic()
            if self.hp_phase_started is None:
                # Same readiness as the successful potion_effect path:
                # harness IDLE, then established capture busy/current checks.
                if self.scenario.stage != 'IDLE':
                    if now-self.effect_created >= 90:
                        self.finish(self.hp_summary())
                    return
                self.hp_phase_started = self.hp_next = now
            duration = (self.hp_baseline_timeout if self.hp_phase == 'baseline' else
                        3 if self.hp_phase == 'low' else 2)
            # Switch at the requested wall-clock boundary, independently of PNG latency.
            if now-self.hp_phase_started >= duration:
                if self.hp_phase == 'baseline':
                    raise ValueError('HP_BAR_BASELINE_CAPTURE_TIMEOUT')
                if self.hp_phase == 'low':
                    await self.hp_restore('three-second-low-window-ended')
                    self.hp_next = self.hp_phase_started
                else:
                    self.hp_suppress_potion = False
                    self.hp_finish_capture('RESTORED_WINDOW_ENDED_CAPTURE_INCOMPLETE')
                    self.finish(self.hp_summary())
                    return
            if self.hp_capture is not None:
                step = self.hp_capture
                attempting = step.capture is None and not step.busy()
                if attempting and 'actual_request_elapsed' not in self.hp_frame:
                    requested = time.monotonic()
                    previous = next((r for r in reversed(self.effect_frames)
                                     if 'actual_request_monotonic_seconds' in r), None)
                    self.hp_frame.update(actual_request_elapsed=requested-self.effect_created,
                        actual_request_monotonic_seconds=requested,
                        actual_request_unix_seconds=time.time(),
                        actual_request_gap_seconds=(None if previous is None else
                            requested-previous['actual_request_monotonic_seconds']),
                        phase_at_request=self.hp_phase, state_at_request=self.effect_state())
                # glfw29 aborted the whole HP scenario on its first current
                # refusal. glfw26 potion_effect had the same first refusal,
                # recorded it, and obtained PNGs from its next scheduled slot.
                await self.poll_established_capture(step)
                if step.done:
                    row = step.results[-1]
                    self.results.extend(step.results)
                    self.hp_frame.update(row, status='OBSERVED' if row.get('status') == 'OBSERVED' else 'UNKNOWN',
                        completed=self.hp_stamp(), phase_at_completion=self.hp_phase,
                        state_at_completion=self.effect_state(),
                        serial_slot_released=self.consumer._readonly_pending is None)
                    if row.get('status') == 'OBSERVED':
                        try:
                            self.hp_frame['crops'] = self.hp_crops(Path(row['png']))
                        except Exception as error:
                            self.effect_error('hp-capture-crops', error)
                    self.effect_frames.append(self.hp_frame)
                    self.hp_capture = None
                    if not self.hp_frame['serial_slot_released']:
                        self.hp_frame['reason'] = 'CAPTURE_SERIAL_SLOT_NOT_RELEASED'
                    if row.get('status') == 'OBSERVED' and self.hp_phase == 'baseline':
                        await self.manual.inventory_broker._world.runtime.dispatch_now(self.hp_change)
                        self.hp_next = self.hp_phase_started
            now = time.monotonic()
            if self.hp_capture is not None or now < self.hp_next or self.busy():
                return
            slot = int((now-self.hp_phase_started)/self.hp_interval)
            due = self.hp_phase_started+slot*self.hp_interval
            self.hp_next = due+self.hp_interval
            self.hp_frame = dict(phase=self.hp_phase, slot=slot, requested_elapsed=due-self.effect_created,
                lateness_seconds=now-due, harness_stage=self.scenario.stage,
                state_at_request=self.effect_state(), capture_route='ESTABLISHED_KIND_CAPTURE_STEP')
            name = 'hp-bar-%s-%03d' % (self.hp_phase, len(self.effect_frames)+1)
            self.hp_capture = EstablishedCaptureSteps(self.manual, self.directory, (('capture', name),))
            self.hp_capture.scenario = self.scenario
        except Exception as error:
            self.effect_error('hp-bar-poll', error)
            try:
                await self.hp_restore('abnormal-capture-or-mutation')
            except Exception as cleanup:
                self.effect_error('hp-bar-restore', cleanup)
            self.hp_suppress_potion = self.hp_restore_required
            self.hp_finish_capture('ABNORMAL_HP_BAR_CAPTURE')
            self.finish(self.hp_summary())

    def hp_crops(self, destination):
        crops = self.effect_crops(destination)
        from PIL import Image
        # glfw26's full party panel spans x45..470/y575..865 at
        # 2880x2160; include both SoloKnight and the lower SoloMage row.
        with Image.open(destination) as image:
            width, height = image.size
            box = [0, round(height*.25), round(width*.1875), round(height*(5/12))]
            path = destination.with_name(destination.stem+'-party-window-full.png')
            image.crop(box).save(path)
            crops['party-window-full'] = dict(png=str(path), box=box,
                basis='GLFW26_FULL_PARTY_WINDOW_WITH_BOTH_ROWS; PIXELS_REQUIRE_REVIEW')
        return crops

    def hp_finish_capture(self, reason):
        if self.hp_capture is not None:
            if self.hp_capture.capture is not None:
                self.hp_capture.capture.close()
                self.hp_capture.capture = None
            self.capture = None
            self.hp_frame.update(status='UNKNOWN', reason=reason, completed=self.hp_stamp())
            self.effect_frames.append(self.hp_frame)
            self.hp_capture = None

    async def tick(self):
        if self.hp_bar:
            return await self.hp_tick()
        return await super().tick()

    def close(self):
        if not self.hp_bar:
            return super().close()
        try:
            try:
                if self.hp_restore_required:
                    # close() is synchronous on this asyncio thread: no tick can
                    # interleave here. Never cross an already-held runtime lock.
                    world = self.manual.inventory_broker._world
                    if world.runtime.lock.locked():
                        raise ValueError('HP_BAR_CLOSE_RUNTIME_LOCK_HELD_RESTORE_UNCONFIRMED')
                    self.hp_change(True, 'synchronous-close-before-owner-cleanup')
            except Exception as error:
                self.effect_error('hp-bar-close-restore', error)
            self.hp_finish_capture('CLOSE_WITH_HP_BAR_CAPTURE_INCOMPLETE')
            self.results.append(dict(kind='hp_bar_close_observe', **self.hp_summary()))
            return super().close()
        finally:
            self.hp_suppress_potion = False
            for target, name, wrapper, owned, saved in reversed(self.hp_hooks):
                if getattr(target, name) is wrapper:
                    if owned:
                        setattr(target, name, saved)
                    else:
                        delattr(target, name)


# Exploration only: no item selection, purchase, inventory mutation or movement
# command. Dorin uses a separate copied start because no safe route from
# Pandora has been established. The wrapper changes only that copy's position.
# Four tiles west: S32 mask1 can_stand/north_step are True at both starts;
# east_step is True through the three cells leading to each old adjacent start.
# Sources: map/0/7ffe8002.s32 (Pandora), map/0/7ffc8002.s32 (Dorin), via
# world_terrain.py. Static mask1 excludes doors and dynamic actor occupancy.
# A normal adjacent companion stays near the knight, away from the NPC to its
# east. No unobserved wait command or companion relocation is injected.
SHOP_PROBES = dict(shop_probe=dict(npc_id=70014, name='Pandora', start=[0, 32641, 32951],
                                  reference_body=[1530, 750]),
                   shop_probe_dorin=dict(npc_id=60001, name='Dorin', start=[0, 32571, 32946],
                                        reference_body=[1530, 775]))
SHOP_PROBES['shop_trade'] = dict(SHOP_PROBES['shop_probe'], trade='shop')
SHOP_PROBES['warehouse_trade'] = dict(SHOP_PROBES['shop_probe_dorin'], trade='warehouse')


def world_grid_to_capture(capture, player, target, scene_size, probe, candidate=0):
    """Probe-only body projection calibrated from the *before-click* GLFW56 PNGs.

    The 2880px PNG is a crop of a 3840px drawable, not a 3840px-wide PNG.
    Nor does scene_size alone establish the live world-camera scale: Pandora
    (32645,32951) and Cole (32635,32951) are about (1530,825)/(630,1275)
    at their feet. Ten grid-X tiles therefore span (+900,-450) capture px,
    or (+90,-45) per tile. Original Coordinate's (+48,+24)/(+48,-24)
    bottom-up basis supplies the axes; the measured top-down scale is 1.875.
    The body centers are read separately from the same BEFORE images. The
    AFTER image has a moved player/camera and must not calibrate this start.

    Reference player->NPC delta is (+1,0). With the copied start four west,
    delta becomes (+4,0), giving Pandora (1800,615), Dorin (1800,640).
    This remains an empirical same-layout inference, not a native camera or
    actor-hitbox proof. capture_to_client performs the crop conversion once.
    """
    require_capture_geometry(capture)
    if list(scene_size) != [1280.0, 960.0]:
        raise ValueError('SHOP_BEFORE_IMAGE_CALIBRATION_GEOMETRY_CHANGED')
    if player['map_id'] != target['map_id']:
        raise ValueError('SHOP_PROJECTION_SAME_MAP_REQUIRED')
    dx = target['grid'][0] - player['grid'][0] - 1
    dy = target['grid'][1] - player['grid'][1]
    # Preserve the three existing body candidates inside the approved equation.
    # Callers select a candidate; they never add scenario-specific corrections.
    if type(candidate) is not int or not 0 <= candidate < 3:
        raise ValueError('WORLD_BODY_CANDIDATE_REQUIRED')
    offset = ((0, 0), (0, -12), (0, 12))[candidate]
    x, y = probe['reference_body']
    point = [round(x + 90*(dx+dy) + offset[0]),
             round(y - 45*(dx-dy) + offset[1])]
    return point, dict(
        coordinate_basis='world_grid_to_capture',
        source='runs/glfw56-shop_probe-claude-20261030-1/before-shop-npc-candidate-0.png; '
               'runs/glfw56-shop_probe_dorin-claude-20261030-1/before-shop-npc-candidate-0.png; '
               'work/source_play_slice/rules/projection-oracle.tsv',
        calibration_png_size=[2880, 2160], reference_player_to_npc_grid=[1, 0],
        reference_body_capture=probe['reference_body'],
        tile_basis_capture=[[90, -45], [90, 45]],
        calibration_pandora_cole_grid_delta=[10, 0],
        calibration_pandora_cole_feet_capture=[[1530, 825], [630, 1275]],
        original_tile_to_capture_scale=1.875,
        body_capture_offset=list(offset), player=player, target=target,
        scene_size=list(scene_size), drawable_to_capture='CROP; NO_PNG_WIDTH_STRETCH',
        limitation='EMPIRICAL_SAME_LAYOUT_CAMERA_AND_SPRITE_BODY; LIVE_HITBOX_UNVERIFIED',
        ui_result='UNKNOWN', formal_pass=False)


for _probe_name in SHOP_PROBES:
    module.STEP_SETS[_probe_name] = (
        ('capture', 'shop-land-entry'), ('shop_probe_prepare', 'shop-probe-prepare'),
        ('capture', 'before-shop-npc-candidate-0'),
        # Presence also selects PrivateSteps' geometry-aware capture path.
        ('private_input', 'shop-npc-candidate-0', dict(
            schema='local-original-input-request-v1', action='left_click',
            expected_scene='Land', locator='shop_probe.npc', candidate=0)),
        ('wait', 'shop-npc-candidate-0-settle', 2),
        ('capture', 'shop-npc-candidate-0-after'),
        ('shop_probe_observe', 'shop-npc-candidate-0-tree', 'npc', 0))


class ShopProbeSteps(HpBarSteps):
    """Bounded native-click exploration, with each next click observation-gated."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.shop_probe = SHOP_PROBES.get(_selected_steps)
        self.shop_blocked = None
        self.shop_sequence = 0

    def shop_write(self, name, value):
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / (name + '.json')
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
        return str(path)

    def shop_server(self):
        current, _ = module.current_kit(self.manual)
        broker, row, selected = current[0].broker, current[1], current[3]
        position = broker.realm.service(current[0].writer).snapshot()
        if position.uid != selected.uid:
            raise ValueError('SHOP_SELECTED_OWNER_CHANGED')
        world, bindings = broker._world, broker._world_handler_bindings
        nearby = []
        for entity in world.entities.near(position.map_id, position.word0, position.word1, 18):
            npc = bindings.town.npc_for(entity.uid) if bindings.town else None
            nearby.append(dict(uid=entity.uid, generation=entity.generation,
                kind=entity.kind.value, map_id=entity.map_id, grid=[entity.x, entity.y],
                alive=entity.alive, template_id=entity.template_id,
                npc_id=npc.npc_id if npc else None,
                name=npc.row.get('l1j_name') if npc else None))
        slot = row.get('_world_handler_state')
        state = slot[1] if slot else None
        menu, window = getattr(state, 'menu', None), getattr(state, 'window', None)
        warehouse = row.get('_world_warehouse_window')
        row_bindings = []
        if window:
            offers = bindings.town.data.shops.offers
            for key, value in window.rows.items():
                offer = offers.get(value) if window.mode == 5 else None
                row_bindings.append(dict(row_key=key, value=value,
                    offer=(dict(key=offer.key, item_id=offer.classic_item_id,
                        name=offer.name_ko, price=offer.selling_price,
                        pack_count=offer.pack_count) if offer else None)))
        wire_rows = ([dict(r.fields) for r in dict(window.value.fields).get(3, ())]
                     if window else [])
        return dict(position=dict(uid=position.uid, map_id=position.map_id,
                                  grid=[position.word0, position.word1]), nearby_actors=nearby,
            menu_target=menu.fields.get(1) if menu else None,
            shop_mode=window.mode if window else None,
            shop_row_count=len(window.rows) if window else None,
            shop_rows=list(window.rows) if window else None,
            shop_row_bindings=row_bindings,
            shop_wire_rows=[dict(row_key=r[1] & 0xffffffff,
                                item_id=r.get(2) if window.mode == 5 else None,
                                price=r.get(4) if window.mode == 5 else r.get(2)) for r in wire_rows],
            warehouse_window=(dict(direction=warehouse['direction'], mode=warehouse['mode'],
                context=warehouse['context'], rows=dict(warehouse['rows'])) if warehouse else None),
            warehouse_results=list(getattr(broker, '_world_warehouse_results', ())),
            server_errors=list(getattr(broker, '_world_handler_errors', ())))

    def shop_assets(self):
        """Read the existing current kit and copied saved sidecars; never write them."""
        from tools.local_original_session import inventory
        current, _ = module.current_kit(self.manual)
        broker, selected = current[0].broker, current[3]
        result = dict(status='UNKNOWN', uid=selected.uid, saved={})
        def summary(frame):
            rows = inventory.validate_kit_frame(frame) if frame else ()
            return dict(row_count=len(rows), adena=sum(dict(r.raw_fields)[4]
                for r in rows if r.template_bits == 7),
                items=[dict(uid=r.identifier, item_id=r.template_bits,
                            quantity=dict(r.raw_fields)[4]) for r in rows])
        try:
            result['current_inventory'] = summary(broker._inventory_current_frame)
            result['current_warehouse'] = summary(
                broker._world_inventory_transactions.restore_warehouse(selected.uid))
            profile = Path(broker._inventory_store.profile)
            for name in ('inventory.json', 'warehouse.json'):
                path = profile.with_name(name)
                if not path.exists():
                    result['saved'][name] = dict(path=str(path), exists=False,
                        **(summary(None) if name == 'warehouse.json' else dict(status='UNKNOWN')))
                    continue
                with path.open('rb') as stream:
                    raw = stream.read(2_000_001)
                if len(raw) > 2_000_000:
                    raise ValueError('SHOP_SAVED_ASSET_SIZE_BOUND')
                data = json.loads(raw)
                matches = [r for r in data['inventories'] if r['uid'] == selected.uid]
                if len(matches) > 1:
                    raise ValueError('SHOP_SAVED_ASSET_OWNER_NOT_UNIQUE')
                result['saved'][name] = dict(path=str(path), exists=True,
                    **summary(bytes.fromhex(matches[0]['frame']) if matches else None))
            policy = getattr(broker, '_world_services', None)
            result['warehouse_policy'] = dict(limit=getattr(policy, 'warehouse_slots', None),
                withdrawal_fee=getattr(policy, 'withdrawal_fee', None),
                minimum_level=getattr(policy, 'minimum_level', None))
            result['status'] = 'OBSERVED'
        except Exception as error:
            result['reason'] = str(error)[:240]
        return result

    def shop_client_actors(self, server):
        # Existing source-bound three-vector lookup + Transform grid reader.
        # These are client grid observations, never measured screen positions.
        from tools.local_original_session import edge, npc_observe
        reader = self.manual.consumer.reader
        proof = edge.EdgeAdapter(reader)
        native, sampler = proof._binding()
        monster, common, inherited = npc_observe._source()
        player, _, _ = npc_observe._source('MyPlayer')
        npc_observe._registry_lookup_source()
        checks = inherited + proof.public['Position']['source_checks'] + proof.lookup_contract['code_checks']
        checks = list({(c['rva'], c['length'], c['sha256']): c for c in checks}.values())
        budget = npc_observe._ObservationBudget(native, sampler)
        rows, counts = [], []
        known = {r['uid'] for r in server['nearby_actors']}
        p = server['position']
        try:
            with budget.installed():
                proof._code(sampler, budget, checks)
                reads, actors, _, route, state, raw, _ = edge._world(
                    native, sampler, proof.public, proof.world, proof.position_source,
                    p['uid'], p['map_id'], tuple(p['grid']), require_current_start=True)
                for offset in (0x8a8, 0x8c0, 0x8d8):
                    begin, count = proof.world.vector(reads, actors, offset, offset + 8,
                                                     proof.public['Player']['max_actor_elements'])
                    counts.append(count)
                    for index in range(count):
                        obj = reads.pair(reads.read(begin + index * 16, 16))[0]
                        vp = reads.pointer(obj)
                        if not sampler.g['base'] <= vp <= sampler.g['base'] + sampler.g['size'] - 16:
                            raise ValueError('SHOP_ACTOR_VTABLE_OUTSIDE_IMAGE')
                        getter = int.from_bytes(sampler.read(vp + 8, 8, image=True), 'little')
                        if getter != sampler.g['base'] + common['ID_getter_RVA']:
                            raise ValueError('SHOP_ACTOR_UID_GETTER_UNSUPPORTED')
                        uid = int.from_bytes(reads.read(obj + common['Actor_ID_u64_offset'], 8), 'little')
                        if uid not in known:
                            continue
                        record = dict(uid=uid, vector_offset=offset, type_rva=vp - sampler.g['base'])
                        contract = next((t for t in (monster, player)
                                         if vp == sampler.g['base'] + t['rva']), None)
                        if contract is None:
                            rows.append(dict(record, status='UNKNOWN', reason='SHOP_ACTOR_TYPE_NOT_SUPPORTED'))
                            continue
                        proof.nav._source_type(reads, sampler, obj, contract, proof.world)
                        if reads.pointer(obj + common['Actor_self_pointer_offset']) != obj:
                            raise ValueError('SHOP_ACTOR_SELF_CHANGED')
                        segment, grid, reason = proof.world.position(
                            sampler, reads, obj, proof.public, proof.position_source)
                        if reason or grid is None or segment != [(v >> 6) + 0x7e00 for v in grid]:
                            raise ValueError(reason or 'SHOP_ACTOR_GRID_INVALID')
                        rows.append(dict(record, status='OBSERVED', map_id=p['map_id'], grid=grid))
                budget.verify()
                if sampler.read(state + 0x360, 36) != raw or sampler.route() != route:
                    raise ValueError('SHOP_ACTOR_SCENE_CHANGED')
                proof._code(sampler, budget, checks)
            reader.validate()
            if self.shop_server() != server:
                raise ValueError('SHOP_SERVER_CHANGED_DURING_ACTOR_READ')
            return dict(status='OBSERVED', actors=rows, vector_counts=counts,
                        typed_bytes_requested=budget.spent, snapshot_atomic=False,
                        screen_projection='UNKNOWN; CLIENT_GRID_ONLY')
        except Exception as error:
            return dict(status='UNKNOWN', reason=str(error)[:240], partial_actors=rows,
                        vector_counts=counts, typed_bytes_requested=budget.spent)

    def shop_tree(self, label, *, owned_layout=None, trigger=None):
        result = dict(status='UNKNOWN', capture=getattr(self, 'last_capture_context', None), layouts=[])
        if trigger is not None:
            result['trigger'] = trigger
        try:
            ui = MemoryUi(self)
            total = 0
            layouts = [owned_layout] if owned_layout is not None else dict.fromkeys(ui.layouts())
            for layout in layouts:
                original_spell = (owned_layout is not None
                                  and ui.ptr(layout) == ui.base + 0x12341c8)
                root = ui.ptr(layout + 0x30)
                if not root:
                    continue
                shown = ui.shown(root)
                tree = dict(layout=layout, root=root, name=ui.string(root + 0x1a8), shown=shown, nodes=[])
                result['layouts'].append(tree)
                pending, seen = ([(root, '', None, 0, 'layout_root')]
                                 if shown or owned_layout is not None else []), set()
                while pending:
                    node, parent_path, parent, child_index, parent_link = pending.pop()
                    if node in seen:
                        if owned_layout is not None:
                            continue  # An explicit ListView inner edge may also be a normal child.
                        raise ValueError('SHOP_UI_TREE_BOUND_OR_CYCLE')
                    if (len(seen) >= (4096 if owned_layout is not None else 512)
                            or total >= (4096 if owned_layout is not None else 2048)):
                        raise ValueError('SHOP_UI_TREE_BOUND_OR_CYCLE')
                    seen.add(node); total += 1
                    name = ui.string(node + 0x1a8)
                    path = parent_path + '.' + name if parent_path else name
                    children = ui.spell_children(node) if original_spell else ui.children(node)
                    entry = dict(node=node, path=path, name=name, shown=ui.shown(node),
                        position=list(ui.vec(node + 0x3c)), size=list(ui.vec(node + 0x6c)))
                    if owned_layout is not None:
                        entry.update(parent=parent, child_index=child_index, children=children,
                                     parent_link=parent_link,
                                     vptr=ui.ptr(node), vptr_rva=ui.ptr(node)-ui.base,
                                     class_name='UNKNOWN', scene_bounds=None)
                        try:
                            # Reuse the established window node_point transform;
                            # zero-size and hidden nodes retain an explicit gap.
                            _, facts = ui.node_point(node, 'companion_ats.buff_spell', layout,
                                                     require_capture=False)
                            entry['scene_bounds'] = facts['scene_bounds']
                        except Exception as error:
                            entry['scene_bounds_reason'] = str(error)[:160]
                        if (tree['name'] in ('NpcShopLayout', 'StorageLayout')
                                and name == 'ItemSlot' and entry['vptr_rva'] == 0x1232f30):
                            # Existing SlotNode payload contract (MemoryUi.slot),
                            # not list order: equipped items are filtered by the client.
                            metadata = ui.ptr(node + 0x808)
                            entry['item_uid'] = ui.ptr(metadata) if metadata else None
                    tree['nodes'].append(entry)
                    walk = [(child, path, node, index, 'child_vector')
                            for index, child in enumerate(children)]
                    if owned_layout is not None and name in ('ListView_Slot', 'ListView'):
                        # DLL AttachPanel uses ListView+CE0. Preserve this edge
                        # separately when Cocos' child vector omits the inner.
                        inner = ui.ptr(node + 0xce0)
                        if inner and inner not in children and ui.descendant(inner, root):
                            entry['list_inner_ce0'] = inner
                            walk.append((inner, path, node, None, 'list_inner_ce0'))
                    pending.extend(reversed(walk))
            ui.validate()
            result.update(status='OBSERVED', node_count=total,
                          scope=('OWNED_LAYOUT_FULL_TREE_NODE_VPTR_CHILD_ORDER_AND_EXISTING_SCENE_BOUNDS'
                                 if owned_layout is not None else 'BOUNDED_REGISTERED_LAYOUT_NODE_NAMES_AND_GEOMETRY'),
                          text_content='UNKNOWN; NODE_NAMES_ARE_NOT_RENDERED_DIALOGUE_TEXT')
        except Exception as error:
            result['reason'] = str(error)[:240]
        if owned_layout is None:
            result['server'] = self.shop_server()
            if self.shop_probe.get('trade'):
                result['assets'] = self.shop_assets()
        result['tree_file'] = self.shop_write(label, result)
        self.shop_last_tree = result['tree_file']
        return result

    @staticmethod
    def shop_visible(tree):
        return {r['root'] for r in tree['layouts'] if r['shown']}

    def shop_prepare(self):
        if input_route != 'GLFW_CALLBACK_INJECTION':
            raise ValueError('SHOP_PROBE_REQUIRES_GLFW_CALLBACK_INJECTION')
        server = self.shop_server()
        self.shop_start_server = server
        try:
            client = self.shop_client_actors(server)
        except Exception as error:
            client = dict(status='UNKNOWN', reason=str(error)[:240], actors=[])
        self.shop_write('shop-land-actors', dict(server=server, client=client,
            requested_target=self.shop_probe,
            start_basis='FOUR_TILES_WEST; STATIC_S32_MASK1_STAND_AND_NORTH_STEP_CLEAR',
            safe_movement='UNKNOWN; SEPARATE_COPIED_START; NO_ROUTE_OR_MOVEMENT_COMMAND',
            companion_control='UNCHANGED; WEST_START_SEPARATES_NORMAL_ADJACENT_SPAWN_FROM_NPC'))
        tree = self.shop_tree('shop-land-ui-tree')
        if tree['status'] != 'OBSERVED':
            raise ValueError('SHOP_INITIAL_UI_OBSERVATION_UNKNOWN')
        p = server['position']
        if [p['map_id'], *p['grid']] != self.shop_probe['start']:
            raise ValueError('SHOP_COPIED_START_POSITION_NOT_OBSERVED')
        targets = [r for r in server['nearby_actors'] if r['npc_id'] == self.shop_probe['npc_id'] and r['alive']]
        if len(targets) != 1:
            raise ValueError('SHOP_TARGET_SERVER_ACTOR_NOT_UNIQUE')
        target = self.shop_target = targets[0]
        matches = [r for r in client.get('actors', ()) if r['uid'] == target['uid'] and r['status'] == 'OBSERVED']
        if len(matches) > 1 or matches and matches[0]['grid'] != target['grid']:
            raise ValueError('SHOP_TARGET_CLIENT_GRID_DUPLICATE_OR_MISMATCH')
        if server['menu_target'] is not None or server['shop_mode'] is not None:
            raise ValueError('SHOP_START_HAS_EXISTING_SERVER_INTERACTION')
        self.shop_initial_tree = tree
        self.shop_baseline_roots = self.shop_visible(tree)
        # Keep all bounded candidates on the observed sprite body. These are
        # capture pixels, not scene units scaled by the full drawable width.
        self.shop_candidate_count = 3
        return dict(status='OBSERVED', actor=target, client_actor=matches[0] if matches else None,
                    client_actor_observation=client['status'],
                    position_basis='CURRENT_SERVER_ENTITY; CLIENT_GRID_WHEN_AVAILABLE',
                    screen_projection='EMPIRICAL_GLFW56_BEFORE_CLICK_BODY; LIVE_HITBOX_UNKNOWN',
                    tree_file=tree['tree_file'], candidate_count=self.shop_candidate_count,
                    ui_result='UNKNOWN', formal_pass=False)

    def shop_action(self, label, locator, action='left_click', **metadata):
        return [('capture', 'before-' + label),
                ('private_input', label, dict(schema='local-original-input-request-v1',
                    action=action, expected_scene='Land', locator=locator, **metadata)),
                ('wait', label + '-settle', 2), ('capture', label + '-after')]

    def shop_require_no_new_server_error(self, server):
        prior = self.shop_start_server['server_errors']
        current = server['server_errors']
        if current == prior:
            return
        # Handler errors are ordered strings. Preserve the first new code as
        # reason and the complete new suffix as evidence, including repeats.
        common = 0
        while common < min(len(prior), len(current)) and prior[common] == current[common]:
            common += 1
        if current[common:]:
            self.shop_new_server_errors = current[common:]
            raise ValueError(self.shop_new_server_errors[0])
        raise ValueError('SHOP_SERVER_ERROR_HISTORY_CHANGED')

    def resolve_request(self, request):
        if not self.shop_probe:
            return super().resolve_request(request)
        locator = request.pop('locator')
        capture = self.last_capture_context
        server = self.shop_server()
        self.shop_require_no_new_server_error(server)
        if server['position']['map_id'] != self.shop_start_server['position']['map_id']:
            raise ValueError('SHOP_PLAYER_MAP_CHANGED')
        target = next((r for r in server['nearby_actors'] if r['uid'] == self.shop_target['uid']), None)
        if target != self.shop_target:
            raise ValueError('SHOP_TARGET_LIFETIME_OR_POSITION_CHANGED')
        ui = MemoryUi(self)
        if locator == 'shop_probe.npc':
            # A miss may move the player. Never project another candidate from
            # a moved camera. A successful talk click may move normally.
            if (not getattr(self, 'shop_reopening', False)
                    and server['position'] != self.shop_start_server['position']):
                raise ValueError('SHOP_PLAYER_MOVED_WITHOUT_DIALOGUE_STOP_NPC_CANDIDATES')
            index = request.pop('candidate')
            director = ui.ptr(ui.base + 0x1807fd8)
            if ui.ptr(director) != ui.base + 0x1237f90:
                raise ValueError('SHOP_DIRECTOR_TYPE_UNKNOWN')
            size = ui.vec(ui.ptr(director + 0x150) + 0x6c)
            point, facts = world_grid_to_capture(capture, server['position'], target,
                                                 size, self.shop_probe, index)
            facts['candidate'] = index
        else:
            binding = self.shop_control
            verified_trade_close = (locator == 'shop_probe.close'
                and getattr(self, 'shop_completed_trades', None)
                and server['menu_target'] is None and server['shop_mode'] is None)
            if server['menu_target'] != self.shop_target['uid'] and not verified_trade_close:
                raise ValueError('SHOP_CURRENT_DIALOGUE_TARGET_REQUIRED')
            # Resolve the same freshly observed live path; do not reuse a raw
            # node pointer from the previous tree or an old capture's point.
            layout = binding['layout']
            if layout not in ui.layouts() or ui.ptr(layout + 0x30) != binding['root']:
                raise ValueError('SHOP_CONTROL_LAYOUT_REPLACED')
            if binding.get('trade_live_node'):
                tree = self.shop_tree('before-' + self.steps[self.index][1] + '-native-tree')
                if binding['operation'] == 'sell':
                    self.shop_sell_geometry(tree, {binding['root']})
                else:
                    self.warehouse_geometry(tree, {binding['root']}, binding['operation'])
                if tree['assets'] != self.shop_trade_assets:
                    raise ValueError('TRADE_ASSETS_CHANGED_BEFORE_NATIVE_INPUT')
                live, row, up, viewport = self.shop_live_row(tree, binding, binding['item_uid'])
                if binding['control'] == 'scroll':
                    node = viewport['node']
                else:
                    self.shop_require_row_visible(row, up, viewport)
                    node = up['node']
                point, facts = ui.node_point(node, 'shop_probe.window_close', layout)
                facts.update(item_uid=binding['item_uid'], control=binding['control'],
                    tree_file=live['tree_file'], row_scene_bounds=row['scene_bounds'],
                    viewport_scene_bounds=viewport['scene_bounds'],
                    identity_basis=binding['identity_basis'])
            elif binding.get('trade_capture_fallback'):
                tree = self.shop_tree('before-' + self.steps[self.index][1] + '-native-tree')
                if binding.get('trade_mode') == 6:
                    self.shop_sell_geometry(tree, {binding['root']})
                else:
                    self.shop_buy_geometry(tree, {binding['root']})
                point = list(binding['point'])
                facts = dict(locator=locator, coordinate_basis='capture_to_client',
                    layout=layout, root=binding['root'], capture_point=point,
                    source=binding['source'], tree_file=tree['tree_file'],
                    conversion='capture_to_client ADDS CROP X=480 ONCE')
            elif binding.get('capture_fallback'):
                # Re-dump/recheck this action's currently visible dialogue,
                # rather than treating a previous PNG as current evidence.
                tree = self.shop_tree('before-' + self.steps[self.index][1] + '-native-tree')
                self.shop_fallback_dialogue(tree, {binding['root']}, binding['control'])
                point = list(binding['point'])
                facts = dict(locator=locator, layout=layout, root=binding['root'],
                    coordinate_basis=binding['coordinate_basis'], source=binding['source'],
                    tree_file=tree['tree_file'], capture_point=point,
                    conversion='capture_to_client ADDS CROP X=480 ONCE',
                    ui_result='UNKNOWN', formal_pass=False)
            else:
                node = ui.path(binding['root'], binding['path'])
                point, facts = ui.node_point(node, 'shop_probe.window_close', layout)
            facts['locator'] = locator
            facts['binding_basis'] = ('CURRENT_DIALOGUE_GEOMETRY_AND_USER_VISUAL_POINT'
                if binding.get('capture_fallback') else
                'CURRENT_SLOTNODE_UID_AND_QUANTITY_NODE_SCENE_BOUNDS'
                if binding.get('trade_live_node') else 'EXACT_VISIBLE_NATIVE_NODE_NAME_IN_NEW_CURRENT_LAYOUT')
            facts['native_action_semantics'] = ('USER_REVIEWED_DIALOGUE_LINK; NEXT_SERVER_AND_UI_OBSERVATION_REQUIRED'
                if binding.get('capture_fallback') else
                'INFERRED_FROM_NODE_NAME; NEXT_SERVER_AND_UI_OBSERVATION_REQUIRED')
        ui.validate()
        if not 0 <= point[0] < capture['png_size'][0] or not 0 <= point[1] < capture['png_size'][1]:
            raise ValueError('SHOP_CANDIDATE_OUTSIDE_CURRENT_CAPTURE')
        self.shop_sequence += 1
        request.update(sequence=self.shop_sequence, x=point[0], y=point[1],
                       coordinate_space='capture', png_size=capture['png_size'])
        return request, facts

    def shop_fallback_dialogue(self, tree, roots, control):
        pandora = self.shop_probe['npc_id'] == 70014 and control in ('buy', 'sell')
        dorin_deposit = self.shop_probe['npc_id'] == 60001 and control in ('deposit', 'retrieve')
        if not (pandora or dorin_deposit):
            raise ValueError('SHOP_DIALOGUE_VISUAL_FALLBACK_NOT_PROVIDED:' + control)
        self.shop_require_no_new_server_error(tree['server'])
        capture = self.last_capture_context
        expected = dict(png_size=[2880, 2160], read_size=[3840, 2160],
                        crop=[480, 0, 2880, 2160], client_rect=[0, 0, 3840, 2160])
        if (tree['status'] != 'OBSERVED'
                or tree['server']['menu_target'] != self.shop_target['uid']
                or tree['server']['shop_mode'] is not None
                or tree['server']['warehouse_window'] is not None
                or any(capture.get(k) != v for k, v in expected.items())):
            raise ValueError('SHOP_DIALOGUE_FALLBACK_CURRENT_MENU_OR_CAPTURE_GEOMETRY_UNKNOWN')
        layouts = [r for r in tree['layouts'] if r['root'] in roots and r['shown']
                   and r['name'] == 'NpcTalkLayout']
        if len(layouts) != 1:
            raise ValueError('SHOP_DIALOGUE_FALLBACK_NATIVE_TALK_LAYOUT_NOT_UNIQUE')
        # User-reviewed GLFW57 Pandora and GLFW59 Dorin dialogue dumps contain
        # generic ListView nodes, with no individual HTML link children.
        expected_nodes = {
            'NpcTalkLayout': ([0.0, 379.0], [450.0, 581.0]),
            'NpcTalkLayout.Root.ListviewScroll.ListView': ([30.0, 40.0], [320.0, 506.0]),
            'NpcTalkLayout.Root.Bt_Close': ([408.0, 563.0], [42.0, 23.0])}
        for path, (position, size) in expected_nodes.items():
            nodes = [n for n in layouts[0]['nodes'] if n['path'] == path and n['shown']]
            if len(nodes) != 1 or nodes[0]['position'] != position or nodes[0]['size'] != size:
                raise ValueError('SHOP_DIALOGUE_FALLBACK_NATIVE_GEOMETRY_CHANGED:' + path)
        if dorin_deposit:
            # Keep Dorin's text/scroll geometry at the reviewed initial menu.
            path = 'NpcTalkLayout.Root.ListviewScroll.Scroll.Bt_Handle'
            handles = [n for n in layouts[0]['nodes'] if n['path'] == path]
            if (len(handles) != 1 or handles[0]['shown']
                    or handles[0]['position'] != [7.0, 290.0]
                    or handles[0]['size'] != [20.0, 76.0]):
                raise ValueError('SHOP_DIALOGUE_FALLBACK_NATIVE_GEOMETRY_CHANGED:' + path)
        return layouts[0]

    def shop_bind_control(self, tree, roots, control):
        names = {
            'buy': {'buy', 'Buy', 'Bt_Buy', 'Btn_Buy', 'Button_Buy'},
            'sell': {'sell', 'Sell', 'Bt_Sell', 'Btn_Sell', 'Button_Sell'},
            'deposit': {'deposit', 'Deposit', 'Bt_Deposit', 'Btn_Deposit', 'Button_Deposit'},
            'retrieve': {'retrieve', 'Retrieve', 'Bt_Retrieve', 'Btn_Retrieve', 'Button_Retrieve'},
            'warehouse_confirm': {'Bt_Ok'},
            'close': {'Bt_Close', 'Btn_Close', 'Button_Close', 'Bt_Quit'}}[control]
        found = [dict(layout=layout['layout'], root=layout['root'], path=node['path'])
                 for layout in tree['layouts'] if layout['root'] in roots and layout['shown']
                 for node in layout['nodes'] if node['shown'] and node['name'] in names
                 and all(n > 0 for n in node['size'])]
        if not found and (control in ('buy', 'sell')
                or control in ('deposit', 'retrieve') and self.shop_probe['npc_id'] == 60001):
            layout = self.shop_fallback_dialogue(tree, roots, control)
            dorin = self.shop_probe['npc_id'] == 60001
            self.shop_control = dict(layout=layout['layout'], root=layout['root'],
                control=control, capture_fallback=True,
                # User-provided personal warehouse links, same GLFW85 menu.
                point=([240, 518] if control == 'deposit' else [240, 572]) if dorin
                      else [334, 979] if control == 'buy' else [518, 976],
                coordinate_basis='capture_to_client',
                source=('runs/glfw59-shop_probe_dorin-claude-20261030-1/shop-npc-candidate-0-after.png' if dorin else
                        'runs/glfw57-shop_probe-claude-20261030-1/shop-npc-candidate-0-after.png'))
            return
        if len(found) != 1:
            raise ValueError('SHOP_VISIBLE_' + control.upper() + '_NODE_NOT_UNIQUE_OR_UNKNOWN')
        self.shop_control = found[0]

    def shop_observe(self, label, phase, candidate=None):
        tree = self.shop_tree(label)
        server = tree['server']
        if self.shop_blocked:
            return dict(status='UNKNOWN', reason='SHOP_FAILED_PREREQUISITE',
                        prerequisite=self.shop_blocked, tree_file=tree['tree_file'], formal_pass=False)
        self.shop_require_no_new_server_error(server)
        if tree['status'] != 'OBSERVED':
            raise ValueError('SHOP_UI_TREE_INCOMPLETE_STOP_CLICK_PROGRESSION')
        if server['position']['map_id'] != self.shop_start_server['position']['map_id']:
            raise ValueError('SHOP_PLAYER_MAP_CHANGED')
        roots = self.shop_visible(tree) - self.shop_baseline_roots
        inserts = []
        if phase == 'npc':
            talks = {r['root'] for r in tree['layouts'] if r['shown']
                     and r['name'] == 'NpcTalkLayout' and r['root'] in roots}
            if server['menu_target'] == self.shop_target['uid'] and talks:
                self.shop_dialogue_roots = talks
                self.shop_dialogue_tree = tree
                if self.shop_probe['npc_id'] == 60001:
                    control = getattr(self, 'shop_next_menu', 'deposit')
                    label, next_phase = 'warehouse-' + control + '-menu', control
                else:
                    control = getattr(self, 'shop_next_menu', 'buy')
                    label, next_phase = 'shop-' + control + '-menu', control
                inserts = [('shop_probe_bind', label + '-binding', control, 'dialogue')]
                inserts += self.shop_action(label, 'shop_probe.' + control)
                inserts += [('shop_probe_observe', label + '-tree', next_phase)]
                observation = 'CURRENT_TARGET_MENU_AND_SHOWN_NATIVE_NPC_TALK; APPROACH_MOVEMENT_ALLOWED'
            elif server['menu_target'] is None and not roots and server['shop_mode'] is None:
                if server['position'] != self.shop_start_server['position']:
                    raise ValueError('SHOP_PLAYER_MOVED_WITHOUT_DIALOGUE_STOP_NPC_CANDIDATES')
                if candidate + 1 >= self.shop_candidate_count:
                    raise ValueError('SHOP_BOUNDED_NPC_CANDIDATES_EXHAUSTED_NO_DIALOGUE_OBSERVED')
                next_candidate = candidate + 1
                label = 'shop-npc-candidate-' + str(next_candidate)
                inserts = self.shop_action(label, 'shop_probe.npc', candidate=next_candidate)
                inserts += [('shop_probe_observe', label + '-tree', 'npc', next_candidate)]
                observation = 'NO_NEW_LAYOUT_OR_SERVER_MENU; PLAYER_AND_TARGET_UNCHANGED'
            else:
                raise ValueError('SHOP_DIALOGUE_SERVER_UI_DISAGREEMENT_OR_TARGET_UNKNOWN')
        elif phase in ('buy', 'sell', 'deposit', 'retrieve'):
            shop_roots = self.shop_visible(tree) - self.shop_visible(self.shop_dialogue_tree)
            if server['menu_target'] != self.shop_target['uid'] or not shop_roots:
                raise ValueError('SHOP_TARGET_AND_NEW_NATIVE_WINDOW_NOT_BOTH_OBSERVED')
            if phase == 'buy' and server['shop_mode'] != 5:
                raise ValueError('SHOP_BUY_LIST_NOT_OBSERVED')
            if phase == 'sell' and server['shop_mode'] != 6:
                raise ValueError('SHOP_SELL_LIST_NOT_OBSERVED')
            if phase in ('deposit', 'retrieve') and (not server['warehouse_window']
                    or server['warehouse_window']['direction'] != ('deposit' if phase == 'deposit' else 'withdraw')):
                raise ValueError('WAREHOUSE_' + phase.upper() + '_WINDOW_NOT_OBSERVED')
            self.shop_window_roots = shop_roots
            if self.shop_probe.get('trade'):
                if phase == 'buy':
                    return self.shop_buy_begin(tree, shop_roots)
                if phase == 'sell':
                    return self.shop_sell_begin(tree, shop_roots)
                return self.warehouse_begin(tree, shop_roots, phase)
            inserts = [('shop_probe_bind', 'shop-close-binding', 'close', 'window')]
            inserts += self.shop_action('shop-window-close', 'shop_probe.close')
            inserts += [('shop_probe_observe', 'shop-window-close-tree', 'close')]
            observation = 'SERVER_' + phase.upper() + '_LIST_AND_NEW_SHOWN_NATIVE_WINDOW'
        elif phase == 'sell_scrolled':
            return self.shop_sell_advance(tree)
        elif phase in ('deposit_quantity', 'retrieve_quantity'):
            operation = phase.partition('_')[0]
            layout = self.warehouse_geometry(tree, self.shop_window_roots, operation)
            if tree['assets'] != self.shop_trade_assets:
                raise ValueError('WAREHOUSE_ASSETS_CHANGED_BEFORE_CONFIRM')
            self.shop_bind_control(tree, self.shop_window_roots, 'warehouse_confirm')
            inserts = self.shop_action('warehouse-' + operation + '-confirm', 'shop_probe.warehouse_confirm')
            inserts += [('shop_probe_observe', 'warehouse-' + operation + '-result-tree', operation + '_result')]
            observation = 'ONE_CURRENT_WAREHOUSE_ROW_INCREMENT_POSTED; COMMIT_MUST_PROVE_QUANTITY1'
        elif phase in ('deposit_result', 'retrieve_result'):
            return self.warehouse_result(tree, phase.partition('_')[0])
        elif phase in ('buy_quantity', 'sell_quantity'):
            operation = phase.partition('_')[0]
            if operation == 'buy':
                self.shop_buy_geometry(tree, self.shop_window_roots)
                before = self.shop_buy_assets
            else:
                self.shop_sell_geometry(tree, self.shop_window_roots)
                before = self.shop_sell_assets
            if tree['assets'] != before:
                raise ValueError('SHOP_ASSETS_CHANGED_BEFORE_' + operation.upper() + '_CONFIRM')
            self.shop_bind_control(tree, self.shop_window_roots, operation)
            inserts = self.shop_action('shop-' + operation + '-confirm', 'shop_probe.' + operation)
            inserts += [('shop_probe_observe', 'shop-' + operation + '-result-tree', operation + '_result')]
            observation = 'ONE_DAGGER_INCREMENT_CLICK_POSTED; QUANTITY_PROVEN_ONLY_BY_COMMIT_RESULT'
        elif phase == 'buy_result':
            return self.shop_buy_result(tree)
        elif phase == 'sell_result':
            return self.shop_sell_result(tree)
        else:
            remaining = self.shop_visible(tree) & self.shop_window_roots
            if remaining:
                raise ValueError('SHOP_NATIVE_WINDOW_STILL_SHOWN_AFTER_CLOSE')
            observation = 'NATIVE_SHOP_WINDOW_ROOTS_NO_LONGER_SHOWN'
            if phase == 'buy_closed':
                inserts = self.shop_reopen_sell()
            elif phase == 'deposit_closed':
                inserts = self.warehouse_reopen_retrieve()
        self.steps[self.index+1:self.index+1] = inserts
        return dict(status='OBSERVED', observation=observation, tree_file=tree['tree_file'],
                    server=server, ui_result='UNKNOWN; PNG_REQUIRES_VISUAL_REVIEW', formal_pass=False)

    def shop_buy_geometry(self, tree, roots):
        # User-reviewed GLFW64 capture: eight visible rows, dagger first,
        # first-row ▲=(775,188). No row node was present in the 27-node dump.
        capture = self.last_capture_context
        expected = dict(png_size=[2880, 2160], read_size=[3840, 2160],
                        crop=[480, 0, 2880, 2160], client_rect=[0, 0, 3840, 2160])
        if (tree['status'] != 'OBSERVED' or tree['server']['shop_mode'] != 5
                or tree['server']['menu_target'] != self.shop_target['uid']
                or any(capture.get(k) != value for k, value in expected.items())):
            raise ValueError('SHOP_DAGGER_CAPTURE_OR_CURRENT_BUY_WINDOW_CHANGED')
        layouts = [l for l in tree['layouts'] if l['shown'] and l['root'] in roots
                   and l['name'] == 'NpcShopLayout']
        if len(layouts) != 1:
            raise ValueError('SHOP_DAGGER_NATIVE_WINDOW_NOT_UNIQUE')
        geometry = {
            'NpcShopLayout': ([0.0, 379.0], [450.0, 581.0]),
            'NpcShopLayout.Root.ListviewScroll.ListView_Slot': ([-205.0, -244.0], [340.0, 500.0]),
            'NpcShopLayout.Root.ListviewScroll.Scroll.Bt_Handle': ([7.0, 397.0], [20.0, 76.0]),
            'NpcShopLayout.Root.Bt_Buy': ([277.0, 15.0], [39.0, 23.0])}
        for path, (position, size) in geometry.items():
            nodes = [n for n in layouts[0]['nodes'] if n['path'] == path and n['shown']]
            if len(nodes) != 1 or nodes[0]['position'] != position or nodes[0]['size'] != size:
                raise ValueError('SHOP_DAGGER_NATIVE_GEOMETRY_CHANGED:' + path)
        bindings = tree['server']['shop_row_bindings']
        if (not bindings or bindings[0] != dict(row_key=1, value=(70014, 4, 1),
                offer=dict(key=(70014, 4, 1), item_id=41, name='단검', price=8, pack_count=1))):
            raise ValueError('SHOP_FIRST_ROW_DAGGER8_PACK1_MAPPING_REQUIRED')
        wire_rows = tree['server']['shop_wire_rows']
        if not wire_rows or wire_rows[0] != dict(row_key=1, item_id=41, price=8):
            raise ValueError('SHOP_FIRST_WIRE_ROW_DAGGER8_REQUIRED')
        return layouts[0]

    def shop_buy_begin(self, tree, roots):
        layout = self.shop_buy_geometry(tree, roots)
        assets = tree['assets']
        if (assets['status'] != 'OBSERVED' or assets['current_inventory']['adena'] != 1895
                or assets['saved']['inventory.json']['adena'] != 1895):
            raise ValueError('SHOP_DAGGER_START_CURRENT_AND_SAVED_ADENA1895_REQUIRED')
        self.shop_buy_assets = assets
        self.shop_control = dict(layout=layout['layout'], root=layout['root'],
            control='dagger_increment', trade_capture_fallback=True, point=[775, 188],
            source='USER_REVIEWED runs/glfw64-shop_probe-claude-20261030-1/shop-buy-menu-after.png')
        inserts = self.shop_action('shop-dagger-increment-once', 'shop_probe.dagger_increment')
        inserts += [('shop_probe_observe', 'shop-dagger-quantity-tree', 'buy_quantity')]
        self.steps[self.index+1:self.index+1] = inserts
        return dict(status='OBSERVED', observation='CURRENT_FIRST_BUY_ROW_DAGGER8_PACK1_AND_MATCHED_CAPTURE_GEOMETRY',
                    binding=self.shop_control, tree_file=tree['tree_file'], formal_pass=False)

    def shop_reopen_sell(self):
        self.shop_reopening, self.shop_next_menu = True, 'sell'
        return (self.shop_action('shop-reopen-for-sell', 'shop_probe.npc', candidate=0)
                + [('shop_probe_observe', 'shop-reopen-for-sell-tree', 'npc', 0)])

    def shop_sell_geometry(self, tree, roots):
        # Row coordinates come from current SlotNode/Count_Up bounds below.
        capture = self.last_capture_context
        expected = dict(png_size=[2880, 2160], read_size=[3840, 2160],
                        crop=[480, 0, 2880, 2160], client_rect=[0, 0, 3840, 2160])
        if (tree['status'] != 'OBSERVED' or tree['server']['shop_mode'] != 6
                or tree['server']['menu_target'] != self.shop_target['uid']
                or any(capture.get(k) != value for k, value in expected.items())):
            raise ValueError('SHOP_SELL_CAPTURE_OR_CURRENT_WINDOW_CHANGED')
        wire = tree['server']['shop_wire_rows']
        mapping = {r['row_key']: r['value'] for r in tree['server']['shop_row_bindings']}
        bought = [r for r in wire if mapping.get(r['row_key']) == self.shop_bought_uid]
        if len(bought) != 1 or bought[0]['price'] != 4:
            raise ValueError('SHOP_BOUGHT_DAGGER_CURRENT_ISSUED_PRICE4_REQUIRED')
        if hasattr(self, 'shop_sell_issued') and (wire, mapping) != self.shop_sell_issued:
            raise ValueError('SHOP_SELL_ISSUED_LIST_CHANGED')
        layouts = [l for l in tree['layouts'] if l['shown'] and l['root'] in roots
                   and l['name'] == 'NpcShopLayout']
        if len(layouts) != 1:
            raise ValueError('SHOP_SELL_NATIVE_WINDOW_NOT_UNIQUE')
        geometry = {
            'NpcShopLayout': ([0.0, 379.0], [450.0, 581.0]),
            'NpcShopLayout.Root.ListviewScroll.ListView_Slot': ([-205.0, -244.0], [340.0, 500.0]),
            'NpcShopLayout.Root.Bt_Sell': ([277.0, 17.0], [35.0, 21.0])}
        for path, (position, size) in geometry.items():
            nodes = [n for n in layouts[0]['nodes'] if n['path'] == path and n['shown']]
            if len(nodes) != 1 or nodes[0]['position'] != position or nodes[0]['size'] != size:
                raise ValueError('SHOP_SELL_GEOMETRY_UNPROVEN:' + path)
        return layouts[0]

    def shop_sell_begin(self, tree, roots):
        try:
            layout = self.shop_sell_geometry(tree, roots)
        except ValueError as error:
            return self.shop_trade_unresolved(tree, roots, 'sell', blocker=str(error))
        self.shop_sell_assets = tree['assets']
        if (tree['assets']['status'] != 'OBSERVED'
                or tree['assets']['current_inventory']['adena'] != 1887):
            raise ValueError('SHOP_SELL_PRECOMMIT_ASSETS_UNKNOWN')
        self.shop_trade_assets = tree['assets']
        self.shop_sell_issued = (tree['server']['shop_wire_rows'],
            {r['row_key']: r['value'] for r in tree['server']['shop_row_bindings']})
        self.shop_sell_scroll_count = 0
        self.shop_control = dict(layout=layout['layout'], root=layout['root'],
            trade_live_node=True, operation='sell', item_uid=self.shop_bought_uid)
        return self.shop_sell_advance(tree)

    def shop_live_row(self, tree, binding, item_uid):
        """Resolve a live row; coordinates come from its current node."""
        live = self.shop_tree('trade-' + self.steps[self.index][1] + '-live',
                              owned_layout=binding['layout'])
        if live['status'] != 'OBSERVED' or len(live['layouts']) != 1:
            raise ValueError('TRADE_CURRENT_FULL_TREE_UNKNOWN')
        layout = live['layouts'][0]
        if not layout['shown'] or layout['root'] != binding['root']:
            raise ValueError('TRADE_CURRENT_WINDOW_REPLACED')
        nodes = layout['nodes']
        slots = [n for n in nodes if n.get('item_uid') == item_uid and n['shown']]
        binding['identity_basis'] = 'CURRENT_SLOTNODE_PAYLOAD_808_UID_AND_CURRENT_ISSUED_REFERENCE'
        by_node = {n['node']: n for n in nodes}
        if not slots and binding['operation'] == 'sell':
            # GLFW86's first visible prices agree with issued wire order. The
            # null payload leaves identity inferred until the server/save verdict.
            mapping = {r['row_key']: r['value'] for r in tree['server']['shop_row_bindings']}
            issued = [mapping.get(r['row_key']) for r in tree['server']['shop_wire_rows']]
            rows = [n for n in nodes if n['name'] == 'ItemListSlot' and n['shown']]
            if (issued.count(item_uid) != 1 or len(rows) != len(issued)
                    or sorted(n['child_index'] for n in rows) != list(range(len(issued)))
                    or len({n['parent'] for n in rows}) != 1):
                raise ValueError('TRADE_CURRENT_SLOTNODE_UID_NOT_FOUND:' + str(item_uid))
            target = next(n for n in rows if n['child_index'] == issued.index(item_uid))
            slots = [n for n in nodes if n['parent'] == target['node']
                     and n['name'] == 'ItemSlot' and n['shown']
                     and n.get('item_uid') is None]
            binding['identity_basis'] = 'INFERRED_ISSUED_ORDER_WITH_SERVER_RESULT_VERDICT'
        elif not slots and binding['operation'] in ('deposit', 'retrieve'):
            # GLFW85 showed the selected red potion as the first deposit row;
            # retrieval starts with the single item produced by that deposit.
            rows = [n for n in nodes if n['name'] == 'ItemListSlot' and n['shown']]
            first = [n for n in rows if n['child_index'] == 0]
            issued = list(tree['server']['warehouse_window']['rows'].values())
            if (len(first) != 1 or issued.count(item_uid) != 1
                    or (binding['operation'] == 'retrieve' and len(issued) != 1)):
                raise ValueError('TRADE_CURRENT_SLOTNODE_UID_NOT_FOUND:' + str(item_uid))
            slots = [n for n in nodes if n['parent'] == first[0]['node']
                     and n['name'] == 'ItemSlot' and n['shown']
                     and n.get('item_uid') is None]
            binding['identity_basis'] = 'INFERRED_REVIEWED_FIRST_ROW_WITH_SERVER_RESULT_VERDICT'
        if not slots:
            raise ValueError('TRADE_CURRENT_SLOTNODE_UID_NOT_FOUND:' + str(item_uid))
        viewport = [n for n in nodes if n['name'] == 'ListView_Slot' and n['shown']]
        if len(viewport) != 1 or not viewport[0].get('scene_bounds'):
            raise ValueError('TRADE_CURRENT_QUANTITY_CONTROL_OR_VIEWPORT_UNKNOWN')
        candidates = []
        for slot in slots:
            # SlotNode ItemSlot owns payload+808; Panel_Slot is its +830 child.
            row = by_node.get(slot['parent'])
            inner = by_node.get(row['parent']) if row else None
            index = row['child_index'] if row else None
            if (row is None or row['name'] != 'ItemListSlot' or not row['shown']
                    or slot['node'] not in row['children'] or inner is None
                    or type(index) is not int or not 0 <= index < len(inner['children'])
                    or inner['children'][index] != row['node']):
                raise ValueError('TRADE_UID_SLOT_ITEMLIST_ROW_UNKNOWN')
            up = [n for n in nodes if n['parent'] == row['node'] and n['name'] == 'Count_Up' and n['shown']]
            if len(up) != 1:
                raise ValueError('TRADE_CURRENT_QUANTITY_CONTROL_OR_VIEWPORT_UNKNOWN')
            if not all(n.get('scene_bounds') for n in (row, up[0])):
                raise ValueError('TRADE_CURRENT_ROW_SCENE_BOUNDS_UNKNOWN')
            candidates.append((row, up[0]))
        if len(candidates) > 1:
            visible = []
            for row, up in candidates:
                try:
                    self.shop_require_row_visible(row, up, viewport[0])
                except ValueError:
                    continue
                visible.append((row, up))
            if len(visible) != 1:
                raise ValueError('TRADE_CURRENT_SLOTNODE_UID_NOT_UNIQUE:' + str(item_uid))
            candidates = visible
        row, up = candidates[0]
        server = tree['server']
        issued = ([r['value'] for r in server['shop_row_bindings']] if binding['operation'] == 'sell'
                  else list(server['warehouse_window']['rows'].values()))
        source = ('current_warehouse' if binding['operation'] == 'retrieve' else 'current_inventory')
        if (issued.count(item_uid) != 1
                or sum(r['uid'] == item_uid for r in tree['assets'][source]['items']) != 1):
            raise ValueError('TRADE_NATIVE_UID_NOT_IN_CURRENT_ISSUED_LIST')
        return live, row, up, viewport[0]

    @staticmethod
    def shop_require_row_visible(row, up, viewport):
        # Cocos shown/scene_bounds.visible do not imply scroll clipping.
        v = viewport['scene_bounds']
        for node in (row, up):
            b = node['scene_bounds']
            if not (v['left'] <= b['left'] < b['right'] <= v['right']
                    and v['bottom'] <= b['bottom'] < b['top'] <= v['top']):
                raise ValueError('TRADE_TARGET_ROW_CLIPPED; SCROLL_AND_CAPTURE_REQUIRED')

    def shop_sell_advance(self, tree):
        self.shop_sell_geometry(tree, self.shop_window_roots)
        if tree['assets'] != self.shop_trade_assets:
            raise ValueError('SHOP_SELL_ASSETS_CHANGED_BEFORE_SELECTION')
        binding = self.shop_control
        live, row, up, viewport = self.shop_live_row(tree, binding, self.shop_bought_uid)
        top = row['scene_bounds']['top']
        previous = getattr(self, 'shop_sell_previous_top', None)
        if previous is not None and top <= previous:
            raise ValueError('SHOP_SELL_WHEEL_DID_NOT_ADVANCE_BOUGHT_ROW')
        try:
            self.shop_require_row_visible(row, up, viewport)
        except ValueError:
            if self.shop_sell_scroll_count >= 16:
                raise ValueError('SHOP_SELL_BOUNDED_SCROLL_EXHAUSTED')
            self.shop_sell_previous_top = top
            self.shop_sell_scroll_count += 1
            binding['control'] = 'scroll'
            label = 'shop-sell-wheel-' + str(self.shop_sell_scroll_count)
            inserts = self.shop_action(label, 'shop_probe.sell_scroll', action='mouse_wheel', delta=-120)
            inserts += [('shop_probe_observe', label + '-tree', 'sell_scrolled')]
            observation = 'TARGET_ROW_OFFSCREEN; ONE_GLFW_WHEEL_THEN_FRESH_CAPTURE_AND_BOUNDS'
        else:
            binding['control'] = 'quantity1'
            inserts = self.shop_action('shop-sell-dagger-increment-once', 'shop_probe.dagger_increment')
            inserts += [('shop_probe_observe', 'shop-sell-dagger-quantity-tree', 'sell_quantity')]
            observation = 'CURRENT_TARGET_ROW_VISIBLE; COUNT_UP_NODE_CENTER_ONCE'
        self.steps[self.index+1:self.index+1] = inserts
        return dict(status='OBSERVED', observation=observation, binding=dict(binding),
                    row_scene_bounds=row['scene_bounds'], tree_file=live['tree_file'], formal_pass=False)

    def shop_sell_result(self, tree):
        assets = tree['assets']
        if assets['status'] != 'OBSERVED' or tree['server']['shop_mode'] is not None:
            raise ValueError('SHOP_SELL_COMMIT_NOT_OBSERVED')
        before, current = self.shop_sell_assets['current_inventory'], assets['current_inventory']
        prior = {r['uid']: r for r in before['items']}
        if (current['adena'] != before['adena'] + 4
                or current['row_count'] != before['row_count'] - 1
                or any(r['uid'] == self.shop_bought_uid for r in current['items'])
                or any(r['uid'] not in prior or (r['item_id'] != 7 and r != prior[r['uid']])
                       for r in current['items'])):
            raise ValueError('SHOP_SOLD_DAGGER1_AND_ADENA_INCREASE4_NOT_OBSERVED')
        if any(assets['saved']['inventory.json'].get(key) != current[key]
               for key in ('row_count', 'adena', 'items')):
            raise ValueError('SHOP_SELL_SAVED_INVENTORY_MISMATCH')
        self.shop_completed_trades.append(dict(operation='sell', item_uid=self.shop_bought_uid,
            adena=current['adena'], current_and_saved=True, tree_file=tree['tree_file']))
        if self.shop_visible(tree) & self.shop_window_roots:
            self.shop_bind_control(tree, self.shop_window_roots, 'close')
            self.steps[self.index+1:self.index+1] = (
                self.shop_action('shop-sell-window-close', 'shop_probe.close')
                + [('shop_probe_observe', 'shop-sell-window-close-tree', 'close')])
        return dict(status='OBSERVED', observation='DAGGER_BUY_AND_SELL_CURRENT_AND_SAVED',
                    completed_trade_operations=self.shop_completed_trades,
                    tree_file=tree['tree_file'], formal_pass=False,
                    ui_result='UNKNOWN; PNG_REQUIRES_VISUAL_REVIEW')

    def warehouse_geometry(self, tree, roots, operation):
        capture = self.last_capture_context
        expected = dict(png_size=[2880, 2160], read_size=[3840, 2160],
                        crop=[480, 0, 2880, 2160], client_rect=[0, 0, 3840, 2160])
        window = tree['server']['warehouse_window']
        direction = 'deposit' if operation == 'deposit' else 'withdraw'
        if (tree['status'] != 'OBSERVED' or not window or window['direction'] != direction
                or window['mode'] != (1 if operation == 'deposit' else 2)
                or tree['server']['menu_target'] != self.shop_target['uid']
                or any(capture.get(k) != v for k, v in expected.items())):
            raise ValueError('WAREHOUSE_CURRENT_WINDOW_OR_CAPTURE_GEOMETRY_CHANGED')
        if (getattr(self, 'warehouse_operation', None) == operation
                and window != self.warehouse_issued):
            raise ValueError('WAREHOUSE_CURRENT_ISSUED_CONTEXT_OR_ROWS_CHANGED')
        layouts = [l for l in tree['layouts'] if l['shown'] and l['root'] in roots
                   and l['name'] == 'StorageLayout']
        if len(layouts) != 1:
            raise ValueError('WAREHOUSE_NATIVE_WINDOW_NOT_UNIQUE')
        return layouts[0]

    @staticmethod
    def warehouse_assets_saved(assets):
        if assets['status'] != 'OBSERVED':
            raise ValueError('WAREHOUSE_CURRENT_AND_SAVED_ASSETS_UNKNOWN')
        for current, saved in (('current_inventory', 'inventory.json'),
                               ('current_warehouse', 'warehouse.json')):
            if any(assets['saved'][saved].get(k) != assets[current][k]
                   for k in ('row_count', 'adena', 'items')):
                raise ValueError('WAREHOUSE_CURRENT_SAVED_MISMATCH:' + saved)
        if assets['warehouse_policy'] != dict(limit=150, withdrawal_fee=30, minimum_level=5):
            raise ValueError('WAREHOUSE_LOCAL_COUNT_LIMIT_FEE_POLICY_CHANGED')
        if assets['current_warehouse']['row_count'] > 150:
            raise ValueError('WAREHOUSE_OCCUPIED_COUNT_OVER_LIMIT')

    def warehouse_begin(self, tree, roots, operation):
        layout = self.warehouse_geometry(tree, roots, operation)
        assets = tree['assets']
        self.warehouse_assets_saved(assets)
        if operation == 'deposit':
            if assets['current_warehouse']['row_count'] != 0:
                raise ValueError('WAREHOUSE_REVIEWED_EMPTY_START_REQUIRED')
            # The actual GLFW85 first visible row is red potion[73], not the
            # first issued UID (equipped items do not appear in this window).
            first = [r for r in assets['current_inventory']['items']
                     if r['item_id'] == 14 and r['quantity'] == 73]
            if len(first) != 1 or assets['current_inventory']['adena'] != 1895:
                raise ValueError('WAREHOUSE_REVIEWED_FIRST_RED_POTION73_AND_ADENA1895_REQUIRED')
            item_uid = first[0]['uid']
            self.warehouse_start_assets = assets
            self.warehouse_player_item = first[0]
            self.shop_completed_trades = []
        else:
            item_uid = self.warehouse_deposited_item['uid']
            if assets != self.warehouse_after_deposit:
                raise ValueError('WAREHOUSE_ASSETS_CHANGED_BEFORE_RETRIEVE')
        self.warehouse_operation, self.warehouse_issued = operation, tree['server']['warehouse_window']
        self.shop_trade_assets = assets
        self.shop_control = dict(layout=layout['layout'], root=layout['root'],
            control='quantity1', trade_live_node=True, operation=operation, item_uid=item_uid)
        live, row, up, viewport = self.shop_live_row(tree, self.shop_control, item_uid)
        if row['child_index'] != 0:
            raise ValueError('WAREHOUSE_REVIEWED_TARGET_NOT_CURRENT_FIRST_NATIVE_ROW')
        self.shop_require_row_visible(row, up, viewport)
        label = 'warehouse-' + operation + '-increment-once'
        self.steps[self.index+1:self.index+1] = (
            self.shop_action(label, 'shop_probe.warehouse_quantity')
            + [('shop_probe_observe', label + '-tree', operation + '_quantity')])
        return dict(status='OBSERVED', observation='CURRENT_FIRST_NATIVE_ROW_UID_AND_COUNT_UP_NODE_BOUND',
                    binding=dict(self.shop_control), tree_file=live['tree_file'], formal_pass=False)

    def warehouse_reopen_retrieve(self):
        self.shop_reopening, self.shop_next_menu = True, 'retrieve'
        return (self.shop_action('warehouse-reopen-for-retrieve', 'shop_probe.npc', candidate=0)
                + [('shop_probe_observe', 'warehouse-reopen-for-retrieve-tree', 'npc', 0)])

    def warehouse_result(self, tree, operation):
        assets = tree['assets']
        self.warehouse_assets_saved(assets)
        if tree['server']['warehouse_window'] is not None or tree['server']['menu_target'] is not None:
            raise ValueError('WAREHOUSE_COMMIT_WINDOW_NOT_RETIRED')
        prior_results = self.shop_start_server['warehouse_results']
        completed = tree['server']['warehouse_results']
        expected_count = 1 if operation == 'deposit' else 2
        if (len(completed) != len(prior_results) + expected_count
                or completed[:len(prior_results)] != prior_results):
            raise ValueError('WAREHOUSE_NORMAL_HANDLER_RESULT_NOT_OBSERVED')
        current = assets['current_inventory']
        bank = assets['current_warehouse']
        before = self.shop_trade_assets['current_inventory']
        original = self.warehouse_player_item
        if operation == 'deposit':
            expected_items = [dict(r, quantity=r['quantity']-1) if r['uid'] == original['uid']
                              else r for r in before['items']]
            if (current['items'] != expected_items or current['adena'] != before['adena']
                    or current['row_count'] != before['row_count']
                    or bank['row_count'] != 1 or bank['items'][0]['item_id'] != original['item_id']
                    or bank['items'][0]['quantity'] != 1 or bank['adena'] != 0):
                raise ValueError('WAREHOUSE_DEPOSIT_EXACTLY_ONE_CURRENT_SAVED_NOT_OBSERVED')
            self.warehouse_deposited_item = bank['items'][0]
            self.warehouse_after_deposit = assets
        else:
            start = self.warehouse_start_assets['current_inventory']
            expected_items = [dict(r, quantity=r['quantity']-30) if r['item_id'] == 7
                              else r for r in start['items']]
            if (current['items'] != expected_items or current['adena'] != start['adena']-30
                    or current['row_count'] != start['row_count'] or bank['row_count'] != 0):
                raise ValueError('WAREHOUSE_RETRIEVE_ONE_AND_FEE30_CURRENT_SAVED_NOT_OBSERVED')
        result = completed[-1]
        if result != dict(uid=assets['uid'], direction='deposit' if operation == 'deposit' else 'withdraw',
                          fee=0 if operation == 'deposit' else 30,
                          player_slots=current['row_count'], warehouse_slots=bank['row_count']):
            raise ValueError('WAREHOUSE_HANDLER_QUANTITY_FEE_OR_SLOT_RESULT_MISMATCH')
        self.shop_completed_trades.append(dict(operation=operation, quantity=1,
            native_item_uid=original['uid'] if operation == 'deposit' else self.warehouse_deposited_item['uid'],
            adena=current['adena'], occupied=bank['row_count'], limit=150,
            current_and_saved=True, tree_file=tree['tree_file']))
        if self.shop_visible(tree) & self.shop_window_roots:
            self.shop_bind_control(tree, self.shop_window_roots, 'close')
            inserts = self.shop_action('warehouse-' + operation + '-close', 'shop_probe.close')
            inserts += [('shop_probe_observe', 'warehouse-' + operation + '-close-tree', operation + '_closed')]
        else:
            inserts = self.warehouse_reopen_retrieve() if operation == 'deposit' else []
        self.steps[self.index+1:self.index+1] = inserts
        return dict(status='OBSERVED', observation='WAREHOUSE_' + operation.upper() + '_ONE_CURRENT_AND_SAVED',
                    completed_trade_operations=self.shop_completed_trades,
                    tree_file=tree['tree_file'], formal_pass=False,
                    ui_result='UNKNOWN; PNG_REQUIRES_VISUAL_REVIEW')

    def shop_buy_result(self, tree):
        assets = tree['assets']
        if assets['status'] != 'OBSERVED' or tree['server']['shop_mode'] is not None:
            raise ValueError('SHOP_BUY_COMMIT_NOT_OBSERVED')
        before, current = self.shop_buy_assets['current_inventory'], assets['current_inventory']
        prior = {r['uid']: r for r in before['items']}
        added = [r for r in current['items'] if r['uid'] not in prior]
        if (len(added) != 1 or added[0]['item_id'] != 41 or added[0]['quantity'] != 1
                or current['adena'] != 1887 or current['row_count'] != before['row_count'] + 1
                or any(r != prior[r['uid']] for r in current['items']
                       if r['uid'] in prior and r['item_id'] != 7)):
            raise ValueError('SHOP_BUY_NEW_DAGGER1_AND_ADENA1887_NOT_OBSERVED')
        saved = assets['saved']['inventory.json']
        if any(saved.get(key) != current[key] for key in ('row_count', 'adena', 'items')):
            raise ValueError('SHOP_BUY_SAVED_INVENTORY_MISMATCH')
        self.shop_bought_uid = added[0]['uid']
        self.shop_completed_trades = [dict(operation='buy', item=added[0], adena=1887,
            current_and_saved=True, tree_file=tree['tree_file'])]
        if self.shop_visible(tree) & self.shop_window_roots:
            self.shop_bind_control(tree, self.shop_window_roots, 'close')
            inserts = self.shop_action('shop-buy-window-close', 'shop_probe.close')
            inserts += [('shop_probe_observe', 'shop-buy-window-close-tree', 'buy_closed')]
        else:
            inserts = self.shop_reopen_sell()
        self.steps[self.index+1:self.index+1] = inserts
        return dict(status='OBSERVED', observation='ONE_DAGGER_BOUGHT_CURRENT_AND_SAVED_ADENA1887',
                    completed_trade_operations=self.shop_completed_trades,
                    tree_file=tree['tree_file'], formal_pass=False,
                    ui_result='UNKNOWN; PNG_REQUIRES_VISUAL_REVIEW')

    def shop_trade_unresolved(self, tree, roots, phase, blocker=None):
        # Preserve the first missing live binding rather than guessing a row.
        # Reuse the existing owned-layout full traversal (including +CE0) to
        # expose unnamed children, without assigning a trade callback to them.
        full_trees = [self.shop_tree('trade-' + phase + '-owned-' + str(index),
                          owned_layout=layout['layout'])['tree_file']
                      for index, layout in enumerate(tree['layouts'])
                      if layout['root'] in roots and layout['shown']]
        import re
        nodes = [dict(layout=l['layout'], root=l['root'], path=n['path'],
                name=n['name'], position=n['position'], size=n['size'])
                for l in tree['layouts'] if l['root'] in roots and l['shown']
                for n in l['nodes'] if n['shown']]
        # Candidate discovery is lexical only. Generic Item/Slot names cannot
        # establish the offered/owned UID or which callback selects a quantity.
        patterns = dict(row=r'(?:row|item|slot)(?:_?\d+)?',
            quantity=r'(?:.*(?:quantity|count|amount|qty).*|.*text_?field.*)',
            confirm=r'(?:bt_|btn_|button_)?(?:ok|confirm|buy|sell|deposit|retrieve)')
        candidates = {role: [n for n in nodes if re.fullmatch(pattern, n['name'], re.I)]
                      for role, pattern in patterns.items()}
        scan = {role: dict(count=len(found), candidates=found,
                    name_evidence='ABSENT' if not found else 'AMBIGUOUS' if len(found) > 1 else 'ONE_LEXICAL_CANDIDATE',
                    action_binding='UNKNOWN; NODE_NAME_ALONE_DOES_NOT_PROVE_ITEM_OR_CALLBACK')
                for role, found in candidates.items()}
        row_reason = ('NO_NAMED_ROW_CANDIDATE' if not candidates['row'] else
                      'NAMED_ROW_CANDIDATES_AMBIGUOUS' if len(candidates['row']) > 1 else
                      'NAMED_ROW_ITEM_METADATA_AND_ACTION_UNPROVEN')
        discovery = dict(status='UNKNOWN', phase=phase, reason=blocker or 'TRADE_' + row_reason,
            tree_file=tree['tree_file'], server=tree['server'], assets=tree.get('assets'),
            native_name_discovery=scan, shown_window_nodes=nodes,
            requested=(['select bought dagger UID ' + str(getattr(self, 'shop_bought_uid', 'UNKNOWN')),
                        'sell quantity 1', 'confirm', 'verify current and saved Adena increase', 'close']
                if phase == 'sell' else
                ['deposit row 1 quantity 1', 'confirm', 'retrieve row 1 quantity 1',
                 'confirm', 'verify withdrawal fee 30, saved count/limit/adena', 'close']),
            owned_full_tree_files=full_trees,
            attempted_trade_inputs=[],
            completed_trade_operations=getattr(self, 'shop_completed_trades', []),
            first_unresolved_step=('SELECT_BOUGHT_DAGGER_NATIVE_ROW_AND_PROVE_QUANTITY_BINDING'
                if phase == 'sell' else 'SELECT_FIRST_ELIGIBLE_NATIVE_DEPOSIT_ROW_AND_PROVE_QUANTITY_BINDING'),
            selected_bought_uid=getattr(self, 'shop_bought_uid', None),
            issued_sell_row_keys=([r['row_key'] for r in tree['server']['shop_row_bindings']
                                  if r['value'] == getattr(self, 'shop_bought_uid', None)]
                                 if phase == 'sell' else None),
            missing='Live native row identity/metadata, quantity=1 and confirmation bindings',
            producer='Current original client window; inspect this live tree and capture',
            formal_pass=False, automatic_retry=False,
            ui_result='UNKNOWN; WINDOW_CAPTURE_REQUIRES_VISUAL_REVIEW')
        discovery['discovery_file'] = self.shop_write('trade-native-binding-unknown', discovery)
        return discovery

    def finish(self, row):
        if (self.shop_probe and getattr(self, 'shop_new_server_errors', None)
                and row.get('status') == 'UNKNOWN' and self.shop_blocked is None):
            row = dict(row, reason=self.shop_new_server_errors[0],
                       new_server_errors=self.shop_new_server_errors)
        if self.shop_probe and self.shop_blocked is None and row.get('status') not in ('OBSERVED', 'POSTED', 'WAITED', 'SKIPPED'):
            self.shop_blocked = dict(step=self.steps[self.index][1], status=row.get('status'), reason=row.get('reason'))
        return super().finish(row)

    async def tick(self):
        if not self.shop_probe or self.done:
            return await super().tick()
        step = self.steps[self.index]
        if self.shop_blocked and step[0] not in ('capture', 'shop_probe_observe'):
            self.finish(dict(status='SKIPPED', reason='SHOP_FAILED_PREREQUISITE',
                             prerequisite=self.shop_blocked, automatic_retry=False)); return
        try:
            # Capture.sample() owns consumer._readonly_pending until collect()
            # consumes its reply. Let the established capture/input dispatchers
            # poll their own in-flight work; a blanket busy gate deadlocks the
            # first capture on its own readonly lease.
            if step[0] in ('shop_probe_prepare', 'shop_probe_observe', 'shop_probe_bind') and self.busy():
                return
            if step[0] == 'shop_probe_prepare':
                self.finish(self.shop_prepare()); return
            if step[0] == 'shop_probe_observe':
                self.finish(self.shop_observe(step[1], *step[2:])); return
            if step[0] == 'shop_probe_bind':
                tree = self.shop_tree(step[1] + '-tree')
                self.shop_require_no_new_server_error(tree['server'])
                if tree['status'] != 'OBSERVED':
                    raise ValueError('SHOP_BINDING_UI_TREE_INCOMPLETE')
                roots = (self.shop_dialogue_roots if step[3] == 'dialogue' else self.shop_window_roots)
                self.shop_bind_control(tree, roots, step[2])
                self.finish(dict(status='OBSERVED', control=step[2], binding=self.shop_control,
                    tree_file=tree['tree_file'], formal_pass=False, ui_result='UNKNOWN')); return
            return await super().tick()
        except Exception as error:
            if self.capture is not None:
                self.capture.close(); self.capture = None
            self.finish(dict(status='UNKNOWN', reason=str(error)[:300],
                             tree_file=getattr(self, 'shop_last_tree', None),
                             automatic_retry=False, formal_pass=False, ui_result='UNKNOWN'))


module.Steps = ShopProbeSteps

# Development headless observation: copied ATS fixture -> normal autonomous AI.
# Startup owner-heal events remain eligible before combat; no GM binding, fake
# hit, forced cast, resource mutation or replay of a failed attack is introduced.
module.STEP_SETS['companion_spell_cast'] = (
    ('spell_cast_prepare', 'spell-cast-preconditions'),
    ('spell_cast_wait', 'spell-cast-buffs', 'buff', 20),
    ('capture', 'spell-cast-after-buffs'),
    ('spell_cast_wait', 'spell-cast-owner-heal', 'heal', 45),
    ('capture', 'spell-cast-after-owner-heal'),
    ('private_input', 'spell-cast-knight-attack',
     dict(locator='spell_cast.monster', action='left_click')),
    ('spell_cast_attack_check', 'spell-cast-attack-check'),
    ('spell_cast_wait', 'spell-cast-energy-bolt', 'combat', 25),
    ('capture', 'spell-cast-after-energy-bolt'))


class CompanionSpellCastSteps(ShopProbeSteps):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.spell_cast = any(s[0] == 'spell_cast_prepare' for s in self.steps)
        if not self.spell_cast:
            return
        self.cast_blocked = None
        self.cast_frames, self.cast_hits, self.cast_attacks = [], [], []
        self.cast_origin = time.monotonic()
        self.cast_attack_at = None
        self.cast_hp_before = None
        self.cast_attack_attempts = []
        self.cast_attack_deadline = None
        self.cast_deadlines, self.cast_sample_counts = {}, {}
        self.cast_entry_stop, self.cast_entry_capture = False, None
        self.cast_entry_shots = []
        self.cast_entry_next = self.cast_origin
        # Constructed before owner.resume(): buff projections during world entry
        # are retained even if the harness reaches IDLE after their animation.
        world = self.manual.inventory_broker._world
        original, owned, saved = world._queue, '_queue' in vars(world), vars(world).get('_queue')
        def queue(recipient, frame):
            count = len(world.outbox.get(recipient, ()))
            result = original(recipient, frame)
            if len(frame) >= 6 and int.from_bytes(frame[2:4], 'little') in (0x4e31, 0x4ed8):
                try:
                    from tools.local_entry_server import protobuf as pb
                    with pb.parse_message(frame[4:-2]) as body:
                        fields = {str(f.number): f.value for f in body.fields if f.wire_type == 0}
                    queued = world.outbox.get(recipient, ())
                    self.cast_frames.append(dict(opcode='0x%04X' % int.from_bytes(frame[2:4], 'little'),
                        recipient=recipient, fields=fields, monotonic_seconds=time.monotonic(),
                        actual_append=len(queued) == count+1 and queued[-1] is frame))
                    del self.cast_frames[:-256]
                except Exception as error:
                    self.cast_frames.append(dict(reason=str(error)[:200], opcode='DECODE_UNKNOWN'))
            return result
        world._queue = queue
        self.cast_queue_hook = (world, original, queue, owned, saved)
        def attack(owner_ref, target_ref, now):
            self.cast_attacks.append(dict(owner=owner_ref.uid, target=target_ref.uid,
                                          at=now, monotonic_seconds=time.monotonic()))
            del self.cast_attacks[:-32]
        def hit(victim_ref, attacker_ref, now):
            state = world.combat.pcs.get(victim_ref.uid)
            self.cast_hits.append(dict(victim=victim_ref.uid, attacker=attacker_ref.uid,
                at=now, hp=None if state is None else state.hp,
                max_hp=None if state is None else state.max_hp,
                monotonic_seconds=time.monotonic()))
            del self.cast_hits[:-64]
        self.cast_event_hooks = [(name, world.events.add('spell_cast_observation', name, callback))
            for name, callback in (('pc_attack_started', attack), ('pc_hit', hit))]
        from tools.local_original_session import launcher
        original_poll = launcher.ProductFeatures.poll
        async def poll(features, *args, **kwargs):
            row = await original_poll(features, *args, **kwargs)
            if getattr(features, 'manual', None) is self.manual and not self.done:
                await self.cast_entry_sample()
            return row
        launcher.ProductFeatures.poll = poll
        self.cast_poll_hook = (launcher.ProductFeatures, original_poll, poll)

    async def cast_entry_sample(self):
        # Existing PotionEffectSteps startup poll pattern. One screenshot lease
        # at a time; stop new entry requests before the regular step dispatcher.
        if self.cast_entry_capture is None:
            if (self.cast_entry_stop or self.busy() or time.monotonic() < self.cast_entry_next
                    or len(self.cast_entry_shots) >= 24):
                return
            observer = module.KitScreenshotObserver(self.manual)
            if not observer.request():
                observer.close()
                self.cast_entry_next = time.monotonic()+1
                return
            self.cast_entry_capture = observer
            self.cast_entry_requested = time.monotonic()
        observer = self.cast_entry_capture
        await observer.sample()
        row = observer.collect()
        completed = time.monotonic()
        if row.get('status') == 'OBSERVED':
            import shutil
            destination = self.directory / ('spell-cast-entry-%02d.png' % len(self.cast_entry_shots))
            shutil.copyfile(row['image_path'], destination)
            observation = dict(kind='spell_cast_entry_capture', status='OBSERVED', png=str(destination),
                requested_monotonic_seconds=self.cast_entry_requested, completed_monotonic_seconds=completed,
                packets_in_request_window=[f for f in self.cast_frames if self.cast_entry_requested <=
                    f.get('monotonic_seconds', 0) <= completed],
                ui_result='UNKNOWN; REQUEST_WINDOW_OVERLAP_DOES_NOT_PROVE_DRAW_FRAME_TIMING')
            self.cast_entry_shots.append(observation)
            self.results.append(observation)
        elif not row.get('cleanup_required') and completed-self.cast_entry_requested < 20:
            return
        else:
            self.cast_entry_shots.append(dict(status='UNKNOWN', row=row,
                requested_monotonic_seconds=self.cast_entry_requested, completed_monotonic_seconds=completed))
        observer.close()
        self.cast_entry_capture = None
        self.cast_entry_next = completed+.25

    def cast_runtime(self):
        world = self.manual.inventory_broker._world
        owner_uid = module.current_kit(self.manual)[0][3].uid
        actors = [r for r in world.companions.active.values() if r.owner_ref.uid == owner_uid]
        if len(actors) != 1:
            raise ValueError('SPELL_CAST_CURRENT_OWNED_COMPANION_NOT_UNIQUE')
        rt = actors[0]
        actor, owner = world.entities.resolve(rt.ref), world.entities.resolve(rt.owner_ref)
        magic = world.companion_ai.magic
        if actor is None or owner is None or not actor.alive or not owner.alive or magic is None:
            raise ValueError('SPELL_CAST_CURRENT_LIVING_ACTORS_AND_MAGIC_REQUIRED')
        return world, rt, actor, owner, magic

    def cast_snapshot(self):
        world, rt, actor, owner, magic = self.cast_runtime()
        state = world.combat.pcs[owner.uid]
        return dict(actor=actor.uid, member=rt.character_id, owner=owner.uid,
            level=rt.record.level, learned_count=len(magic.learned_for(rt.record)),
            mp=rt.record.mp, max_mp=rt.record.max_mp, hp=rt.record.hp,
            owner_hp=state.hp, owner_max_hp=state.max_hp,
            owner_position=[owner.map_id, owner.x, owner.y],
            companion_position=[actor.map_id, actor.x, actor.y],
            armor_uid=magic.equipment_uid(rt, 'armor'), ats=magic.ats(rt),
            events=[dict(r) for r in magic.events if r.get('actor') == actor.uid],
            attacks=list(self.cast_attacks), hits=list(self.cast_hits), frames=list(self.cast_frames),
            ui_result='UNKNOWN; PNG_REQUIRES_VISUAL_REVIEW', formal_pass=False)

    def resolve_request(self, request):
        if not self.spell_cast or request.get('locator') != 'spell_cast.monster':
            return super().resolve_request(request)
        if self.cast_attack_deadline is not None and time.monotonic() >= self.cast_attack_deadline:
            raise ValueError('SPELL_CAST_ATTACK_RETRY_DEADLINE_EXPIRED')
        capture = self.last_capture_context
        if not capture or self.results[-1].get('kind') != 'capture' or self.results[-1].get('status') != 'OBSERVED':
            raise ValueError('SPELL_CAST_CURRENT_CAPTURE_REQUIRED')
        world, rt, actor, owner, magic = self.cast_runtime()
        from tools.local_original_session.npc_ai import local_line_clear
        known = world.visibility.known.get(owner.uid, ())
        candidates = []
        for entity in world.entities:
            slot = world.spawner.slot_for(entity.uid)
            brain = None if world.ai is None else world.ai.brains.get(entity.uid)
            if (slot and slot[0].active and slot[1].hp > 0 and entity.alive
                    and slot[0].monster.attack_interval_ms > 0
                    and slot[0].monster.damage.max > 0
                    and brain is not None and brain.ref == entity.ref
                    and entity.uid in known and entity.map_id == owner.map_id
                    and max(abs(entity.x-owner.x), abs(entity.y-owner.y)) <= 7
                    and local_line_clear(world.terrain, owner.map_id, owner.x, owner.y, entity.x, entity.y)):
                candidates.append(entity)
        if not candidates:
            raise ValueError('SPELL_CAST_NO_CURRENT_VISIBLE_RETALIATING_MONSTER_WITHIN_7')
        previous = self.cast_attack_attempts[0]['target_ref'] if self.cast_attack_attempts else None
        target = next((e for e in candidates if e.ref == previous), None)
        if target is None:
            target = min(candidates, key=lambda e: (
                world.ai.brains[e.uid].target != owner.uid,
                not world.spawner.slot_for(e.uid)[0].monster.aggressive,
                max(abs(e.x-owner.x), abs(e.y-owner.y)), e.uid))
        group, slot = world.spawner.slot_for(target.uid)
        before = (owner.ref, owner.x, owner.y, target.ref, target.x, target.y)
        ui = MemoryUi(self)
        director = ui.ptr(ui.base + 0x1807fd8)
        if ui.ptr(director) != ui.base + 0x1237f90:
            raise ValueError('SPELL_CAST_DIRECTOR_TYPE_UNKNOWN')
        size = ui.vec(ui.ptr(director + 0x150) + 0x6c)
        point, projection = world_grid_to_capture(capture,
            dict(map_id=owner.map_id, grid=[owner.x, owner.y]),
            dict(map_id=target.map_id, grid=[target.x, target.y]),
            size, SHOP_PROBES['shop_probe'], len(self.cast_attack_attempts))
        ui.validate()
        if (world.entities.resolve(target.ref) is not target or not target.alive or
                before != (owner.ref, owner.x, owner.y, target.ref, target.x, target.y)):
            raise ValueError('SPELL_CAST_TARGET_OR_CAMERA_ORIGIN_CHANGED')
        now = time.monotonic()
        if not self.cast_attack_attempts:
            self.cast_attack_at = now
            self.cast_attack_deadline = now + 15
            self.cast_hp_before = world.combat.pcs[owner.uid].hp
            self.cast_combat_before = list(magic.events)
        self.cast_target = target.ref
        self.cast_attack_attempts.append(dict(target_ref=target.ref, target_uid=target.uid,
            target_generation=target.generation, target_hp_before=slot.hp,
            owner_uid=owner.uid, owner_position=[owner.map_id, owner.x, owner.y],
            target_position=[target.map_id, target.x, target.y],
            monotonic_seconds=now, template_id=group.monster.template_id,
            group_id=group.spec.group_id, monster=group.monster.name_ko,
            attack_interval_ms=group.monster.attack_interval_ms,
            damage_max=group.monster.damage.max))
        request = dict(request)
        request.pop('locator')
        request.update(schema='local-original-input-request-v1', expected_scene='Land',
                       sequence=getattr(getattr(self, 'private_inputs', None), 'last_sequence', 0)+1,
                       x=point[0], y=point[1], coordinate_space='capture', png_size=capture['png_size'])
        return request, dict(projection, target_uid=target.uid, target_generation=target.generation,
            owner_position=[owner.map_id, owner.x, owner.y], target_position=[target.map_id,target.x,target.y],
            target_template_id=group.monster.template_id, group_id=group.spec.group_id,
            monster=group.monster.name_ko, target_hp_before=slot.hp,
            attack_interval_ms=group.monster.attack_interval_ms,
            attempt=len(self.cast_attack_attempts), capture=capture,
            limitation='PANDORA_EMPIRICAL_BODY_PROJECTION; MONSTER_HITBOX_AND_CAMERA_UNKNOWN',
            ui_result='UNKNOWN', automatic_retry=False)

    def cast_attack_evidence(self):
        world, _, _, owner, _ = self.cast_runtime()
        pc_attacks = [a for a in self.cast_attacks if any(
            a['owner'] == attempt['owner_uid'] and a['target'] == attempt['target_uid']
            and a['monotonic_seconds'] >= attempt['monotonic_seconds']
            for attempt in self.cast_attack_attempts)]
        hp_drops = []
        for attempt in self.cast_attack_attempts:
            found = world.spawner.slot_for(attempt['target_uid'])
            if (found is not None and found[1].uid == attempt['target_uid']
                    and found[1].hp < attempt['target_hp_before']):
                hp_drops.append(dict(target_uid=attempt['target_uid'],
                    target_generation=attempt['target_generation'],
                    before=attempt['target_hp_before'], after=found[1].hp,
                    source='UNKNOWN; NPC_HP_DROP_ALONE_DOES_NOT_PROVE_KNIGHT_SWING'))
        return dict(pc_attacks=pc_attacks, target_hp_drops=hp_drops,
                    owner_position=[owner.map_id, owner.x, owner.y],
                    attempts=[dict(a, target_ref=str(a['target_ref'])) for a in self.cast_attack_attempts])

    def cast_observe(self, phase):
        snapshot = self.cast_snapshot()
        magic = self.cast_runtime()[4]
        events = [e for e in snapshot['events'] if e.get('spell') in magic.rules
                  and e.get('mp_before', 0)-e.get('mp_after', 0) == magic.rules[e['spell']].mp > 0]
        if phase == 'buff':
            matched = [e for e in events if e['spell'] in ('shield','blessed_armor')
                       and e.get('target') == snapshot['actor']]
            ok = {e['spell'] for e in matched} == {'shield','blessed_armor'}
        elif phase == 'heal':
            # CompanionMagic.cast records amount AFTER apply_heal returns its
            # actual clamped HP delta. Include startup events retained before
            # IDLE: a later monster hit/low-HP observation is not required.
            matched = [e for e in events if e['spell'] == 'heal'
                       and e.get('target') == snapshot['owner'] and e.get('amount', 0) > 0]
            ok = bool(matched)
        else:
            attacks = [a for a in self.cast_attacks if a['owner'] == snapshot['owner']
                and a['target'] == self.cast_target.uid and a['monotonic_seconds'] >= self.cast_attack_at]
            matched = [e for e in events if e not in self.cast_combat_before
                and e['spell'] == 'energy_bolt' and e.get('target') == self.cast_target.uid]
            ok = bool(attacks and matched)
        from tools.local_original_session.world_feature_magic import SPELL_DISPLAY
        projection = []
        for event in matched:
            display = SPELL_DISPLAY.get(magic.rules[event['spell']].key)
            frames = [f for f in self.cast_frames if f.get('actual_append')
                      and f.get('recipient') == snapshot['owner']]
            casts = [f for f in frames if display and f.get('opcode') == '0x4E31'
                and f['fields'].get('1') == display['action_id']
                and f['fields'].get('2') == snapshot['actor']
                and f['fields'].get('3') == event['target']]
            graphics = [g['gfx'] for g in display['graphics']
                        if g['field'] == 'castgfx' and g['status'] == 'PRESENT'] if display else []
            effects = [f for f in frames if f.get('opcode') == '0x4ED8'
                and f['fields'].get('1') == event['target'] and f['fields'].get('2') in graphics]
            projection.append(dict(spell=event['spell'], cast_4e31=casts, effects_4ed8=effects,
                projection_result='OBSERVED' if casts and (not graphics or effects) else 'UNKNOWN',
                matching_basis='ACTOR_TARGET_ACTION_AND_GFX; EXACT_EVENT_PACKET_AND_DRAW_FRAME_ORDER_UNKNOWN',
                scope='WORLD_OUTBOX_APPEND_ONLY; SEND_AND_NATIVE_CONSUMPTION_UNKNOWN'))
        return dict(status='OBSERVED' if ok else 'UNKNOWN', phase=phase,
            reason=None if ok else 'SPELL_CAST_%s_NOT_OBSERVED_BY_DEADLINE' % phase.upper(),
            matched_cast_events=matched, packet_projection=projection, server=snapshot,
            scope='SERVER_AUTONOMOUS_CAST_AND_MP_DEBIT_ONLY; CAPTURE_TIMING_AND_NATIVE_ANIMATION_UNKNOWN',
            formal_pass=False, ui_result='UNKNOWN')

    def finish(self, row):
        if self.spell_cast and self.steps[self.index][0] == 'capture':
            requested, completed = getattr(self, 'cap_started', None), time.monotonic()
            row = dict(row, requested_monotonic_seconds=requested, completed_monotonic_seconds=completed,
                packets_in_request_window=[f for f in self.cast_frames if requested is not None
                    and requested <= f.get('monotonic_seconds', 0) <= completed],
                ui_result='UNKNOWN; REQUEST_WINDOW_OVERLAP_DOES_NOT_PROVE_DRAW_FRAME_TIMING', formal_pass=False)
        if self.spell_cast and self.cast_blocked is None and row.get('status') not in ('OBSERVED','POSTED','WAITED','SKIPPED'):
            self.cast_blocked = dict(step=self.steps[self.index][1], reason=row.get('reason'), status=row.get('status'))
        return super().finish(row)

    async def tick(self):
        if not self.spell_cast or self.done:
            return await super().tick()
        step = self.steps[self.index]
        if self.cast_blocked and step[0] != 'capture':
            self.finish(dict(status='SKIPPED', reason='SPELL_CAST_FAILED_PREREQUISITE', prerequisite=self.cast_blocked)); return
        try:
            if self.started is None:
                self.started = time.monotonic()
            if step[0] == 'spell_cast_prepare':
                self.cast_entry_stop = True
                if self.cast_entry_capture is not None:
                    return
                state = self.cast_snapshot()
                if input_route != 'GLFW_CALLBACK_INJECTION' or not state['armor_uid'] or state['level'] != 30 or state['learned_count'] != 38:
                    raise ValueError('SPELL_CAST_GLFW_LEVEL30_LEARNED38_WORN_ARMOR_REQUIRED')
                self.finish(dict(status='OBSERVED', server=state, formal_pass=False)); return
            if step[0] == 'spell_cast_attack_check':
                evidence = self.cast_attack_evidence()
                if evidence['pc_attacks']:
                    matched = evidence['pc_attacks'][0]
                    selected = next(a for a in self.cast_attack_attempts
                        if a['target_uid'] == matched['target'])
                    self.cast_target = selected['target_ref']
                    self.finish(dict(status='OBSERVED', proof_scope='PC_ATTACK_STARTED_AFTER_4E30',
                        attack_evidence=evidence, formal_pass=False)); return
                if evidence['target_hp_drops']:
                    selected = next(a for a in self.cast_attack_attempts
                        if a['target_uid'] == evidence['target_hp_drops'][0]['target_uid'])
                    self.cast_target = selected['target_ref']
                    self.finish(dict(status='OBSERVED', proof_scope='TARGET_HP_DROP_SOURCE_UNKNOWN',
                        attack_evidence=evidence, formal_pass=False)); return
                latest = self.cast_attack_attempts[-1]
                elapsed = time.monotonic() - latest['monotonic_seconds']
                if elapsed < 3 or (elapsed < 5 and evidence['owner_position'] != latest['owner_position']):
                    return  # Give a real approach time to reach the selected monster.
                if (time.monotonic() >= self.cast_attack_deadline
                        or len(self.cast_attack_attempts) >= 3):
                    self.finish(dict(status='UNKNOWN', reason='SPELL_CAST_ATTACK_NOT_OBSERVED_BY_DEADLINE',
                        attack_evidence=evidence, deadline_seconds=15, formal_pass=False)); return
                attempt = len(self.cast_attack_attempts)
                self.steps[self.index+1:self.index+1] = [
                    ('capture', 'spell-cast-before-attack-retry-%d' % attempt),
                    ('private_input', 'spell-cast-knight-attack-retry-%d' % attempt,
                     dict(locator='spell_cast.monster', action='left_click')),
                    ('spell_cast_attack_check', 'spell-cast-attack-check-%d' % attempt)]
                self.finish(dict(status='WAITED', reason='NO_PC_ATTACK_OR_TARGET_HP_DROP',
                    attack_evidence=evidence, retry=attempt, deadline_seconds=15,
                    formal_pass=False)); return
            if step[0] == 'spell_cast_wait':
                phase = step[2]
                deadline = self.cast_deadlines.setdefault(phase, time.monotonic()+step[3])
                row = self.cast_observe(step[2])
                if row['status'] == 'UNKNOWN' and time.monotonic() < deadline:
                    count = self.cast_sample_counts.get(phase, 0)
                    if count < 12 and time.monotonic()-self.started >= 1:
                        self.cast_sample_counts[phase] = count+1
                        self.steps[self.index+1:self.index+1] = [
                            ('capture', 'spell-cast-%s-wait-%02d' % (phase,count)), step]
                        self.finish(dict(status='WAITED', phase=phase,
                            deadline_monotonic_seconds=deadline, scope='CAPTURE_SLOT; CAST_NOT_YET_OBSERVED'))
                    return
                self.finish(dict(row, deadline_seconds=step[3])); return
            return await super().tick()
        except Exception as error:
            self.finish(dict(status='UNKNOWN', reason=str(error)[:300], formal_pass=False, automatic_retry=False))

    def close(self):
        try:
            if self.spell_cast:
                if self.cast_entry_capture is not None:
                    self.cast_entry_capture.close()
                    self.cast_entry_capture = None
                self.results.append(dict(kind='spell_cast_close', frames=self.cast_frames,
                    hits=self.cast_hits, attacks=self.cast_attacks, entry_captures=self.cast_entry_shots, formal_pass=False,
                    ui_result='UNKNOWN; FRAME_AND_SCREENSHOT_TIMING_REQUIRES_REVIEW'))
            super().close()
        finally:
            if self.spell_cast:
                cls, original_poll, poll = self.cast_poll_hook
                if cls.poll is poll:
                    cls.poll = original_poll
                world, original, hook, owned, saved = self.cast_queue_hook
                if world._queue is hook:
                    if owned:
                        world._queue = saved
                    else:
                        delattr(world, '_queue')
                for event, entry in self.cast_event_hooks:
                    world.events.remove(event, entry)


module.Steps = CompanionSpellCastSteps

# Observation only: original SpellLayout input, unchanged spell display producers.
# The screenshot observer is serial. Requested offsets and actual request times
# are both retained; a late PNG is never labelled an exact 200ms draw frame.
_knight_steps = [('knight_prepare', 'knight-skill-preconditions'),
                 ('knight_open', 'knight-original-magic-window'),
                 ('wait', 'knight-magic-window-settle', .5)]
for _knight_key in (89, 90):
    _knight_steps.extend((('knight_ready', 'knight-%d-reuse-ready' % _knight_key, _knight_key),
        ('capture', 'knight-%d-before' % _knight_key),
        ('private_input', 'knight-%d-native-cast' % _knight_key,
         dict(locator='knight.magic.%d' % _knight_key, action='left_double_click'))))
    for _knight_delay in (.2, .6, 1.2):
        _knight_steps.append(('knight_capture', 'knight-%d-after-%03dms' %
            (_knight_key, round(_knight_delay*1000)), _knight_key, _knight_delay))
    _knight_steps.append(('knight_observe', 'knight-%d-server-observe' % _knight_key, _knight_key))
_knight_steps.append(('knight_counter', 'knight-optional-counter-observe'))
module.STEP_SETS['knight_skill_cast'] = tuple(_knight_steps)


class KnightSkillCastSteps(CompanionSpellCastSteps):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.knight_skill = _selected_steps == 'knight_skill_cast'
        if not self.knight_skill:
            return
        from tools.local_original_session.ui_open_commands import UIOpenCommands
        self.knight_ui = UIOpenCommands(self.manual)
        self.knight_frames, self.knight_inputs, self.knight_origins = [], {}, {}
        self.knight_failed_skills = {}
        self.knight_ready_started, self.knight_capture_origins = {}, {}
        self.knight_counter_started = None
        self.knight_blocked = None
        self.knight_pending_key = None
        world = self.manual.inventory_broker._world
        original, owned, saved = world._queue, '_queue' in vars(world), vars(world).get('_queue')

        def queue(recipient, frame):
            count = len(world.outbox.get(recipient, ()))
            result = original(recipient, frame)
            opcode = int.from_bytes(frame[2:4], 'little') if len(frame) >= 6 else None
            if opcode not in (0x4e31, 0x4ed8, 0x4e91):
                return result
            row = dict(opcode='0x%04X' % opcode, recipient=recipient,
                monotonic_seconds=time.monotonic(), pending_skill=self.knight_pending_key)
            try:
                from tools.local_entry_server import protobuf as pb
                with pb.parse_message(frame[4:-2]) as body:
                    row['fields'] = {str(f.number): f.value for f in body.fields if f.wire_type == 0}
                    if opcode == 0x4e91:
                        row['icons'] = []
                        for child in body.occurrences(2):
                            if child.wire_type == 2:
                                with pb.parse_message(bytes(child.value)) as icon:
                                    row['icons'].append({str(f.number): f.value
                                        for f in icon.fields if f.wire_type == 0})
                queued = world.outbox.get(recipient, ())
                row['actual_append'] = len(queued) == count+1 and queued[-1] is frame
                key = self.knight_pending_key
                uid = getattr(self, 'knight_uid', None)
                if (opcode == 0x4e31 and row['actual_append'] and key in (89, 90)
                        and recipient == uid and row['fields'].get('2') == uid
                        and row['fields'].get('3') == uid and row['fields'].get('1') == 19):
                    self.knight_origins.setdefault(key, row['monotonic_seconds'])
            except Exception as error:
                row['reason'] = str(error)[:200]
            self.knight_frames.append(row)
            del self.knight_frames[:-256]
            return result

        world._queue = queue
        self.knight_queue_hook = (world, original, queue, owned, saved)

    def knight_snapshot(self):
        current, _ = module.current_kit(self.manual)
        broker, uid = current[0].broker, current[3].uid
        world, magic = broker._world, broker._world_magic
        pc, state = world.combat.pcs[uid], magic.states.get(uid)
        if state is None:
            raise ValueError('KNIGHT_CURRENT_MAGIC_STATE_REQUIRED')
        return dict(uid=uid, character_class=pc.profile.character_class, level=pc.profile.level,
            hp=pc.hp, max_hp=pc.max_hp, mp=pc.mp, learned=sorted(state.learned),
            buffs=dict(state.buffs), events=[dict(e) for e in broker._world_magic_events
                if e.get('uid') == uid], counter_events=[dict(e) for e in broker._knight_events
                if e.get('uid') == uid], server_errors=list(broker._world_handler_errors))

    def knight_tree(self, label):
        # The broad shop dump in glfw74 recorded only the authored 203 nodes.
        # Scope the same dump to the original layout and its native child vector.
        ui = MemoryUi(self)
        layout = ui.named_layout('SpellLayout')
        if not layout or ui.ptr(layout) != ui.base + 0x12341c8:
            raise ValueError('KNIGHT_ORIGINAL_SPELL_LAYOUT_TYPE_REQUIRED')
        ui.validate()
        return self.shop_tree(label, owned_layout=layout)

    def knight_fixed_spell_point(self, key, tree, ui, layout, root, capture):
        # glfw76: SpellLayout's visible ListviewScroll inner has no child nodes.
        # These are capture pixels measured in that exact 2880x2160 layout.
        fixed = {89: [2685, 700], 90: [2263, 845]}
        if key not in fixed or tree.get('status') != 'OBSERVED':
            raise ValueError('KNIGHT_FIXED_SPELL_TREE_REQUIRED')
        layouts = [row for row in tree.get('layouts', ())
                   if row.get('layout') == layout and row.get('root') == root]
        if len(layouts) != 1:
            raise ValueError('KNIGHT_FIXED_SPELL_LAYOUT_IDENTITY_CHANGED')
        listview = ui.path(root, 'Root.ListviewScroll')
        inners = [node for node in ui.children(listview)
                  if ui.string(node + 0x1a8) == '' and ui.shown(node)]
        if len(inners) != 1:
            raise ValueError('KNIGHT_FIXED_SPELL_INNER_NOT_UNIQUE')
        inner = inners[0]
        recorded = [node for node in layouts[0]['nodes'] if node.get('node') == inner]
        recorded_root = [node for node in layouts[0]['nodes'] if node.get('node') == root]
        if (len(recorded) != 1 or len(recorded_root) != 1
                or recorded[0].get('children') != []
                or ui.children(inner) or ui.spell_children(inner)):
            raise ValueError('KNIGHT_FIXED_SPELL_NATIVE_ROWS_NOW_PRESENT_OR_UNOBSERVED')
        _, window_facts = ui.node_point(root, 'knight.magic.window', layout)
        _, inner_facts = ui.node_point(inner, 'knight.magic.inner', layout)
        window = window_facts['scene_bounds']
        viewport = inner_facts['scene_bounds']
        if (tuple(window.get(field) for field in ('left', 'bottom', 'right', 'top'))
                != (899.0, 380.0, 1279.0, 960.0)
                or tuple(viewport.get(field) for field in ('left', 'bottom', 'right', 'top'))
                != (975.0, 429.0, 1223.0, 925.0)
                or window.get('visible') is not True or viewport.get('visible') is not True
                or recorded_root[0].get('scene_bounds') != window
                or recorded[0].get('scene_bounds') != viewport):
            raise ValueError('KNIGHT_FIXED_SPELL_SCENE_BOUNDS_CHANGED')
        point = fixed[key]
        if not all(rect[0] < point[0] < rect[2] and rect[1] < point[1] < rect[3]
                   for rect in (window_facts['capture_rect'], inner_facts['capture_rect'])):
            raise ValueError('KNIGHT_FIXED_SPELL_POINT_OUTSIDE_OBSERVED_WINDOW')
        return point, dict(locator='knight.magic.%d' % key, layout=layout, root=root,
            listview=listview, inner=inner, window_scene_bounds=window,
            inner_scene_bounds=viewport, capture_rect=inner_facts['capture_rect'],
            coordinate_basis='capture_to_client',
            point_basis='GLFW76_4_COLUMN_ROW5_COL4_89_ROW6_COL1_90',
            native_slot=None, ui_result='UNKNOWN; SERVER_CAST_REQUIRED')

    def resolve_request(self, request):
        if not self.knight_skill or not str(request.get('locator', '')).startswith('knight.magic.'):
            return super().resolve_request(request)
        key = int(request['locator'].rsplit('.', 1)[1])
        capture = self.last_capture_context
        if not capture or self.results[-1].get('kind') != 'capture' or self.results[-1].get('status') != 'OBSERVED':
            raise ValueError('KNIGHT_IMMEDIATELY_PRECEDING_CAPTURE_REQUIRED')
        if (capture['png_size'] != [2880, 2160] or capture['read_size'] != [3840, 2160]
                or capture['crop'] != [480, 0, 2880, 2160]):
            raise ValueError('KNIGHT_ESTABLISHED_CAPTURE_GEOMETRY_REQUIRED')
        from tools.local_original_session.world_feature_companion_ats import _ats_window_spell_catalog
        expected = _ats_window_spell_catalog(self.manual.inventory_broker).get(key)
        if expected is None:
            raise ValueError('KNIGHT_FIXED_CLIENT_KEY_TO_NATIVE_ROW_MAPPING_UNKNOWN:%d' % key)
        tree = self.knight_tree('knight-%d-before-native-cast-tree' % key)
        ui = MemoryUi(self)
        layout = ui.named_layout('SpellLayout')
        if not layout or ui.ptr(layout) != ui.base + 0x12341c8:
            raise ValueError('KNIGHT_ORIGINAL_SPELL_LAYOUT_TYPE_REQUIRED')
        root = ui.ptr(layout + 0x30)
        if not ui.shown(root):
            raise ValueError('KNIGHT_ORIGINAL_SPELL_WINDOW_NOT_SHOWN')
        rows = ui.spell_rows(layout)
        # The catalog joins the fixed client's key to row/icon. A hidden page
        # or retained copy can carry the same metadata: require the current
        # panel and icon to be shown, sized and backed by a drawable texture.
        candidates, rejected = [], []
        for row in rows:
            if (row['kind'] != 1 or not (row['spell_row'] == expected['spell_row']
                    or row['icon'] == expected['icon'])
                    or row['name'] and row['name'] != expected['name']):
                continue
            try:
                node = row['node']
                panel, icon_node = ui.ptr(node + 0x830), ui.ptr(node + 0x820)
                if (not panel or not icon_node or not ui.descendant(panel, root)
                        or not ui.descendant(icon_node, root)
                        or not ui.shown(node) or not ui.shown(panel) or not ui.shown(icon_node)
                        or any(value <= 0 for value in ui.vec(panel + 0x6c))
                        or any(value <= 0 for value in ui.vec(icon_node + 0x6c))):
                    raise ValueError('KNIGHT_SPELL_PANEL_OR_ICON_NOT_VISIBLE')
                renderer = ui.ptr(icon_node + 0x720)
                texture = ui.ptr(renderer + 0x3b8) if renderer else 0
                draw_handle = ui.ptr(texture + 0x20) if texture else 0
                if not draw_handle:
                    raise ValueError('KNIGHT_SPELL_ICON_TEXTURE_NOT_DRAWABLE')
                point, facts = ui.node_point(panel, request['locator'], layout)
                if not self.ats_spell_bounds_valid(facts['scene_bounds']):
                    raise ValueError('KNIGHT_SPELL_VISIBLE_PANEL_BOUNDS_REQUIRED')
                candidates.append(dict(row=row, panel=panel, icon_node=icon_node,
                    texture=texture, texture_draw_handle=draw_handle,
                    point=point, facts=facts))
            except (ValueError, OSError) as error:
                rejected.append(dict(row=row, reason=str(error)[:160]))
        fixed_error = None
        if not rows and not candidates:
            try:
                point, facts = self.knight_fixed_spell_point(key, tree, ui, layout, root, capture)
                slot = None
            except ValueError as error:
                fixed_error = str(error)
        self.shop_write('knight-%d-native-spell-rows' % key,
            dict(expected=expected, rows=rows, candidates=candidates, rejected=rejected,
                 layout=layout, root=root, capture=capture,
                 fixed_capture_point=(point if not rows and not candidates and fixed_error is None else None),
                 fixed_refusal=fixed_error,
                 scope='VISIBLE_NATIVE_ROW_OR_EXACT_GLFW76_LAYOUT_CAPTURE_POINT; SERVER_CAST_REQUIRED'))
        if fixed_error:
            raise ValueError(fixed_error)
        if rows or candidates:
            if len(candidates) != 1:
                raise ValueError('KNIGHT_VISIBLE_NATIVE_SKILL_ROW_NOT_UNIQUE:%d; TREE=%s' %
                                 (key, tree['tree_file']))
            selected = candidates[0]
            slot, point, facts = selected['row'], selected['point'], selected['facts']
        ui.validate()
        self.knight_pending_key = key
        self.knight_inputs[key] = time.monotonic()
        value = dict(request)
        value.pop('locator')
        value.update(schema='local-original-input-request-v1', expected_scene='Land',
            sequence=getattr(getattr(self, 'private_inputs', None), 'last_sequence', 0)+1,
            x=point[0], y=point[1], coordinate_space='capture', png_size=capture['png_size'])
        return value, dict(facts, locator=request['locator'], skill_key=key, native_slot=slot,
            expected=expected, capture=capture, tree_file=tree['tree_file'], automatic_retry=False,
            binding_basis=('GLFW76_FIXED_CAPTURE_POINT_EXACT_LAYOUT' if slot is None else
                           'CONFIRMED_FIXED_CLIENT_CATALOG_AND_UNIQUE_LIVE_KIND_ROW_ICON_NAME'),
            input_scope='ORIGINAL_SPELL_WINDOW_DOUBLE_CLICK; CAST_UNCONFIRMED', formal_pass=False)

    def knight_observe(self, key):
        snapshot = self.knight_snapshot()
        origin = self.knight_inputs.get(key)
        frames = [f for f in self.knight_frames if f.get('actual_append')
                  and f['recipient'] == snapshot['uid'] and origin is not None
                  and f['monotonic_seconds'] >= origin]
        casts = [f for f in frames if f['opcode'] == '0x4E31'
                 and f['fields'].get('1') == 19 and f['fields'].get('2') == snapshot['uid']
                 and f['fields'].get('3') == snapshot['uid']]
        effects = [f for f in frames if f['opcode'] == '0x4ED8'
                   and f['fields'].get('1') == snapshot['uid']
                   and f['fields'].get('2') == {89: 5831, 90: 5832}[key]]
        icons = [f for f in frames if f['opcode'] == '0x4E91'
                 and f['fields'].get('1') == 1 and any(
                     r.get('4') == {89: 20161, 90: 20479}[key] for r in f.get('icons', ()))]
        all_events = [e for e in snapshot['events'] if e.get('key') == key
                      and e not in self.knight_before_events]
        cost = self.manual.inventory_broker._world_magic.spells[key].mp
        events = [e for e in all_events if e.get('outcome') == 'cast'
                  and e.get('target') == snapshot['uid']
                  and e.get('mp_before', 0)-e.get('mp_after', 0) == cost > 0]
        # Require the server event and actual queued projections. A rendered
        # effect is not required: Counter Barrier may have no visible animation.
        observed = bool(events and casts and effects and icons)
        return dict(status='OBSERVED' if observed else 'UNKNOWN',
            reason=None if observed else 'KNIGHT_CAST_OR_SERVER_PACKET_PROJECTION_NOT_OBSERVED',
            skill_key=key, server_cast_events=events, all_new_skill_events=all_events,
            cast_4e31=casts, gfx_4ed8=effects,
            buff_icon_4e91=icons, server=snapshot, ui_result='UNKNOWN; PNG_REQUIRES_VISUAL_REVIEW',
            scope='ORIGINAL_UI_REQUEST_AND_SERVER_EVENT_OUTBOX_APPEND; SEND_NATIVE_CONSUMPTION_AND_EFFECT_VISIBILITY_UNKNOWN',
            formal_pass=False)

    def finish(self, row):
        if not self.knight_skill:
            return super().finish(row)
        step = self.steps[self.index]
        row = dict(row, formal_pass=False, ui_result='UNKNOWN; PNG_REQUIRES_VISUAL_REVIEW')
        if step[0] in ('capture', 'knight_capture'):
            requested, completed = getattr(self, 'cap_started', None), time.monotonic()
            if requested is not None and self.started is not None and requested < self.started:
                requested = None  # A missing cast never requested this slot's PNG.
            row.update(requested_monotonic_seconds=requested, completed_monotonic_seconds=completed,
                packets_in_request_window=[f for f in self.knight_frames if requested is not None
                    and requested <= f['monotonic_seconds'] <= completed],
                observed_packets=list(self.knight_frames))
            if step[0] == 'knight_capture':
                timing = self.knight_capture_origins.get(step[1], {})
                origin = timing.get('cast_origin')
                schedule_origin = timing.get('schedule_origin')
                row.update(skill_key=step[2], requested_offset_seconds=step[3], cast_4e31_origin=origin,
                    schedule_origin_monotonic_seconds=schedule_origin,
                    schedule_basis='ACTUAL_SELF_CAST_4E31' if origin is not None else 'NATIVE_INPUT_ATTEMPT_CAST_UNCONFIRMED',
                    actual_request_offset_seconds=None if requested is None or schedule_origin is None else requested-schedule_origin,
                    timing_scope='SERIAL_REQUEST_TIMES; EXACT_NATIVE_DRAW_FRAME_AT_OFFSET_UNKNOWN')
            if row.get('status') == 'OBSERVED':
                from PIL import Image
                destination = Path(row['png'])
                with Image.open(destination) as image:
                    width, height = image.size
                    box = [round(width*.65), 0, width, round(height*.35)]
                    crop = destination.with_name(destination.stem+'-buff-top-right.png')
                    image.crop(box).save(crop)
                    enlarged = destination.with_name(destination.stem+'-buff-top-right-2x.png')
                    region = image.crop(box)
                    region.resize((region.width*2, region.height*2), Image.Resampling.NEAREST).save(enlarged)
                row['buff_icon_crop'] = dict(png=str(crop), box=box,
                    enlarged_png=str(enlarged), enlargement=2,
                    scope='BROAD_UPPER_RIGHT_QA_REGION; ICON_VISIBILITY_UNJUDGED; NEVER_INPUT_GEOMETRY')
        if row.get('status') not in ('OBSERVED', 'POSTED', 'WAITED', 'SKIPPED'):
            failure = dict(step=step[1], reason=row.get('reason'), status=row.get('status'))
            if self.knight_blocked is None and step[0] in ('knight_prepare', 'knight_open'):
                self.knight_blocked = failure
            if step[0] == 'private_input':
                self.knight_failed_skills[int(step[2]['locator'].rsplit('.', 1)[1])] = failure
            elif step[0] == 'knight_ready':
                self.knight_failed_skills[step[2]] = failure
        return super().finish(row)

    async def tick(self):
        if not self.knight_skill or self.done:
            return await super().tick()
        step = self.steps[self.index]
        if self.knight_blocked and step[0] != 'capture':
            self.finish(dict(status='SKIPPED', reason='KNIGHT_FAILED_PREREQUISITE', prerequisite=self.knight_blocked))
            return
        try:
            if self.started is None:
                self.started = time.monotonic()
            if step[0] == 'knight_prepare':
                from tools.local_original_session.world_feature_knight_skills import _equipment
                state = self.knight_snapshot()
                self.knight_uid = state['uid']
                broker = self.manual.inventory_broker
                if (input_route != 'GLFW_CALLBACK_INJECTION' or state['character_class'] != 1
                        or state['level'] < 50 or not {89, 90}.issubset(state['learned'])
                        or state['mp'] < 15 or state['hp'] <= 130
                        or _equipment(broker.realm._world_context, state['uid']) is None):
                    raise ValueError('KNIGHT_GLFW_LEVEL50_LEARNED89_90_MP15_HP131_WORN_TWOHAND_REQUIRED')
                self.knight_before_events = list(state['events'])
                self.knight_counter_before = list(state['counter_events'])
                self.finish(dict(status='OBSERVED', server=state)); return
            if step[0] == 'knight_open':
                if self.knight_ui.pending is None:
                    if self.busy():
                        return
                    if not await self.knight_ui.request('open_magic_window'):
                        return
                result = self.knight_ui.collect()
                if result['status'] == 'PENDING':
                    return
                self.finish(dict(status='OBSERVED' if result['status'] == 'RETURNED' else 'UNKNOWN',
                    original_callback=result, scope='ORIGINAL_TOGGLE_RETURN_ONLY; WINDOW_CHECK_FOLLOWS')); return
            if step[0] == 'knight_ready':
                broker = self.manual.inventory_broker
                state = broker._world_magic.states[self.knight_uid]
                ready_started = self.knight_ready_started.setdefault(step[2], time.monotonic())
                if broker._world.runtime.clock() < state.next_cast_at:
                    if time.monotonic()-ready_started < 10:
                        return
                    self.finish(dict(status='UNKNOWN', reason='KNIGHT_CURRENT_REUSE_NOT_READY_BY_DEADLINE')); return
                self.finish(dict(status='OBSERVED', skill_key=step[2], next_cast_at=state.next_cast_at,
                    basis='CURRENT_PRODUCT_MAGIC_REUSE_DEADLINE')); return
            if step[0] == 'knight_capture':
                if step[2] in self.knight_failed_skills and step[2] not in self.knight_inputs:
                    self.finish(dict(status='SKIPPED', prerequisite=self.knight_failed_skills[step[2]],
                        reason='THIS_SKILL_NATIVE_INPUT_NOT_POSTED')); return
                origin = self.knight_origins.get(step[2], self.knight_inputs.get(step[2]))
                if origin is None:
                    self.finish(dict(status='UNKNOWN', reason='KNIGHT_NATIVE_INPUT_ATTEMPT_NOT_OBSERVED')); return
                if time.monotonic() < origin+step[3]:
                    return
                if self.capture is None and not self.busy():
                    self.knight_capture_origins[step[1]] = dict(schedule_origin=origin,
                        cast_origin=self.knight_origins.get(step[2]))
                await self.do_capture(step[1]); return
            if step[0] == 'knight_observe':
                self.finish(self.knight_observe(step[2])); return
            if step[0] == 'knight_counter':
                seconds = float(os.environ.get('VERIFY_KNIGHT_COUNTER_SECONDS', '0'))
                if not 0 <= seconds <= 30:
                    raise ValueError('KNIGHT_OPTIONAL_COUNTER_SECONDS_0_TO_30_REQUIRED')
                if self.knight_counter_started is None:
                    self.knight_counter_started = time.monotonic()
                state = self.knight_snapshot()
                events = [e for e in state['counter_events'] if e not in self.knight_counter_before
                          and e.get('kind') == 'counter']
                if seconds == 0:
                    self.finish(dict(status='SKIPPED', reason='OPTIONAL_LIVE_COUNTER_OBSERVATION_NOT_REQUESTED')); return
                if not events and time.monotonic()-self.knight_counter_started < seconds:
                    return
                if events:
                    self.steps[self.index+1:self.index+1] = [('capture', 'knight-live-counter-reaction')]
                self.finish(dict(status='OBSERVED' if events else 'UNKNOWN', counter_events=events,
                    reason=None if events else 'NO_NATURAL_COUNTER_EVENT_BY_DEADLINE',
                    scope='ACTUAL_NPC_PHYSICAL_SWING_COUNTER_EVENT; NO_SYNTHETIC_HIT_OR_COUNTER')); return
            if step[0] == 'private_input':
                key = int(step[2]['locator'].rsplit('.', 1)[1])
                if key in self.knight_failed_skills:
                    self.finish(dict(status='SKIPPED', reason='THIS_SKILL_REUSE_PREREQUISITE_FAILED',
                        prerequisite=self.knight_failed_skills[key])); return
            return await super().tick()
        except Exception as error:
            if self.capture is not None:
                self.capture.close(); self.capture = None
            self.finish(dict(status='UNKNOWN', reason=str(error)[:400], automatic_retry=False))

    def close(self):
        if not self.knight_skill:
            return super().close()
        try:
            if self.capture is not None:
                self.capture.close(); self.capture = None
            self.knight_ui.close()
            self.results.append(dict(kind='knight_skill_close', frames=self.knight_frames,
                input_started_monotonic_seconds=self.knight_inputs,
                self_cast_4e31_monotonic_seconds=self.knight_origins,
                blocked=self.knight_blocked, failed_skills=self.knight_failed_skills,
                formal_pass=False, ui_result='UNKNOWN'))
            return super().close()
        finally:
            world, original, hook, owned, saved = self.knight_queue_hook
            if world._queue is hook:
                if owned:
                    world._queue = saved
                else:
                    delattr(world, '_queue')


module.STEP_SETS['pet_window_toggle'] = (
    ('pet_toggle_prepare', 'pet-toggle-preconditions'),
    ('capture', 'pet-toggle-initially-closed'),
    ('private_input', 'pet-toggle-ctrl-e-open', dict(locator='pet_toggle.key', action='key_press', key='Ctrl+E')),
    ('pet_toggle_observe', 'pet-toggle-open-observed', 'open'),
    ('capture', 'pet-toggle-original-menu-open'),
    ('private_input', 'pet-toggle-native-hold-row', dict(locator='pet_toggle.hold', action='left_click')),
    ('pet_toggle_hold', 'pet-toggle-server-hold-observed'),
    ('capture', 'pet-toggle-held-menu-before-close'),
    ('private_input', 'pet-toggle-ctrl-e-close', dict(locator='pet_toggle.key', action='key_press', key='Ctrl+E')),
    ('pet_toggle_observe', 'pet-toggle-close-observed', 'closed'),
    ('pet_toggle_move', 'pet-toggle-owner-move-away', 'away'),
    ('pet_toggle_remote', 'pet-toggle-remote-preconditions'),
    ('capture', 'pet-toggle-remote-before-key'),
    ('private_input', 'pet-toggle-remote-ctrl-e-open', dict(locator='pet_toggle.key', action='key_press', key='Ctrl+E')),
    ('pet_toggle_observe', 'pet-toggle-remote-open-observed', 'remote_open'),
    ('capture', 'pet-toggle-remote-menu-open'),
    ('private_input', 'pet-toggle-remote-ctrl-e-close', dict(locator='pet_toggle.key', action='key_press', key='Ctrl+E')),
    ('pet_toggle_observe', 'pet-toggle-remote-close-observed', 'remote_closed'),
    ('pet_toggle_move', 'pet-toggle-owner-return-for-click', 'return'),
    ('capture', 'pet-toggle-before-companion-click'),
    ('private_input', 'pet-toggle-companion-click', dict(locator='pet_toggle.companion', action='left_click')),
    ('pet_toggle_observe', 'pet-toggle-click-remains-closed', 'click_closed'),
    ('capture', 'pet-toggle-after-companion-click'))


if (_selected_steps == 'pet_window_toggle'
        and os.environ.get('VERIFY_PET_NATIVE_CLICK_MOVE') == '1'):
    _pet_click_steps = []
    for _step in module.STEP_SETS['pet_window_toggle']:
        if _step[0] != 'pet_toggle_move':
            _pet_click_steps.append(_step)
            continue
        _direction = _step[2]
        for _hop in range(3):
            _name = 'pet-native-' + _direction + '-%d' % _hop
            _pet_click_steps += [('capture', 'before-' + _name),
                ('private_input', _name, dict(locator='pet_toggle.move_' + _direction, action='left_click')),
                ('pet_toggle_click_move_observe', _name + '-consumed', _direction),
                ('capture', 'after-' + _name)]
    module.STEP_SETS['pet_window_toggle'] = tuple(_pet_click_steps)


class PetWindowToggleSteps(KnightSkillCastSteps):
    """Independent input/visibility experiment; never opens a menu by bridge command."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pet_toggle = _selected_steps == 'pet_window_toggle'
        self.pet_toggle_blocked = None
        self.pet_toggle_observed = set()
        self.pet_toggle_ingress = []
        self.pet_toggle_attack_hook = None
        self.pet_toggle_trail = []
        self.pet_toggle_move_pending = None
        self.pet_toggle_actor_clicks = 0

    def pet_toggle_watch_attack(self):
        broker = self.broker()
        original = broker._world_attack
        owned, saved = '_world_attack' in vars(broker), vars(broker).get('_world_attack')
        async def attack(*args, **kwargs):
            from tools.local_entry_server import protobuf as pb
            frame = args[3] if len(args) > 3 else kwargs.get('frame')
            entry = dict(monotonic_seconds=time.monotonic(), opcode='0x4E30')
            try:
                with pb.parse_message(frame.payload) as body:
                    entry['target_uid'] = next((f.value for f in body.fields
                        if f.number == 1 and f.wire_type == 0), None)
            except Exception as error:
                entry['decode_reason'] = str(error)[:160]
            self.pet_toggle_ingress.append(entry)
            del self.pet_toggle_ingress[:-32]
            result = await original(*args, **kwargs)
            entry['handler_return'] = result
            return result
        broker._world_attack = attack
        self.pet_toggle_attack_hook = (broker, original, attack, owned, saved)

    def pet_toggle_actor(self):
        current, _ = module.current_kit(self.manual)
        world, owner_uid = self.broker()._world, current[3].uid
        actors = [a for a in world.companions.active.values() if a.owner_ref.uid == owner_uid]
        if len(actors) != 1:
            raise ValueError('PET_TOGGLE_ONE_CURRENT_OWNED_COMPANION_REQUIRED')
        actor = actors[0]
        owner, entity = world.entities.resolve(actor.owner_ref), world.entities.resolve(actor.ref)
        if owner is None or entity is None or not owner.alive or not entity.alive:
            raise ValueError('PET_TOGGLE_CURRENT_LIVING_OWNER_AND_COMPANION_REQUIRED')
        name = self.broker()._companion_rows[actor.character_id]['name']
        if name != 'SoloMage':
            raise ValueError('PET_TOGGLE_SOLOMAGE_REQUIRED')
        if hasattr(self, 'actor_uid') and actor.ref.uid != self.actor_uid:
            raise ValueError('PET_TOGGLE_COMPANION_CHANGED')
        return actor, owner, entity

    def pet_toggle_position(self):
        actor, owner, entity = self.pet_toggle_actor()
        scene = self.scene()
        if (scene.get('status') != 'OBSERVED' or scene.get('current') != 'Land'
                or scene.get('pending') != 'none' or scene.get('root_ready') is not True):
            raise ValueError('PET_TOGGLE_CURRENT_LAND_SCENE_UNKNOWN')
        current, _ = module.current_kit(self.manual)
        position = current[3]
        if (position.uid != owner.uid or position.map_id != owner.map_id
                or (position.word0, position.word1) != (owner.x, owner.y)
                or entity.map_id != owner.map_id):
            raise ValueError('PET_TOGGLE_CURRENT_SERVER_POSITION_DISAGREEMENT')
        return dict(owner=[owner.map_id, owner.x, owner.y],
            companion=[entity.map_id, entity.x, entity.y],
            distance_grid=max(abs(entity.x-owner.x), abs(entity.y-owner.y)),
            owner_displacement=max(abs(owner.x-self.pet_toggle_origin[1]),
                                   abs(owner.y-self.pet_toggle_origin[2])),
            movement_mode=actor.record.movement_mode, scene=scene,
            actor_click_requests=self.pet_toggle_actor_clicks,
            companion_outside_screen='UNKNOWN; GRID_DISTANCE_IS_NOT_VISIBILITY_PROOF')

    def pet_toggle_move(self, direction):
        # Reuse the existing public MoveGoal producer and native consumer;
        # coordinates come from its live collision-neighbor reader, never PNGs.
        from tools.local_original_session import commands
        if self.started is None:
            self.started = time.monotonic()
        state = self.pet_toggle_position()
        if self.pet_toggle_move_pending is not None:
            pending = self.pet_toggle_move_pending
            result = self.manual.last_result
            if result.get('sequence') == pending['sequence']:
                if result.get('status') == 'UNKNOWN' or result.get('cleanup_required'):
                    raise ValueError('PET_TOGGLE_MOVE_CONSUMER_UNKNOWN:' + str(result.get('reason')))
                if result.get('status') == 'COMMITTED':
                    current, _ = module.current_kit(self.manual)
                    if ([current[3].word0, current[3].word1] != pending['target']
                            or current[2].committed != pending['before_commits'] + 1):
                        raise ValueError('PET_TOGGLE_MOVE_COMMITTED_POSITION_MISMATCH')
                    if direction == 'away':
                        self.pet_toggle_trail.append(pending['origin'])
                    else:
                        self.pet_toggle_trail.pop()
                    self.pet_toggle_move_pending = None
                    self.pet_toggle_moves_done += 1
                    self.started = time.monotonic()
            if self.pet_toggle_move_pending is not None:
                if time.monotonic()-self.started >= 15:
                    raise ValueError('PET_TOGGLE_MOVE_COMMIT_DEADLINE')
                return
        if (direction == 'away' and self.pet_toggle_moves_done >= 12
                or direction == 'return' and not self.pet_toggle_trail):
            self.finish(dict(status='OBSERVED', direction=direction,
                native_move_commits=self.pet_toggle_moves_done, position=state,
                basis='EXISTING_PUBLIC_MOVEGOAL_NATIVE_CONSUMER_COMMITTED', formal_pass=False))
            self.pet_toggle_moves_done = 0
            return
        if self.busy():
            return
        if not self.manual.allow_move:
            raise ValueError('PET_TOGGLE_EXISTING_NATIVE_MOVEGOAL_NOT_ENABLED')
        current, _ = module.current_kit(self.manual)
        position, proof = current[3], self.broker().realm.edge_passability
        neighbors = proof.tile_neighbors(position.uid, position.map_id, position.packed)
        if (neighbors.get('status') not in ('OBSERVED', 'OBSERVED_PARTIAL')
                or neighbors.get('stable_double_read') is not True
                or neighbors.get('uid') != position.uid or neighbors.get('map_id') != position.map_id
                or neighbors.get('start_grid') != [position.word0, position.word1]):
            raise ValueError('PET_TOGGLE_LIVE_NATIVE_MOVEMENT_NEIGHBORS_UNKNOWN:' + str({k: neighbors.get(k) for k in ('status','reason','stable_double_read','uid','map_id','start_grid')}))
        choices = [r['grid_target'] for r in neighbors['directions']
            if r.get('status') == 'OBSERVED' and r.get('blocked') is False]
        if direction == 'return':
            target = self.pet_toggle_trail[-1]
            if target not in choices:
                raise ValueError('PET_TOGGLE_RETURN_EDGE_NOT_CURRENTLY_CLEAR')
        else:
            # Prefer monotonically farther cells from the held companion.
            companion = state['companion'][1:]
            distance = lambda grid: max(abs(grid[0]-companion[0]), abs(grid[1]-companion[1]))
            choices = [g for g in choices if distance(g) > state['distance_grid']]
            if not choices:
                raise ValueError('PET_TOGGLE_NO_CLEAR_EDGE_AWAY_FROM_COMPANION')
            target = max(choices, key=lambda g: (distance(g), abs(sum(g)-sum(companion))))
        self.consumer.reader.validate()
        fresh, _ = module.current_kit(self.manual)
        if fresh[3] is not position or self.pet_toggle_position() != state:
            raise ValueError('PET_TOGGLE_MOVE_AUTHORITY_CHANGED')
        sequence = self.manual.sequence + 1
        self.pet_toggle_move_pending = dict(sequence=sequence, target=list(target),
            origin=[position.word0, position.word1], before_commits=current[2].committed)
        commands._atomic(self.manual.directory / 'command.request.json',
            dict(schema=commands.REQUEST_SCHEMA, sequence=sequence, command='MoveGoal',
                 uid=position.uid, x=target[0], y=target[1]), 1024)

    def pet_toggle_windows(self):
        ui = MemoryUi(self)
        menus = []
        for layout in dict.fromkeys(ui.layouts()):
            if ui.ptr(layout) != ui.base + 0x122b6c0:
                continue
            root = ui.ptr(layout + 0x30)
            shown = bool(root and ui.shown(root))
            item = dict(layout=layout, root=root, actor=ui.ptr(layout + 0xb8), shown=shown)
            if shown:
                # The existing bridge renders follow/wait in one Dismiss row;
                # Rest is hidden. These seven authored rows identify the pet
                # menu separately from the companion ATS settings window.
                list_view = ui.path(root, 'Root.Pet_Main.ListviewScroll.ListView')
                _, viewport_facts = ui.node_point(list_view, 'pet_toggle.viewport',
                                                  layout, require_capture=False)
                viewport = viewport_facts['scene_bounds']
                inner = ui.ptr(list_view + 0xce0)
                if not inner or not ui.descendant(inner, list_view):
                    raise ValueError('PET_TOGGLE_CURRENT_LIST_INNER_REQUIRED')
                pending, visited, descendants = [(list_view, 0), (inner, 0)], set(), []
                while pending:
                    node, depth = pending.pop()
                    if node in visited:
                        continue
                    visited.add(node)
                    descendants.append(node)
                    if depth < 6:
                        pending.extend((child, depth + 1) for child in ui.spell_children(node))
                def displayed_row(name):
                    matches, candidates = [], []
                    for node in descendants:
                        if ui.string(node + 0x1a8) != name or not ui.shown(node):
                            continue
                        _, facts = ui.node_point(node, 'pet_toggle.' + name, layout, require_capture=False)
                        bounds = facts['scene_bounds']
                        contained = (bounds['visible']
                            and viewport['left'] <= bounds['left'] < bounds['right'] <= viewport['right']
                            and viewport['bottom'] <= bounds['bottom'] < bounds['top'] <= viewport['top'])
                        candidates.append((node, bounds, contained))
                        if contained:
                            matches.append(node)
                    if len(matches) != 1:
                        self.shop_tree('pet-toggle-menu-tree', owned_layout=layout,
                            trigger=dict(row=name, candidates=candidates,
                                         descendants=len(descendants)))
                        raise ValueError('PET_TOGGLE_VISIBLE_ROW_NOT_UNIQUE:' + name
                                         + ':matches=' + str(len(matches))
                                         + ':descendants=' + str(len(descendants)))
                    return matches[0]
                item['menu_nodes'] = {name: displayed_row(name) for name in PET_NAMES}
                item['viewport_scene_bounds'] = viewport
                item['title_nodes'] = [node for node in descendants if ui.string(node + 0x1a8) == 'Tx_Pet' and ui.shown(node)]
            menus.append(item)
        ats = {}
        for key in ('ATSLayout', 'SLCompATS'):
            layout = ui.named_layout(key)
            ats[key] = bool(layout and ui.shown(ui.ptr(layout + 0x30)))
        ui.validate()
        return dict(pet_menus=menus, ats_windows=ats)

    def resolve_request(self, request):
        if not self.pet_toggle or not request.get('locator', '').startswith('pet_toggle.'):
            return super().resolve_request(request)
        capture = getattr(self, 'last_capture_context', None)
        if (not capture or self.results[-1].get('kind') != 'capture'
                or self.results[-1].get('status') != 'OBSERVED'):
            raise ValueError('PET_TOGGLE_IMMEDIATELY_PRECEDING_CAPTURE_REQUIRED')
        actor, owner, entity = self.pet_toggle_actor()
        request = dict(request)
        locator = request.pop('locator')
        request.update(schema='local-original-input-request-v1', expected_scene='Land',
            sequence=getattr(getattr(self, 'private_inputs', None), 'last_sequence', 0)+1)
        if locator == 'pet_toggle.key':
            self.pet_toggle_key_before = self.callback_rows()
            self.pet_toggle_key_signals_before = self.server_signals()
            return request, dict(locator=locator, actor=actor.ref.uid,
                position=self.pet_toggle_position(),
                basis='OWNED_GLFW_CONTROL_E_CALLBACK_SEQUENCE')
        if locator in ('pet_toggle.move_away', 'pet_toggle.move_return'):
            state = self.pet_toggle_position()
            if locator.endswith('away'):
                targets = [[owner.x+dx, owner.y+dy] for dx,dy in ((4,4),(4,-4),(-4,4),(-4,-4))]
                targets.sort(key=lambda grid: max(abs(grid[0]-entity.x), abs(grid[1]-entity.y)), reverse=True)
            else:
                def toward(now, goal):
                    return now + max(-4, min(4, goal-now))
                targets = [[toward(owner.x,self.pet_toggle_origin[1]), toward(owner.y,self.pet_toggle_origin[2])]]
            target = next((grid for grid in targets if self.broker()._world.terrain.can_stand(owner.map_id,*grid) is True), None)
            if target is None:
                raise ValueError('PET_TOGGLE_CURRENT_NATIVE_CLICK_TERRAIN_TARGET_UNKNOWN')
            ui = MemoryUi(self)
            director = ui.ptr(ui.base + 0x1807fd8)
            size = ui.vec(ui.ptr(director + 0x150) + 0x6c)
            point, facts = world_grid_to_capture(capture,
                dict(map_id=owner.map_id, grid=[owner.x,owner.y]),
                dict(map_id=owner.map_id, grid=target), size, SHOP_PROBES['shop_probe'])
            ui.validate()
            self.pet_click_move_before = state
            self.pet_click_move_counters = module.current_kit(self.manual)[0][2].committed
            request.update(x=point[0], y=point[1], coordinate_space='capture', png_size=capture['png_size'])
            return request, dict(facts, before=state, target=target,
                route='EXISTING_OWNED_GLFW_WORLD_CLICK; NATIVE_PATH_AND_SERVER_MOVE_UNCHANGED')
        if locator == 'pet_toggle.hold':
            shown = [p for p in self.pet_toggle_windows()['pet_menus'] if p['shown']]
            if len(shown) != 1 or shown[0]['actor'] != self.actor_uid:
                raise ValueError('PET_TOGGLE_OWNED_VISIBLE_MENU_REQUIRED_FOR_HOLD')
            self.pet_toggle_hold_before = self.server_signals()
            ui = MemoryUi(self)
            node = shown[0]['menu_nodes']['Dismiss']
            # Snapshot/InstallPetCallbacks preserve native touch at +3EC and
            # install the live movement std::function at +4F0 (+38 callable).
            # A visible decoration is not a valid native hold action.
            callback = ui.ptr(node + 0x528)
            if ui.read(node + 0x3ec, 1) != b'\x01' or not callback:
                raise ValueError('PET_TOGGLE_NATIVE_HOLD_ROW_NOT_ACTIONABLE')
            point, facts = ui.node_point(node, locator, shown[0]['layout'])
            ui.validate()
            request.update(x=point[0], y=point[1], coordinate_space='capture', png_size=capture['png_size'])
            return request, dict(facts, locator=locator, actor=actor.ref.uid,
                touch_enabled=True, callback=callback,
                viewport_scene_bounds=shown[0]['viewport_scene_bounds'])
        before = (owner.ref, owner.x, owner.y, entity.ref, entity.x, entity.y)
        ui = MemoryUi(self)
        director = ui.ptr(ui.base + 0x1807fd8)
        if ui.ptr(director) != ui.base + 0x1237f90:
            raise ValueError('PET_TOGGLE_DIRECTOR_TYPE_UNKNOWN')
        size = ui.vec(ui.ptr(director + 0x150) + 0x6c)
        point, facts = world_grid_to_capture(capture,
            dict(map_id=owner.map_id, grid=[owner.x, owner.y]),
            dict(map_id=entity.map_id, grid=[entity.x, entity.y]),
            size, SHOP_PROBES['shop_probe'])
        ui.validate()
        if before != (owner.ref, owner.x, owner.y, entity.ref, entity.x, entity.y):
            raise ValueError('PET_TOGGLE_TARGET_OR_CAMERA_ORIGIN_CHANGED')
        request.update(x=point[0], y=point[1], coordinate_space='capture', png_size=capture['png_size'])
        self.pet_toggle_actor_clicks += 1
        self.pet_toggle_click_before = self.callback_rows()
        self.pet_toggle_click_at = time.monotonic()
        return request, dict(facts, locator=locator, actor=actor.ref.uid)

    def finish(self, row):
        if self.pet_toggle and row.get('status') not in ('OBSERVED', 'POSTED', 'WAITED', 'SKIPPED'):
            if self.pet_toggle_blocked is None:
                self.pet_toggle_blocked = dict(step=self.steps[self.index][1],
                    status=row.get('status'), reason=row.get('reason'))
        return super().finish(row)

    async def tick(self):
        if not self.pet_toggle or self.done:
            return await super().tick()
        step = self.steps[self.index]
        if self.pet_toggle_blocked and step[0] != 'capture':
            self.finish(dict(status='SKIPPED', reason='PET_TOGGLE_FAILED_PREREQUISITE',
                prerequisite=self.pet_toggle_blocked, automatic_retry=False)); return
        try:
            if step[0] == 'pet_toggle_prepare':
                if self.busy():
                    return
                if input_route != 'GLFW_CALLBACK_INJECTION':
                    raise ValueError('PET_TOGGLE_REQUIRES_GLFW_CALLBACK_INJECTION')
                actor, owner, entity = self.pet_toggle_actor()
                self.actor_uid, self.member_id = actor.ref.uid, actor.character_id
                self.pet_toggle_origin = [owner.map_id, owner.x, owner.y]
                self.pet_toggle_moves_done = 0
                self.pet_toggle_initial_mode = actor.record.movement_mode
                self.pet_toggle_preexisting_clicks = [r for r in self.callback_rows()
                    if r.get('actor') == self.actor_uid and 'CLICK' in str(r.get('status', ''))]
                if self.pet_toggle_preexisting_clicks:
                    raise ValueError('PET_TOGGLE_PRIOR_COMPANION_CLICK_OBSERVED')
                facts = self.pet_toggle_windows()
                if any(p['shown'] for p in facts['pet_menus']) or any(facts['ats_windows'].values()):
                    raise ValueError('PET_TOGGLE_START_WITH_PET_AND_ATS_WINDOWS_CLOSED')
                self.pet_toggle_watch_attack()
                self.finish(dict(status='OBSERVED', actor=self.actor_uid, member=self.member_id,
                    companion_name='SoloMage', windows=facts, position=self.pet_toggle_position(),
                    initial_movement_mode=self.pet_toggle_initial_mode,
                    input_order='FIRST_INPUT_AFTER_LOGIN_SUMMON_IS_CTRL_E; NO_ACTOR_CLICK', formal_pass=False)); return
            if step[0] == 'private_input' and step[2].get('locator') == 'pet_toggle.hold':
                if self.pet_toggle_actor()[0].record.movement_mode == 'HOLD':
                    self.pet_toggle_hold_before = self.server_signals()
                    self.finish(dict(status='SKIPPED', reason='CURRENT_COMPANION_ALREADY_HOLD')); return
            if step[0] == 'pet_toggle_hold':
                if self.started is None:
                    self.started = time.monotonic()
                actor, _, _ = self.pet_toggle_actor()
                signals = [r for r in self.server_signals() if r not in self.pet_toggle_hold_before
                    and r.get('operation') == 'movement-hold' and r.get('actor') == self.actor_uid]
                ok = actor.record.movement_mode == 'HOLD' and (self.pet_toggle_initial_mode == 'HOLD' or signals)
                if not ok and time.monotonic()-self.started < 8:
                    return
                self.finish(dict(status='OBSERVED' if ok else 'UNKNOWN', server_signals=signals,
                    movement_mode=actor.record.movement_mode,
                    reason=None if ok else 'PET_TOGGLE_NATIVE_HOLD_NOT_CONSUMED', formal_pass=False)); return
            if step[0] == 'pet_toggle_click_move_observe':
                if self.started is None:
                    self.started = time.monotonic()
                state = self.pet_toggle_position()
                before = self.pet_click_move_before
                elapsed = time.monotonic()-self.started
                progress = (state['distance_grid'] >= before['distance_grid'] + 3 if step[2] == 'away'
                    else state['owner_displacement'] < before['owner_displacement'] or state['owner_displacement'] <= 2)
                committed = module.current_kit(self.manual)[0][2].committed
                memory, _ = self.manual.consumer.reader.sample(include_input_state=False)
                transform = memory.get('move_state',{}).get('transform',{})
                aligned = transform.get('status') == 'OBSERVED' and transform.get('current_grid') == state['owner'][1:]
                ok = progress and committed > self.pet_click_move_counters and aligned
                if not ok and elapsed < 10:
                    return
                self.finish(dict(status='OBSERVED' if ok else 'UNKNOWN', before=before, after=state,
                    native_transform=transform, commits_before=self.pet_click_move_counters, commits_after=committed,
                    reason=None if ok else 'PET_TOGGLE_NATIVE_CLICK_MOVE_NOT_CONSUMED', formal_pass=False)); return
            if step[0] == 'pet_toggle_move':
                self.pet_toggle_move(step[2]); return
            if step[0] == 'pet_toggle_remote':
                position = self.pet_toggle_position()
                ok = (position['distance_grid'] >= 6 and position['owner_displacement'] >= 6
                    and position['movement_mode'] == 'HOLD' and self.pet_toggle_actor_clicks == 0)
                self.finish(dict(status='OBSERVED' if ok else 'UNKNOWN', position=position,
                    reason=None if ok else 'PET_TOGGLE_ACTUAL_REMOTE_GAP_NOT_OBSERVED',
                    formal_pass=False)); return
            if step[0] == 'pet_toggle_observe':
                stage = step[2]
                if self.started is None:
                    self.started = time.monotonic()
                facts = self.pet_toggle_windows()
                shown = [p for p in facts['pet_menus'] if p['shown']]
                ok = (len(shown) == 1 and shown[0]['actor'] == self.actor_uid if stage in ('open', 'remote_open')
                      else not shown)
                ok = ok and not any(facts['ats_windows'].values())
                predecessor = {'closed': 'open', 'remote_open': 'closed',
                    'remote_closed': 'remote_open', 'click_closed': 'remote_closed'}.get(stage)
                ok = ok and (predecessor is None or predecessor in self.pet_toggle_observed)
                position = self.pet_toggle_position()
                if stage != 'click_closed':
                    ok = ok and self.pet_toggle_actor_clicks == 0
                if stage.startswith('remote_'):
                    ok = ok and position['distance_grid'] >= 6 and position['owner_displacement'] >= 6
                callbacks = [r for r in self.callback_rows()
                    if r not in getattr(self, 'pet_toggle_key_before', [])]
                key_signals = [r for r in self.server_signals()
                    if r not in getattr(self, 'pet_toggle_key_signals_before', [])]
                ingress = []
                if stage == 'click_closed':
                    callbacks = [r for r in self.callback_rows() if r not in self.pet_toggle_click_before]
                    # A closed menu alone cannot prove the companion was hit.
                    hit = [r for r in callbacks if r.get('actor') == self.actor_uid
                           and r.get('status') == 'ACTOR_CLICK_MENU_SUPPRESSED']
                    ingress = [r for r in self.pet_toggle_ingress
                        if r['monotonic_seconds'] >= self.pet_toggle_click_at
                        and r.get('target_uid') == self.actor_uid]
                    ok = ok and bool(hit or ingress)
                    if shown:
                        raise ValueError('PET_TOGGLE_COMPANION_CLICK_OPENED_PET_MENU')
                    if time.monotonic()-self.started < 2:
                        return
                if not ok and time.monotonic()-self.started < 8:
                    return
                if ok:
                    self.pet_toggle_observed.add(stage)
                self.finish(dict(status='OBSERVED' if ok else 'UNKNOWN', windows=facts,
                    stage=stage, position=position, native_callback_rows=callbacks, actor=self.actor_uid,
                    decoded_attack_ingress=ingress, server_signals_since_key=key_signals,
                    remote_native_actor_missing_request=any(r.get('status') == 'HOTKEY_PET_REMOTE_REQUEST_QUEUED'
                        for r in callbacks),
                    reason=None if ok else 'PET_TOGGLE_EXPECTED_NATIVE_MENU_OR_CLICK_NOT_OBSERVED',
                    scope='OWNED_GLFW_INPUT_AND_ORIGINAL_PET_MENU_VISIBILITY; NOT_FULL_EQUIVALENCE',
                    formal_pass=False)); return
            return await super().tick()
        except Exception as error:
            if self.capture is not None:
                self.capture.close(); self.capture = None
            self.finish(dict(status='UNKNOWN', reason=str(error)[:300], automatic_retry=False,
                             formal_pass=False))

    def close(self):
        try:
            return super().close()
        finally:
            if self.pet_toggle_attack_hook is not None:
                broker, original, hook, owned, saved = self.pet_toggle_attack_hook
                if broker._world_attack is hook:
                    if owned:
                        broker._world_attack = saved
                    else:
                        delattr(broker, '_world_attack')


module.STEP_SETS['companion_head_mp'] = (
    ('wait', 'head-mp-world-settle', 2),
    ('head_mp_observe', 'head-mp-before-capture', 12),
    ('capture', 'companion-head-mp-world-and-party'),
    ('head_mp_observe', 'head-mp-after-capture', 0))


class CompanionHeadMpSteps(PetWindowToggleSteps):
    """Passive current-UID HUD/party comparison; never changes MP or visibility."""
    def head_mp_actor(self):
        current, _ = module.current_kit(self.manual)
        broker, owner_uid = self.broker(), current[3].uid
        world = broker._world
        actors = [a for a in world.companions.active.values() if a.owner_ref.uid == owner_uid]
        if len(actors) != 1:
            raise ValueError('HEAD_MP_ONE_CURRENT_OWNED_COMPANION_REQUIRED')
        actor = actors[0]
        owner, entity = world.entities.resolve(actor.owner_ref), world.entities.resolve(actor.ref)
        if owner is None or entity is None or not owner.alive or not entity.alive:
            raise ValueError('HEAD_MP_CURRENT_LIVING_OWNER_AND_COMPANION_REQUIRED')
        if hasattr(self, 'head_mp_uid') and actor.ref.uid != self.head_mp_uid:
            raise ValueError('HEAD_MP_COMPANION_LIFETIME_CHANGED')
        if hasattr(self, 'head_mp_ref') and actor.ref != self.head_mp_ref:
            raise ValueError('HEAD_MP_COMPANION_GENERATION_CHANGED')
        self.head_mp_uid, self.head_mp_ref = actor.ref.uid, actor.ref
        pc = world.combat.pcs.get(owner_uid)
        return actor, dict(actor_uid=actor.ref.uid, actor_generation=actor.ref.generation,
            member_id=actor.character_id,
            owner_uid=owner_uid, mp=actor.record.mp, max_mp=actor.record.effective_max_mp,
            base_max_mp=actor.record.max_mp,
            mp_percent=broker._companion_party.percent(actor.record.mp, actor.record.effective_max_mp),
            owner_mp=None if pc is None else pc.mp,
            owner_max_mp=None if pc is None else pc.max_mp,
            companion_position=[entity.map_id, entity.x, entity.y],
            owner_position=[owner.map_id, owner.x, owner.y])

    def head_mp_snapshot(self):
        import math
        scene = self.scene()
        if (scene.get('status') != 'OBSERVED' or scene.get('current') != 'Land'
                or scene.get('pending') != 'none' or scene.get('root_ready') is not True):
            raise ValueError('HEAD_MP_CURRENT_LAND_SCENE_UNKNOWN')
        actor, authority = self.head_mp_actor()
        ui = MemoryUi(self)
        manager, control = ui.ptr(ui.manager + 0x3e8), ui.ptr(ui.manager + 0x3f0)
        if not manager or not control:
            raise ValueError('HEAD_MP_CURRENT_ACTOR_HUD_MANAGER_REQUIRED')
        # run381 selection3 and the original ActorHudManager lookup: RB tree,
        # exact UID key. No old process pointer or DLL pointer is the selector.
        head = ui.ptr(manager + 0x10)
        node, seen, found = ui.ptr(head + 8), set(), None
        for _ in range(64):
            if ui.read(node + 0x19, 1) != b'\0':
                break
            if node in seen:
                raise ValueError('HEAD_MP_HUD_TREE_CYCLE')
            seen.add(node)
            uid = ui.ptr(node + 0x20)
            if uid == actor.ref.uid:
                found = node
                break
            signed = lambda value: value if value < 1 << 63 else value - (1 << 64)
            node = ui.ptr(node + (0 if signed(actor.ref.uid) < signed(uid) else 0x10))
        if found is None:
            raise ValueError('HEAD_MP_CURRENT_UID_HUD_NOT_FOUND')
        hud, hud_control = ui.ptr(found + 0x28), ui.ptr(found + 0x30)
        if not hud or not hud_control or ui.ptr(hud) != ui.base + 0x121aed0:
            raise ValueError('HEAD_MP_CURRENT_PLAYER_ACTOR_HUD_TYPE_UNKNOWN')
        native_actor = ui.ptr(hud + 0x18)
        container, bar = ui.ptr(hud + 0x180), ui.ptr(hud + 0x1a8)
        if not native_actor or not container or not bar:
            raise ValueError('HEAD_MP_NATIVE_ACTOR_CONTAINER_AND_BAR_REQUIRED')
        percent = ui.struct.unpack('<f', ui.read(bar + 0x704, 4))[0]
        if not math.isfinite(percent) or not 0 <= percent <= 100:
            raise ValueError('HEAD_MP_PERCENT_OUT_OF_RANGE')
        native = dict(actor_uid=actor.ref.uid, actor_ptr=native_actor, hud_ptr=hud,
            mp_container_ptr=container, mp_bar_ptr=bar,
            self_bool=ui.read(hud + 0x201, 1) == b'\1', mp_percent=percent,
            container_visible=ui.visible(container), container_shown=ui.shown(container),
            bar_visible=ui.visible(bar), bar_shown=ui.shown(bar))
        party = dict(status='UNKNOWN', reason='CURRENT_UID_PARTY_ROW_NOT_FOUND')
        try:
            layouts = [p for p in ui.layouts() if ui.ptr(p) == ui.base + 0x121e8c8]
            if len(layouts) == 1:
                layout = layouts[0]
                matches = [(i, ui.ptr(layout + 0xc0 + i*16)) for i in range(8)]
                matches = [(i, row) for i, row in matches if row and ui.ptr(row) == actor.ref.uid]
                if len(matches) == 1:
                    index, row = matches[0]
                    party = dict(status='OBSERVED', layout=layout, row=row, index=index,
                        actor_uid=actor.ref.uid, mp_percent=ui.struct.unpack('<f', ui.read(row+0x10, 4))[0],
                        hidden=ui.read(row+8, 1) == b'\1', folded=ui.read(row+0x25, 1) == b'\1', bars={})
                    for offset in (0x78, 0x80, 0x88):
                        ptr = ui.ptr(row + offset)
                        entry = dict(node=ptr)
                        if ptr:
                            entry.update(visible=ui.visible(ptr), shown=ui.shown(ptr))
                            if offset == 0x78:
                                entry['mp_percent'] = ui.struct.unpack('<f', ui.read(ptr+0x704, 4))[0]
                        party['bars'][hex(offset)] = entry
        except Exception as error:
            party.update(status='UNKNOWN', reason=str(error)[:200])
        ui.validate()
        owner = self.scenario.owner
        boundary = module.current_kit(self.manual)[0][5]
        rows = self.json_rows(boundary, 'companion-head-mp-%s.json' % actor.ref.uid)
        matched = [r for r in rows if r.get('schema') == 'companion-head-mp-v1'
            and r.get('status') == 'MAPPED_VISIBLE'
            and r.get('mp_percent_known') is True
            and r.get('pid') == owner.child.pid and r.get('birth') == int(owner.child.identity['birth'])
            and r.get('candidate_sha256') == owner.image_sha
            and all(r.get(k) == native[k] for k in ('actor_uid', 'actor_ptr', 'hud_ptr',
                                                   'mp_container_ptr', 'mp_bar_ptr'))
            and r.get('actor_generation') == actor.ref.generation
            and r.get('owner_uid') == actor.owner_ref.uid and r.get('member_id') == actor.character_id
            and 0 <= time.time()-Path(r['evidence_file']).stat().st_mtime <= 2]
        positive = authority['mp_percent'] > 0 and percent > 0
        equal = percent == authority['mp_percent']
        shown = native['container_shown'] and native['bar_shown']
        ok = positive and equal and shown and bool(matched) and not native['self_bool']
        return dict(status='OBSERVED' if ok else 'UNKNOWN',
            reason=None if ok else
                ('POSITIVE_MP_NOT_OBSERVED' if not positive else
                 'HEAD_MP_NATIVE_PERCENT_DISAGREES' if not equal else
                 'HEAD_MP_NATIVE_NODE_HIDDEN' if not shown else
                 'HEAD_MP_NONSELF_FLAG_CHANGED' if native['self_bool'] else 'HEAD_MP_CURRENT_DLL_IDENTITY_UNKNOWN'),
            authority=authority, native=native, party=party,
            dll=dict(status='OBSERVED' if matched else 'UNKNOWN',
                     observation=matched[-1] if matched else None,
                     latest_rows=rows if not matched else [], maximum_file_age_seconds=2),
            scene=scene, sampled_monotonic_seconds=time.monotonic(),
            ui_result='UNKNOWN; NATIVE_NODE_STATE_REQUIRES_PNG_REVIEW', formal_pass=False,
            scope='PASSIVE_CURRENT_UID_MEMORY_AND_FULL_WORLD_PNG; NO_RESOURCE_MUTATION',
            limitations=['NODE_VISIBLE_AND_POSITIVE_PERCENT_DO_NOT_PROVE_RENDERED_PIXELS',
                         'BEFORE_AND_AFTER_MEMORY_DO_NOT_IDENTIFY_THE_CAPTURED_RENDER_FRAME',
                         'CAST_ABSORB_REGEN_AND_REMOVE_RECREATE_NOT_DRIVEN_BY_THIS_SCENARIO'])

    async def tick(self):
        if self.done or self.steps[self.index][0] != 'head_mp_observe':
            return await super().tick()
        step = self.steps[self.index]
        if self.started is None:
            self.started = time.monotonic()
        try:
            observation = self.head_mp_snapshot()
        except Exception as error:
            observation = dict(status='UNKNOWN', reason=str(error)[:300], formal_pass=False,
                               ui_result='UNKNOWN')
        if observation['status'] != 'OBSERVED' and time.monotonic()-self.started < step[2]:
            return
        observation.update(wait_limit_seconds=step[2], automatic_retry=False)
        if step[1] == 'head-mp-after-capture':
            png = next((r for r in reversed(self.results)
                        if r.get('png') and r.get('status') == 'OBSERVED'), None)
            observation['capture'] = png
            observation['before_capture'] = next((r for r in self.results
                if r.get('step') == 'head-mp-before-capture'), None)
            if png is None:
                observation.update(status='UNKNOWN', reason='HEAD_MP_WORLD_CAPTURE_NOT_OBSERVED')
        self.finish(observation)


def play_smoke_action(label, locator, action='left_click', **extra):
    # In particular there is no settle delay before the teleport effect PNG.
    steps = [('capture', 'before-' + label),
             ('private_input', label, dict(locator='play.' + locator, action=action, **extra))]
    if locator == 'teleport':
        steps += [('play_observe', label + '-server', locator), ('capture', 'after-' + label),
                  ('capture', 'after-' + label + '-next-capture')]
    else:
        steps += [('capture', 'after-' + label), ('play_observe', label + '-server', locator)]
    return steps



def play_smoke_key_action(label):
    # Keyboard input needs no point geometry. Use the teleport's just-finished
    # server observation, then capture the result without another pre-key PNG.
    return [('private_input', label, dict(locator='play.key', action='key_press', key='Ctrl+E')),
            ('capture', 'after-' + label), ('play_observe', label + '-server', 'key')]


_play_steps = [('play_move', 'play-entry-move', 1),
               ('capture', 'play-entry-after-movement'),
               ('play_observe', 'play-entry-session', 'entry')]
for _item in ('brave', 'haste'):
    _play_steps += [('play_inventory', 'play-bag-for-' + _item, True)]
    _play_steps += play_smoke_action('play-use-' + _item, _item, 'left_double_click')
# The bag remains open after potion use. Teleport is next, before combat.
_play_steps += play_smoke_action('play-use-teleport', 'teleport', 'left_double_click')
# A random destination can contain monsters: do not add movement, waits, or
# another screenshot between teleport observation and the companion window.
for _toggle in ('open', 'close'):
    _play_steps += play_smoke_key_action('play-companion-' + _toggle)
_play_steps += [('play_quit', 'play-request-normal-quit')]
module.STEP_SETS['play_smoke'] = tuple(_play_steps)
# Run this against SourceProfile=<first RunName>, without using fresh potions.
_play_reconnect_steps = [('wait', 'play-reconnect-render-settle', 1),
    ('play_observe', 'play-reconnect-restored-server', 'restore')]
for _buff_index in (2, 3):
    _play_reconnect_steps += [
        ('capture', 'play-reconnect-before-buff-%d' % _buff_index),
        ('private_input', 'play-reconnect-buff-hover-%d' % _buff_index,
            dict(locator='play.buff_hover_%d' % _buff_index, action='mouse_move')),
        ('wait', 'play-reconnect-buff-tooltip-settle-%d' % _buff_index, .3),
        ('capture', 'play-reconnect-buff-tooltip-%d' % _buff_index)]
_play_reconnect_steps += [('play_quit', 'play-reconnect-request-normal-quit')]
module.STEP_SETS['play_smoke_reconnect'] = tuple(_play_reconnect_steps)


class PlaySmokeSteps(CompanionHeadMpSteps):
    """Real native input plus passive packet/save observations; no game-state edits.

    Missing items/monsters/UI nodes stay UNKNOWN. Independent later steps and
    normal SourceQuit still run. PNGs are for Claude; no pixel PASS is inferred.
    """
    active = None
    templates = dict(brave=296, haste=17, teleport=23)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not PLAY_SMOKE_SCENARIO:
            return
        PlaySmokeSteps.active = self
        broker = self.manual.inventory_broker
        self.play_broker = broker
        self.play_profile = Path(broker._inventory_store.profile).parent
        self.play_initial_save = self.play_saved()
        self.play_packets, self.play_ingress, self.play_moves, self.play_damage = [], [], [], []
        self.play_baselines, self.play_hooks = {}, []
        self.play_exit_report = {}
        self.play_owner_uid = None
        self.play_last_attack_uid = None
        # Observe the actual send, including restore paths that bypass _world_send.
        original = broker._send
        async def send(writer, row, replies, **options):
            entries = []
            for wire in replies:
                opcode = int.from_bytes(wire[2:4], 'little') if len(wire) >= 6 else None
                if opcode not in (0x4e5b, 0x4e91, 0x4ed8, 0x4e31):
                    continue
                entry = dict(opcode='0x%04X' % opcode, send_returned=False,
                    recipient=getattr(broker, '_world_pcs', {}).get(id(writer), (None, None))[1],
                    monotonic_seconds=time.monotonic())
                try:
                    from tools.local_entry_server import protobuf as pb
                    with pb.parse_message(wire[4:-2]) as body:
                        entry['fields'] = {str(f.number): f.value for f in body.fields if f.wire_type == 0}
                        entry['icons'] = []
                        if opcode == 0x4e91:
                            for child in body.occurrences(2):
                                if child.wire_type == 2:
                                    with pb.parse_message(bytes(child.value)) as icon:
                                        entry['icons'].append({str(f.number): f.value for f in icon.fields if f.wire_type == 0})
                        if opcode == 0x4e5b:
                            entry['speed_bonuses'] = []
                            for child in body.occurrences(2):
                                if child.wire_type == 2:
                                    with pb.parse_message(bytes(child.value)) as bonuses:
                                        for bonus in bonuses.occurrences(1):
                                            if bonus.wire_type == 2:
                                                with pb.parse_message(bytes(bonus.value)) as fields:
                                                    entry['speed_bonuses'].append({str(f.number): f.value
                                                        for f in fields.fields if f.wire_type == 0})
                except Exception as error:
                    entry['decode_error'] = str(error)[:160]
                entries.append(entry)
            self.play_packets.extend(entries)
            del self.play_packets[:-512]
            result = await original(writer, row, replies, **options)
            for entry in entries:
                entry.update(send_returned=True, completed_monotonic_seconds=time.monotonic())
            return result
        self.play_hook(broker, '_send', send)
        original_attack = broker._world_attack
        async def attack(*args, **kwargs):
            from tools.local_entry_server import protobuf as pb
            frame = args[3] if len(args) > 3 else kwargs['frame']
            entry = dict(opcode='0x4E30', monotonic_seconds=time.monotonic())
            try:
                with pb.parse_message(frame.payload) as body:
                    entry['fields'] = {str(f.number): f.value for f in body.fields if f.wire_type == 0}
            except Exception as error:
                entry.update(fields={}, decode_error=str(error)[:160])
            self.play_ingress.append(entry)
            result = await original_attack(*args, **kwargs)
            entry['handler_return'] = result
            return result
        self.play_hook(broker, '_world_attack', attack)
        world = broker._world
        original_swing = world._apply_monster_swing
        def swing(owner_uid, attacker_uid, target, monster, hp, rolled, now):
            companions = [rt for rt in world.companions.active.values()
                if rt.owner_ref.uid == owner_uid]
            companion_targets = [dict(member=rt.character_id,
                target=None if rt.target is None else rt.target.uid,
                action=rt.action) for rt in companions]
            result = original_swing(owner_uid, attacker_uid, target, monster, hp, rolled, now)
            if owner_uid == attacker_uid:
                self.play_damage.append(dict(owner_uid=owner_uid, target_uid=target.uid,
                    generation=target.generation, hp_before=hp, landed=rolled.landed,
                    rolled_damage=rolled.damage, companion_targets=companion_targets,
                    monotonic_seconds=time.monotonic()))
                del self.play_damage[:-64]
            return result
        self.play_hook(world, '_apply_monster_swing', swing)
        # The harness normally waits for COMMITTED or 12 seconds after IDLE.
        # Reuse its startup poll pattern to attempt movement at the first Land
        # admission, without that extra wait. Native readiness remains authoritative.
        from tools.local_original_session import launcher
        original_poll = launcher.ProductFeatures.poll
        async def poll(features, *args, **kwargs):
            result = await original_poll(features, *args, **kwargs)
            if (getattr(features, 'manual', None) is self.manual
                    and self.scenario is not None
                    and (self.index == 0 or _selected_steps == 'play_smoke_reconnect'
                         and self.index < 5)
                    and self.scene().get('current') == 'Land'):
                await self.tick()
            return result
        self.play_hook(launcher.ProductFeatures, 'poll', poll)

    def play_hook(self, obj, name, hook):
        self.play_hooks.append((obj, name, hook, name in vars(obj), vars(obj).get(name)))
        setattr(obj, name, hook)

    def play_saved(self):
        path = self.play_profile / 'consumable-effects.json'
        try:
            return dict(path=str(path), **json.loads(path.read_text(encoding='utf-8-sig')))
        except (OSError, ValueError) as error:
            return dict(path=str(path), status='UNKNOWN', reason=str(error)[:200])

    def play_health(self):
        world = self.play_broker._world
        pc = world.combat.pcs.get(self.play_owner_uid)
        trace = self.play_broker._world_item_effects.restore_trace
        after_death = any(r.get('phase') == 'after_death'
            and (self.play_owner_uid is None or r.get('uid', self.play_owner_uid) == self.play_owner_uid)
            for r in trace)
        hp = None if pc is None else pc.hp
        return dict(knight_hp=hp, death=after_death or pc is not None
            and (pc.dead or hp is not None and hp <= 0),
            death_trace=[dict(r) for r in trace if r.get('phase') == 'after_death'])

    def finish(self, row):
        if PLAY_SMOKE_SCENARIO:
            health = self.play_health()
            row = dict(row, **health)
            if health['death']:
                row.update(status='UNKNOWN', reason='DEATH', formal_pass=False)
                if self.steps[self.index][0] != 'play_quit':
                    # Stop gameplay once its save/restore premise is lost.
                    self.steps[self.index+1:] = [('play_quit', 'play-death-request-normal-quit')]
        return super().finish(row)

    def play_snapshot(self):
        current, _ = module.current_kit(self.manual)
        broker, position, world = current[0].broker, current[3], self.play_broker._world
        uid, now = position.uid, world.runtime.clock()
        self.play_owner_uid = uid
        pc = world.combat.pcs.get(uid)
        bag = module.inv.validate_kit_frame(broker._inventory_current_frame)
        effects = broker._world_item_effects
        companions = [rt for rt in world.companions.active.values()
            if rt.owner_ref.uid == uid]
        return dict(uid=uid, position=[position.map_id, position.word0, position.word1],
            session_bound=broker._world_bound(current[0].writer),
            broker_failure=broker.failure.is_set(), scene=self.scene(),
            hp=None if pc is None else pc.hp,
            companion=[dict(member=rt.character_id, uid=rt.ref.uid,
                hp=rt.record.hp, mp=rt.record.mp, combat_mode=rt.record.combat_mode,
                action=rt.action, target=None if rt.target is None else rt.target.uid)
                for rt in companions],
            buffs={} if pc is None else {k: dict(remaining=max(0, deadline-now), interval_rate=rate)
                for k, (deadline, rate) in pc.buffs.items()},
            speed_interval_factor=world.combat.speed_factor(uid, now),
            inventory=[dict(uid=i.identifier, template=i.template_bits, quantity=dict(i.raw_fields).get(4, 0))
                for i in bag if i.template_bits in self.templates.values()],
            restore_trace=list(effects.restore_trace), saved=self.play_saved(),
            server_errors=list(getattr(broker, '_world_handler_errors', ())),
            item_errors=list(getattr(broker, '_world_item_errors', ())))

    def resolve_request(self, request):
        locator = request.get('locator', '')
        if not PLAY_SMOKE_SCENARIO or not locator.startswith('play.'):
            return super().resolve_request(request)
        request = dict(request)
        control = request.pop('locator')[5:]
        capture = self.last_capture_context
        # Same immediate-before-capture contract as the existing resolvers.
        if (control != 'key' and (not capture or self.results[-1].get('kind') != 'capture'
                or self.results[-1].get('status') != 'OBSERVED')):
            raise ValueError('INPUT_IMMEDIATELY_PRECEDING_CAPTURE_REQUIRED')
        snapshot = self.play_snapshot()
        self.play_baselines[control] = dict(server=snapshot, at=time.monotonic())
        request.update(schema='local-original-input-request-v1', expected_scene='Land',
            sequence=getattr(getattr(self, 'private_inputs', None), 'last_sequence', 0)+1)
        if control == 'key':
            return request, dict(locator=locator, basis='OWNED_GLFW_CONTROL_E_CALLBACK_SEQUENCE')
        ui = MemoryUi(self)
        if control in self.templates:
            template = self.templates[control]
            item = next((r for r in snapshot['inventory'] if r['template'] == template and r['quantity'] > 0), None)
            if item is None:
                raise ValueError('PLAY_ITEM_NOT_IN_CURRENT_KIT:%s' % template)
            layout = ui.layout('self_bag')
            node = ui.slot(layout, 'self_bag', item['uid'])
            # Reuse talkscroll_visible_slot's live UID/drawable traversal:
            # inventory Slot nodes can have zero size. Use a drawable's native
            # bounds, never the zero-size slot origin or a new grid formula.
            pending, visited, candidates = [(node, 0)], set(), []
            while pending:
                drawable, depth = pending.pop()
                if drawable in visited:
                    continue
                visited.add(drawable)
                if len(visited) > 128:
                    raise ValueError('TALKSCROLL_SLOT_DESCENDANT_BOUND')
                if not ui.shown(drawable):
                    continue
                if all(n > 0 for n in ui.vec(drawable + 0x6c)):
                    point, facts = ui.node_point(drawable, locator, layout, require_capture=False)
                    rect = facts['capture_rect']
                    if (35 <= rect[2]-rect[0] <= 175 and 35 <= rect[3]-rect[1] <= 175
                            and 2190 <= point[0] < 2750 and 80 <= point[1] < 1200):
                        candidates.append((point, facts))
                if depth < 4:
                    pending.extend((child, depth+1) for child in ui.children(drawable))
            if not candidates:
                raise ValueError('PLAY_ITEM_DRAWABLE_NOT_IN_VISIBLE_CAPTURE_GRID:%s' % item['uid'])
            point, facts = candidates[0]
            facts.update(item_uid=item['uid'], template=template, native_slot=node)
            self.play_baselines[control]['item'] = item
        elif control == 'bag':
            point, facts = capture_control_point(capture, 'hud.bag_icon',
                ValueError('ESTABLISHED_HUD_BAG_ICON_CAPTURE_POINT'), self)
        elif control.startswith('buff_hover_'):
            index = int(control.rsplit('_', 1)[1])
            layout = ui.named_layout('HudBuffLayout', 0x348)
            if not layout:
                raise ValueError('PLAY_CURRENT_HUD_BUFF_LAYOUT_REQUIRED')
            root = ui.ptr(layout + 0x30)
            pending, seen, panels = [(root, 0)], set(), []
            while pending:
                node, depth = pending.pop()
                if node in seen:
                    continue
                seen.add(node)
                if not ui.shown(node):
                    continue
                if ui.string(node + 0x1a8) == 'Panel_Slot':
                    point, facts = ui.node_point(node, locator, layout)
                    panels.append((point, facts, node))
                if depth < 6:
                    pending.extend((child, depth + 1) for child in ui.children(node))
            panels.sort(key=lambda row: (row[0][1], row[0][0]))
            if index >= len(panels):
                raise ValueError('PLAY_NO_BUFF_PANEL_AT_INDEX:%d:COUNT=%d' % (index, len(panels)))
            point, facts, node = panels[index]
            facts.update(buff_panel=node, ordinal=index, panel_count=len(panels),
                         identity='CURRENT_NATIVE_PANEL; NAME_CONFIRMED_ONLY_BY_TOOLTIP_PNG')
        elif control == 'bag_close':
            try:
                point, facts = ui.point('self_bag.close')
            except Exception as error:
                point, facts = capture_close_point(capture, 'self_bag.close', error)
        elif control == 'monster':
            world = self.play_broker._world
            uid = snapshot['uid']
            owner = world.entities.get(uid)
            known = world.visibility.known.get(uid, ())
            candidates = [e for e in world.entities if e.alive and e.uid in known
                and e.map_id == owner.map_id and world.spawner.slot_for(e.uid)
                and world.spawner.slot_for(e.uid)[1].hp > 0
                and max(abs(e.x-owner.x), abs(e.y-owner.y)) <= 7]
            if not candidates:
                raise ValueError('PLAY_NO_CURRENT_VISIBLE_MONSTER_WITHIN_7; NO_FIXTURE_SPAWN_OR_TELEPORT')
            # Prefer another live target on later clicks so ASSIST switching
            # can be observed; one remaining monster stays a valid attack.
            target = min(candidates, key=lambda e: (e.uid == self.play_last_attack_uid,
                max(abs(e.x-owner.x), abs(e.y-owner.y)), e.uid))
            self.play_last_attack_uid = target.uid
            group, slot = world.spawner.slot_for(target.uid)
            director = ui.ptr(ui.base + 0x1807fd8)
            size = ui.vec(ui.ptr(director + 0x150) + 0x6c)
            point, facts = world_grid_to_capture(capture,
                dict(map_id=owner.map_id, grid=[owner.x, owner.y]),
                dict(map_id=target.map_id, grid=[target.x, target.y]),
                size, SHOP_PROBES['shop_probe'], request.pop('candidate'))
            self.play_baselines[control].update(target_uid=target.uid,
                generation=target.generation, hp=slot.hp, monster=group.monster.name_ko)
        else:
            raise ValueError('PLAY_UNKNOWN_LOCATOR:' + control)
        ui.validate()
        request.update(x=point[0], y=point[1], coordinate_space='capture', png_size=capture['png_size'])
        return request, dict(facts, capture=capture, locator=locator)

    def play_observe(self, phase):
        from tools.local_original_session.world_item_effects import CONSUMABLE_BUFF_ICONS
        snapshot = self.play_snapshot()
        before = self.play_baselines.get(phase, {})
        packets = [p for p in self.play_packets if p['send_returned'] and p['recipient'] == snapshot['uid']
            and p['monotonic_seconds'] >= before.get('at', 0)]
        ok = snapshot['session_bound'] and not snapshot['broker_failure']
        details = dict()
        active = all(snapshot['buffs'].get(k, {}).get('remaining', 0) > 0 for k in ('brave', 'haste'))
        def icon_sent(template):
            catalog, image_key, _ = CONSUMABLE_BUFF_ICONS[template]
            return any(p['opcode'] == '0x4E91' and p.get('fields', {}).get('1') == 1
                and any(i.get('1') == catalog and i.get('4') == image_key and i.get('3', 0) > 0
                        for i in p.get('icons', ())) for p in packets)
        speed_sent = any(p['opcode'] == '0x4E5B' and p.get('fields', {}).get('1') == snapshot['uid']
            and any(b.get('1') == 0 and b.get('2', 0) > 0 for b in p.get('speed_bonuses', ())) for p in packets)
        if phase in ('brave', 'haste', 'teleport'):
            item = before.get('item')
            remaining = next((r['quantity'] for r in snapshot['inventory']
                              if item and r['uid'] == item['uid']), 0)
            consumed = item is not None and item['quantity']-remaining == 1
            details.update(item_before=item, quantity_after=remaining, consumed_one=consumed)
            ok = ok and consumed
            if phase == 'teleport':
                relocated = snapshot['position'] != before.get('server', {}).get('position')
                effect = any(p['opcode'] == '0x4ED8' and p.get('fields', {}).get('2') == 169 for p in packets)
                details.update(relocated=relocated, teleport_effect_4ed8=effect)
                ok = ok and relocated and effect and active and speed_sent and all(icon_sent(t) for t in (296, 17))
            else:
                ok = ok and snapshot['buffs'].get(phase, {}).get('remaining', 0) > 0
                ok = ok and speed_sent and icon_sent(self.templates[phase])
        elif phase in ('buffs', 'restore'):
            ok = ok and active and snapshot['speed_interval_factor'] < 1
            if phase == 'restore':
                saved = next((r for r in self.play_initial_save.get('rows', ()) if r['uid'] == snapshot['uid']), {})
                details['source_saved_row'] = saved
                ok = ok and all(saved.get('potion_remaining', {}).get(str(t), 0) > 0 for t in (296, 17))
                ok = ok and speed_sent and all(icon_sent(t) for t in (296, 17))
        elif phase == 'monster':
            target = before.get('target_uid')
            slot = self.play_broker._world.spawner.slot_for(target) if target is not None else None
            ingress = [r for r in self.play_ingress if r['monotonic_seconds'] >= before.get('at', float('inf'))
                       and r.get('fields', {}).get('1') == target]
            swings = [p for p in packets if p['opcode'] == '0x4E31'
                      and p.get('fields', {}).get('2') == snapshot['uid'] and p.get('fields', {}).get('3') == target]
            hp_after = slot[1].hp if slot and slot[1].uid == target else None
            player_damage = [r for r in self.play_damage if r['target_uid'] == target
                and r['owner_uid'] == snapshot['uid']
                and r['monotonic_seconds'] >= before.get('at', float('inf'))]
            companion_before = [r['target'] for r in before.get('server', {}).get('companion', ())]
            companion_at_swing = [c['target'] for r in player_damage
                for c in r['companion_targets']]
            companion_after = [r['target'] for r in snapshot['companion']]
            target_switched = (target in companion_at_swing
                and any(previous != target for previous in companion_before))
            details.update(target_before=before, hp_after=hp_after, attack_4e30=ingress,
                swings_and_direction_4e31=swings,
                player_damage=player_damage,
                companion_target_transition=dict(before=companion_before,
                    at_player_swing=companion_at_swing, after=companion_after,
                    selected_target=target, switched=target_switched,
                    status='OBSERVED' if target_switched else 'UNKNOWN'),
                hp_drop=None if hp_after is None else before['hp']-hp_after,
                damage_attribution='HP_DELTA_MAY_INCLUDE_COMPANION; 4E31_F5_IS_DIRECTION')
            ok = ok and bool(ingress and swings and player_damage and target_switched)
        elif phase in ('bag', 'bag_close'):
            details['inventory_window'] = self.self_bag_visibility()
            ok = ok and details['inventory_window']['shown'] == (phase == 'bag')
        elif phase == 'key':
            try:
                details['native_windows'] = self.pet_toggle_windows()
            except Exception as error:
                details['native_windows'] = dict(status='UNKNOWN', reason=str(error)[:200])
            details['window_verdict'] = 'CLAUDE_PNG_REVIEW_REQUIRED; VISIBILITY_NOT_AN_AUTOMATED_PASS'
        return dict(status='OBSERVED' if ok else 'UNKNOWN', server=snapshot, packets=packets,
            **details, reason=None if ok else 'PLAY_SERVER_OBSERVATION_INCOMPLETE',
            ui_result='CLAUDE_PNG_REVIEW_REQUIRED', formal_pass=False,
            scope='SERVER_PACKET_SAVE_AND_SESSION_ONLY; NO_PIXEL_OR_FULL_EQUIVALENCE_CLAIM')

    async def tick(self):
        if not PLAY_SMOKE_SCENARIO or self.done:
            return await super().tick()
        step = self.steps[self.index]
        try:
            if step[0] == 'play_move':
                # Existing public MoveGoal -> native consumer, not server dispatch.
                from tools.local_original_session import commands
                if self.started is None:
                    self.started = time.monotonic()
                    self.state = dict(commits=[], pending=None, origin=self.play_snapshot())
                state = self.state
                pending = state['pending']
                if pending:
                    result = self.manual.last_result
                    if result.get('sequence') == pending['sequence'] and result.get('status') in ('COMMITTED', 'UNKNOWN', 'REFUSED'):
                        state['commits'].append(dict(request=pending, result=dict(result),
                            completed_monotonic_seconds=time.monotonic(), server=self.play_snapshot()))
                        state['pending'] = None
                        if result['status'] != 'COMMITTED':
                            self.finish(dict(status='UNKNOWN', **state)); return
                    elif time.monotonic()-pending['at'] < 15:
                        return
                    else:
                        self.finish(dict(status='UNKNOWN', reason='MOVE_COMMIT_NOT_OBSERVED', **state)); return
                if len(state['commits']) >= step[2]:
                    self.play_moves.extend(state['commits'])
                    self.finish(dict(status='OBSERVED', **state,
                        movement_scope='EARLIEST_NATIVE_ADMITTED_LAND_INPUT; PRE_LAND_LOADING_INPUT_UNVERIFIED',
                        speed_scope='SERVER_INTERVAL_FACTOR_AND_COMMIT_TIMES; RENDERED_SPEED_REQUIRES_PNG_REVIEW')); return
                if self.busy():
                    return
                current, _ = module.current_kit(self.manual)
                p = current[3]
                neighbors = self.play_broker.realm.edge_passability.tile_neighbors(p.uid, p.map_id, p.packed)
                choices = [r['grid_target'] for r in neighbors.get('directions', ())
                           if r.get('status') == 'OBSERVED' and r.get('blocked') is False]
                if not choices:
                    self.finish(dict(status='UNKNOWN', reason='LIVE_NATIVE_MOVEMENT_NEIGHBORS_UNKNOWN', neighbors=neighbors)); return
                sequence = self.manual.sequence + 1
                target = choices[0]
                state['pending'] = dict(sequence=sequence, target=target, at=time.monotonic(),
                                        scenario_stage=self.scenario.stage)
                commands._atomic(self.manual.directory / 'command.request.json',
                    dict(schema=commands.REQUEST_SCHEMA, sequence=sequence, command='MoveGoal',
                         uid=p.uid, x=target[0], y=target[1]), 1024)
                return
            if step[0] == 'play_inventory':
                shown = self.self_bag_visibility()['shown']
                if shown != step[2]:
                    control = 'bag' if step[2] else 'bag_close'
                    self.steps[self.index+1:self.index+1] = play_smoke_action(step[1] + '-click', control)
                self.finish(dict(status='OBSERVED', shown=shown, requested_shown=step[2])); return
            if step[0] == 'play_observe':
                if self.started is None:
                    self.started = time.monotonic()
                row = self.play_observe(step[2])
                if (row['status'] == 'UNKNOWN' and step[2] != 'teleport'
                        and not self.play_health()['death']
                        and time.monotonic()-self.started < 8):
                    return
                self.finish(row); return
            if step[0] == 'play_quit':
                self.finish(dict(status='OBSERVED', action='HARNESS_STOP_THEN_EXISTING_SOURCE_QUIT',
                                 normal_exit_verified=False, verdict='PENDING_CLOSE_OBSERVATION'))
                # The harness sets stop on done; launcher retains FIRST/close.
                return
            return await super().tick()
        except Exception as error:
            if self.capture is not None:
                self.capture.close(); self.capture = None
            self.finish(dict(status='UNKNOWN', reason=str(error)[:300], automatic_retry=False, formal_pass=False))

    def close(self):
        if not PLAY_SMOKE_SCENARIO:
            return super().close()
        try:
            saved = self.play_saved()
            uid = next((r.get('server', {}).get('uid') for r in self.results if r.get('server')), None)
            row = next((r for r in saved.get('rows', ()) if r['uid'] == uid), {})
            normal = self.play_exit_report.get('normal_exit_verified') is True
            remaining = row.get('potion_remaining', {})
            ok = normal and all(remaining.get(str(t), 0) > 0 for t in (296, 17))
            self.results.append(dict(kind='play_quit_observe', step='play-after-normal-quit-save',
                status='OBSERVED' if ok else 'UNKNOWN', normal_exit_verified=normal,
                exit_report=self.play_exit_report, saved=saved, selected_saved_row=row,
                restore_trace=list(self.play_broker._world_item_effects.restore_trace),
                formal_pass=False, reason=None if ok else 'NORMAL_QUIT_OR_REMAINING_POTIONS_UNVERIFIED'))
        finally:
            for obj, name, hook, owned, saved in reversed(self.play_hooks):
                if getattr(obj, name) is hook:
                    if owned:
                        setattr(obj, name, saved)
                    else:
                        delattr(obj, name)
            super().close()


module.Steps = PlaySmokeSteps
if PLAY_SMOKE_SCENARIO:
    # Observe the finished launcher's existing SourceQuit result before the
    # imported harness calls Steps.close() and persists verify-shots.json.
    from tools.local_original_session import launcher as _play_launcher
    _play_run = _play_launcher.run_session
    async def _play_run_with_exit_report(*args, **kwargs):
        report = await _play_run(*args, **kwargs)
        if PlaySmokeSteps.active is not None:
            PlaySmokeSteps.active.play_exit_report = {k: report.get(k) for k in
                ('reason', 'source_quit', 'close_wait_end', 'close_via', 'native_close_error',
                 'normal_exit_verified', 'game_logout_protocol', 'exit_outcome')}
        return report
    _play_launcher.run_session = _play_run_with_exit_report
if _selected_steps == 'item_tooltip_hover':
    # A separate scenario: existing step sets and input routes stay unchanged.
    module.STEP_SETS['item_tooltip_hover'] = (
        ('capture', 'item-hover-initial'), ('item_hover_open', 'item-hover-open-bag'),
        ('capture', 'item-hover-before'),
        ('private_input', 'item-hover-move', dict(
            schema='local-original-input-request-v1', action='mouse_move',
            expected_scene='Land', locator='item_hover.slot')),
        ('wait', 'item-hover-dwell', 3), ('capture', 'item-hover-after'),
        ('item_hover_observe', 'item-hover-model'))

    class ItemTooltipHoverSteps(PrivateSteps):
        def hover_snapshot(self):
            ui = MemoryUi(self)
            tooltip = ui.ptr(ui.manager + 0x3f8)
            result = dict(tooltip_manager=tooltip,
                tooltip_ready=ui.ptr(tooltip + 0x10) if tooltip else None,
                tooltip_target=ui.ptr(tooltip + 0x20) if tooltip else None)
            parts = result['tooltip_ready']
            if parts:
                result['tooltip_parts'] = {}
                for name, offset in (('root', 0), ('background', 8), ('panel', 0x10), ('description', 0x18)):
                    node = ui.ptr(parts + offset)
                    if node:
                        try:
                            result['tooltip_parts'][name] = dict(node=node,
                                visible=ui.visible(node), shown=ui.shown(node),
                                position=ui.vec(node + 0x3c), size=ui.vec(node + 0x6c))
                        except ValueError as error:
                            result['tooltip_parts'][name] = dict(node=node, reason=str(error)[:160])
            if getattr(self, 'hover_item', None):
                layout = ui.layout('self_bag')
                slot = ui.slot(layout, 'self_bag', self.hover_item['uid'])
                result.update(slot=slot, slot_flags={hex(offset): ui.read(slot + offset, 1)[0]
                    for offset in (0x1f8, 0x1f9, 0x3ea, 0x6f0)},
                    mouse_over_callable=ui.ptr(slot + 0x5a8))
                metadata = ui.ptr(slot + 0x808)
                result['slot_content'] = dict(mode=ui.struct.unpack('<i', ui.read(metadata + 0xb0, 4))[0])
                for name, offset in (('name', 0x30), ('description', 0x50), ('prefix', 0x70)):
                    try:
                        result['slot_content'][name] = ui.string(metadata + offset)
                    except ValueError as error:
                        result['slot_content'][name + '_reason'] = str(error)[:160]
            current = module.current_kit(self.manual)[0]
            broker = current[0].broker
            uid = current[3].uid
            state = broker._world.combat.pcs[uid]
            calculated, _, _ = broker._world_stats_for(current[3])
            result['weight'] = dict(f17=state.status_fields[17],
                carried=calculated.carried_weight, capacity=calculated.max_weight)
            return result

        def resolve_request(self, request):
            request = dict(request)
            locator = request.pop('locator')
            capture = self.last_capture_context
            if self.results[-1].get('kind') != 'capture' or self.results[-1].get('status') != 'OBSERVED':
                raise ValueError('INPUT_IMMEDIATELY_PRECEDING_CAPTURE_REQUIRED')
            if locator == 'item_hover.bag':
                point, facts = capture_control_point(capture, 'hud.bag_icon',
                    ValueError('ESTABLISHED_HUD_BAG_ICON_CAPTURE_POINT'), self)
            else:
                ui = MemoryUi(self)
                layout = ui.layout('self_bag')
                rows = module.inv.validate_kit_frame(
                    module.current_kit(self.manual)[0][0].broker._inventory_current_frame)
                selected = None
                for item in rows:
                    if dict(item.raw_fields).get(4, 0) <= 0:
                        continue
                    try:
                        slot = ui.slot(layout, 'self_bag', item.identifier)
                        panel = ui.ptr(slot + 0x830)
                        point, facts = ui.node_point(panel or slot, locator, layout)
                    except ValueError:
                        continue
                    selected = item
                    break
                if selected is None:
                    raise ValueError('ITEM_HOVER_VISIBLE_OWNED_SLOT_REQUIRED')
                self.hover_item = dict(uid=selected.identifier, template=selected.template_bits,
                    slot=slot, metadata=ui.ptr(slot + 0x808))
                facts.update(item=self.hover_item)
                facts['before_hover'] = self.hover_snapshot()
            request.update(sequence=getattr(getattr(self, 'private_inputs', None), 'last_sequence', 0) + 1,
                coordinate_space='capture', png_size=capture['png_size'], x=point[0], y=point[1])
            return request, dict(facts, coordinate_space='capture', coordinate_basis='capture_to_client')

        async def tick(self):
            if not self.done and self.steps[self.index][0] == 'item_hover_open':
                try:
                    ui = MemoryUi(self)
                    layout = ui.named_layout('InventoryLayout')
                    shown = bool(layout and ui.shown(ui.ptr(layout + 0x30)))
                    if not shown:
                        self.steps[self.index + 1:self.index + 1] = [
                            ('capture', 'item-hover-before-open'),
                            ('private_input', 'item-hover-bag-click', dict(
                                schema='local-original-input-request-v1', action='left_click',
                                expected_scene='Land', locator='item_hover.bag')),
                            ('wait', 'item-hover-open-dwell', 2)]
                    self.finish(dict(status='OBSERVED', bag_shown=shown))
                except Exception as error:
                    self.finish(dict(status='UNKNOWN', reason=str(error)[:300]))
                return
            if not self.done and self.steps[self.index][0] == 'item_hover_observe':
                try:
                    self.finish(dict(status='OBSERVED', item=getattr(self, 'hover_item', None),
                        native_state=self.hover_snapshot(),
                        ui_result='REQUIRES_CAPTURE_REVIEW', formal_pass=False))
                except Exception as error:
                    self.finish(dict(status='UNKNOWN', reason=str(error)[:300], formal_pass=False))
                return
            return await super().tick()

    module.Steps = ItemTooltipHoverSteps

TOOLTIP_WINDOWS = {
    'item_tooltip_owner_bag': 'self_bag',
    'item_tooltip_companion_bag': 'companion_bag',
    'item_tooltip_companion_equipment': 'companion_equipment',
    'item_tooltip_companion_equipment_empty': 'companion_equipment',
    'item_tooltip_companion_equipment_lifecycle': 'companion_equipment',
    'item_tooltip_bags_equipment': 'bags_equipment',
    'item_tooltip_bags_equipment_lifecycle': 'bags_equipment',
    'item_tooltip_shop': 'shop',
    'item_tooltip_shop_sell': 'shop_sell',
    'item_tooltip_warehouse': 'warehouse',
    'item_tooltip_warehouse_retrieve': 'warehouse_retrieve',
}
# The PowerShell wrapper already prepares the correct fresh start for these
# two existing names. An explicit environment selection changes only this run's
# Python steps; the old scenarios have no behavioral change without the opt-in.
_tooltip_window = TOOLTIP_WINDOWS.get(_selected_steps)
if os.environ.get('VERIFY_TOOLTIP_WINDOW') in ('shop', 'shop_sell', 'warehouse', 'warehouse_retrieve'):
    _requested_window = os.environ['VERIFY_TOOLTIP_WINDOW']
    if _selected_steps != {'shop': 'shop_probe', 'shop_sell': 'shop_probe', 'warehouse': 'shop_probe_dorin',
                           'warehouse_retrieve': 'shop_probe_dorin'}[_requested_window]:
        raise ValueError('TOOLTIP_WINDOW_FRESH_WRAPPER_SCENARIO_REQUIRED')
    _tooltip_window = _requested_window


def tooltip_window_steps(role):
    # Native NPC rows own a custom tooltip closure; +808 is legitimately null.
    # Hover is enough to exercise that closure without changing trade quantity.
    select = [] if role in ('shop', 'warehouse', 'companion_equipment_empty') else [
        ('capture', role + '-select-before'),
        ('private_input', role + '-select-once', dict(
            schema='local-original-input-request-v1', action='left_click',
            expected_scene='Land', locator='window_hover.' + role)),
        ('wait', role + '-select-settle', 1),
        ('capture', role + '-select-after'),
        ('window_hover_observe', role + '-select-model', role),
    ]
    return select + [
        ('capture', role + '-hover-before'),
        ('private_input', role + '-hover-move', dict(
            schema='local-original-input-request-v1', action='mouse_move',
            expected_scene='Land', locator='window_hover.' + role)),
        ('wait', role + '-hover-dwell', 3),
        ('capture', role + '-hover-after'),
        ('window_hover_observe', role + '-hover-model', role),
    ]


if _tooltip_window:
    if input_route != 'GLFW_CALLBACK_INJECTION':
        raise ValueError('TOOLTIP_WINDOW_REQUIRES_GLFW_CALLBACK_INJECTION')
    if _tooltip_window in ('shop', 'shop_sell', 'warehouse', 'warehouse_retrieve'):
        _probe = 'shop_probe' if _tooltip_window in ('shop', 'shop_sell') else 'shop_probe_dorin'
        SHOP_PROBES[_selected_steps] = dict(SHOP_PROBES[_probe])
        module.STEP_SETS[_selected_steps] = module.STEP_SETS[_probe]
    else:
        _tooltip_steps = []
        if _tooltip_window in ('self_bag', 'bags_equipment'):
            _tooltip_steps += [('capture', 'owner-bag-initial'),
                               ('window_hover_open', 'owner-bag-open')]
            _tooltip_steps += tooltip_window_steps('self_bag')
        if _tooltip_window != 'self_bag':
            _tooltip_steps += [('pet', 'open_pet_window'), ('wait', 'pet_settle', 3),
                               ('scenario_prepare', 'companion-preconditions')]
        for _role, _row in (('companion_bag', 'Alert'), ('companion_equipment', 'Gather')):
            if _tooltip_window not in (_role, 'bags_equipment'):
                continue
            if _role == 'companion_equipment' and _tooltip_window == 'bags_equipment':
                _tooltip_steps += scenario_action('companion-bag-close-before-gear', 'companion_bag.close')
            _tooltip_steps += scenario_action(_role + '-open', 'pet.' + _row)
            _tooltip_steps += tooltip_window_steps(_role)
        if _selected_steps in ('item_tooltip_companion_equipment_lifecycle',
                               'item_tooltip_bags_equipment_lifecycle'):
            _tooltip_steps += scenario_action('gear-tooltip-close', 'companion_equipment.close',
                observe=dict(hidden='companion_equipment'))
            _tooltip_steps += [('window_hover_closed', 'gear-tooltip-after-close')]
            _tooltip_steps += scenario_action('gear-tooltip-reopen', 'pet.Gather')
            _tooltip_steps += [(step[0], 'reopened-' + step[1], *step[2:])
                               for step in tooltip_window_steps('companion_equipment')]
            _tooltip_steps += tooltip_window_steps('companion_equipment_empty')
        if _selected_steps == 'item_tooltip_companion_equipment_empty':
            _tooltip_steps += tooltip_window_steps('companion_equipment_empty')
        if (_selected_steps == 'item_tooltip_bags_equipment_lifecycle'
                and os.environ.get('VERIFY_FINAL_HEAD_MP') == '1'):
            _tooltip_steps = list(module.STEP_SETS['companion_head_mp']) + _tooltip_steps
        module.STEP_SETS[_selected_steps] = tuple(_tooltip_steps)

    class WindowTooltipHoverSteps(PlaySmokeSteps):
        """Read current slot ownership and metadata, then inject one real hover."""
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            if _tooltip_window == 'warehouse_retrieve':
                self.shop_next_menu = 'retrieve'
            elif _tooltip_window == 'shop_sell':
                self.shop_next_menu = 'sell'

        def native_string_snapshot(self, ui, at):
            raw = ui.read(at, 32)
            size, capacity = ui.struct.unpack_from('<QQ', raw, 16)
            result = dict(address=at, length=size, capacity=capacity)
            if capacity < size or size > 65536:
                return dict(result, reason='NATIVE_STRING_LAYOUT_UNSUPPORTED')
            result['storage'] = 'SSO' if capacity < 16 else 'HEAP'
            result['pointer'] = at if capacity < 16 else ui.struct.unpack_from('<Q', raw)[0]
            text = raw[:size] if capacity < 16 else ui.read(result['pointer'], min(size, 4096)) if size else b''
            result.update(text=text.decode('utf-8', errors='replace'), truncated=size > len(text))
            return result

        def shop_native_snapshot(self, ui, index=0):
            app = ui.ptr(ui.base + 0x1668790)
            if not app or not ui.read(app + 0xd8, 1)[0]:
                raise ValueError('TOOLTIP_CURRENT_APP_NOT_READY')
            manager = ui.ptr(app + 0xd0)
            first, last = ui.ptr(manager + 0x180), ui.ptr(manager + 0x188)
            if last < first or (last - first) % 16 or last - first > 16 * 128:
                raise ValueError('TOOLTIP_CURRENT_SUBSYSTEM_VECTOR_BOUND')
            matches = []
            for at in range(first, last, 16):
                obj = ui.ptr(at)
                if obj and ui.ptr(obj) == ui.base + 0x11c9d28:
                    col = ui.ptr(ui.ptr(obj) - 8)
                    if ui.struct.unpack('<I', ui.read(col + 12, 4))[0] == 0x172e5a0:
                        matches.append(obj)
            if len(matches) != 1:
                raise ValueError('TOOLTIP_CURRENT_SHOP_SUBSYSTEM_NOT_UNIQUE')
            subsystem = matches[0]
            model = ui.ptr(subsystem + 0x70)
            kind = ui.struct.unpack('<I', ui.read(model, 4))[0]
            if kind not in (1, 2):
                raise ValueError('TOOLTIP_CURRENT_NATIVE_SHOP_KIND_UNKNOWN')
            owner, offset, stride = (subsystem, 0x40, 0x90) if kind == 2 else (model, 0x18, 0x50)
            begin, end = ui.ptr(owner + offset), ui.ptr(owner + offset + 8)
            if end < begin or (end - begin) % stride or end - begin > stride * 1024:
                raise ValueError('TOOLTIP_CURRENT_NATIVE_SHOP_ROWS_BOUND')
            rows = []
            for ordinal, at in enumerate(range(begin, end, stride)):
                rows.append(dict(index=ordinal, address=at, **(
                    dict(row_key=ui.struct.unpack('<I', ui.read(at + 0x38, 4))[0]) if kind == 2 else
                    dict(uid=ui.ptr(at + 8)))))
            result = dict(subsystem=subsystem, model=model, kind=kind, begin=begin, end=end,
                stride=stride, rows=rows,
                formatter_pair=dict(object=ui.ptr(subsystem + 0x18), control=ui.ptr(subsystem + 0x20)),
                source_basis='AE8960_TD172E5A0_VPTR11C9D28; BUY_SUBSYSTEM40; SELL_MODEL18_STRIDE50_UID8')
            formatter = result['formatter_pair']['object']
            if formatter:
                head = ui.ptr(formatter + 0x10)
                result['formatter_rules_tree'] = dict(object=formatter, head=head,
                    count=ui.ptr(formatter + 0x18),
                    head_links=({hex(offset): ui.ptr(head + offset) for offset in (0, 8, 0x10)}
                                if head else None))
            if kind == 2 and index < len(rows):
                row = rows[index]['address']
                vector = dict(address=row + 0x68, begin=ui.ptr(row + 0x68),
                    end=ui.ptr(row + 0x70), capacity_end=ui.ptr(row + 0x78), elements=[])
                if (vector['end'] >= vector['begin'] and (vector['end'] - vector['begin']) % 32 == 0
                        and vector['end'] - vector['begin'] <= 32 * 256):
                    vector['elements'] = [self.native_string_snapshot(ui, at)
                        for at in range(vector['begin'], vector['end'], 32)]
                else:
                    vector['reason'] = 'CURRENT_BUY_DESCRIPTION_VECTOR_UNSUPPORTED'
                result['selected_raw_row'] = dict(index=index, address=row, row_key=rows[index]['row_key'],
                    description_vector=vector,
                    f9_repeated_field=dict(address=row + 0x18, pointer_word=ui.ptr(row + 0x18),
                        count=ui.struct.unpack('<I', ui.read(row + 0x20, 4))[0]))
            return result

        def buy_issued_rows(self):
            current, _ = module.current_kit(self.manual)
            state = current[1]['_world_handler_state'][1]
            if state.window is None or state.window.mode != 5:
                raise ValueError('TOOLTIP_CURRENT_BUY_ISSUED_LIST_REQUIRED')
            rows = []
            for row in dict(state.window.value.fields).get(3, ()):
                fields = dict(row.fields)
                rows.append(dict(row_key=fields[1] & 0xffffffff, template=fields[2],
                    icon=fields[3], price=fields[4],
                    name_token=fields[5].decode('utf-8'),
                    description_terms=[{number: (value.decode('utf-8', errors='replace')[:2048]
                        if isinstance(value, bytes) else value) for number, value in child.fields}
                        for child in fields.get(9, ())]))
            return rows

        def warehouse_native_rows(self, ui):
            app = ui.ptr(ui.base + 0x1668790)
            if not app or not ui.read(app + 0xd8, 1)[0]:
                raise ValueError('TOOLTIP_CURRENT_APP_NOT_READY')
            manager = ui.ptr(app + 0xd0)
            first, last = ui.ptr(manager + 0x180), ui.ptr(manager + 0x188)
            if last < first or (last - first) % 16 or last - first > 16 * 128:
                raise ValueError('TOOLTIP_CURRENT_SUBSYSTEM_VECTOR_BOUND')
            storage = []
            for at in range(first, last, 16):
                obj = ui.ptr(at)
                if not obj:
                    continue
                vptr = ui.ptr(obj)
                if not ui.base + 8 <= vptr < ui.base + ui.sampler.g['size']:
                    continue
                col = ui.ptr(vptr - 8)
                if not ui.base <= col < ui.base + ui.sampler.g['size'] - 24:
                    continue
                signature, offset, cd_offset, td_rva, class_rva, self_rva = ui.struct.unpack(
                    '<6I', ui.read(col, 24))
                if signature == 1 and td_rva == 0x1730be0:
                    literal = b'.?AVStorageSubsystem@lineage@@\0'
                    if ui.read(ui.base + td_rva + 16, len(literal)) != literal:
                        raise ValueError('TOOLTIP_STORAGE_RTTI_NAME_CHANGED')
                    storage.append(obj)
            if len(storage) != 1:
                raise ValueError('TOOLTIP_CURRENT_STORAGE_SUBSYSTEM_NOT_UNIQUE')
            subsystem = storage[0]
            if _tooltip_window == 'warehouse_retrieve':
                # B has a distinct row-key/ItemInfo tree; never reuse A's ordinal.
                return dict(subsystem=subsystem, model=ui.ptr(subsystem + 0x38), rows=None,
                    source_basis='CURRENT_STORAGE_B_OWNER_ONLY; ROW_UID_MAP_UNKNOWN')
            model = ui.ptr(subsystem + 0x28)
            begin, end = ui.ptr(model + 0x20), ui.ptr(model + 0x28)
            if end < begin or (end - begin) % 16 or end - begin > 16 * 150:
                raise ValueError('TOOLTIP_FILTERED_STORAGE_A_VECTOR_BOUND')
            entities = []
            for index, at in enumerate(range(begin, end, 16)):
                entity = ui.ptr(at)
                if not entity:
                    raise ValueError('TOOLTIP_FILTERED_STORAGE_ENTITY_NULL')
                entities.append(dict(index=index, entity=entity, uid=ui.ptr(entity + 8)))
            return dict(subsystem=subsystem, model=model, begin=begin, end=end, rows=entities,
                source_basis='A50200_GETTER_RTTI;5BFE70..5C00C8_FILTERED_A_PAIR_VECTOR_AND_ENTITY_UID')

        def npc_hover_point(self, ui, capture, locator, role):
            server = self.shop_server()
            self.shop_require_no_new_server_error(server)
            if server['menu_target'] != self.shop_target['uid']:
                raise ValueError('TOOLTIP_CURRENT_NPC_TARGET_REQUIRED')
            selling = role == 'shop' and _tooltip_window == 'shop_sell'
            if role == 'shop' and server['shop_mode'] != (6 if selling else 5):
                raise ValueError('TOOLTIP_CURRENT_NPC_BUY_TARGET_REQUIRED')
            if role == 'warehouse' and not server['warehouse_window']:
                raise ValueError('TOOLTIP_CURRENT_WAREHOUSE_WINDOW_REQUIRED')
            layouts = [p for p in ui.layouts() if ui.ptr(p + 0x30) in self.shop_window_roots
                       and ui.shown(ui.ptr(p + 0x30))]
            if len(layouts) != 1:
                raise ValueError('TOOLTIP_NPC_CURRENT_WINDOW_NOT_UNIQUE')
            layout = layouts[0]
            tree = self.shop_tree(role + '-hover-current-slots', owned_layout=layout)
            if tree['status'] != 'OBSERVED' or len(tree['layouts']) != 1:
                raise ValueError('TOOLTIP_NPC_SLOT_TREE_UNKNOWN')
            nodes = tree['layouts'][0]['nodes']
            rows = [n for n in nodes if n['name'] == 'ItemListSlot' and n['shown']]
            native_warehouse = None
            if role == 'warehouse':
                try:
                    native_warehouse = self.warehouse_native_rows(ui)
                except ValueError as error:
                    native_warehouse = dict(rows=None, reason=str(error)[:240],
                        source_basis='CURRENT_VISIBLE_GEOMETRY_ONLY; NATIVE_MODEL_UID_UNRESOLVED')
            native_shop = self.shop_native_snapshot(ui) if selling else None
            issued = ((native_shop['rows'] if selling else self.buy_issued_rows())
                      if role == 'shop' else native_warehouse['rows'])
            geometry_only = issued is None
            if geometry_only:
                issued = [dict(index=index, uid=None, uid_status='UNKNOWN') for index in range(len(rows))]
            if (len(rows) != len(issued) or len({n['parent'] for n in rows}) != 1
                    or sorted(n['child_index'] for n in rows) != list(range(len(issued)))):
                raise ValueError('TOOLTIP_CURRENT_BUY_NATIVE_ISSUED_ORDER_MISMATCH')
            viewport = [n for n in nodes if n['name'] == 'ListView_Slot' and n['shown']]
            if len(viewport) != 1 or not viewport[0].get('scene_bounds'):
                raise ValueError('TOOLTIP_CURRENT_BUY_VIEWPORT_UNKNOWN')
            for row in sorted(rows, key=lambda n: n['child_index']):
                slots = [n for n in nodes if n['parent'] == row['node']
                         and n['name'] == 'ItemSlot' and n['shown']]
                if len(slots) != 1:
                    continue
                panels = [n for n in nodes if n['parent'] == slots[0]['node']
                          and n['name'] == 'Panel_Slot' and n['shown']]
                if len(panels) != 1:
                    continue
                try:
                    self.shop_require_row_visible(row, panels[0], viewport[0])
                    point, facts = ui.node_point(panels[0]['node'], locator, layout)
                except ValueError:
                    continue
                index = row['child_index']
                selected = dict(layout=layout, root=ui.ptr(layout + 0x30),
                    row_node=row['node'], slot=slots[0]['node'], panel=panels[0]['node'],
                    metadata=ui.ptr(slots[0]['node'] + 0x808),
                    native_row_index=index, issued_row=issued[index],
                    issued_rows=None if geometry_only else issued,
                    identity_basis='CURRENT_BUY_RESPONSE_ORDER_TO_NATIVE_CHILD_INDEX; NO_INVENTORY_UID',
                    source_basis='AE741B..7491_COPY_INDEX_AFE450; AE75F2..7602_REGISTER; AE7638..7644_APPEND',
                    tree_file=tree['tree_file'])
                registry_name = 'NpcShopLayout' if role == 'shop' else 'StorageLayout'
                named = ui.named_layout(registry_name)
                selected['named_registry'] = dict(name=registry_name, layout=named,
                    equals_current_tree_layout=named == layout)
                pair_begin, pair_end = ui.ptr(layout + 0x100), ui.ptr(layout + 0x108)
                pair_observation = dict(begin=pair_begin, end=pair_end, index=index)
                if (pair_end >= pair_begin and (pair_end - pair_begin) % 16 == 0
                        and pair_end - pair_begin <= 16 * 1024):
                    pair_observation['count'] = (pair_end - pair_begin) // 16
                    if index < pair_observation['count']:
                        pair_object = ui.ptr(pair_begin + index * 16)
                        pair_observation.update(object=pair_object,
                            control=ui.ptr(pair_begin + index * 16 + 8))
                        if pair_object:
                            item_list = ui.ptr(pair_object + 8)
                            icon_panel = ui.ptr(pair_object + 0x10)
                            text_item = ui.ptr(pair_object + 0x18)
                            pair_observation.update(item_list=item_list, panel=icon_panel,
                                text_item=text_item, item_list_equals_tree=item_list == row['node'],
                                panel_equals_tree=icon_panel == panels[0]['node'],
                                text_item_tree=[dict(node=n['node'], name=n['name'], path=n['path'])
                                                for n in nodes if n['node'] == text_item])
                else:
                    pair_observation['reason'] = 'CURRENT_PC_ROW_PAIR_VECTOR_UNSUPPORTED'
                selected['pc_row_pair'] = pair_observation
                if role == 'shop':
                    try:
                        selected['native_shop'] = self.shop_native_snapshot(ui, index)
                    except ValueError as error:
                        selected['native_shop'] = dict(reason=str(error)[:240])
                    if selling:
                        uid = issued[index]['uid']
                        references = [r for r in server['shop_row_bindings'] if r['value'] == uid]
                        if len(references) != 1:
                            raise ValueError('TOOLTIP_SELL_NATIVE_UID_NOT_IN_CURRENT_SERVER_ISSUED_LIST')
                        selected.update(uid=uid, server_issued_row=references[0],
                            identity_basis='CURRENT_NATIVE_SELL_DERIVED_ROW_UID_AND_VISIBLE_ROW_ORDINAL',
                            source_basis=native_shop['source_basis'])
                if role == 'warehouse':
                    uid = issued[index]['uid']
                    issued_uids = list(server['warehouse_window']['rows'].values())
                    if uid is not None and issued_uids.count(uid) != 1:
                        raise ValueError('TOOLTIP_FILTERED_NATIVE_UID_NOT_IN_CURRENT_WAREHOUSE_ISSUED_LIST')
                    selected.update(uid=uid, native_warehouse_model=native_warehouse,
                        issued_warehouse_window=server['warehouse_window'],
                        identity_basis=('CURRENT_VISIBLE_ROW_GEOMETRY_ONLY; UID_UNKNOWN' if geometry_only else
                                        'CURRENT_FILTERED_NATIVE_A_ENTITY_UID_AND_VISIBLE_ROW_ORDINAL'),
                        source_basis=native_warehouse['source_basis'])
                facts.update(row_scene_bounds=row['scene_bounds'],
                    viewport_scene_bounds=viewport[0]['scene_bounds'],
                    mapping_limitation='STATIC_NATIVE_ORDER_CONTRACT_PLUS_CURRENT_COUNT_AND_CHILD_ORDER; NOT_RAW_UID_READBACK')
                return point, facts, selected
            raise ValueError('TOOLTIP_CURRENT_BUY_FULLY_VISIBLE_ICON_REQUIRED')

        def hover_model(self, role):
            ui = MemoryUi(self)
            binding = self.window_hover_bindings[role]
            layout, root, slot = binding['layout'], binding['root'], binding['slot']
            if (ui.ptr(layout + 0x30) != root or not ui.shown(root)
                    or not ui.shown(slot) or not ui.descendant(slot, root)):
                raise ValueError('TOOLTIP_CURRENT_SLOT_OWNERSHIP_CHANGED')
            metadata = ui.ptr(slot + 0x808)
            custom_row = role in ('shop', 'warehouse')
            if custom_row:
                if role == 'shop':
                    current_rows = (self.shop_native_snapshot(ui)['rows'] if _tooltip_window == 'shop_sell'
                                    else self.buy_issued_rows())
                else:
                    if self.shop_server()['warehouse_window'] != binding['issued_warehouse_window']:
                        raise ValueError('TOOLTIP_CURRENT_WAREHOUSE_ISSUED_WINDOW_CHANGED')
                    current_rows = (None if binding['issued_rows'] is None else
                                    self.warehouse_native_rows(ui)['rows'])
                if current_rows != binding['issued_rows']:
                    raise ValueError('TOOLTIP_CURRENT_BUY_ISSUED_LIST_CHANGED')
            elif metadata != binding['metadata'] or ui.ptr(metadata) != binding['uid']:
                raise ValueError('TOOLTIP_CURRENT_SLOT_UID_OR_METADATA_CHANGED')
            tooltip = ui.ptr(ui.manager + 0x3f8)
            parts = ui.ptr(tooltip + 0x10) if tooltip else None
            result = dict(role=role, item=binding, tooltip_manager=tooltip,
                tooltip_ready=parts,
                tooltip_target=ui.ptr(tooltip + 0x20) if tooltip else None,
                slot_flags={hex(offset): ui.read(slot + offset, 1)[0]
                            for offset in (0x1f8, 0x1f9, 0x3ea, 0x6f0)},
                mouse_over_callable=ui.ptr(slot + 0x5a8),
                mouse_over_function_words=[ui.ptr(slot + 0x570 + i * 8) for i in range(8)],
                content=(dict(mode=None, source='ORIGINAL_CUSTOM_NPC_ROW_CLOSURE',
                    issued_row=binding['issued_row'], rendered_text='UNKNOWN; CAPTURE_PIXEL_REVIEW_REQUIRED')
                    if custom_row else
                    dict(mode=ui.struct.unpack('<i', ui.read(metadata + 0xb0, 4))[0])))
            if custom_row:
                result['hover_owners'] = {}
                for name, node in (('slot', slot), ('row', binding['row_node']), ('panel', binding['panel'])):
                    result['hover_owners'][name] = dict(node=node,
                        callable=ui.ptr(node + 0x5a8),
                        function_words=[ui.ptr(node + 0x570 + i * 8) for i in range(8)])
            for name, offset in (() if custom_row else (('name', 0x30), ('description', 0x50), ('prefix', 0x70))):
                try:
                    raw = ui.read(metadata + offset, 32)
                    size, capacity = ui.struct.unpack_from('<QQ', raw, 16)
                    if size > 8192 or capacity < size:
                        raise ValueError('TOOLTIP_METADATA_STRING_BOUND')
                    text = (raw[:size] if capacity < 16 else
                            ui.read(ui.struct.unpack_from('<Q', raw)[0], size))
                    result['content'][name] = text.decode('utf-8')
                except ValueError as error:
                    result['content'][name + '_reason'] = str(error)[:160]
            if parts:
                result['tooltip_parts'] = {}
                for name, offset in (('root', 0), ('background', 8), ('panel', 0x10), ('description', 0x18)):
                    node = ui.ptr(parts + offset)
                    if node:
                        try:
                            result['tooltip_parts'][name] = dict(node=node,
                                visible=ui.visible(node), shown=ui.shown(node),
                                position=ui.vec(node + 0x3c), size=ui.vec(node + 0x6c))
                        except ValueError as error:
                            result['tooltip_parts'][name] = dict(node=node, reason=str(error)[:160])
            ui.validate()
            return result

        def resolve_request(self, request):
            locator = request.get('locator', '')
            if locator == 'window_hover.open_owner_bag':
                capture = self.last_capture_context
                point, facts = capture_control_point(capture, 'hud.bag_icon',
                    ValueError('ESTABLISHED_HUD_BAG_ICON_CAPTURE_POINT'), self)
            elif locator.startswith('window_hover.'):
                role = locator.partition('.')[2]
                capture = self.last_capture_context
                if self.results[-1].get('kind') != 'capture' or self.results[-1].get('status') != 'OBSERVED':
                    raise ValueError('INPUT_IMMEDIATELY_PRECEDING_CAPTURE_REQUIRED')
                ui = MemoryUi(self)
                candidates = []
                if role in ('shop', 'warehouse'):
                    point, facts, selected = self.npc_hover_point(ui, capture, locator, role)
                elif role == 'companion_equipment_empty':
                    layout = ui.layout('companion_equipment')
                    grid = ui.ptr(layout + 0xb8)
                    first, last = ui.ptr(grid + 0x158), ui.ptr(grid + 0x160)
                    if last < first or (last-first) % 8 or last-first > 8192:
                        raise ValueError('UI_SLOT_VECTOR_BOUND')
                    empty_evidence = []
                    for at in range(first, last, 8):
                        slot = ui.ptr(at)
                        metadata = ui.ptr(slot + 0x808) if slot else None
                        entry = dict(slot=slot, metadata=metadata,
                            uid=ui.ptr(metadata) if metadata else None,
                            shown=ui.shown(slot) if slot else False,
                            panel=ui.ptr(slot + 0x830) if slot else None)
                        empty_evidence.append(entry)
                        if metadata and ui.ptr(metadata) in (0, 0xffffffffffffffff) and ui.shown(slot):
                            candidates.append((ui.ptr(metadata), slot, None))
                    (self.directory / 'companion-gear-empty-slots.json').write_text(
                        json.dumps(empty_evidence, indent=2), encoding='utf-8')
                else:
                    layout = ui.layout(role)
                    rows = (module.inv.validate_kit_frame(self.broker()._inventory_current_frame)
                            if role == 'self_bag' else self.frames()[1])
                    worn = self.worn() if role == 'companion_equipment' else None
                    for item in rows:
                        if dict(item.raw_fields).get(4, 0) <= 0 or (worn is not None and item.identifier not in worn):
                            continue
                        try:
                            candidates.append((item.identifier, ui.slot(layout, role, item.identifier), item.template_bits))
                        except ValueError:
                            continue
                if role not in ('shop', 'warehouse'):
                    selected = None
                for uid, slot, template in candidates:
                    try:
                        panel = ui.ptr(slot + 0x830)
                        point, facts = ui.node_point(panel or slot, locator, layout)
                        selected = dict(uid=uid, template=template, layout=layout,
                            root=ui.ptr(layout + 0x30), slot=slot, metadata=ui.ptr(slot + 0x808))
                        break
                    except ValueError:
                        continue
                if selected is None:
                    raise ValueError('TOOLTIP_VISIBLE_CURRENT_SLOT_REQUIRED:' + role)
                ui.validate()
                if not hasattr(self, 'window_hover_bindings'):
                    self.window_hover_bindings = {}
                self.window_hover_bindings[role] = selected
                facts.update(item=selected, before_hover=self.hover_model(role))
            else:
                return super().resolve_request(request)
            request = dict(request)
            request.pop('locator')
            request.update(sequence=getattr(getattr(self, 'private_inputs', None), 'last_sequence', 0) + 1,
                coordinate_space='capture', png_size=capture['png_size'], x=point[0], y=point[1])
            if self.shop_probe:
                self.shop_sequence = request['sequence']
            return request, dict(facts, coordinate_space='capture', coordinate_basis='capture_to_client')

        def shop_observe(self, label, phase, candidate=None):
            result = super().shop_observe(label, phase, candidate)
            if result['status'] == 'OBSERVED' and phase in ('buy', 'sell', 'deposit', 'retrieve'):
                self.steps[self.index + 1:self.index + 1] = tooltip_window_steps(
                    'shop' if _tooltip_window in ('shop', 'shop_sell') else 'warehouse')
            return result

        async def tick(self):
            if not self.done and self.steps[self.index][0] in ('window_hover_open', 'window_hover_observe', 'window_hover_closed'):
                if self.busy():
                    return
                try:
                    if self.steps[self.index][0] == 'window_hover_open':
                        ui = MemoryUi(self)
                        layout = ui.named_layout('InventoryLayout')
                        shown = bool(layout and ui.shown(ui.ptr(layout + 0x30)))
                        ui.validate()
                        if not shown:
                            self.steps[self.index + 1:self.index + 1] = scenario_action(
                                'owner-bag-button', 'window_hover.open_owner_bag')
                        self.finish(dict(status='OBSERVED', bag_shown=shown))
                    elif self.steps[self.index][0] == 'window_hover_closed':
                        ui = MemoryUi(self)
                        layout = ui.named_layout('SLCompGear')
                        tooltip = ui.ptr(ui.manager + 0x3f8)
                        parts = ui.ptr(tooltip + 0x10) if tooltip else None
                        tooltip_root = ui.ptr(parts) if parts else None
                        state = dict(layout=layout, layout_present=bool(layout),
                            shown=bool(layout and ui.shown(ui.ptr(layout + 0x30))),
                            tooltip_manager=tooltip, tooltip_target=ui.ptr(tooltip + 0x20) if tooltip else None,
                            tooltip_root=tooltip_root, tooltip_shown=ui.shown(tooltip_root) if tooltip_root else False)
                        ui.validate()
                        self.finish(dict(status='OBSERVED', native_state=state,
                            formal_pass=False, ui_result='REQUIRES_CAPTURE_PIXEL_REVIEW'))
                    else:
                        role = self.steps[self.index][2]
                        self.finish(dict(status='OBSERVED', native_state=self.hover_model(role),
                            capture=self.last_capture_context,
                            ui_result='REQUIRES_CAPTURE_PIXEL_REVIEW', formal_pass=False))
                except Exception as error:
                    self.finish(dict(status='UNKNOWN', reason=str(error)[:300], formal_pass=False))
                return
            return await super().tick()

    module.Steps = WindowTooltipHoverSteps

if _selected_steps in ('knight_status_paralyze', 'knight_status_stun', 'knight_status_poison'):
    from status_feedback_scenario import install as install_status_scenario
    install_status_scenario(module, module.Steps, MemoryUi, world_grid_to_capture,
                            SHOP_PROBES['shop_probe'], _selected_steps)

if __name__ == '__main__':
    raise SystemExit(module.main())
