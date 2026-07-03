# -*- coding: utf-8 -*-
"""Runtime version option helpers for Tools version selectors."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from cabal.env_detect import _probe_version
from cabal.installers.dotnet_releases import DotnetReleaseSet, get_cached_release_set


@dataclass(frozen=True)
class VersionOption:
    tool_key: str
    version: str
    label: str
    channel: str
    is_latest: bool = False
    is_lts: bool = False
    source_url: str = ""
    fetched_at: datetime | None = None


@dataclass(frozen=True)
class VersionProviderResult:
    tool_key: str
    options: tuple[VersionOption, ...]
    source_url: str
    stale: bool = False
    message: str = ""


VERSION_SOURCE_URLS: dict[str, str] = {
    "node": "https://nodejs.org/en/about/previous-releases",
    "dotnet": "https://dotnet.microsoft.com/platform/support/policy/dotnet-core",
    "python": "https://devguide.python.org/versions/",
    "bun": "https://bun.sh/docs/installation",
    "npm": "https://docs.npmjs.com/cli",
    "pnpm": "https://pnpm.io/installation",
}


def installed_version_for(tool_key: str) -> str | None:
    if tool_key == "python":
        import platform

        return platform.python_version()
    if tool_key == "dotnet":
        return _probe_version("dotnet", "--version")
    if tool_key == "node":
        return _probe_version("node", "--version")
    if tool_key == "npm":
        return _probe_version("npm", "--version")
    if tool_key == "pnpm":
        return _probe_version("pnpm", "--version")
    if tool_key == "bun":
        return _probe_version("bun", "--version")
    return None


def _option(
    tool_key: str,
    version: str,
    label: str,
    channel: str,
    *,
    is_latest: bool = False,
    is_lts: bool = False,
) -> VersionOption:
    return VersionOption(
        tool_key=tool_key,
        version=version,
        label=label,
        channel=channel,
        is_latest=is_latest,
        is_lts=is_lts,
        source_url=VERSION_SOURCE_URLS[tool_key],
        fetched_at=datetime.now(timezone.utc),
    )


def _dotnet_release_options(release_set: DotnetReleaseSet | None) -> list[VersionOption]:
    """Build dotnet VersionOptions from live releases-index data.

    Falls back to channel-only placeholders when no live or cached data is
    available (network outage with an empty cache) so the picker still renders.
    """
    if release_set is None or release_set.latest_lts is None:
        return [
            _option("dotnet", "lts", "Latest LTS SDK", "lts", is_lts=True),
            _option("dotnet", "sts", "Latest STS SDK", "sts", is_latest=True),
        ]
    options = [
        _option(
            "dotnet",
            release_set.latest_lts.latest_sdk,
            f"Latest LTS ({release_set.latest_lts.latest_sdk})",
            "lts",
            is_lts=True,
            is_latest=True,
        )
    ]
    if release_set.previous_lts is not None:
        options.append(
            _option(
                "dotnet",
                release_set.previous_lts.latest_sdk,
                f"Previous LTS ({release_set.previous_lts.latest_sdk})",
                "lts-previous",
                is_lts=True,
            )
        )
    if release_set.preview is not None:
        options.append(
            _option(
                "dotnet",
                release_set.preview.latest_sdk,
                f"Next preview ({release_set.preview.latest_sdk})",
                "preview",
            )
        )
    return options


def version_options_for(
    tool_key: str,
    *,
    installed_version: str | None = None,
) -> VersionProviderResult:
    """Return non-blocking version choices for a covered runtime.

    The Tools screen calls this during render, so this never performs network
    I/O — it only reads whatever is already known. `dotnet` is the one entry
    backed by live data: it reads a 24h cache (`get_cached_release_set`,
    fresh-or-stale, never fetching) populated by a background worker
    (`cabal.installers.dotnet_releases.refresh_release_cache`), and falls back
    to static channel placeholders until that cache has something to read.
    """
    if tool_key not in VERSION_SOURCE_URLS:
        return VersionProviderResult(tool_key, (), "", stale=True, message="No provider")

    installed = installed_version if installed_version is not None else installed_version_for(tool_key)
    options: list[VersionOption] = []
    if installed:
        options.append(
            VersionOption(
                tool_key=tool_key,
                version=installed,
                label=f"Installed {installed}",
                channel="installed",
                source_url=VERSION_SOURCE_URLS[tool_key],
            )
        )

    if tool_key == "node":
        options.extend(
            [
                _option(tool_key, "lts", "Latest LTS", "lts", is_lts=True),
                _option(tool_key, "latest", "Latest current", "latest", is_latest=True),
            ]
        )
    elif tool_key == "dotnet":
        options.extend(_dotnet_release_options(get_cached_release_set()))
    elif tool_key == "python":
        options.extend(
            [
                _option(tool_key, "bugfix", "Latest bugfix branch", "stable", is_latest=True),
                _option(tool_key, "security", "Supported security branch", "stable"),
            ]
        )
    else:
        options.append(_option(tool_key, "latest", "Latest stable", "latest", is_latest=True))

    if not installed:
        return VersionProviderResult(
            tool_key,
            tuple(options),
            VERSION_SOURCE_URLS[tool_key],
            stale=True,
            message="Installed version unavailable; showing channel choices.",
        )
    return VersionProviderResult(tool_key, tuple(options), VERSION_SOURCE_URLS[tool_key])
