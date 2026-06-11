# -*- coding: utf-8 -*-
"""Parser tests for cabal.gh_accounts using captured `gh auth status` output."""

from __future__ import annotations

from cabal.gh_accounts import GhAccount, parse_auth_status

TWO_ACCOUNTS_ONE_INVALID = """\
github.com
  ✓ Logged in to github.com account dwcy (keyring)
  - Active account: true
  - Git operations protocol: https
  - Token: gho_************************************
  - Token scopes: 'gist', 'read:org', 'repo', 'workflow'

  X Failed to log in to github.com account dawid-ql (C:\\Users\\Dawid\\AppData\\Roaming\\GitHub CLI\\hosts.yml)
  - Active account: false
  - The token in C:\\Users\\Dawid\\AppData\\Roaming\\GitHub CLI\\hosts.yml is invalid.
  - To re-authenticate, run: gh auth login -h github.com
  - To forget about this account, run: gh auth logout -h github.com -u dawid-ql
"""

SINGLE_ACCOUNT = """\
github.com
  ✓ Logged in to github.com account dwcy (keyring)
  - Active account: true
  - Git operations protocol: https
  - Token: gho_************************************
"""

NOT_LOGGED_IN = (
    "You are not logged into any GitHub hosts. To log in, run: gh auth login\n"
)


def test_two_accounts_one_invalid():
    accounts = parse_auth_status(TWO_ACCOUNTS_ONE_INVALID)
    assert accounts == [
        GhAccount("dwcy", "github.com", active=True, valid=True, storage="keyring"),
        GhAccount(
            "dawid-ql",
            "github.com",
            active=False,
            valid=False,
            storage="C:\\Users\\Dawid\\AppData\\Roaming\\GitHub CLI\\hosts.yml",
        ),
    ]


def test_single_account_active():
    accounts = parse_auth_status(SINGLE_ACCOUNT)
    assert len(accounts) == 1
    assert accounts[0].user == "dwcy"
    assert accounts[0].active is True
    assert accounts[0].valid is True


def test_not_logged_in_yields_no_accounts():
    assert parse_auth_status(NOT_LOGGED_IN) == []


def test_empty_input():
    assert parse_auth_status("") == []
