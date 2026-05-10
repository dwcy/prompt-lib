# SessionStart hook — detects project state and injects context for Claude
# Outputs JSON with additionalContext so Claude knows what to do on session start

try {
    $cwd = Get-Location

    $claudeMdExists = Test-Path (Join-Path $cwd "CLAUDE.md")

    if (-not $claudeMdExists) {
        $message = "No CLAUDE.md was found in this project directory ($cwd). Before doing anything else, ask the user: 'No CLAUDE.md found for this project. Would you like to describe it now so I can create one? Or say later and I will remind you next session.' If they describe the project, create a CLAUDE.md at the project root with: a project name heading, what the project does, the tech stack, key directories, and any important workflows. If they say later or skip, proceed normally without creating it."

        @{ additionalContext = $message } | ConvertTo-Json -Compress
        exit 0
    }

    $stackHints = @()

    $slnFiles    = Get-ChildItem -Path $cwd -Filter "*.sln"   -ErrorAction SilentlyContinue
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

        $isMonorepo = ($pkgJson -match '"workspaces"') -or
                      (Test-Path (Join-Path $cwd "pnpm-workspace.yaml")) -or
                      (Test-Path (Join-Path $cwd "turbo.json")) -or
                      (Test-Path (Join-Path $cwd "nx.json")) -or
                      (Test-Path (Join-Path $cwd "lerna.json"))

        if ($isMonorepo) {
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

    @{ additionalContext = $message } | ConvertTo-Json -Compress

} catch {
    # Never fail session start — exit cleanly without context
    exit 0
}
