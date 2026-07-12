#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod backend;

use std::sync::Mutex;

use tauri::Manager;

/// Holds the resolved backend connection (and, when this shell spawned it, the
/// child handle) so the app-exit handler can shut it down gracefully.
#[derive(Default)]
struct BackendHandle(Mutex<Option<backend::BackendState>>);

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
        .manage(BackendHandle::default())
        .setup(|app| {
            let handle_for_spawn = app.handle().clone();
            let handle_for_apply = app.handle().clone();

            // Adopt-or-spawn runs off the main thread so window creation is never
            // blocked on it; the frontend's own connectivity/health-strip state
            // (already polling GET /api/health) covers the UI during the wait.
            tauri::async_runtime::spawn(async move {
                let outcome =
                    tauri::async_runtime::spawn_blocking(move || backend::adopt_or_spawn(&handle_for_spawn))
                        .await;
                match outcome {
                    Ok(Ok(state)) => {
                        if let Some(window) = handle_for_apply.get_webview_window("main") {
                            let _ = window.eval(&backend::injection_script(&state.connection()));
                        }
                        *handle_for_apply
                            .state::<BackendHandle>()
                            .0
                            .lock()
                            .expect("backend state mutex poisoned") = Some(state);
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
                let state = app_handle
                    .state::<BackendHandle>()
                    .0
                    .lock()
                    .expect("backend state mutex poisoned")
                    .take();
                if let Some(state) = state {
                    backend::shutdown(state);
                }
            }
        });
}
