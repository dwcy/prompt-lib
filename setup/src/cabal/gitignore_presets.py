# -*- coding: utf-8 -*-
"""Stack-specific .gitignore presets keyed by project-template stem."""

from __future__ import annotations

GITIGNORE_BY_TEMPLATE: dict[str, str] = {
    "python": """\
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
dist/
*.egg-info/
.eggs/
# Virtualenvs
.venv/
venv/
env/
ENV/
# Tooling caches
.pytest_cache/
.mypy_cache/
.ruff_cache/
.tox/
.coverage
htmlcov/
# Notebooks
.ipynb_checkpoints/
# Editors / OS
.idea/
.vscode/
*.swp
.DS_Store
Thumbs.db
# Env
.env
.env.local
# MCP (project-scope; may contain env-var values)
.mcp.json
""",
    "dotnet": """\
# .NET build outputs
bin/
obj/
out/
artifacts/
# Visual Studio / Rider
.vs/
.vshistory/
.idea/
*.user
*.suo
*.userprefs
*.userosscache
*.sln.docstates
# Symbols / coverage
*.pdb
*.opendb
TestResults/
coverage/
*.coverage
*.coverage.xml
# NuGet
*.nupkg
packages/
# Editor / OS
.vscode/
*.swp
.DS_Store
Thumbs.db
# Env
.env
# MCP (project-scope; may contain env-var values)
.mcp.json
""",
    "frontend": """\
# Dependencies
node_modules/
.pnpm-store/
# Build / output
dist/
build/
out/
.next/
.nuxt/
.output/
.svelte-kit/
.vercel/
.netlify/
.astro/
.expo/
# Cache
.cache/
.parcel-cache/
.turbo/
.eslintcache
.stylelintcache
# Coverage / test
coverage/
playwright-report/
test-results/
# Logs
npm-debug.log*
yarn-debug.log*
yarn-error.log*
pnpm-debug.log*
*.log
# Editor / OS
.vscode/
.idea/
*.swp
.DS_Store
Thumbs.db
# Env
.env
.env.*
!.env.example
# MCP (project-scope; may contain env-var values)
.mcp.json
""",
    "monorepo": """\
# Monorepo orchestrators
.turbo/
.nx/
.rush/
# Common build outputs
node_modules/
dist/
build/
out/
.next/
.svelte-kit/
coverage/
# Cache
.cache/
.parcel-cache/
# Logs
*.log
npm-debug.log*
yarn-debug.log*
pnpm-debug.log*
# Editor / OS
.vscode/
.idea/
.DS_Store
Thumbs.db
# Env
.env
.env.*
!.env.example
# MCP (project-scope; may contain env-var values)
.mcp.json
""",
    "unity": """\
# Unity-generated
[Ll]ibrary/
[Tt]emp/
[Oo]bj/
[Bb]uild/
[Bb]uilds/
[Ll]ogs/
[Uu]ser[Ss]ettings/
[Mm]emoryCaptures/
[Rr]ecordings/
# Generated solution / project files
*.csproj
*.unityproj
*.sln
*.suo
*.user
*.userprefs
*.pidb
*.booproj
*.svd
*.pdb
*.mdb
*.opendb
*.VC.db
# Build artifacts
ExportedObj/
.consulo/
*.apk
*.aab
*.unitypackage
crashlytics-build.properties
# OS / editor
.vscode/
.idea/
.DS_Store
Thumbs.db
# MCP (project-scope; may contain env-var values)
.mcp.json
""",
    "other": """\
# OS
.DS_Store
Thumbs.db
ehthumbs.db
desktop.ini
# Editor
.vscode/
.idea/
*.swp
*.swo
*~
# Logs
*.log
# Env
.env
.env.local
# MCP (project-scope; may contain env-var values)
.mcp.json
""",
}
