<#
.SYNOPSIS
  Finds (and optionally kills) orphaned Claude Code helper processes on Windows.

.DESCRIPTION
  Claude Code / Claude Desktop sessions spawn node.exe, claude.exe, sh.exe and
  small unix helpers (du.exe, grep.exe, rg.exe, tail.exe, head.exe). Known bugs
  can leave these running after a session ends ("orphans"), eating RAM and disk I/O.

  Default mode is a safe REPORT ONLY (nothing is killed).

.USAGE
  Report only:            powershell -ExecutionPolicy Bypass -File .\Claude-ProcessCheck.ps1
  Kill orphans:            powershell -ExecutionPolicy Bypass -File .\Claude-ProcessCheck.ps1 -Kill
  Also kill old --resume: powershell -ExecutionPolicy Bypass -File .\Claude-ProcessCheck.ps1 -Kill -ResumeAgeHours 2
#>

param(
  [switch]$Kill,                 # actually terminate flagged processes (default: dry run)
  [int]$ResumeAgeHours = 0       # >0: also flag claude.exe/node.exe "--resume" procs older than N hours
)

$names = @('node.exe','claude.exe','sh.exe','bash.exe','du.exe','grep.exe','rg.exe','tail.exe','head.exe','uname.exe','cygpath.exe')
$filter = ($names | ForEach-Object { "Name='$_'" }) -join ' OR '

$procs = Get-CimInstance Win32_Process -Filter $filter
if (-not $procs) { Write-Host 'No matching processes found. All clean!' -ForegroundColor Green; return }

$allPids = @{}
Get-CimInstance Win32_Process | ForEach-Object { $allPids[$_.ProcessId] = $_.Name }

$rows = foreach ($p in $procs) {
  $parentAlive = $allPids.ContainsKey($p.ParentProcessId)
  $parentName  = if ($parentAlive) { $allPids[$p.ParentProcessId] } else { '(dead)' }
  $ageH        = [math]::Round(((Get-Date) - $p.CreationDate).TotalHours, 1)
  $memMB       = [math]::Round($p.WorkingSetSize / 1MB, 0)
  $cmd         = if ($p.CommandLine) { $p.CommandLine } else { '' }

  $isClaudeRelated = $cmd -match 'claude|anthropic|\\\.claude\\|ripgrep' -or
                     $p.Name -in @('du.exe','grep.exe','rg.exe','tail.exe','head.exe','sh.exe','uname.exe','cygpath.exe','claude.exe')

  $orphan = $false; $reason = ''
  if (-not $parentAlive -and $isClaudeRelated) { $orphan = $true; $reason = 'parent process is gone' }
  if ($ResumeAgeHours -gt 0 -and $cmd -match '--resume' -and $ageH -gt $ResumeAgeHours) {
    $orphan = $true; $reason = "--resume proc older than $ResumeAgeHours h"
  }

  # Never flag node.exe that does NOT look Claude-related (protects your dev servers!)
  if ($p.Name -eq 'node.exe' -and -not ($cmd -match 'claude|anthropic')) { $orphan = $false; $reason = '' }

  [pscustomobject]@{
    PID     = $p.ProcessId
    Name    = $p.Name
    Parent  = "$($p.ParentProcessId) $parentName"
    AgeHrs  = $ageH
    MemMB   = $memMB
    Orphan  = $orphan
    Reason  = $reason
    Cmd     = if ($cmd.Length -gt 90) { $cmd.Substring(0,90) + '...' } else { $cmd }
  }
}

$rows | Sort-Object -Property @{e='Orphan';Descending=$true}, @{e='MemMB';Descending=$true} |
  Format-Table PID, Name, Parent, AgeHrs, MemMB, Orphan, Reason -AutoSize

$totalMB  = ($rows | Measure-Object MemMB -Sum).Sum
$orphans  = $rows | Where-Object Orphan
$orphanMB = ($orphans | Measure-Object MemMB -Sum).Sum

Write-Host ""
Write-Host ("Total: {0} processes, {1} MB RAM. Flagged as orphaned: {2} processes, {3} MB RAM." -f `
  $rows.Count, $totalMB, $orphans.Count, [int]$orphanMB) -ForegroundColor Cyan

if ($orphans.Count -eq 0) { return }

if ($Kill) {
  Write-Host "`nKilling flagged processes..." -ForegroundColor Yellow
  foreach ($o in $orphans) {
    try { Stop-Process -Id $o.PID -Force -ErrorAction Stop; Write-Host ("  killed {0} {1}" -f $o.PID, $o.Name) }
    catch { Write-Host ("  could not kill {0} {1}: {2}" -f $o.PID, $o.Name, $_.Exception.Message) -ForegroundColor Red }
  }
  # conhost.exe orphans that belonged to killed console helpers die on their own;
  # sweep any leftover ripgrep consoles explicitly:
  Get-Process rg -ErrorAction SilentlyContinue | Where-Object { $_.StartTime -lt (Get-Date).AddHours(-1) } | Stop-Process -Force -ErrorAction SilentlyContinue
} else {
  Write-Host "`nDry run only - nothing was killed. Re-run with -Kill to remove the flagged orphans." -ForegroundColor Yellow
}
