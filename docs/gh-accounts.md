# GitHub accounts — switching behavior

The cabal wizard's **Accounts** modal (GitHub view → Accounts button) lists the
gh CLI accounts for `github.com` and lets you switch the active one, add another
account via the GitHub device flow, re-authenticate an account whose token went
stale, or forget an account. Under the hood it drives `gh auth status`,
`gh auth switch`, `gh auth login --with-token`, and `gh auth logout`
(`setup/src/cabal/gh_accounts.py`). Switching also refreshes the repo list,
which follows the newly active account.

## Behaviors to know

- **Switching is global per host, not per terminal.** `gh auth switch` changes
  the active account for every shell, editor, and Claude Code session on the
  machine, immediately. There is no per-session switch; for a one-off shell,
  export `GH_TOKEN` in that shell instead.
- **`GH_TOKEN` / `GITHUB_TOKEN` override the active account.** If either is
  exported, gh uses it and ignores `gh auth switch` entirely — switching will
  look broken. The modal shows a warning banner when it detects one.
- **Commit identity does not change.** Switching accounts swaps the API/push
  token only. `user.name` / `user.email` (and the `git-identity` wrapper +
  `~/.claude/git-policy.json`) decide commit authorship, independently of gh.
- **Push permissions flip with the switch.** HTTPS pushes through gh's
  credential helper authenticate as the newly active account; a repo the other
  account cannot write to will start rejecting pushes mid-work.
- **SSH remotes are unaffected.** gh accounts only govern HTTPS/API traffic;
  `git@github.com:` remotes keep using your SSH key.
- **Invalid tokens are flagged.** Accounts whose stored token no longer works
  show as `✗ (invalid token)` with Re-auth / Forget actions instead of Switch.
