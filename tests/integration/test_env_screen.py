"""Smoke tests for EnvScreen (regression guard for the 005-extraction NameErrors).

Mounting EnvScreen through Textual's compose() pipeline is the only thing that
catches missing module-level names like _PATH_KEYS / _GH_TOKEN_KEYS / update_profile;
direct method calls bypass the render pipeline and miss shadow bugs entirely.
"""

from __future__ import annotations

import pytest

from cabal.app import CabalApp
from cabal.views.env import EnvScreen


@pytest.mark.asyncio
async def test_env_screen_mounts_without_nameerror():
    app = CabalApp()
    async with app.run_test() as pilot:
        app.push_screen(EnvScreen())
        await pilot.pause()

        assert isinstance(app.screen, EnvScreen)


def test_update_profile_is_importable_from_env_screen():
    from cabal.views import env as env_module

    assert callable(env_module.update_profile)


def test_path_keys_and_gh_token_keys_live_in_env_module():
    from cabal.views import env as env_module

    assert "PROJECTS_PATH" in env_module._PATH_KEYS
    assert "GITHUB_PERSONAL_ACCESS_TOKEN" in env_module._GH_TOKEN_KEYS
