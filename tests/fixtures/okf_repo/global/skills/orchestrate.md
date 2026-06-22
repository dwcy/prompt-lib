# /orchestrate

Routes work to specialist agents.

Use @python-architect when the task is Python service architecture.

| Signal | Agent | Reason |
|---|---|---|
| pytest, fixture | `python-tester` | Test implementation belongs to the Python tester. |
| CSS, layout | `frontend-css` | Styling-only work belongs to frontend-css. |
| legacy | `missing-agent` | This fixture keeps unresolved edges visible. |
