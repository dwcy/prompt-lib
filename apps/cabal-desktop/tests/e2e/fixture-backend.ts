import { type ChildProcessWithoutNullStreams, spawn } from "node:child_process";
import { once } from "node:events";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const REPO_ROOT = fileURLToPath(new URL("../../../../", import.meta.url));
const HANDSHAKE_FILE = join(tmpdir(), "cabal-playwright-handshake.json");
const START_TIMEOUT_MS = 45_000;

interface FixtureHandshake {
  port: number;
  token: string;
}

export interface FixtureBackend {
  readonly port: number;
  readonly token: string;
  readonly projectDir: string;
  stop: () => Promise<void>;
  close: () => Promise<void>;
}

export function fixtureHandshakePath(): string {
  return HANDSHAKE_FILE;
}

export async function launchFixtureBackend(): Promise<FixtureBackend> {
  await rm(HANDSHAKE_FILE, { force: true });
  const projectDir = await mkdtemp(join(tmpdir(), "cabal-e2e-project-"));
  await writeFile(
    join(projectDir, "CLAUDE.md"),
    "# Cabal E2E Fixture\n\nDeterministic project used by the browser smoke suite.\n",
    "utf8",
  );
  await writeFile(
    join(projectDir, "package.json"),
    JSON.stringify({ name: "cabal-e2e-fixture", private: true }, null, 2),
    "utf8",
  );

  const child = spawnBackend(projectDir);
  let output = "";
  child.stdout.on("data", (chunk: Buffer) => {
    output += chunk.toString("utf8");
  });
  child.stderr.on("data", (chunk: Buffer) => {
    output += chunk.toString("utf8");
  });

  try {
    const handshake = await waitForHandshake(child, () => output);
    await waitForHealth(handshake, child, () => output);
    let stopped = false;

    async function stop(): Promise<void> {
      if (stopped) return;
      stopped = true;
      try {
        await fetch(`http://127.0.0.1:${handshake.port}/api/system/shutdown`, {
          method: "POST",
          headers: { authorization: `Bearer ${handshake.token}` },
        });
      } catch {
        // The fallback below owns process termination when graceful shutdown cannot connect.
      }
      try {
        await waitForExit(child, 8_000);
      } catch {
        child.kill();
        await waitForExit(child, 5_000).catch(() => undefined);
      }
    }

    return {
      port: handshake.port,
      token: handshake.token,
      projectDir,
      stop,
      close: async () => {
        await stop();
        await rm(HANDSHAKE_FILE, { force: true });
        await rm(projectDir, { recursive: true, force: true });
      },
    };
  } catch (error) {
    child.kill();
    await rm(HANDSHAKE_FILE, { force: true });
    await rm(projectDir, { recursive: true, force: true });
    throw error;
  }
}

function spawnBackend(projectDir: string): ChildProcessWithoutNullStreams {
  return spawn(
    "uv",
    [
      "run",
      "python",
      "-m",
      "cabal.webapi",
      "--project",
      projectDir,
      "--storage-path",
      join(projectDir, "cabal-e2e.sqlite"),
      "--handshake-path",
      HANDSHAKE_FILE,
    ],
    {
      cwd: REPO_ROOT,
      env: { ...process.env, PYTHONUNBUFFERED: "1" },
      stdio: "pipe",
      windowsHide: true,
    },
  );
}

async function waitForHandshake(
  child: ChildProcessWithoutNullStreams,
  output: () => string,
): Promise<FixtureHandshake> {
  const deadline = Date.now() + START_TIMEOUT_MS;
  while (Date.now() < deadline) {
    throwIfExited(child, output());
    try {
      const parsed: unknown = JSON.parse(await readFile(HANDSHAKE_FILE, "utf8"));
      if (
        typeof parsed === "object" &&
        parsed !== null &&
        "port" in parsed &&
        "token" in parsed &&
        typeof parsed.port === "number" &&
        typeof parsed.token === "string"
      ) {
        return { port: parsed.port, token: parsed.token };
      }
    } catch {
      // Atomic handshake creation is asynchronous; retry until the bounded deadline.
    }
    await delay(100);
  }
  throw new Error(`Fixture backend did not write a handshake.\n${output()}`);
}

async function waitForHealth(
  handshake: FixtureHandshake,
  child: ChildProcessWithoutNullStreams,
  output: () => string,
): Promise<void> {
  const deadline = Date.now() + START_TIMEOUT_MS;
  while (Date.now() < deadline) {
    throwIfExited(child, output());
    try {
      const response = await fetch(`http://127.0.0.1:${handshake.port}/api/health`, {
        headers: { authorization: `Bearer ${handshake.token}` },
      });
      if (response.ok) return;
    } catch {
      // Socket binding can precede ASGI readiness by a few event-loop turns.
    }
    await delay(100);
  }
  throw new Error(`Fixture backend did not become healthy.\n${output()}`);
}

async function waitForExit(
  child: ChildProcessWithoutNullStreams,
  timeoutMs: number,
): Promise<void> {
  if (child.exitCode !== null) return;
  await Promise.race([
    once(child, "exit").then(() => undefined),
    delay(timeoutMs).then(() => {
      throw new Error("Fixture backend did not exit before the deadline");
    }),
  ]);
}

function throwIfExited(child: ChildProcessWithoutNullStreams, output: string): void {
  if (child.exitCode === null) return;
  throw new Error(`Fixture backend exited with code ${child.exitCode}.\n${output}`);
}

function delay(milliseconds: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}
