# -*- coding: utf-8 -*-
"""Cloud + IaC CLIs — Terraform, Azure, GCloud, AWS."""

from __future__ import annotations

import platform
import shutil

from cabal.installers._common import _run_install, _WINGET_FLAGS
from cabal.installers.container_services import install_container_service


def terraform_install() -> tuple[bool, str]:
    sysname = platform.system()
    if sysname == "Windows":
        if shutil.which("winget"):
            return _run_install(["winget", "install", "--id", "Hashicorp.Terraform", *_WINGET_FLAGS])
        if shutil.which("choco"):
            return _run_install(["choco", "install", "terraform", "-y"])
        return False, "Install manually from https://developer.hashicorp.com/terraform/install"
    if sysname == "Darwin":
        if shutil.which("brew"):
            return _run_install(["brew", "install", "hashicorp/tap/terraform"])
        return False, "Install manually from https://developer.hashicorp.com/terraform/install"
    if sysname == "Linux":
        if shutil.which("apt-get"):
            # HashiCorp apt repo must be configured first; bare `apt install terraform` may fail.
            return _run_install(["sudo", "apt-get", "install", "-y", "terraform"])
        if shutil.which("dnf"):
            return _run_install(["sudo", "dnf", "install", "-y", "terraform"])
        return False, "See https://developer.hashicorp.com/terraform/install for distro-specific steps"
    return False, f"Unsupported platform: {sysname}"


def az_install() -> tuple[bool, str]:
    sysname = platform.system()
    if sysname == "Windows":
        if shutil.which("winget"):
            return _run_install(["winget", "install", "--id", "Microsoft.AzureCLI", *_WINGET_FLAGS])
        return False, "Install manually from https://aka.ms/installazurecliwindows"
    if sysname == "Darwin":
        if shutil.which("brew"):
            return _run_install(["brew", "install", "azure-cli"])
        return False, "Install manually from https://docs.microsoft.com/cli/azure/install-azure-cli-macos"
    if sysname == "Linux":
        if shutil.which("apt-get"):
            return _run_install(["sudo", "apt-get", "install", "-y", "azure-cli"])
        if shutil.which("dnf"):
            return _run_install(["sudo", "dnf", "install", "-y", "azure-cli"])
        return False, "See https://docs.microsoft.com/cli/azure/install-azure-cli-linux for distro-specific steps"
    return False, f"Unsupported platform: {sysname}"


def gcloud_install() -> tuple[bool, str]:
    sysname = platform.system()
    if sysname == "Windows":
        if shutil.which("winget"):
            return _run_install(["winget", "install", "--id", "Google.CloudSDK", *_WINGET_FLAGS])
        return False, "Install manually from https://cloud.google.com/sdk/docs/install"
    if sysname == "Darwin":
        if shutil.which("brew"):
            return _run_install(["brew", "install", "--cask", "google-cloud-sdk"])
        return False, "Install manually from https://cloud.google.com/sdk/docs/install"
    if sysname == "Linux":
        if shutil.which("apt-get"):
            return _run_install(["sudo", "apt-get", "install", "-y", "google-cloud-cli"])
        return False, "See https://cloud.google.com/sdk/docs/install for distro-specific steps"
    return False, f"Unsupported platform: {sysname}"


def aws_install() -> tuple[bool, str]:
    sysname = platform.system()
    if sysname == "Windows":
        if shutil.which("winget"):
            return _run_install(["winget", "install", "--id", "Amazon.AWSCLI", *_WINGET_FLAGS])
        return False, "Install manually from https://aws.amazon.com/cli/"
    if sysname == "Darwin":
        if shutil.which("brew"):
            return _run_install(["brew", "install", "awscli"])
        return False, "Install manually from https://aws.amazon.com/cli/"
    if sysname == "Linux":
        if shutil.which("apt-get"):
            return _run_install(["sudo", "apt-get", "install", "-y", "awscli"])
        if shutil.which("dnf"):
            return _run_install(["sudo", "dnf", "install", "-y", "awscli"])
        return False, "See https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2-linux.html"
    return False, f"Unsupported platform: {sysname}"


def azure_sql_local_install() -> tuple[bool, str]:
    from cabal.installers.databases import DATABASE_CONTAINER_SPECS

    return install_container_service(DATABASE_CONTAINER_SPECS["azure-sql-local"])


def cosmos_db_emulator_install() -> tuple[bool, str]:
    sysname = platform.system()
    if sysname == "Windows":
        if shutil.which("winget"):
            return _run_install(["winget", "install", "--id", "Microsoft.Azure.CosmosEmulator", *_WINGET_FLAGS])
        return False, "Install manually from https://learn.microsoft.com/azure/cosmos-db/emulator"
    return (
        False,
        "Cosmos DB Emulator desktop install is Windows-focused. Use the Linux "
        "container preview or Microsoft emulator docs for this platform.",
    )


def azurite_install() -> tuple[bool, str]:
    from cabal.installers.databases import DATABASE_CONTAINER_SPECS

    if shutil.which("docker") or shutil.which("podman"):
        return install_container_service(DATABASE_CONTAINER_SPECS["azurite"])
    if shutil.which("npm"):
        return _run_install(["npm", "install", "-g", "azurite"])
    return False, "Install Docker, Podman, or npm first, then install Azurite."
