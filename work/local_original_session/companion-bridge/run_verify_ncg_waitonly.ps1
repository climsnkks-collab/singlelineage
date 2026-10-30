param(
    [Parameter(Mandatory=$true)][string] $RunName,
    [string] $Steps = 'main',
    [string] $SourceProfile = 'manual-test-knight',
    [int] $Timeout = 600,
    [ValidateSet('companion4','uiopen')] [string] $BridgeKind = 'companion4',
    [switch] $ReviveCompanion,
    [string] $CandidateBridge = '',
    [string] $CandidateSha256 = '',
    [switch] $NoCompanion,
    [string] $InputPlan = '',
    [int] $SpellCastStartX = 32632,
    [int] $SpellCastStartY = 32835
)
# Headless verification: owned non-input desktop. Source profile is copied (read only).
$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../../..')).Path
Set-Location -LiteralPath $taskRoot
$taskPython = 'C:\Users\Chansol\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
function Require([bool] $ok, [string] $code) { if (-not $ok) { throw $code } }
Require (@(Get-Process -Name LC.guard -ErrorAction SilentlyContinue).Count -eq 0) 'LIVE_GAME_ALREADY_PRESENT'
Require (@(Get-NetTCPConnection -State Listen -LocalPort 12000,14030 -ErrorAction SilentlyContinue).Count -eq 0) 'TEST_PORT_OCCUPIED'
$profile = Join-Path $taskRoot ('work/local_original_session/validation-profiles/' + $RunName)
$run = Join-Path $taskRoot ('work/local_original_session/runs/' + $RunName)
Require ((-not (Test-Path -LiteralPath $profile)) -and (-not (Test-Path -LiteralPath $run))) 'FRESH_RUN_REQUIRED'
if ($Steps -eq 'knight_skill_cast') {
 Require ($env:VERIFY_INPUT_ROUTE -ceq 'GLFW_CALLBACK_INJECTION') 'KNIGHT_SKILL_REQUIRES_GLFW_CALLBACK_INJECTION'
}
New-Item -ItemType Directory -Path $profile | Out-Null
$src = Join-Path $taskRoot ('work/local_original_session/validation-profiles/' + $SourceProfile)
Get-ChildItem -LiteralPath $src -File | Where-Object { $_.Name -notmatch '\.bak' } | ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $profile $_.Name) }
if ($Steps -in @('knight_status_paralyze','knight_status_stun','knight_status_poison')) {
 Require ($env:VERIFY_INPUT_ROUTE -ceq 'GLFW_CALLBACK_INJECTION') 'STATUS_REQUIRES_GLFW_CALLBACK_INJECTION'
 # Requested fresh-copy fixture. Ordinary restore, world clock and input routes remain authoritative.
 $prepareStatus = @'
import json, sys, time
from pathlib import Path
from tools.local_original_session.world_magic import PlayerMagic, load_catalog
profile, kind = Path(sys.argv[1]), sys.argv[2].removeprefix('knight_status_')
characters = json.loads((profile / 'characters.json').read_text(encoding='utf-8-sig'))['characters']
if not characters or characters[0]['class'] != 1:
    raise ValueError('STATUS_FRESH_KNIGHT_REQUIRED')
uid = characters[0]['uid']
p = profile / 'magic.json'
data = json.loads(p.read_text(encoding='utf-8-sig'))
rows = [r for r in data['rows'] if r['uid'] == uid]
if len(rows) != 1:
    raise ValueError('STATUS_EXISTING_MAGIC_ROW_REQUIRED')
engine, now = PlayerMagic(load_catalog()), time.monotonic()
engine.restore(uid, rows[0], now)
if kind == 'poison':
    engine.state(uid).poison = dict(until=now+80, next_tick=now+50,
        tick_seconds=3, damage=1, source_uid=uid)
else:
    engine.apply_status(uid, kind, now, 30, spell={'paralyze':32, 'stun':86}[kind], onset=50)
replacement = engine.snapshot(uid, now)
data['rows'] = [replacement if r['uid'] == uid else r for r in data['rows']]
p.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print('STATUS_FRESH_COPY_TEST_INIT uid=%s kind=%s onset=50 duration=30; normal-login restore, original source untouched' % (uid, kind))
'@
 $prepareStatus | & $taskPython -X utf8 -B - $profile $Steps
 Require ($LASTEXITCODE -eq 0) 'STATUS_FRESH_COPY_PREPARATION_FAILED'
 $env:SL_PLAYER_MAGIC_BUFF_UI = '1'
}
if ($Steps -eq 'knight_skill_cast') {
 # Explicit test fixture in the fresh copy only. Reuse a real owned sword UID;
 # no book-learning/equipment-click claim, runtime cast admission stays intact.
 $prepareKnightSkill = @'
import json, os, sys
from pathlib import Path
from tools.local_original_session import inventory, equipment_store
from tools.local_original_session.game_data import load_m1
from tools.local_original_session.world_feature_knight_skills import POLICIES
from tools.local_original_session.world_magic import PlayerMagic, load_catalog

profile = Path(sys.argv[1])
def read(name):
    return json.loads((profile / name).read_text(encoding='utf-8-sig'))
def write(name, value):
    (profile / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
def one(rows, key, uid, code):
    selected = [r for r in rows if r[key] == uid]
    if len(selected) != 1:
        raise ValueError(code)
    return selected[0]

chars = read('characters.json')['characters']
if not chars or chars[0]['class'] != 1:
    raise ValueError('KNIGHT_SKILL_SELECTED_KNIGHT_REQUIRED')
uid = chars[0]['uid']
data = load_m1()
magic, progress, vitals = read('magic.json'), read('progression.json'), read('vitals.json')
companions = read('companion.json')
equipment, bag = read('equipment.json'), read('inventory.json')
learned = one(magic['rows'], 'uid', uid, 'KNIGHT_SKILL_MAGIC_ROW_REQUIRED')
growth = one(progress['rows'], 'uid', uid, 'KNIGHT_SKILL_PROGRESSION_ROW_REQUIRED')
health = one(vitals['rows'], 'uid', uid, 'KNIGHT_SKILL_VITALS_ROW_REQUIRED')
equipped = one(equipment['equipment'], 'character_uid', uid, 'KNIGHT_SKILL_EQUIPMENT_ROW_REQUIRED')
frame = bytes.fromhex(one(bag['inventories'], 'uid', uid, 'KNIGHT_SKILL_INVENTORY_ROW_REQUIRED')['frame'])
items = inventory.validate_kit_frame(frame)
swords = [i for i in items if dict(i.raw_fields)[4] > 0 and
          (d := data.items.get(i.template_bits)) is not None and
          d.kind == 'weapon' and d.weapon_type == 'twohand' and 1 in d.classes and
          equipment_store.two_handed(d) is True]
if not swords:
    raise ValueError('KNIGHT_SKILL_OWNED_TWO_HANDED_SWORD_REQUIRED')
sword = min(swords, key=lambda i: i.identifier)
spells = PlayerMagic(load_catalog(), runtime_policies=POLICIES).spells
minimum_level = max(spells[k].classes[1] for k in (89, 90))
growth['level'] = max(growth['level'], minimum_level)
growth['exp'] = max(growth['exp'], data.exp_for_level(growth['level']))
growth['max_hp'] = max(growth['max_hp'] or 0, 600)
growth['max_mp'] = max(growth['max_mp'] or 0, 100)
health.update(hp=growth['max_hp'], mp=growth['max_mp'])
joint_owner = companions['owners'].get(str(uid))
if not isinstance(joint_owner, dict) or not all(
        type(joint_owner.get(key)) is int for key in
        ('exp', 'level', 'max_hp', 'max_mp', 'lawful', 'exp_half')):
    raise ValueError('KNIGHT_SKILL_CANONICAL_COMPANION_OWNER_REQUIRED')
# Companion enter adopts this joint owner as the canonical progression state.
# Keep its existing exp_half, member records, rewards and identities intact.
joint_owner.update((key, growth[key]) for key in
                   ('exp', 'level', 'max_hp', 'max_mp', 'lawful'))
learned['learned'] = sorted(set(learned['learned']) | {89, 90})
learned['buffs'] = [b for b in learned['buffs'] if b['spell'] not in (89, 90)]
learned['reuse_remaining'] = 0.0
# Equipment sidecar selects the existing owned item; the bag bytes and all UIDs
# remain unchanged. A two-handed weapon must not retain a worn shield.
by_uid = {i.identifier: data.items.get(i.template_bits) for i in items}
slots = {k: v for k, v in equipped.get('slots', {}).items()
         if by_uid.get(v) is None or by_uid[v].slot != 'shield'}
equipped['weapon_uid'] = sword.identifier
equipped['revision'] += 1
if slots:
    equipped['slots'] = slots
else:
    equipped.pop('slots', None)
equipment_store.EquipmentStore._kit_state(equipped, {c['uid'] for c in chars}, {uid: frame}, data.items)
positions = None
counter_seconds = float(os.environ.get('VERIFY_KNIGHT_COUNTER_SECONDS') or '0')
if counter_seconds > 0:
    # Same existing field-start admission as companion_spell_cast. No runtime
    # teleport, monster spawn, projection or guaranteed counter outcome.
    from tools.local_original_session.world_terrain import default_terrain
    x, y = int(sys.argv[2]), int(sys.argv[3])
    population = json.loads(Path('tools/local_original_session/data/m6/map0_population.json').read_text(encoding='utf-8'))
    groups = [g for g in population['groups'] if g['map_id']['value'] == 0 and
              g['rect']['value']['x1'] <= x <= g['rect']['value']['x2'] and
              g['rect']['value']['y1'] <= y <= g['rect']['value']['y2']]
    town = json.loads(Path('tools/local_original_session/data/m1/town.json').read_text(encoding='utf-8'))['bounds']['value']
    if not groups or town['x1'] <= x <= town['x2'] and town['y1'] <= y <= town['y2']:
        raise ValueError('KNIGHT_SKILL_MAP0_POPULATION_OUTSIDE_TOWN_REQUIRED')
    if default_terrain().can_stand(0, x, y) is not True:
        raise ValueError('KNIGHT_SKILL_START_STATIC_TERRAIN_UNKNOWN_OR_BLOCKED')
    positions = read('positions.json')
    selected = one(positions['positions'], 'uid', uid, 'KNIGHT_SKILL_OWNER_POSITION_REQUIRED')
    selected.update(map_id=0, grid=[x, y])
for name, value in (('magic.json', magic), ('progression.json', progress),
                    ('vitals.json', vitals), ('equipment.json', equipment),
                    ('companion.json', companions)):
    write(name, value)
if positions is not None:
    write('positions.json', positions)
    print('KNIGHT_SKILL_COUNTER_COPY_START map=0 grid=%s,%s groups=%s; observation requested, counter outcome unverified' %
          (x, y, ','.join(g['group_id']['value'] for g in groups)))
saved_growth = one(read('progression.json')['rows'], 'uid', uid, 'KNIGHT_SKILL_PROGRESS_READBACK_REQUIRED')
saved_health = one(read('vitals.json')['rows'], 'uid', uid, 'KNIGHT_SKILL_VITALS_READBACK_REQUIRED')
saved_learned = one(read('magic.json')['rows'], 'uid', uid, 'KNIGHT_SKILL_MAGIC_READBACK_REQUIRED')
saved_equipment = one(read('equipment.json')['equipment'], 'character_uid', uid,
                      'KNIGHT_SKILL_EQUIPMENT_READBACK_REQUIRED')
saved_joint = read('companion.json')['owners'].get(str(uid))
if (saved_growth['level'] < minimum_level or saved_health['hp'] <= 130
        or saved_health['mp'] < 15 or not {89, 90} <= set(saved_learned['learned'])
        or saved_equipment['weapon_uid'] != sword.identifier
        or not isinstance(saved_joint, dict)
        or any(saved_joint[key] != saved_growth[key] for key in
               ('exp', 'level', 'max_hp', 'max_mp', 'lawful'))):
    raise ValueError('KNIGHT_SKILL_COPY_PREPARATION_READBACK_MISMATCH')
write('knight-skill-prepared.json', dict(schema='knight-skill-prepared-v1',
    steps=sys.argv[5], source_profile=sys.argv[4], profile=str(profile.resolve()),
    uid=uid, progression=saved_growth, vitals=saved_health, canonical_companion_owner=saved_joint,
    learned_spells=saved_learned['learned'], equipment=saved_equipment,
    sword=dict(uid=sword.identifier, template=sword.template_bits),
    counter_start=None if positions is None else [0, x, y],
    scope='FRESH_PROFILE_COPY_READBACK_BEFORE_GAME; RUNTIME_STATE_SEPARATE'))
print('KNIGHT_SKILL_COPY_PREPARED uid=%s learned=89,90 level=%s hp=%s mp=%s sword_uid=%s template=%s; synthetic learned/level/vitals/equipment fixture; inventory UIDs unchanged' %
      (uid, growth['level'], health['hp'], health['mp'], sword.identifier, sword.template_bits))
'@
 $prepareKnightSkill | & $taskPython -X utf8 -B - $profile $SpellCastStartX $SpellCastStartY $SourceProfile $Steps
 Require ($LASTEXITCODE -eq 0) 'KNIGHT_SKILL_COPY_PREPARATION_FAILED'
 $env:SL_SPELL_EXP = '1'
}
if ($Steps -eq 'companion_spell_cast') {
 Require (-not $NoCompanion) 'SPELL_CAST_COMPANION_REQUIRED'
 Require ($env:VERIFY_INPUT_ROUTE -ceq 'GLFW_CALLBACK_INJECTION') 'SPELL_CAST_REQUIRES_GLFW_CALLBACK_INJECTION'
 # Prepare only the fresh copy. Existing character learning/level/equipment
 # authority is required, never manufactured by editing companion learned_spells.
 $prepareSpellCast = @'
import json, sys
from pathlib import Path
from tools.local_original_session import ats_config_codec as codec
from tools.local_original_session.world_magic import PlayerMagic, load_catalog
from tools.local_original_session.world_terrain import default_terrain
profile, x, y = Path(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
def read(name):
    return json.loads((profile / name).read_text(encoding='utf-8-sig'))
def write(name, value):
    (profile / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
chars, companions = read('characters.json'), read('companion.json')
owner = chars['characters'][0]['uid']
members = [r for r in companions['records'] if r['owner_character_id'] == owner and r['class_id'] == 3 and r['summoned']]
if len(members) != 1 or members[0]['level'] != 30:
    raise ValueError('SPELL_CAST_EXISTING_LEVEL30_SUMMONED_MAGE_REQUIRED')
member = members[0]
magic = read('magic.json')
learned = [r for r in magic['rows'] if r['uid'] == member['character_id']]
rules = PlayerMagic(load_catalog()).spells
names = {s.name: s.key for s in rules.values()}
if len(learned) != 1 or len(set(learned[0]['learned'])) != 38 or not {names[n] for n in ('shield','blessed_armor','energy_bolt','heal')} <= set(learned[0]['learned']):
    raise ValueError('SPELL_CAST_REAL_MAGIC_STORE_LEARNED38_REQUIRED')
population = json.loads(Path('tools/local_original_session/data/m6/map0_population.json').read_text(encoding='utf-8'))
groups = [g for g in population['groups'] if g['map_id']['value'] == 0 and
          g['rect']['value']['x1'] <= x <= g['rect']['value']['x2'] and
          g['rect']['value']['y1'] <= y <= g['rect']['value']['y2']]
town = json.loads(Path('tools/local_original_session/data/m1/town.json').read_text(encoding='utf-8'))['bounds']['value']
if not groups or town['x1'] <= x <= town['x2'] and town['y1'] <= y <= town['y2']:
    raise ValueError('SPELL_CAST_MAP0_POPULATION_OUTSIDE_TOWN_REQUIRED')
if default_terrain().can_stand(0, x, y) is not True:
    raise ValueError('SPELL_CAST_START_STATIC_TERRAIN_UNKNOWN_OR_BLOCKED')
positions = read('positions.json')
selected = [r for r in positions['positions'] if r['uid'] == owner]
if len(selected) != 1:
    raise ValueError('SPELL_CAST_OWNER_POSITION_REQUIRED')
selected[0].update(map_id=0, grid=[x,y])
progress = [r for r in read('progression.json')['rows'] if r['uid'] == owner]
vitals = read('vitals.json')
owner_vitals = [r for r in vitals['rows'] if r['uid'] == owner]
if len(progress) != 1 or len(owner_vitals) != 1 or progress[0]['max_hp'] <= 0:
    raise ValueError('SPELL_CAST_OWNER_HP_STORES_REQUIRED')
owner_vitals[0]['hp'] = max(1, progress[0]['max_hp'] * 40 // 100)
member.update(hp=member['max_hp'], mp=member['max_mp'], alive=True,
              movement_mode='FOLLOW', combat_mode='ASSIST', support_enabled=True)
if member['mp'] < sum(s.mp for s in rules.values() if s.name in ('shield','blessed_armor','energy_bolt','heal')):
    raise ValueError('SPELL_CAST_MP_BUDGET_REQUIRED')
ats = read('ats-scopes.json')
scope = ats['characters'].get(str(member['character_id']))
if not scope or not scope.get('companion_config'):
    raise ValueError('SPELL_CAST_EXISTING_COMPANION_ATS_SCOPE_REQUIRED')
# Explicit test fixture, kind1/f4 keys through the existing codec; no UI-save claim.
scope['companion_ats'] = codec.wrap_blob(codec.build_ats(
    buff_spells=[names['shield'], names['blessed_armor']],
    sequence_spells=[names['energy_bolt']],
    conditional=[(2,70,names['heal'])])).hex()
write('positions.json', positions)
write('vitals.json', vitals)
write('companion.json', companions)
write('ats-scopes.json', ats)
print('SPELL_CAST_COPY_PREPARED member=%s mp=%s owner_hp=%s/%s start=0,%s,%s groups=%s; synthetic ATS fixture; real learning unchanged' %
      (member['character_id'],member['mp'],owner_vitals[0]['hp'],progress[0]['max_hp'],x,y,
       ','.join(g['group_id']['value'] for g in groups)))
'@
 $prepareSpellCast | & $taskPython -X utf8 -B - $profile $SpellCastStartX $SpellCastStartY
 Require ($LASTEXITCODE -eq 0) 'SPELL_CAST_COPY_PREPARATION_FAILED'
 # Existing product display opt-in emits actual 4E31/4ED8 cast projections.
 $env:SL_SPELL_EXP = '1'
}
if ($Steps -in @('shop_probe', 'shop_probe_dorin', 'shop_trade', 'warehouse_trade')) {
 Require ($env:VERIFY_INPUT_ROUTE -ceq 'GLFW_CALLBACK_INJECTION') 'SHOP_PROBE_REQUIRES_GLFW_CALLBACK_INJECTION'
 Require ([bool]$CandidateBridge -and ($CandidateSha256 -match '^[0-9a-f]{64}$')) 'SHOP_PROBE_PINNED_CANDIDATE_REQUIRED'
 # Edit only the just-created test copy. The source profile and its other
 # sidecars remain the input; no runtime teleport or movement is injected.
 $characters = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $profile 'characters.json') | ConvertFrom-Json
 $positionPath = Join-Path $profile 'positions.json'
 $positions = Get-Content -Raw -Encoding UTF8 -LiteralPath $positionPath | ConvertFrom-Json
 Require (($positions.version -eq 1) -and (@($characters.characters).Count -gt 0)) 'SHOP_PROBE_PROFILE_SCHEMA'
 $uid = $characters.characters[0].uid
 $selectedPosition = @($positions.positions | Where-Object { $_.uid -eq $uid })
 Require ($selectedPosition.Count -eq 1) 'SHOP_PROBE_SELECTED_POSITION_REQUIRED'
 $selectedPosition[0].map_id = 0
 # Four tiles west of the NPC. Existing world_terrain static S32 mask1:
 # starts can_stand/north_step True; east steps to the old adjacent start
 # clear. Normal adjacent mage spawn remains near the knight, off NPC body.
 # This does not claim a dynamic route/door/occupancy or native click PASS.
 $selectedPosition[0].grid = $(if ($Steps -in @('shop_probe', 'shop_trade')) { @(32641,32951) } else { @(32571,32946) })
 [System.IO.File]::WriteAllText($positionPath, (($positions | ConvertTo-Json -Depth 20) + "`n"), (New-Object System.Text.UTF8Encoding $false))
 if ($Steps -in @('shop_probe_dorin', 'warehouse_trade')) {
  # TEST_INIT only in the fresh copy. Warehouse admission requires level5.
  # Companion enter adopts its joint owner, so mirror only level/exp there;
  # preserve HP/MP, lawful, exp_half, members, inventory and every identity.
  $prepareWarehouseLevel = @'
import json, sys
from pathlib import Path
from tools.local_original_session.game_data import load_m1
profile, uid = Path(sys.argv[1]), int(sys.argv[2])
def read(name):
    return json.loads((profile / name).read_text(encoding='utf-8-sig'))
progress, companions = read('progression.json'), read('companion.json')
matches = [r for r in progress['rows'] if r['uid'] == uid]
joint = companions['owners'].get(str(uid))
if len(matches) != 1 or not isinstance(joint, dict):
    raise ValueError('WAREHOUSE_COPY_GROWTH_AND_CANONICAL_OWNER_REQUIRED')
growth = matches[0]
if any(type(row.get(key)) is not int for row in (growth, joint) for key in ('level', 'exp')):
    raise ValueError('WAREHOUSE_COPY_LEVEL_EXP_REQUIRED')
before = dict(progression={k: growth[k] for k in ('level', 'exp')},
              canonical_owner={k: joint[k] for k in ('level', 'exp')})
level = max(5, growth['level'], joint['level'])
exp = max(load_m1().exp_for_level(level), growth['exp'], joint['exp'])
growth.update(level=level, exp=exp)
joint.update(level=level, exp=exp)
for name, data in (('progression.json', progress), ('companion.json', companions)):
    (profile / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
saved = [r for r in read('progression.json')['rows'] if r['uid'] == uid]
owner = read('companion.json')['owners'].get(str(uid))
if (len(saved) != 1 or any(row.get(k) != v for row in (saved[0], owner)
                         for k, v in (('level', level), ('exp', exp)))):
    raise ValueError('WAREHOUSE_COPY_LEVEL_EXP_READBACK_MISMATCH')
print('WAREHOUSE_COPY_TEST_INIT uid=%s before=%s level=%s exp=%s; fresh copy only, no natural-growth claim' %
      (uid, json.dumps(before, sort_keys=True), level, exp))
'@
  $prepareWarehouseLevel | & $taskPython -X utf8 -B - $profile $uid
  Require ($LASTEXITCODE -eq 0) 'WAREHOUSE_COPY_LEVEL_PREPARATION_FAILED'
 }
}
$raw = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $taskRoot 'work/local_original_session/manual-play/item-equipment-runtime-config.json')
$end = $raw.LastIndexOf('}')
$config = Join-Path $profile 'world-config.json'
$text = $raw.Substring(0, $end).TrimEnd() + ",`n  `"world`": {`"policy`": `"LOCAL_M1_WORLD_INTEREST_SPAWN`", `"starter_kit`": `"test_knight`"}`n}`n"
[System.IO.File]::WriteAllText($config, $text, (New-Object System.Text.UTF8Encoding $false))
if ($NoCompanion) {
 # Saved store has the companion mage rows; keep the server companion flag only (no pet UI/bridge).
 $env:SL_COMPANION = '1'
 Remove-Item Env:SL_COMPANION_PET_UI,Env:SL_COMPANION_BRIDGE -ErrorAction SilentlyContinue
} else {
 $env:SL_COMPANION = '1'
 $env:SL_COMPANION_PET_UI = '1'
 $env:SL_COMPANION_BRIDGE = '1'
 if ($ReviveCompanion) {
  $cp = Join-Path $profile 'companion.json'
  $cj = Get-Content -Raw -Encoding UTF8 -LiteralPath $cp | ConvertFrom-Json
  foreach ($r in $cj.records) { $r.alive = $true; $r.hp = $r.max_hp; $r.mp = $r.max_mp }
  [System.IO.File]::WriteAllText($cp, (($cj | ConvertTo-Json -Depth 20) + "`n"), (New-Object System.Text.UTF8Encoding $false))
 }
}
if ($BridgeKind -eq 'uiopen') {
 $bridge = Join-Path $taskRoot 'work/local_original_session/ui-open-bridge/own-login-bridge-dg49.dll'
 $candHashExpected = '511840fedca21818b0bcfd64e4111c6f213b6a25d9604b84488d2a814f7dc775'
} else {
 $bridge = Join-Path $taskRoot 'work/local_original_session/companion-bridge/own-login-bridge-companion4.dll'
 $candHashExpected = '1e9a78b611dbe526e49ab635527e31f5b288f34c516f40a5d1881ecaa6912f1b'
}
if ($CandidateBridge) {
 $bridge = $CandidateBridge
 $candHashExpected = $CandidateSha256
 Require ($candHashExpected -match '^[0-9a-f]{64}$') 'CANDIDATE_SHA_REQUIRED'
}
$env:VERIFY_PRIVATE_POSTER = '1'
if ($InputPlan) {
 Require ($Steps -eq 'private_input_plan') 'INPUT_PLAN_STEPS_REQUIRED'
 $env:VERIFY_INPUT_PLAN = (Resolve-Path -LiteralPath $InputPlan).Path
} else {
 Remove-Item Env:VERIFY_INPUT_PLAN -ErrorAction SilentlyContinue
}
function Hash([string] $path) { (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() }
function NoGame { @(Get-Process -Name LC.guard -ErrorAction SilentlyContinue).Count -eq 0 }
$slot = Join-Path $taskRoot 'work/standalone_boot/current-unmodified-clone/own-login-bridge-dg49.dll'
$bridgeBaseline = Join-Path $taskRoot 'work/local_original_session/native-verified-socket-duplicate/own-login-bridge-dg49.dll'
$baseHash = '1d1f60a03144f0214bee56c4a875d4444d51811649135a1eaab82ec2e2899f75'
$candHash = $candHashExpected
Require (((Hash $slot) -ceq $baseHash) -and ((Hash $bridgeBaseline) -ceq $baseHash) -and ((Hash $bridge) -ceq $candHash)) ('BRIDGE_PIN_CHANGED slot=' + (Hash $slot) + ' cand=' + (Hash $bridge))
$installed = $false
$runCode = -1
try {
Copy-Item -LiteralPath $bridge -Destination $slot -Force
$installed = $true
Require ((Hash $slot) -ceq $candHash) 'INSTALLED_BRIDGE_MISMATCH'
$ErrorActionPreference = 'Continue'
& $taskPython -X utf8 -B (Join-Path $PSScriptRoot 'verify_ncg_waitonly.py') $RunName --candidate-bridge $bridge --expected-uuid a1416ea8-d0e1-4b93-b622-c27752ef6b51 --store (Join-Path $profile 'characters.json') --feature-config $config --steps $Steps --tool-timeout-seconds $Timeout *> (Join-Path $profile 'execution.log')
$runCode = $LASTEXITCODE
$ErrorActionPreference = 'Stop'
} finally {
 if ($installed) {
  for ($i = 0; $i -lt 30 -and -not (NoGame); $i++) { Start-Sleep -Seconds 1 }
  Require (NoGame) 'LIVE_GAME_PREVENTS_SLOT_RESTORE'
  Copy-Item -LiteralPath $bridgeBaseline -Destination $slot -Force
  Require ((Hash $slot) -ceq $baseHash) 'BASELINE_RESTORE_FAILED'
  Write-Output 'SLOT_RESTORED=1d1f'
 }
 if ($Steps -eq 'knight_skill_cast' -and (Test-Path -LiteralPath $run)) {
  $prepared = Join-Path $profile 'knight-skill-prepared.json'
  if (Test-Path -LiteralPath $prepared) {
   Copy-Item -LiteralPath $prepared -Destination (Join-Path $run 'knight-skill-prepared.json') -ErrorAction Stop
  }
 }
}
Write-Output ('RUN_EXIT=' + $runCode)
for ($i = 0; $i -lt 20 -and @(Get-Process -Name LC.guard -ErrorAction SilentlyContinue).Count -gt 0; $i++) { Start-Sleep -Seconds 1 }
Write-Output ('LC_LEFT=' + @(Get-Process -Name LC.guard -ErrorAction SilentlyContinue).Count)
exit $runCode

