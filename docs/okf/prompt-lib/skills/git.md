---
type: skill
title: git
description: "name: git"
resource: global/skills/git.md
tags:
  - prompt-lib
  - skill
  - claude-code
timestamp: "2026-06-18T00:00:00Z"
id: "skill:git"
relations:
  -
    confidence: explicit
    evidence:
      -
        extractor: agent_token
        line: 41
        resource: global/skills/git.md
        text: @gitignore-auditor
    kind: routes_to
    reason: Skill references @gitignore-auditor.
    target: "agent:gitignore-auditor"
  -
    confidence: explicit
    evidence:
      -
        extractor: agent_token
        line: 55
        resource: global/skills/git.md
        text: @secret-auditor
    kind: routes_to
    reason: Skill references @secret-auditor.
    target: "agent:secret-auditor"
---

# git

name: git

- Source: `global/skills/git.md`
- Category: `skill`
