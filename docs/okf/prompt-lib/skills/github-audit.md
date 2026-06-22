---
type: skill
title: github-audit
description: "name: github-audit"
resource: global/skills/github-audit.md
tags:
  - prompt-lib
  - skill
  - claude-code
timestamp: "2026-06-18T00:00:00Z"
id: "skill:github-audit"
relations:
  -
    confidence: explicit
    evidence:
      -
        extractor: agent_token
        line: 128
        resource: global/skills/github-audit.md
        text: @github-config-manager
    kind: routes_to
    reason: Skill references @github-config-manager.
    target: "agent:github-config-manager"
---

# github-audit

name: github-audit

- Source: `global/skills/github-audit.md`
- Category: `skill`
