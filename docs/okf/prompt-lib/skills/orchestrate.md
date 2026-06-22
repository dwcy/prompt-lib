---
type: skill
title: orchestrate
description: /orchestrate — Automatic Subagent Routing
resource: global/skills/orchestrate.md
tags:
  - prompt-lib
  - skill
  - claude-code
timestamp: "2026-06-18T00:00:00Z"
id: "skill:orchestrate"
relations:
  -
    confidence: structured
    evidence:
      -
        extractor: routing_table
        line: 71
        resource: global/skills/orchestrate.md
        text: 19 | API contract / endpoints / OpenAPI / GraphQL schema / REST surface | design / structure | api-designer
    kind: routes_to
    reason: api-designer
    target: "agent:api-designer"
  -
    confidence: structured
    evidence:
      -
        extractor: routing_table
        line: 77
        resource: global/skills/orchestrate.md
        text: 25 | dead code / unused CSS / unused assets / unused dependencies / stale files / repo cleanup / clutter | clean / remove / refactor / audit | code-cleaner
    kind: routes_to
    reason: code-cleaner
    target: "agent:code-cleaner"
  -
    confidence: structured
    evidence:
      -
        extractor: routing_table
        line: 68
        resource: global/skills/orchestrate.md
        text: "16 | verify / plan conformance / \"does the code match\" / architecture review | verify / check / audit | code-plan-verifier"
    kind: routes_to
    reason: code-plan-verifier
    target: "agent:code-plan-verifier"
  -
    confidence: structured
    evidence:
      -
        extractor: routing_table
        line: 70
        resource: global/skills/orchestrate.md
        text: 18 | dataset / CSV / Parquet / SQL results / metrics / logs | analyse / profile / explore | data-analyst
    kind: routes_to
    reason: data-analyst
    target: "agent:data-analyst"
  -
    confidence: structured
    evidence:
      -
        extractor: routing_table
        line: 72
        resource: global/skills/orchestrate.md
        text: 20 | database schema / migration / indexing / normalisation / data model | architect / design / review | db-architect
    kind: routes_to
    reason: db-architect
    target: "agent:db-architect"
  -
    confidence: structured
    evidence:
      -
        extractor: routing_table
        line: 54
        resource: global/skills/orchestrate.md
        text: "2 | .NET / C# / csproj / CQRS / MediatR / Clean Architecture | architect / design / structure / review / DI / domain | dotnet-architect"
    kind: routes_to
    reason: dotnet-architect
    target: "agent:dotnet-architect"
  -
    confidence: structured
    evidence:
      -
        extractor: routing_table
        line: 53
        resource: global/skills/orchestrate.md
        text: "1 | .NET / C# / csproj / CQRS / MediatR | test / xUnit / NUnit / NSubstitute / Moq / TestContainers | dotnet-tester"
    kind: routes_to
    reason: dotnet-tester
    target: "agent:dotnet-tester"
  -
    confidence: structured
    evidence:
      -
        extractor: routing_table
        line: 57
        resource: global/skills/orchestrate.md
        text: 5 | React / Vue / Next.js / Nuxt / Angular (not Vite+Zustand stack) | architect / design / component / state | frontend-architect
    kind: routes_to
    reason: frontend-architect
    target: "agent:frontend-architect"
  -
    confidence: structured
    evidence:
      -
        extractor: routing_table
        line: 58
        resource: global/skills/orchestrate.md
        text: 6 | CSS / globals.css / design tokens / theming / CSS modules | implement / scaffold / audit | frontend-css
    kind: routes_to
    reason: frontend-css
    target: "agent:frontend-css"
  -
    confidence: structured
    evidence:
      -
        extractor: routing_table
        line: 59
        resource: global/skills/orchestrate.md
        text: 7 | UI design / UX / wireframe / design system / colors / typography / mockup | design / plan / vision | frontend-designer
    kind: routes_to
    reason: frontend-designer
    target: "agent:frontend-designer"
  -
    confidence: structured
    evidence:
      -
        extractor: routing_table
        line: 74
        resource: global/skills/orchestrate.md
        text: 22 | repo URL / GitHub repository / clone (mine for features or code) | analyse / research / extract | git-repo-analyst
    kind: routes_to
    reason: git-repo-analyst
    target: "agent:git-repo-analyst"
  -
    confidence: structured
    evidence:
      -
        extractor: routing_table
        line: 64
        resource: global/skills/orchestrate.md
        text: 12 | GitHub settings / branch protection / secret scanning / Dependabot | configure / set up / audit | github-config-manager
    kind: routes_to
    reason: github-config-manager
    target: "agent:github-config-manager"
  -
    confidence: structured
    evidence:
      -
        extractor: routing_table
        line: 65
        resource: global/skills/orchestrate.md
        text: 13 | .gitignore / staged files / pre-commit / `git add | audit / check | gitignore-auditor
    kind: routes_to
    reason: gitignore-auditor
    target: "agent:gitignore-auditor"
  -
    confidence: structured
    evidence:
      -
        extractor: routing_table
        line: 67
        resource: global/skills/orchestrate.md
        text: 15 | new project / CLAUDE.md missing / init / scaffold | setup / initialise | init-project
    kind: routes_to
    reason: init-project
    target: "agent:init-project"
  -
    confidence: structured
    evidence:
      -
        extractor: routing_table
        line: 76
        resource: global/skills/orchestrate.md
        text: 24 | security review / OWASP / vulnerability / auth flow / session / CSRF / XSS / injection / hardening / pre-release security | review / audit / scan / check | owasp-security-reviewer
    kind: routes_to
    reason: owasp-security-reviewer
    target: "agent:owasp-security-reviewer"
  -
    confidence: structured
    evidence:
      -
        extractor: routing_table
        line: 63
        resource: global/skills/orchestrate.md
        text: 11 | Raspberry Pi / Arduino / GPIO / I2C / SPI / UART / sensor / motor / servo | any | pi-arduino-architect
    kind: routes_to
    reason: pi-arduino-architect
    target: "agent:pi-arduino-architect"
  -
    confidence: structured
    evidence:
      -
        extractor: routing_table
        line: 61
        resource: global/skills/orchestrate.md
        text: 9 | Python / FastAPI / Django / SQLAlchemy / pyproject.toml | architect / design / structure / async / service layer | python-architect
    kind: routes_to
    reason: python-architect
    target: "agent:python-architect"
  -
    confidence: structured
    evidence:
      -
        extractor: routing_table
        line: 60
        resource: global/skills/orchestrate.md
        text: 8 | Python / FastAPI / Django / SQLAlchemy / pyproject.toml | test / pytest / fixture / async test | python-tester
    kind: routes_to
    reason: python-tester
    target: "agent:python-tester"
  -
    confidence: structured
    evidence:
      -
        extractor: routing_table
        line: 56
        resource: global/skills/orchestrate.md
        text: 4 | React + (Vite / Zustand / Biome / Zod / MUI Icons) | architect / design / component / state | react-architect
    kind: routes_to
    reason: react-architect
    target: "agent:react-architect"
  -
    confidence: structured
    evidence:
      -
        extractor: routing_table
        line: 69
        resource: global/skills/orchestrate.md
        text: 17 | requirements / user stories / acceptance criteria / scope / vague request | analyse / scope / elicit | requirements-analyst
    kind: routes_to
    reason: requirements-analyst
    target: "agent:requirements-analyst"
  -
    confidence: structured
    evidence:
      -
        extractor: routing_table
        line: 66
        resource: global/skills/orchestrate.md
        text: 14 | API keys / secrets / credentials / tokens / passwords | scan / audit / pre-commit | secret-auditor
    kind: routes_to
    reason: secret-auditor
    target: "agent:secret-auditor"
  -
    confidence: structured
    evidence:
      -
        extractor: routing_table
        line: 55
        resource: global/skills/orchestrate.md
        text: 3 | TanStack Router / TanStack Query / TanStack Form / TanStack Table / typed routes / route loaders | any | tanstack-architect
    kind: routes_to
    reason: tanstack-architect
    target: "agent:tanstack-architect"
  -
    confidence: structured
    evidence:
      -
        extractor: routing_table
        line: 62
        resource: global/skills/orchestrate.md
        text: 10 | Unity / MonoBehaviour / ScriptableObject / scene / prefab / Assets/ | architect / design / review | unity-architect
    kind: routes_to
    reason: unity-architect
    target: "agent:unity-architect"
  -
    confidence: structured
    evidence:
      -
        extractor: routing_table
        line: 75
        resource: global/skills/orchestrate.md
        text: 23 | new UI component / content page / interaction behaviour / a11y / UX best practice | analyse / review / question | ux-analyst
    kind: routes_to
    reason: ux-analyst
    target: "agent:ux-analyst"
  -
    confidence: structured
    evidence:
      -
        extractor: routing_table
        line: 73
        resource: global/skills/orchestrate.md
        text: 21 | URL / web page / article / docs page / changelog (a link to read) | analyse / research / extract | website-content-analyst
    kind: routes_to
    reason: website-content-analyst
    target: "agent:website-content-analyst"
---

# orchestrate

/orchestrate — Automatic Subagent Routing

- Source: `global/skills/orchestrate.md`
- Category: `skill`
