$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$target = if ($args.Count -gt 0) { $args[0].ToLowerInvariant() } else { "" }
$targetArgs = @()
if ($args.Count -gt 1) {
    $targetArgs = @($args[1..($args.Count - 1)])
}

switch ($target) {
    "web" {
        & (Join-Path $root "run-web.cmd") @targetArgs
    }
    "tauri" {
        & (Join-Path $root "run-tauri.cmd") @targetArgs
    }
    default {
        Write-Error "Unknown app '$target'. Expected 'web' or 'tauri'."
        exit 2
    }
}

exit $LASTEXITCODE
