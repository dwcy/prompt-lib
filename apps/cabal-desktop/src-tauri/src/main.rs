#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod backend;

use std::{
    sync::{
        atomic::{AtomicBool, Ordering},
        Mutex,
    },
    thread,
    time::Duration,
};

use tauri::Manager;

/// Holds the resolved backend connection (and, when this shell spawned it, the
/// child handle) so the app-exit handler can shut it down gracefully.
#[derive(Default)]
struct BackendHandle {
    state: Mutex<Option<backend::BackendState>>,
    shutting_down: AtomicBool,
}

const BACKEND_MONITOR_INTERVAL: Duration = Duration::from_secs(2);
const BACKEND_MONITOR_FAILURE_THRESHOLD: usize = 3;

/// Reload-safe source of the backend connection. The `window.__CABAL__` eval is
/// one-shot and wiped by any webview reload (F5/Ctrl+R), so the frontend's
/// runtimeConfig.ts polls this command on every page load until the sidecar
/// handshake has completed. Returns `None` while the handshake is still pending.
#[tauri::command]
fn backend_config(
    handle: tauri::State<'_, BackendHandle>,
) -> Option<backend::BackendConnection> {
    handle
        .state
        .lock()
        .expect("backend state mutex poisoned")
        .as_ref()
        .map(|state| state.connection())
}

fn main() {
    tauri::Builder::default()
        // single-instance must be the first registered plugin.
        .plugin(tauri_plugin_single_instance::init(|app, _argv, _cwd| {
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.set_focus();
            }
        }))
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_window_state::Builder::default().build())
        .plugin(tauri_plugin_dialog::init())
        .manage(BackendHandle::default())
        .invoke_handler(tauri::generate_handler![backend_config])
        .setup(|app| {
            let handle_for_spawn = app.handle().clone();
            let handle_for_apply = app.handle().clone();

            // Adopt-or-spawn runs off the main thread so window creation is never
            // blocked on it; the frontend's own connectivity/health-strip state
            // (already polling GET /api/health) covers the UI during the wait.
            tauri::async_runtime::spawn(async move {
                let outcome = tauri::async_runtime::spawn_blocking(move || {
                    backend::adopt_or_spawn(&handle_for_spawn)
                })
                .await;
                match outcome {
                    Ok(Ok(state)) => {
                        // Store the state FIRST so the `backend_config` command (the durable
                        // config source) is answerable the moment it exists; the eval below is
                        // only a best-effort fast path that saves the frontend one IPC poll.
                        let connection = state.connection();
                        *handle_for_apply
                            .state::<BackendHandle>()
                            .state
                            .lock()
                            .expect("backend state mutex poisoned") = Some(state);
                        if let Some(window) = handle_for_apply.get_webview_window("main") {
                            let _ = window.eval(&backend::injection_script(&connection));
                        }
                        start_backend_monitor(handle_for_apply);
                    }
                    Ok(Err(err)) => {
                        eprintln!("cabal-desktop: failed to start the cabal backend: {err}");
                    }
                    Err(join_err) => {
                        eprintln!("cabal-desktop: backend startup task panicked: {join_err}");
                    }
                }
            });

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building the cabal desktop shell")
        .run(|app_handle, event| {
            // Per contracts/desktop-shell.contract.md: shut down gracefully on
            // RunEvent::Exit, killing only a backend this shell itself spawned.
            if let tauri::RunEvent::Exit = event {
                app_handle
                    .state::<BackendHandle>()
                    .shutting_down
                    .store(true, Ordering::Release);
                let state = app_handle
                    .state::<BackendHandle>()
                    .state
                    .lock()
                    .expect("backend state mutex poisoned")
                    .take();
                if let Some(state) = state {
                    backend::shutdown(state);
                }
            }
        });
}

fn start_backend_monitor(app: tauri::AppHandle) {
    thread::spawn(move || {
        let mut consecutive_failures = 0;
        loop {
            thread::sleep(BACKEND_MONITOR_INTERVAL);
            let handle = app.state::<BackendHandle>();
            if handle.shutting_down.load(Ordering::Acquire) {
                return;
            }

            let connection = handle
                .state
                .lock()
                .expect("backend state mutex poisoned")
                .as_ref()
                .map(|state| state.connection());
            if connection
                .as_ref()
                .is_some_and(backend::connection_is_alive)
            {
                consecutive_failures = 0;
                continue;
            }
            consecutive_failures += 1;
            if consecutive_failures < BACKEND_MONITOR_FAILURE_THRESHOLD {
                continue;
            }
            consecutive_failures = 0;

            if let Some(stale) = handle
                .state
                .lock()
                .expect("backend state mutex poisoned")
                .take()
            {
                backend::shutdown(stale);
            }

            match backend::adopt_or_spawn(&app) {
                Ok(state) => {
                    if handle.shutting_down.load(Ordering::Acquire) {
                        backend::shutdown(state);
                        return;
                    }
                    // Same ordering as startup: make `backend_config` answerable before the
                    // best-effort eval refreshes any already-loaded page.
                    let connection = state.connection();
                    *handle.state.lock().expect("backend state mutex poisoned") = Some(state);
                    if let Some(window) = app.get_webview_window("main") {
                        let _ = window.eval(&backend::injection_script(&connection));
                    }
                }
                Err(err) => eprintln!("cabal-desktop: backend reconnect failed: {err}"),
            }
        }
    });
}
