//! Adopt-or-spawn lifecycle for the `cabal-backend` process, per
//! specs/015-web-ui-overhaul/contracts/desktop-shell.contract.md.

use std::{
    env, fs,
    path::PathBuf,
    time::{Duration, Instant},
};

use serde::{Deserialize, Serialize};
use tauri::AppHandle;
use tauri_plugin_shell::{process::CommandChild, ShellExt};

const HANDSHAKE_SCHEMA: &str = "cabal-handshake.v1";
const HANDSHAKE_POLL_INTERVAL: Duration = Duration::from_millis(150);
const HANDSHAKE_POLL_TIMEOUT: Duration = Duration::from_secs(15);
const HEALTH_CHECK_TIMEOUT: Duration = Duration::from_millis(800);
const SHUTDOWN_GRACE: Duration = Duration::from_secs(5);

#[derive(Debug, Clone, Deserialize)]
struct Handshake {
    schema: String,
    port: u16,
    token: String,
}

/// Runtime backend connection info injected into the webview as `window.__CABAL__`
/// (see src/lib/runtimeConfig.ts's `CabalRuntimeConfig`).
#[derive(Debug, Clone, Serialize)]
pub struct BackendConnection {
    pub port: u16,
    pub token: String,
}

/// Owns the child process handle only when THIS shell spawned the backend; adopted
/// (already-running) backends are never killed on shutdown, per the contract.
pub struct BackendState {
    connection: BackendConnection,
    spawned_child: Option<CommandChild>,
}

impl BackendState {
    pub fn connection(&self) -> BackendConnection {
        self.connection.clone()
    }
}

/// `window.__CABAL__ = { port, token };` — matches `CabalRuntimeConfig` exactly.
pub fn injection_script(connection: &BackendConnection) -> String {
    let payload = serde_json::to_string(connection).unwrap_or_else(|_| "null".to_string());
    format!("window.__CABAL__ = {payload};")
}

/// Adopt a live backend if its handshake checks out, otherwise spawn a fresh one and
/// block the calling thread (bounded, with backoff) until a fresh handshake appears.
pub fn adopt_or_spawn(app: &AppHandle) -> Result<BackendState, String> {
    if let Some(existing) = read_handshake() {
        if backend_is_alive(&existing) {
            return Ok(BackendState {
                connection: BackendConnection { port: existing.port, token: existing.token },
                spawned_child: None,
            });
        }
        // Stale: process is dead or unresponsive. Remove it so a fresh spawn's own
        // start-refusal check never mistakes this for a second live instance.
        let _ = fs::remove_file(handshake_path());
    }

    let child = spawn_backend(app)?;
    let handshake = wait_for_handshake()?;
    Ok(BackendState {
        connection: BackendConnection { port: handshake.port, token: handshake.token },
        spawned_child: Some(child),
    })
}

/// Ask a spawned backend to shut down cleanly (`POST /api/system/shutdown`); only
/// kills the process if it doesn't exit within the grace window. Adopted backends
/// are left untouched — the shell only ever closes its own window for those.
pub fn shutdown(state: BackendState) {
    let BackendState { connection, spawned_child } = state;
    let Some(child) = spawned_child else { return };

    let url = format!("http://127.0.0.1:{}/api/system/shutdown", connection.port);
    let requested = ureq::post(&url)
        .set("Authorization", &format!("Bearer {}", connection.token))
        .timeout(HEALTH_CHECK_TIMEOUT)
        .call()
        .is_ok();

    if requested {
        let deadline = Instant::now() + SHUTDOWN_GRACE;
        while Instant::now() < deadline {
            if read_handshake().is_none() {
                return; // Backend removed its own handshake on clean exit.
            }
            std::thread::sleep(HANDSHAKE_POLL_INTERVAL);
        }
    }
    let _ = child.kill();
}

fn handshake_path() -> PathBuf {
    user_data_dir().join("cabal").join("webapi-handshake.json")
}

/// Mirrors `platformdirs.user_data_dir("cabal", appauthor=False)`.
fn user_data_dir() -> PathBuf {
    #[cfg(target_os = "windows")]
    {
        env::var_os("LOCALAPPDATA")
            .or_else(|| env::var_os("APPDATA"))
            .map(PathBuf::from)
            .unwrap_or_else(|| home_dir().join("AppData").join("Local"))
    }
    #[cfg(target_os = "macos")]
    {
        home_dir().join("Library").join("Application Support")
    }
    #[cfg(all(unix, not(target_os = "macos")))]
    {
        env::var_os("XDG_DATA_HOME")
            .map(PathBuf::from)
            .unwrap_or_else(|| home_dir().join(".local").join("share"))
    }
}

fn home_dir() -> PathBuf {
    env::var_os("USERPROFILE")
        .or_else(|| env::var_os("HOME"))
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("."))
}

fn read_handshake() -> Option<Handshake> {
    let raw = fs::read_to_string(handshake_path()).ok()?;
    let handshake: Handshake = serde_json::from_str(&raw).ok()?;
    (handshake.schema == HANDSHAKE_SCHEMA).then_some(handshake)
}

/// `GET /api/health` with the handshake token; true only on a genuine 2xx reply —
/// this is the adoption check, not a pid-liveness check (matches the contract's
/// "read handshake file -> GET /api/health with token -> if healthy, adopt it").
fn backend_is_alive(handshake: &Handshake) -> bool {
    let url = format!("http://127.0.0.1:{}/api/health", handshake.port);
    ureq::get(&url)
        .set("Authorization", &format!("Bearer {}", handshake.token))
        .timeout(HEALTH_CHECK_TIMEOUT)
        .call()
        .map(|response| response.status() == 200)
        .unwrap_or(false)
}

fn wait_for_handshake() -> Result<Handshake, String> {
    let deadline = Instant::now() + HANDSHAKE_POLL_TIMEOUT;
    loop {
        if let Some(handshake) = read_handshake() {
            if backend_is_alive(&handshake) {
                return Ok(handshake);
            }
        }
        if Instant::now() >= deadline {
            return Err("timed out waiting for the cabal backend to start".to_string());
        }
        std::thread::sleep(HANDSHAKE_POLL_INTERVAL);
    }
}

/// Dev mode: no bundled sidecar binary exists yet (ships in T095/T096), so run the
/// backend straight out of the repo's uv environment instead of `sidecar()`.
#[cfg(debug_assertions)]
fn spawn_backend(app: &AppHandle) -> Result<CommandChild, String> {
    let repo_root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("..")
        .join("..")
        .canonicalize()
        .map_err(|err| format!("resolving repo root from CARGO_MANIFEST_DIR: {err}"))?;

    let (mut rx, child) = app
        .shell()
        .command("uv")
        .current_dir(repo_root)
        .args(["run", "cabal-backend"])
        .spawn()
        .map_err(|err| format!("spawning dev backend (`uv run cabal-backend`): {err}"))?;

    // Drain output so the child's stdout/stderr pipes never fill and block it;
    // full log surfacing into the UI is a later module's job (Services, T076-T078).
    tauri::async_runtime::spawn(async move {
        use tauri_plugin_shell::process::CommandEvent;
        while let Some(event) = rx.recv().await {
            if let CommandEvent::Error(err) = event {
                eprintln!("cabal-backend (dev): {err}");
            }
        }
    });

    Ok(child)
}

/// Production: the real PyInstaller-built sidecar, bundled via `bundle.externalBin`
/// (wired in T096 — this call is unreachable in debug builds, so it can't break
/// `cargo check`/`cargo build`/`tauri dev` before that wiring lands).
#[cfg(not(debug_assertions))]
fn spawn_backend(app: &AppHandle) -> Result<CommandChild, String> {
    let (mut rx, child) = app
        .shell()
        .sidecar("cabal-backend")
        .map_err(|err| format!("resolving cabal-backend sidecar: {err}"))?
        .spawn()
        .map_err(|err| format!("spawning cabal-backend sidecar: {err}"))?;

    tauri::async_runtime::spawn(async move {
        use tauri_plugin_shell::process::CommandEvent;
        while let Some(event) = rx.recv().await {
            if let CommandEvent::Error(err) = event {
                eprintln!("cabal-backend: {err}");
            }
        }
    });

    Ok(child)
}
