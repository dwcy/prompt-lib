# -*- coding: utf-8 -*-
"""Azure collector for the environment browser — all `az` subprocess I/O lives here.

Key Vault secrets are `permission_gated` rather than `readable`: listing names needs far less
than reading a value, so the only honest answer is to try on demand and report the refusal with
the role it would need (FR-021). App Service settings come back inline with the list call, and a
`@Microsoft.KeyVault(...)` value is surfaced as the reference it is, never resolved (FR-022).
Read-only throughout (FR-023) — every `az` verb used is `list` or `show`.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from cabal.dashboard_links import find_azd_environment_name, find_azd_link, find_iac_link
from cabal.models.envsources import (
    AvailabilityState,
    LinkConfidence,
    Retrievability,
    SourceKind,
    VariableContainer,
    VariableEntry,
    VariableSource,
)

VAULT_SOURCE_ID = "azure_keyvault"
APP_SOURCE_ID = "azure_app_settings"
VAULT_LABEL = "Key Vault"
APP_LABEL = "App settings"

_AZ = "az"
_TIMEOUT = 15
KEYVAULT_REFERENCE_PREFIX = "@Microsoft.KeyVault("

REASON_VAULT_GATED = "reading a Key Vault secret requires the Key Vault Secrets User role"
REASON_DENIED_ROLE = (
    "access denied — reading this secret requires the Key Vault Secrets User role on the vault"
)

_HINT_NO_CLI = "the Azure CLI (az) is not installed"
_HINT_NOT_AUTHED = "Azure sign-in is required — run `az login`"
_HINT_TIMEOUT = "the Azure CLI did not answer within {timeout}s"
_HINT_FAILED = "Azure returned: {detail}"

_REASON_EXPLICIT = "an Azure scope you recorded for this project"
_REASON_AZD = "Azure Developer CLI files in this project ({signal})"
_REASON_IAC = "infrastructure-as-code in this project ({signal})"
_REASON_MACHINE = "this machine's default Azure sign-in — not a link to this project"


def detect_link(project: Path, explicit=None):
    """Walk the four-signal ladder (FR-030) and return (confidence, reason, subscription, group).

    Signals 1-3 are pure file detection; only `machine_default` shells out, and only when the
    first three miss — which is what keeps every project on a signed-in machine from looking
    Azure-linked (FR-032).
    """
    if explicit is not None:
        return (
            LinkConfidence.EXPLICIT,
            _REASON_EXPLICIT,
            explicit.subscription_id,
            explicit.resource_group,
        )
    azd = find_azd_link(project)
    if azd is not None:
        environment = find_azd_environment_name(project)
        signal = f"{azd}, environment {environment}" if environment else azd
        return LinkConfidence.AZD, _REASON_AZD.format(signal=signal), None, None
    iac = find_iac_link(project)
    if iac is not None:
        return LinkConfidence.IAC, _REASON_IAC.format(signal=iac), None, None
    subscription = _machine_subscription()
    if subscription is None:
        return None, None, None, None
    return LinkConfidence.MACHINE_DEFAULT, _REASON_MACHINE, subscription, None


def collect_azure(project: Path, explicit=None) -> list[VariableSource]:
    """Key vault and app-service settings for the project's Azure scope; never raises."""
    confidence, reason, subscription, resource_group = detect_link(project, explicit)
    if confidence is None:
        return []
    if shutil.which(_AZ) is None:
        return [_degraded(VAULT_SOURCE_ID, VAULT_LABEL, SourceKind.AZURE_KEYVAULT, _HINT_NO_CLI, confidence, reason)]

    vaults = _vault_source(subscription, resource_group, confidence, reason)
    apps = _app_source(subscription, resource_group, confidence, reason)
    return [vaults, apps]


def reveal_vault_secret(container_id: str, name: str):
    """Read one Key Vault secret; an RBAC refusal becomes a stated denial, never a 5xx."""
    vault = container_id.rsplit(":", 1)[-1]
    code, payload = _az(["keyvault", "secret", "show", "--vault-name", vault, "--name", name])
    if code != 0:
        return None, _classify_secret_failure(payload)
    try:
        document = json.loads(payload)
    except ValueError:
        return None, "Azure returned a response this module could not read"
    value = document.get("value") if isinstance(document, dict) else None
    return (value, None) if isinstance(value, str) else (None, "the vault returned no value")


def reveal_app_setting(container_id: str, name: str):
    """App settings come back inline; re-read the list rather than caching from the listing."""
    _prefix, _kind, resource_group, app = container_id.split(":", 3)
    code, payload = _az(
        ["webapp", "config", "appsettings", "list", "--name", app, "--resource-group", resource_group]
    )
    if code != 0:
        return None, _classify(payload)
    try:
        document = json.loads(payload)
    except ValueError:
        return None, "Azure returned a response this module could not read"
    if not isinstance(document, list):
        return None, "Azure returned no settings for that application"
    for item in document:
        if isinstance(item, dict) and item.get("name") == name:
            value = item.get("value")
            return (str(value) if value is not None else ""), None
    return None, "that setting is no longer present on the application"


def _vault_source(subscription, resource_group, confidence, reason) -> VariableSource:
    code, payload = _az(_scoped(["keyvault", "list"], subscription, resource_group))
    if code != 0:
        return _degraded(VAULT_SOURCE_ID, VAULT_LABEL, SourceKind.AZURE_KEYVAULT, _classify(payload), confidence, reason)
    vaults = _as_list(payload)
    containers: list[VariableContainer] = []
    for vault in vaults:
        vault_name = vault.get("name") if isinstance(vault, dict) else None
        if not isinstance(vault_name, str) or not vault_name:
            continue
        containers.append(_vault_container(vault_name))
    populated = [container for container in containers if container.entries]
    state = AvailabilityState.OK if populated else AvailabilityState.EMPTY
    return _source(
        VAULT_SOURCE_ID, VAULT_LABEL, SourceKind.AZURE_KEYVAULT, state, None, confidence, reason, populated
    )


def _vault_container(vault_name: str) -> VariableContainer:
    container_id = f"{VAULT_SOURCE_ID}:{vault_name}"
    code, payload = _az(["keyvault", "secret", "list", "--vault-name", vault_name])
    entries: list[VariableEntry] = []
    for secret in _as_list(payload) if code == 0 else []:
        name = _secret_name(secret)
        if name is None:
            continue
        attributes = secret.get("attributes") if isinstance(secret, dict) else None
        updated = attributes.get("updated") if isinstance(attributes, dict) else None
        entries.append(
            VariableEntry(
                name=name,
                source_id=VAULT_SOURCE_ID,
                container_id=container_id,
                target=vault_name,
                entry_type="secret",
                updated_at=updated if isinstance(updated, str) else None,
                retrievability=Retrievability.PERMISSION_GATED,
                retrievability_reason=REASON_VAULT_GATED,
            )
        )
    return VariableContainer(
        id=container_id, source_id=VAULT_SOURCE_ID, label=vault_name, qualifier=VAULT_LABEL, entries=entries
    )


def _app_source(subscription, resource_group, confidence, reason) -> VariableSource:
    code, payload = _az(_scoped(["webapp", "list"], subscription, resource_group))
    if code != 0:
        return _degraded(APP_SOURCE_ID, APP_LABEL, SourceKind.AZURE_APP_SETTINGS, _classify(payload), confidence, reason)
    containers: list[VariableContainer] = []
    for app in _as_list(payload):
        name = app.get("name") if isinstance(app, dict) else None
        group = app.get("resourceGroup") if isinstance(app, dict) else None
        if not isinstance(name, str) or not isinstance(group, str):
            continue
        containers.append(_app_container(name, group))
    populated = [container for container in containers if container.entries]
    state = AvailabilityState.OK if populated else AvailabilityState.EMPTY
    return _source(
        APP_SOURCE_ID, APP_LABEL, SourceKind.AZURE_APP_SETTINGS, state, None, confidence, reason, populated
    )


def _app_container(app: str, resource_group: str) -> VariableContainer:
    container_id = f"{APP_SOURCE_ID}:{resource_group}:{app}"
    code, payload = _az(
        ["webapp", "config", "appsettings", "list", "--name", app, "--resource-group", resource_group]
    )
    entries: list[VariableEntry] = []
    for setting in _as_list(payload) if code == 0 else []:
        name = setting.get("name") if isinstance(setting, dict) else None
        if not isinstance(name, str) or not name:
            continue
        raw = setting.get("value")
        is_reference = isinstance(raw, str) and raw.startswith(KEYVAULT_REFERENCE_PREFIX)
        entries.append(
            VariableEntry(
                name=name,
                source_id=APP_SOURCE_ID,
                container_id=container_id,
                target=app,
                entry_type="keyvault_reference" if is_reference else "app_setting",
                retrievability=Retrievability.READABLE,
                is_reference=is_reference,
            )
        )
    return VariableContainer(
        id=container_id, source_id=APP_SOURCE_ID, label=app, qualifier=resource_group, entries=entries
    )


def _scoped(args: list[str], subscription: str | None, resource_group: str | None) -> list[str]:
    scoped = list(args)
    if resource_group:
        scoped += ["--resource-group", resource_group]
    if subscription:
        scoped += ["--subscription", subscription]
    return scoped


def _secret_name(secret) -> str | None:
    if not isinstance(secret, dict):
        return None
    name = secret.get("name")
    if isinstance(name, str) and name:
        return name
    identifier = secret.get("id")
    return identifier.rsplit("/", 1)[-1] if isinstance(identifier, str) and identifier else None


def _machine_subscription() -> str | None:
    if shutil.which(_AZ) is None:
        return None
    code, payload = _az(["account", "show"])
    if code != 0:
        return None
    try:
        document = json.loads(payload)
    except ValueError:
        return None
    identifier = document.get("id") if isinstance(document, dict) else None
    return identifier if isinstance(identifier, str) and identifier else None


def _source(source_id, label, kind, state, hint, confidence, reason, containers) -> VariableSource:
    return VariableSource(
        id=source_id,
        kind=kind,
        label=label,
        state=state,
        hint=hint,
        outside_repository=True,
        link_confidence=confidence,
        link_reason=reason,
        containers=containers,
    )


def _degraded(source_id, label, kind, hint, confidence, reason) -> VariableSource:
    return _source(source_id, label, kind, AvailabilityState.DEGRADED, hint, confidence, reason, [])


def _as_list(payload: str) -> list:
    try:
        document = json.loads(payload)
    except ValueError:
        return []
    return document if isinstance(document, list) else []


def _az(args: list[str]) -> tuple[int, str]:
    """`az <args> -o json` — returns (0, body) or (code, diagnostic text). Never raises.

    Runs the resolved executable rather than the bare name: on Windows `az` is a `.CMD`
    wrapper, and CreateProcess cannot launch it from the name alone (WinError 2).
    """
    executable = shutil.which(_AZ)
    if executable is None:
        return 1, _HINT_NO_CLI
    try:
        result = subprocess.run(
            [executable, *args, "-o", "json"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_TIMEOUT,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        return 1, _HINT_TIMEOUT.format(timeout=_TIMEOUT)
    except OSError as exc:
        return 1, str(exc)
    if result.returncode != 0:
        return result.returncode, ((result.stderr or result.stdout) or "").strip()
    return 0, result.stdout or ""


def _classify(detail: str) -> str:
    lowered = (detail or "").lower()
    if "did not answer" in lowered:
        return detail
    if "az login" in lowered or "not logged in" in lowered or "no subscription" in lowered:
        return _HINT_NOT_AUTHED
    return _HINT_FAILED.format(detail=(detail or "").strip() or "an unexplained failure")


# Azure phrases an RBAC refusal several ways depending on which plane answered
# ("not authorized", "Forbidden", "does not have secrets get permission"). Any of them
# is a permission problem, and reporting it as a generic failure would send the reader
# looking for an outage instead of a role assignment (FR-021).
_DENIAL_MARKERS = (
    "not authorized",
    "unauthorized",
    "forbidden",
    "denied",
    "authorization",
    "permission",
    "403",
)


def _classify_secret_failure(detail: str) -> str:
    lowered = (detail or "").lower()
    if any(marker in lowered for marker in _DENIAL_MARKERS):
        return REASON_DENIED_ROLE
    return _classify(detail)
