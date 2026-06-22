---
type: skill
title: github-scaffold
description: "name: github-scaffold"
resource: global/skills/github-scaffold.md
tags:
  - prompt-lib
  - skill
  - claude-code
timestamp: "2026-06-18T00:00:00Z"
id: "skill:github-scaffold"
relations:
  -
    confidence: explicit
    evidence:
      -
        extractor: agent_token
        line: 211
        resource: global/skills/github-scaffold.md
        text: @github-config-manager
    kind: routes_to
    reason: Skill references @github-config-manager.
    target: "agent:github-config-manager"
  -
    confidence: explicit
    evidence:
      -
        extractor: agent_token
        line: 209
        resource: global/skills/github-scaffold.md
        text: @init-project
    kind: routes_to
    reason: Skill references @init-project.
    target: "agent:init-project"
---

# github-scaffold

name: github-scaffold

- Source: `global/skills/github-scaffold.md`
- Category: `skill`
