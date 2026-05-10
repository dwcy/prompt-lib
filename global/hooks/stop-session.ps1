# Stop hook — warn about uncommitted changes at session end

try {
    git rev-parse --git-dir 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        exit 0
    }

    $status = git status --porcelain 2>$null
    if ($status) {
        $lines = ($status -split "`n") | Where-Object { $_ -ne "" }
        $count = $lines.Count
        $branch = git rev-parse --abbrev-ref HEAD 2>$null

        @{
            additionalContext = "Session ending with $count uncommitted change(s) on branch '$branch'. Consider committing or stashing before closing."
        } | ConvertTo-Json -Compress
    }
} catch {
    # Never fail the session stop
}

exit 0
