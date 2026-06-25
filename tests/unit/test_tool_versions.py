"""Runtime version provider tests."""

from __future__ import annotations

from cabal.installers.versions import version_options_for


def test_version_options_include_installed_when_metadata_unavailable():
    result = version_options_for("node", installed_version="v22.0.0")

    assert any(option.channel == "installed" and option.version == "v22.0.0" for option in result.options)


def test_node_versions_mark_lts_from_upstream_status():
    result = version_options_for("node", installed_version="v22.0.0")

    assert any(option.is_lts for option in result.options)


def test_dotnet_versions_mark_lts_and_sts():
    result = version_options_for("dotnet", installed_version="9.0.100")
    channels = {option.channel for option in result.options}

    assert "lts" in channels
    assert "sts" in channels
    assert any(option.is_lts for option in result.options)


def test_python_versions_do_not_fake_lts():
    result = version_options_for("python", installed_version="3.13.0")

    assert not any(option.is_lts for option in result.options)
    assert {"stable", "installed"} <= {option.channel for option in result.options}
