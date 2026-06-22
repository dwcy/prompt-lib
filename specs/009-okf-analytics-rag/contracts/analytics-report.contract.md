# Contract: Analytics Report

## Command

```bash
python -m cabal.okf analytics docs/okf/prompt-lib --db .cabal/okf/index.sqlite --format json
```

## Required JSON Keys

```json
{
  "agents_with_many_routes": [],
  "skills_with_many_routes": [],
  "agents_never_referenced": [],
  "skill_graph_overlap": [],
  "skill_text_overlap": [],
  "skills_same_agent_similar_reasons": [],
  "relation_density_by_category": [],
  "changed_concepts": []
}
```

## Finding Requirements

- Route pressure findings include concept ids and counts.
- Graph overlap findings include both skill ids and shared agent ids.
- Text overlap findings include both skill ids, score, and shared terms.
- Changed concepts include concept ids and require a previous index input.
- Human output must summarize the top findings without stack traces.
