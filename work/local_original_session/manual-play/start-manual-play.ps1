param([switch] $World, [switch] $TestKnight, [int] $Stance = -1, [ValidateSet(0, 1, 2, 3)] [int] $Hpbar = 0, [ValidateSet(0, 1, 2, 3)] [int] $MapExp = 0, [string] $ArrowExp = '0', [ValidateSet('', '0', 'off')] [string] $ShopExp = '', [switch] $PolyExp, [string] $PolyForm = 'orc', [string] $EnchantExp = '', [ValidateSet('', '0', 'off')] [string] $WarehouseExp = '', [switch] $Companion, [switch] $CompanionPetUi, [switch] $SpellExp, [switch] $CompanionReviveExp, [switch] $CompanionBridge, [switch] $FullWorld)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../../..')).Path
$taskRoot = (Get-Location).Path
$taskPython = 'C:\Users\Chansol\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
function Require([bool] $ok, [string] $code) { if (-not $ok) { throw $code } }
function Hash([string] $path) { (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() }
Require (@(Get-Process -Name LC.guard -ErrorAction SilentlyContinue).Count -eq 0) 'GAME_ALREADY_RUNNING'
Require (@(Get-NetTCPConnection -State Listen -LocalPort 12000,14030 -ErrorAction SilentlyContinue).Count -eq 0) 'LOCAL_GAME_PORT_OCCUPIED'
$pins = @{
 'tools/local_original_session/restart.py' = 'bdc519842d6484ce929571c607746703f092268f1fcead3415ae3407b877177e'
 'tools/local_original_session/attack.py' = 'fcd57d7d32611e91277677708d25442d132343c67e821a50b42bdff8f12bac7f'
 'tools/local_original_session/attack_feedback.py' = 'a0ee6b4bcc366caf8329222d3bf303c9c27463577d65c1cfb1c4d33143da0b31'
 'tools/local_original_session/attack_session.py' = 'e0bb5fa96bf53d01586f12ddb5970571eec5d5c6f0976ebb5af4c0a8b900c8c0'
 'tools/local_original_session/feature_config.py' = '7b444f403d11c920a7afdcb0cb9b3fd4713a314033624ba01d630989909138a2'
 'tools/local_original_session/inventory.py' = '0441a23a0d2568f7f843a1852d7492ede5f2c36a29174df3194dc62181128f79'
 'tools/local_original_session/inventory_store.py' = 'ec718f65a1767a204bf797a2e3f6ff8b03669e8f5dc5d423ffec287e7b23a091'
 'tools/local_original_session/observe.py' = '8a2b6f25f95f5d39e44ec6e0b4936e50170deca8d2d6e9e99c4e229d4b5531b6'
 'tools/local_original_session/attack_action_observe.py' = 'a3465588dff68add0b7f9158adade3436bdce39d8c21466f93d121f8bfc5b533'
 'tools/local_original_session/edge.py' = 'e758a6eb692b44d8bf5742150592ddda8814abda8d58d418c3710d0c42447d28'
 'tools/local_original_session/launcher.py' = 'ff44cfe2baca59ae69c9649899eaf523c56efe704c5d24e597043a2f2d90ddd8'
 'tools/local_original_session/broker.py' = 'ccd6700f65e927eaabe7074aa6980bc2ebad32315bdd748f4046340db37ce522'
 'tools/local_original_session/manual_move_commands.py' = '2cbe1d0bf3acfe3974dac11dd1be153cd39bb407c746bffb22a47f050b5bd571'
 'tools/local_original_session/inventory_observe.py' = 'd381f7e1f8effd5f22565260bf9611c7dfb361e741018755da682267d355cf37'
 'tools/local_original_session/athame_policy.py' = '21f61a827fc2273d0b4e33c1bcbb41a34b0742e757add7c2b5dbf343d0e19b33'
 'tools/local_original_session/equipment_change.py' = 'df3bf2138fbdc206f78e1b37e7e666f2da8bcdde4f9f450a23960577dd283aba'
 'tools/local_original_session/equipment_store.py' = '6fffd5b81a132fdef2cc9125c033c7f83ad0b52eff19eb715a03ae2e3554f3e3'
 'tools/local_original_session/equipment_observe.py' = '71225a49be2c7a3020dbd13f714bdf7121b8223579425ec8c6f03ee5ad0cf0bf'
 'tools/local_original_session/item_equipment_effect.py' = 'e360bcaea3159f75e69ed6255d41b1909a4cd0210df6d808e1b13d05e325ca45'
 'tools/local_original_session/item_use_session.py' = '83d152a39e9e1f2ad84bfadd0951e7c533a9ec16690e0d7e0bc77e83a5ec5034'
 'work/local_original_session/manual-play/item-equipment-runtime-config.json' = 'f75c73d001cc3d06b80d9d3a1a4e8cb79888561a595571ea46b5b0a4c81d3aae'
 'work/standalone_boot/current-unmodified-clone/LC.guard.exe' = '8b9e2628286c295adf71bf3c0cb0882164aeaa7d63b97f50c46114b53650b684'
 'work/standalone_boot/current-unmodified-clone/own-login-bridge-dg49.dll' = '1d1f60a03144f0214bee56c4a875d4444d51811649135a1eaab82ec2e2899f75'
 'tools/local_original_session/input.py' = '565b559b5c58be06eb4f42f2e95413b9af85803162744ef0d7145506f1af602d'
}
foreach ($path in $pins.Keys) { Require ((Hash $path) -ceq $pins[$path]) "PLAY_SOURCE_CHANGED:$path" }
# -FullWorld: the hunt bots' world (MapExp 2 dungeons/population + M5 maps).
if ($FullWorld) { $MapExp = 2 }
$profile = Join-Path $taskRoot 'work/local_original_session/validation-profiles/manual-user-play'
$runPrefix = 'manual-user-play-'
if ($TestKnight) {
 # Test-only knight profile (never the user's manual-user-play) on the M1 world with data/m1/starter.json kits.test_knight.
 $World = $true
 $profile = Join-Path $taskRoot 'work/local_original_session/validation-profiles/manual-test-knight'
 $runPrefix = 'manual-test-knight-'
}
# Companion is restricted to the test knight; never modify manual-user-play.
# -CompanionBridge: companion bridge candidate DLL (companion-nopatch) in the bridge slot for this run only,
# with the companion and pet window enabled. The pinned bridge is restored when the run ends.
if ($CompanionBridge) { $Companion = $true; $CompanionPetUi = $true }
if ($CompanionPetUi) { $Companion = $true }
# run404: opt-in in-place 4F16; default retained-UID 4E96 replacement.
if ($CompanionReviveExp) { $Companion = $true; $env:SL_COMPANION_REVIVE_EXP = '1' } else { Remove-Item Env:SL_COMPANION_REVIVE_EXP -ErrorAction SilentlyContinue }
if ($SpellExp) { $Companion = $true; $env:SL_SPELL_EXP = '1' } else { Remove-Item Env:SL_SPELL_EXP -ErrorAction SilentlyContinue }
if ($Companion) {
 Require ([bool]$TestKnight) 'COMPANION_REQUIRES_TESTKNIGHT'
 $env:SL_COMPANION = '1'
 Write-Host '?? ?: ?? ?? ??, ??? ?? ??/?? ????? ?? (LOCAL ?? ??)'
} else { Remove-Item Env:SL_COMPANION -ErrorAction SilentlyContinue }
if ($CompanionPetUi) {
 $env:SL_COMPANION_PET_UI = '1'
 Write-Host '?? ??: ?? ???? ??/??/??/??/?? ?? (?? ?? ?? ??)'
} else { Remove-Item Env:SL_COMPANION_PET_UI -ErrorAction SilentlyContinue }
$source = Join-Path $taskRoot 'work/local_original_session/validation-profiles/manual-background-combined-83'
$closed = Get-Content -Raw -LiteralPath (Join-Path $taskRoot 'work/local_original_session/runs/manual-background-combined-83/result.json') | ConvertFrom-Json
Require (($closed.cleanup.owned_job_empty -eq $true) -and ($closed.broker.cleanup_complete -eq $true)) 'SOURCE_SESSION_NOT_CLEANED'
if (-not (Test-Path -LiteralPath $profile)) {
 New-Item -ItemType Directory -Path $profile | Out-Null
 foreach ($name in @('characters.json','positions.json','account-settings.bin')) {
  Copy-Item -LiteralPath (Join-Path $source $name) -Destination (Join-Path $profile $name)
 }
 if ($TestKnight) {
  # lc-owned-character-store-v1 row (name/UID must equal the fixed own profile SoloKnight/1): class 1 knight, gender 0 (male, sprite 61), STR/DEX/CON/WIS/CHA/INT
  # = L1J knight base 16/12/14/9/12/8 + 4 bonus points on STR/CON (total 75, L1KnightClassFeature/C_CreateChar).
  $knight = '{"schema":"lc-owned-character-store-v1","next_uid":2,"characters":[{"uid":1,"name":"SoloKnight","class":1,"gender":0,"attributes":[18,12,16,9,12,8]}]}' + "`n"
  [System.IO.File]::WriteAllText((Join-Path $profile 'characters.json'), $knight, (New-Object System.Text.UTF8Encoding $false))
 }
}
foreach ($name in @('characters.json','positions.json','account-settings.bin')) { Require (Test-Path -LiteralPath (Join-Path $profile $name) -PathType Leaf) 'INCOMPLETE_PLAY_PROFILE' }
$runName = $runPrefix + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N').Substring(0,8)
$run = Join-Path $taskRoot ('work/local_original_session/runs/' + $runName)
Write-Host '寃뚯엫 援ъ꽦: 濡쒖뺄 ?몃깽?좊━ 吏湲됀룹븘?댄뀥 ?ъ슜쨌?λ퉬 ???蹂듭썝 ?곌껐'
Write-Host '?섎룞 ?뚮젅?대? ?쒖옉?⑸땲?? 濡쒓렇??罹먮┃???좏깮/?대룞/醫낅즺??吏곸젒 議곗옉?섏꽭??'
Write-Host ('?꾩슜 ??? ' + $profile)
Write-Host ('?ㅽ뻾 湲곕줉: ' + $run)
$featureConfig = 'work/local_original_session/manual-play/item-equipment-runtime-config.json'
if ($MapExp -gt 0 -or $ArrowExp -ne '0' -or $PolyExp -or $EnchantExp -ne '') { $World = $true }
if ($World) {
 # Same pinned config plus the opt-in M1 world key, written next to the run record.
 $raw = Get-Content -Raw -Encoding UTF8 -LiteralPath $featureConfig
 $end = $raw.LastIndexOf('}')
 Require ($end -gt 0) 'PLAY_FEATURE_CONFIG_SHAPE'
 $worldConfig = Join-Path $taskRoot ('work/local_original_session/runs/' + $runName + '.world-config.json')
 $kit = ''
 if ($TestKnight) { $kit = ", `"starter_kit`": `"test_knight`"" }
 $text = $raw.Substring(0, $end).TrimEnd() + ",`n  `"world`": {`"policy`": `"LOCAL_M1_WORLD_INTEREST_SPAWN`"" + $kit + "}`n}`n"
 [System.IO.File]::WriteAllText($worldConfig, $text, (New-Object System.Text.UTF8Encoding $false))
 $featureConfig = $worldConfig
 Write-Host ('?붾뱶 耳? 留먰븯????遺곸そ 珥덉썝 紐?異쒗쁽 (' + $worldConfig + ')')
 if ($TestKnight) { Write-Host '?뚯뒪??湲곗궗(????몃깽?좊━媛 ?놁쓣 ??吏湲?: ?κ?쨌??諛⑺뙣쨌鍮꾨뒛 媛묒샆쨌蹂댄샇 留앺넗 李⑹슜, ?ш뎄쨌?곗뀛痢졖룸?痢졖룹옣媛묒? 媛諛⑹뿉???붾툝?대┃ 李⑹슜, 鍮④컙 臾쇱빟 100쨌珥덈줉 臾쇱빟 20쨌?⑷린??臾쇱빟 20쨌?꾨뜲??1000' }
}
if ($Stance -ge 0) { $env:SL_EXPERIMENT_ACTOR_F4 = [string]$Stance; Write-Host ("?먯꽭 ?ㅽ뿕: ActorNotify f4 = " + $Stance) } else { Remove-Item Env:SL_EXPERIMENT_ACTOR_F4 -ErrorAction SilentlyContinue }
if ($Hpbar -gt 0) { $env:SL_EXPERIMENT_HPBAR = [string]$Hpbar; Write-Host ("HP ?쒖떆 ?ㅽ뿕 ?꾨낫: " + $Hpbar) } else { Remove-Item Env:SL_EXPERIMENT_HPBAR -ErrorAction SilentlyContinue }
# run386: present f6=0 LOCAL candidate; f14=1 native default; raw f9..12 absent.
# -ArrowExp 'f6' or 'f6,f14' overrides these values.
$env:SL_EXPERIMENT_ARROW = $ArrowExp
# LOCAL shop defaults on in a world configuration; 0/off disables it.
if ($ShopExp -ne '') { $env:SL_EXPERIMENT_SHOP = '0' } else { Remove-Item Env:SL_EXPERIMENT_SHOP -ErrorAction SilentlyContinue }
# run390: form selection, normal grade1, duration and zero-stance restoration remain LOCAL experiments.
if ($PolyExp) { $env:SL_EXPERIMENT_POLY = $PolyForm; Write-Host ('蹂???ㅽ뿕 ??? ' + $PolyForm) } else { Remove-Item Env:SL_EXPERIMENT_POLY -ErrorAction SilentlyContinue }
# run393: raw7 interaction and SC0967 operands/status are LOCAL candidates.
# -EnchantExp 1; overrides '1,f3=2,f4=6' apply to required f1..5.
if ($EnchantExp -ne '') { $env:SL_EXPERIMENT_ENCHANT = $EnchantExp } else { Remove-Item Env:SL_EXPERIMENT_ENCHANT -ErrorAction SilentlyContinue }
# LOCAL personal warehouse defaults on in a world configuration; 0/off disables it.
if ($WarehouseExp -ne '') { $env:SL_EXPERIMENT_WAREHOUSE = '0' } else { Remove-Item Env:SL_EXPERIMENT_WAREHOUSE -ErrorAction SilentlyContinue }
# run380 section 8 LOCAL candidates; f2=0/f3=false/f4=false are not official values.
# 1 same-map baseline; 2 dungeon round trip; 3 same-map baseline minus 4E95.
if ($FullWorld) { $env:SL_EXPERIMENT_M5 = '1'; Write-Host '?꾩껜 ?붾뱶: ?섏쟾쨌異붽? 留돠룸す 梨꾩? (?щ깷 遊뉕낵 媛숈? ?ㅼ젙)' } else { Remove-Item Env:SL_EXPERIMENT_M5 -ErrorAction SilentlyContinue }
if ($MapExp -gt 0) { $env:SL_EXPERIMENT_MAP = [string]$MapExp; Write-Host ("留??꾪솚 ?ㅽ뿕 ?꾨낫: " + $MapExp + " (?먮낯 ?뺤긽媛믨낵 ?붾㈃ ?숈옉? 誘명솗??") } else { Remove-Item Env:SL_EXPERIMENT_MAP -ErrorAction SilentlyContinue }
$product = 'sibling-manual-play-spawn'
$slot = Join-Path $taskRoot 'work/standalone_boot/current-unmodified-clone/own-login-bridge-dg49.dll'
$bridgeBaseline = Join-Path $taskRoot 'work/local_original_session/native-verified-socket-duplicate/own-login-bridge-dg49.dll'
$bridgeCandidate = Join-Path $taskRoot 'work/local_original_session/companion-bridge/own-login-bridge-companion-nopatch.dll'
$bridgeBaseHash = '1d1f60a03144f0214bee56c4a875d4444d51811649135a1eaab82ec2e2899f75'
$bridgeCandidateHash = '13ed7d7dbaa99fc0620b4321cdc745b6094ae7a3e61b6bab58131ebf40a63695'
function NoGame { @(Get-Process -Name LC.guard -ErrorAction SilentlyContinue).Count -eq 0 }
if ($CompanionBridge) {
 Require (((Hash $slot) -ceq $bridgeBaseHash) -and ((Hash $bridgeBaseline) -ceq $bridgeBaseHash) -and ((Hash $bridgeCandidate) -ceq $bridgeCandidateHash)) 'BRIDGE_PIN_CHANGED'
 $product = 'sibling-manual-play-companion-nopatch'
 $env:SL_COMPANION_BRIDGE = '1'
 # Companion settings open the DLL-owned companion ATS window (buff/combat/recovery/option tabs).
 $env:COMPANION_ATS_WINDOW = '1'
 Write-Host '?숇즺 釉뚮━吏: companion-nopatch DLL???대쾲 ?ㅽ뻾?먮쭔 釉뚮━吏 ?먮━???ㅼ튂 (?앸굹硫??먮옒 DLL 蹂듭썝)'
} else { Remove-Item Env:SL_COMPANION_BRIDGE -ErrorAction SilentlyContinue; Remove-Item Env:COMPANION_ATS_WINDOW -ErrorAction SilentlyContinue }
$installed = $false
$runCode = -1
try {
 if ($CompanionBridge) {
  Copy-Item -LiteralPath $bridgeCandidate -Destination $slot -Force
  $installed = $true
  Require ((Hash $slot) -ceq $bridgeCandidateHash) 'INSTALLED_BRIDGE_MISMATCH'
 }
 & $taskPython -X utf8 -B -m tools.local_original_session.launcher --run --control-mode manual --product $product --image work/standalone_boot/current-unmodified-clone/LC.guard.exe --expected-uuid a1416ea8-d0e1-4b93-b622-c27752ef6b51 --store (Join-Path $profile 'characters.json') --run-directory $run --feature-config $featureConfig
 $runCode = $LASTEXITCODE
} finally {
 if ($installed) {
  for ($i = 0; $i -lt 30 -and -not (NoGame); $i++) { Start-Sleep -Seconds 1 }
  Require (NoGame) 'LIVE_GAME_PREVENTS_SLOT_RESTORE'
  Copy-Item -LiteralPath $bridgeBaseline -Destination $slot -Force
  Require ((Hash $slot) -ceq $bridgeBaseHash) 'BASELINE_RESTORE_FAILED'
 }
}
exit $runCode
