---
description: Unity C# file conventions — loaded automatically when editing scripts under Assets/. Numeric LoC budgets + 5 concern-separation triggers.
paths:
  - "Assets/**/*.cs"
---

## File intent

One-line `///` summary on every script naming its single responsibility. Update when the purpose changes.

## Numeric LoC budgets

| File kind | Soft cap | Hard cap |
|---|---:|---:|
| MonoBehaviour | 200 | 350 |
| ScriptableObject | 150 | 300 |
| Plain C# class (systems, services, DTOs) | 200 | 350 |
| Editor script | 250 | 400 |

- **Soft cap** = stop and ask "does this script own one responsibility?".
- **Hard cap** = split, OR write a justification at line 1: `// > 350 LoC justified: <one-line structural reason>`.
- Non-substantive reasons fail the verifier audit.

## The 5 concern-separation triggers

See `_size-discipline.md` for the canonical list. Two or more firing → split before writing.

Unity-specific signals to watch:

- A MonoBehaviour that owns gameplay logic AND input AND UI updates AND audio → 4 concerns. Extract systems / ScriptableObject events.
- `Update()` doing > 2 unrelated things → orchestrate via plain C# subsystems called from Update.
- Sprawling `OnEnable` / `OnDisable` pairs subscribing to > 3 unrelated event sources → extract a subscription manager.

## Split patterns

- **MonoBehaviour as a thin shell** — lifecycle hooks (`Awake`, `OnEnable`, `Update`) delegate to plain C# subsystems. The MB owns Inspector wiring + lifecycle; the subsystem owns logic.
- **ScriptableObject event channel** — replace direct MB-to-MB references with a SO event when > 2 listeners want the same signal.
- **Runtime set ScriptableObject** — replace `FindObjectsOfType` with an SO that all instances register/unregister to.
- **System / Service** — pure C# class, no Unity dependency, dependency-injected into the MB through SerializeField or VContainer.

## Hard rules to enforce

- No business logic in MonoBehaviours — delegate to plain C# classes.
- No `FindObjectOfType` or `GameObject.Find` at runtime — cache or inject.
- No `GetComponent` in `Update` — always cache in `Awake`.
- `OnEnable` subscribes; `OnDisable` unsubscribes — always paired.
- No GC allocations in `Update` (no `new` keyword inside hot loops, no LINQ over `IEnumerable`).
- `[SerializeField] private` over `public` fields for Inspector-exposed data.

## Naming

- Scripts: PascalCase matching the type name (`PlayerController.cs` → `class PlayerController`).
- ScriptableObjects: `<Domain><Kind>` (`PlayerStatsConfig`, `GameStartedEvent`).
- Folders under `Assets/Scripts/` organised by feature, not by file kind. Avoid an `Assets/Scripts/MonoBehaviours/` dump.

## DRY and YAGNI

- Extract shared logic on the second duplication, not speculatively.
- Remove unused `SerializeField`s — they pollute the Inspector and lie about dependencies.
- No `// TODO` left in committed scripts.
