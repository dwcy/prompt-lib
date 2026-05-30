"""Textual screens — one file per top-level screen.

Cross-screen pushes (Home → Operations → Update etc.) are imported lazily
inside `action_*` handlers to avoid circular module-level imports. See
research.md R5.
"""
