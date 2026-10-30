param(
    [Parameter(Mandatory=$true)][string] $RunName,
    [string] $Steps = 'pet_after_capture_late',
    [string] $SourceProfile = 'manual-test-knight',
    [int] $Timeout = 110,
    [switch] $ReviveCompanion,
    [Parameter(Mandatory=$true)][string] $CandidateBridge,
    [Parameter(Mandatory=$true)][string] $CandidateSha256,
    [string] $InputPlan = ''
)
$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../../..')).Path
$capture = Join-Path $taskRoot 'work/standalone_boot/current-unmodified-clone/Capture'
$preexisting = Join-Path $taskRoot ('work/local_original_session/validation-profiles/' + $RunName + '-capture-preexisting')
$produced = Join-Path $taskRoot ('work/local_original_session/validation-profiles/' + $RunName + '-capture-produced')
function Require([bool] $ok, [string] $code) { if (-not $ok) { throw $code } }
foreach ($path in @($capture, $preexisting, $produced)) {
    $full = [IO.Path]::GetFullPath($path)
    Require ($full.StartsWith($taskRoot + '\', [StringComparison]::OrdinalIgnoreCase)) 'CAPTURE_PATH_OUTSIDE_WORKSPACE'
}
Require (@(Get-Process -Name LC.guard -ErrorAction SilentlyContinue).Count -eq 0) 'LIVE_GAME_ALREADY_PRESENT'
Require (@(Get-NetTCPConnection -State Listen -LocalPort 12000,14030 -ErrorAction SilentlyContinue).Count -eq 0) 'TEST_PORT_OCCUPIED'
Require ((Test-Path -LiteralPath $capture -PathType Container) -and
         -not (Test-Path -LiteralPath $preexisting) -and
         -not (Test-Path -LiteralPath $produced)) 'CAPTURE_SWAP_PRECONDITION'
# Preserve all prior run PNGs; capture swap/finally restoration below is unchanged.
$captureItem = Get-Item -LiteralPath $capture
Require (-not [bool]($captureItem.Attributes -band [IO.FileAttributes]::ReparsePoint)) 'CAPTURE_REPARSE_POINT'
$before = @(Get-ChildItem -LiteralPath $capture -File)
Require (@($before | Where-Object {$_.Name -notmatch '^LinC\d{4}\.png$'}).Count -eq 0) 'CAPTURE_UNEXPECTED_FILE'
$beforeBytes = ($before | Measure-Object -Property Length -Sum).Sum
$swapped = $false
$runCode = 1
try {
    Move-Item -LiteralPath $capture -Destination $preexisting -ErrorAction Stop
    $swapped = $true
    New-Item -ItemType Directory -Path $capture -ErrorAction Stop | Out-Null
    & (Join-Path $PSScriptRoot 'run_verify_ncg_waitonly.ps1') -RunName $RunName -Steps $Steps -SourceProfile $SourceProfile -Timeout $Timeout -ReviveCompanion:$ReviveCompanion -CandidateBridge $CandidateBridge -CandidateSha256 $CandidateSha256 -InputPlan $InputPlan
    $runCode = $LASTEXITCODE
} finally {
    if ($swapped) {
        Require (@(Get-Process -Name LC.guard -ErrorAction SilentlyContinue).Count -eq 0) 'LIVE_GAME_PREVENTS_CAPTURE_RESTORE'
        if (Test-Path -LiteralPath $capture) {
            Move-Item -LiteralPath $capture -Destination $produced -ErrorAction Stop
        }
        Move-Item -LiteralPath $preexisting -Destination $capture -ErrorAction Stop
        $after = @(Get-ChildItem -LiteralPath $capture -File)
        Require (($after.Count -eq $before.Count) -and
                 (($after | Measure-Object -Property Length -Sum).Sum -eq $beforeBytes)) 'CAPTURE_RESTORE_MISMATCH'
        Write-Output ('CAPTURE_RESTORED=' + $after.Count)
        # The run already copied each screenshot it used into runs/<RunName>.
        if (Test-Path -LiteralPath $produced) {
            Remove-Item -LiteralPath $produced -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}
exit $runCode
