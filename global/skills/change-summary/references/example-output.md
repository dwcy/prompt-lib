# Example — target depth and tone

This is a condensed example of the bar to match. Notice: every row explains a *mechanism* (what was actually broken or contradictory) in words that don't assume the reader knows the codebase, not just a summary of the diff hunk.

---

## Authentication

| File | Reason |
|---|---|
| `src/auth/session.py` | The session cookie was being set without the `Secure` flag, meaning a browser would also send it over plain HTTP — so on a network that could see unencrypted traffic, someone could steal a logged-in session just by watching. Added the flag so the cookie is only ever sent over HTTPS. |
| `src/auth/middleware.py`, `src/auth/decorators.py` | Both files independently re-implemented the same "is this user an admin" check, and one of the two copies had a typo that always evaluated to true. Removed the duplicate and pointed both call sites at one shared, tested function. |

## Dead code removed

| File | Reason |
|---|---|
| `src/legacy/old_login.py` — deleted | This was the previous login flow, replaced months ago, but never deleted — so it was still reachable at its old URL with none of the security fixes applied to the new flow. Removed it entirely rather than leaving an unpatched back door. |

## Tests

| File | Reason |
|---|---|
| `tests/test_session.py` | Added a test asserting the `Secure` flag is set, so the auth fix above can't silently regress. |

---

Note what this example does *not* do: it doesn't say "updated session.py to add Secure flag" (that's the diff, not the explanation), and it doesn't invent a reason it can't support — if the actual PR body or commit message doesn't say why, say what the change does and note plainly that the motivation is inferred from the code itself.
