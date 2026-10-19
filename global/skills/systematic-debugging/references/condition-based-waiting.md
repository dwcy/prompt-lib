# Condition-based waiting

A test that waits a fixed number of milliseconds is asserting two things: that the work finishes, and that it finishes inside that window. The second assertion is about the machine, not the code. On a loaded CI runner it fails; on a fast laptop it wastes the whole window every run. Both are why "flaky" tests are almost always "timed" tests.

Wait for the condition instead. Poll a predicate at a short interval until it is true or a generous timeout expires. The test then runs as fast as the code allows and fails with a message that names what never happened.

## Shape

```text
waitFor(condition, description, timeout):
    deadline = now + timeout
    while now < deadline:
        if condition(): return
        sleep(10 ms)
    fail("Timed out after {timeout} waiting for {description}")
```

The `description` is not optional. "Timed out waiting for the job row to reach status=done" is a bug report; "Timed out" is a shrug.

## Python (pytest, asyncio)

```python
import asyncio
import time


def wait_for(condition, description, timeout=5.0, interval=0.01):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(interval)
    raise AssertionError(f"Timed out after {timeout}s waiting for {description}")


async def wait_for_async(condition, description, timeout=5.0, interval=0.01):
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        if condition():
            return
        await asyncio.sleep(interval)
    raise AssertionError(f"Timed out after {timeout}s waiting for {description}")
```

Use: `wait_for(lambda: repo.get(job_id).status == "done", "job to reach status=done")`.

Textual apps under `App.run_test()`: `await pilot.pause()` settles the message loop and is the correct call after a keypress or click. It is not a timed wait. When you need a widget to reach a state after a worker finishes, poll the state with `wait_for_async` rather than stacking `pilot.pause(0.5)` calls.

## TypeScript (Vitest, Playwright)

Vitest already ships this: `await vi.waitFor(() => expect(store.getState().status).toBe("done"))` polls the callback until it stops throwing. Prefer it over `await new Promise(r => setTimeout(r, 500))`.

Playwright's locators auto-wait. `await expect(page.getByRole("status")).toHaveText("Done")` retries until the timeout; a preceding `page.waitForTimeout()` adds nothing but time.

For code that has no built-in helper:

```ts
export async function waitFor(
  condition: () => boolean,
  description: string,
  timeoutMs = 5000,
  intervalMs = 10,
): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (condition()) return;
    await new Promise((r) => setTimeout(r, intervalMs));
  }
  throw new Error(`Timed out after ${timeoutMs}ms waiting for ${description}`);
}
```

## The one legitimate fixed wait

Verifying that something happens *N times over a known interval* (a heartbeat every 100 ms, a debounce of 300 ms) needs a timed window, because the assertion is about time. Even then, wait for the triggering condition first, then the timed window, and leave a comment saying why the number is there:

```python
wait_for(lambda: scheduler.started, "scheduler to start")
time.sleep(0.35)  # debounce is 300ms; we assert exactly one flush happened inside it
assert flush_count == 1
```

A fixed sleep with no comment explaining which interval it mirrors is a flake waiting to happen.

## Replacing an existing sleep

1. Ask what the sleep was waiting for. The answer is the `description`.
2. Find the observable state that becomes true when that thing has happened. That is the `condition`.
3. Replace the sleep with the poller. Keep the old duration as the timeout only if it was generous; otherwise widen it. The timeout is a ceiling, not an expectation.
4. Run the test ten times in a row. If it still flakes, the condition is wrong or the code has a real race. Either way, that is the bug to debug now, not a reason to put the sleep back.
