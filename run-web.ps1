[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $ViteArgs
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$appDirectory = Join-Path $root "apps\cabal-desktop"
$exitCode = 1
$backend = $null

$startInfo = [System.Diagnostics.ProcessStartInfo]::new()
$startInfo.FileName = (Get-Command uv -ErrorAction Stop).Source
$startInfo.WorkingDirectory = $root
$startInfo.UseShellExecute = $false
$startInfo.Arguments = 'run cabal-backend --project "' + $root + '"'
# CABAL_DEV opens CORS to the Vite dev origins; packaged builds never set it.
$startInfo.EnvironmentVariables["CABAL_DEV"] = "1"

try {
    $backend = [System.Diagnostics.Process]::Start($startInfo)
    Push-Location $appDirectory
    try {
        & pnpm dev @ViteArgs
        $exitCode = $LASTEXITCODE
    }
    finally {
        Pop-Location
    }
}
finally {
    if ($null -ne $backend -and -not $backend.HasExited) {
        try {
            & "$env:SystemRoot\System32\taskkill.exe" /PID $backend.Id /T /F *> $null
        }
        catch {
            # The backend may have completed between the state check and cleanup.
        }
    }
    if ($null -ne $backend) {
        $backend.Dispose()
    }
}

exit $exitCode
