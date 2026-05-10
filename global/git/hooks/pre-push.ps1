# Pre-push hook: runs dotnet test before pushing (PowerShell / Windows)

Write-Host "Running dotnet test before push..." -ForegroundColor Blue

try { $dotnetVersion = dotnet --version; Write-Host "Using .NET $dotnetVersion" -ForegroundColor Green }
catch { Write-Host "Error: dotnet command not found. Please install .NET SDK." -ForegroundColor Red; exit 1 }

$allProjects = Get-ChildItem -Path . -Filter "*.csproj" -Recurse |
    Where-Object { $_.FullName -notmatch '\.git|node_modules|\\bin\\|\\obj\\' }

$testProjects = $allProjects | Where-Object {
    (Get-Content $_.FullName -Raw) -match 'Microsoft\.NET\.Test\.Sdk|xunit|nunit|mstest'
} | Select-Object -ExpandProperty FullName

if ($testProjects.Count -eq 0) {
    Write-Host "No test projects found. Looking for solution files..." -ForegroundColor Yellow

    $solutionFiles = Get-ChildItem -Path . -Filter "*.sln" -Recurse |
        Where-Object { $_.FullName -notmatch '\.git|node_modules|\\bin\\|\\obj\\' } |
        Select-Object -ExpandProperty FullName

    if ($solutionFiles.Count -eq 0) {
        if ($allProjects.Count -eq 0) {
            Write-Host "No .NET projects found. Skipping." -ForegroundColor Green
            exit 0
        }
        dotnet test --verbosity quiet --no-build
        if ($LASTEXITCODE -ne 0) { Write-Host "Error: Tests failed!" -ForegroundColor Red; exit 1 }
    } else {
        foreach ($solution in $solutionFiles) {
            Write-Host "Testing: $solution" -ForegroundColor Blue
            dotnet test $solution --verbosity quiet --no-build
            if ($LASTEXITCODE -ne 0) { Write-Host "Error: Tests failed for $solution" -ForegroundColor Red; exit 1 }
        }
    }
} else {
    foreach ($project in $testProjects) {
        Write-Host "Testing: $project" -ForegroundColor Blue
        dotnet test $project --verbosity quiet --no-build
        if ($LASTEXITCODE -ne 0) { Write-Host "Error: Tests failed for $project" -ForegroundColor Red; exit 1 }
    }
}

Write-Host "All tests passed. Pushing..." -ForegroundColor Green
exit 0
