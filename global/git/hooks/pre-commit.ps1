# Pre-commit hook: runs dotnet format on staged .cs files (PowerShell / Windows)

try { $null = dotnet --version }
catch {
    Write-Host "Error: dotnet command not found. Please install .NET SDK." -ForegroundColor Red
    exit 1
}

$stagedFiles = git diff --cached --name-only --diff-filter=ACM | Where-Object { $_ -match '\.cs$' }

if (-not $stagedFiles) { exit 0 }

$solutionFiles = Get-ChildItem -Path . -Filter "*.sln" -Recurse |
    Where-Object { $_.FullName -notmatch '\.git|node_modules|\\bin\\|\\obj\\' } |
    Select-Object -ExpandProperty FullName

if (-not $solutionFiles) {
    $projectFiles = Get-ChildItem -Path . -Filter "*.csproj" -Recurse |
        Where-Object { $_.FullName -notmatch '\.git|node_modules|\\bin\\|\\obj\\' } |
        Select-Object -ExpandProperty FullName

    if (-not $projectFiles) {
        Write-Host "Error: No .csproj files found." -ForegroundColor Red
        exit 1
    }

    foreach ($project in $projectFiles) {
        $result = dotnet format $project --verbosity quiet 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Error: dotnet format failed on $project" -ForegroundColor Red
            Write-Host $result -ForegroundColor Red
            exit 1
        }
    }
} else {
    foreach ($solution in $solutionFiles) {
        $result = dotnet format $solution --verbosity quiet 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Error: dotnet format failed on $solution" -ForegroundColor Red
            Write-Host $result -ForegroundColor Red
            exit 1
        }
    }
}

$modifiedFiles = git diff --name-only
if ($modifiedFiles) {
    Write-Host "Error: dotnet format modified files. Stage the changes before committing:" -ForegroundColor Red
    $modifiedFiles | ForEach-Object { Write-Host "  $_" -ForegroundColor Red }
    Write-Host ""
    Write-Host "Run 'git add .' to stage, or 'git commit --no-verify' to skip this check." -ForegroundColor Yellow
    exit 1
}

exit 0
