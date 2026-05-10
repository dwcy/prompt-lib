# SessionStart hook — detects project state and injects context for Claude
# Outputs JSON with additionalContext so Claude knows what to do on session start

$cwd = Get-Location

# Check if CLAUDE.md exists in current directory
$claudeMdExists = Test-Path (Join-Path $cwd "CLAUDE.md")

if (-not $claudeMdExists) {
    # New project — prompt Claude to invoke init-project
    $message = "IMPORTANT: No CLAUDE.md was found in this project directory ($cwd). This project has not been initialized yet. Before doing any other work, proactively invoke the @init-project agent to help the developer set up project conventions, architecture rules, and a CLAUDE.md file."

    @{
        additionalContext = $message
    } | ConvertTo-Json -Compress

    exit 0
}

# Existing project — detect stack and prompt Claude to invoke load-project
$stackHints = @()

$slnFiles  = Get-ChildItem -Path $cwd -Filter "*.sln"  -ErrorAction SilentlyContinue
$csprojFiles = Get-ChildItem -Path $cwd -Recurse -Filter "*.csproj" -Depth 3 -ErrorAction SilentlyContinue

if ($slnFiles.Count -gt 0 -or $csprojFiles.Count -gt 0) {
    $stackHints += ".NET"
}

if ((Test-Path (Join-Path $cwd "requirements.txt")) -or
    (Test-Path (Join-Path $cwd "pyproject.toml")) -or
    (Test-Path (Join-Path $cwd "Pipfile"))) {
    $stackHints += "Python"
}

if (Test-Path (Join-Path $cwd "package.json")) {
    $pkgJson = Get-Content (Join-Path $cwd "package.json") -Raw -ErrorAction SilentlyContinue
    if ($pkgJson -match '"apps"' -or (Test-Path (Join-Path $cwd "apps"))) {
        $stackHints += "Monorepo"
    } else {
        $stackHints += "JavaScript/TypeScript"
    }
}

if ((Test-Path (Join-Path $cwd "Assets")) -and (Test-Path (Join-Path $cwd "ProjectSettings"))) {
    $stackHints += "Unity3D"
}

$stackLabel = if ($stackHints.Count -gt 0) { $stackHints -join " + " } else { "unknown stack" }

$message = "Existing project detected ($stackLabel) in $cwd. A CLAUDE.md exists. Proactively invoke the @load-project agent to read the project context and announce which specialist subagents are available for this session."

@{
    additionalContext = $message
} | ConvertTo-Json -Compress
