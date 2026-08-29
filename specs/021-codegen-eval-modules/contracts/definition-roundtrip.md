# Contract: Benchmark Definition Round-Trip

**Surface**: `setup/src/cabal/webapi/evals_definitions_service.py`  
**Contract tests**: `tests/contract/test_definition_roundtrip.py` — MUST be written and observed failing before implementation (Constitution Gate 3).

This contract exists because the user chose **full GUI authoring** of the benchmark tree (FR-050–FR-055), and the classic failure of every config editor is to parse into a model, re-serialise, and silently discard the comments, key order, and unmodelled fields a human wrote.

That matters more than usual here: `evals/` is **committed** while `evals/results/` is gitignored. Definitions are source. Damage shows up as noise in a diff and, worse, can change what a benchmark measures — which would silently invalidate every comparison made against it.

---

## The four guarantees

### G1 — A module-authored definition is accepted by the unmodified CLI

The load-bearing test for SC-013:

1. Create a task, rubric, and config profile entirely through the service.
2. Run `python -m cabal.evals validate` **as a subprocess**, with no module code in the loop.
3. Assert it passes with no hand-editing.

Asserting against the imported validator would not prove this — the point is that a definition authored here is indistinguishable from a hand-written one *to the real tool*.

### G2 — Reading then writing an untouched definition changes nothing

Load a hand-written definition, save it without edits, assert the file is **byte-identical**.

This is the guarantee that keeps diffs honest. A round-trip that reformats produces a diff full of noise, in which a real change is invisible to a reviewer.

Test corpus must include definitions with comments, non-alphabetical key order, and unusual-but-valid whitespace.

### G3 — Unmodelled content survives an edit

Load a definition containing a field the editor does not model, change one field it *does* model, save.

Assert: the changed field changed, and **the unmodelled field is still present and unchanged**.

### G4 — What cannot be preserved is not silently mangled

When a definition cannot be represented faithfully enough to guarantee G2 and G3, the service reports `editable: false` and the module opens it **read-only** (`contracts/evals-api.md`).

Refusing to edit is correct behaviour, not a limitation to work around. The alternative — a best-effort save that quietly drops content — is the failure this whole contract exists to prevent.

---

## Write protocol

Every save:

1. **Validate first.** An invalid definition is refused with the specific problem, and **nothing is written** (FR-052). Never write-then-validate: that leaves a broken tree behind on failure, and a broken tree blocks launching (FR-031).
2. **Check the content hash.** The precondition digest binds to the file's current hash. A hash mismatch means the file changed on disk since the editor opened it → `409 definition_changed_externally`, and the user is told rather than having their edit overwrite the external change (FR-053).
3. **Write atomically.** A crash mid-write must not leave a truncated definition — the file is source, and a corrupt one blocks all launching.

---

## Deletion

Deleting a definition MUST NOT break any stored run that referenced it (FR-054).

This falls out of reading a run against **the manifest it recorded at launch** rather than against the current tree (data-model cross-cutting rule 5). The contract test: record a run, delete the task definition it used, then assert the run's comparison still renders completely.

---

## Explicitly out of scope

**Git operations.** The service reports which definitions are uncommitted (FR-055) and stops there. Committing is the user's own workflow — this repository's commit policy runs through the `git-identity` wrapper, and a GUI that committed on the user's behalf would bypass it.
