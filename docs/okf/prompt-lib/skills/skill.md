---
type: skill
title: SKILL
description: "name: infographics-design"
resource: global/skills/infographics-design/SKILL.md
tags:
  - prompt-lib
  - skill
  - claude-code
timestamp: "2026-06-18T00:00:00Z"
id: "skill:skill"
relations:
  -
    confidence: explicit
    evidence:
      -
        extractor: agent_token
        line: 20
        resource: global/skills/infographics-design/SKILL.md
        text: @frontend-architect
    kind: routes_to
    reason: Skill references @frontend-architect.
    target: "agent:frontend-architect"
  -
    confidence: explicit
    evidence:
      -
        extractor: agent_token
        line: 9
        resource: global/skills/css-guide/SKILL.md
        text: @frontend-css
    kind: routes_to
    reason: Skill references @frontend-css.
    target: "agent:frontend-css"
  -
    confidence: explicit
    evidence:
      -
        extractor: agent_token
        line: 20
        resource: global/skills/infographics-design/SKILL.md
        text: @react-architect
    kind: routes_to
    reason: Skill references @react-architect.
    target: "agent:react-architect"
---

# SKILL

name: infographics-design

- Source: `global/skills/infographics-design/SKILL.md`
- Category: `skill`
