param([switch]$Run,[ValidateSet('control','candidate')][string]$Variant='control',
    [ValidateSet('normal','codec-diagnostic')][string]$Mode='normal')
$ErrorActionPreference='Stop'
$python='C:\Users\Chansol\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$entry='C:\Users\Chansol\Documents\ChatGPT\싱글리니지\tools\clone_observer\observer.py'
$expected='C:\Users\Chansol\Documents\ChatGPT\싱글리니지\tools\clone_observer\launch.ps1'
if([IO.Path]::GetFullPath($PSCommandPath) -cne $expected){throw 'fixed_observer_launcher_required'}
$arguments=@('-I','-B',('"'+$entry+'"'),'--variant',$Variant,'--mode',$Mode)
if($Run){$arguments+='--run'}
# Ordinary hidden controller console. No Verb RunAs/UAC/retries. Its own fixed
# game's public first-gate notice can be visible; no UI clicking or input.
$process=Start-Process -FilePath $python -ArgumentList $arguments -WindowStyle Hidden -PassThru
$process.WaitForExit()
exit $process.ExitCode
