# -*- coding: utf-8 -*-
"""Container + Kubernetes tooling — Docker, Podman, kubectl, OpenShift CLI."""

from __future__ import annotations

import platform
import shutil

from cabal.installers._common import _run_install, _WINGET_FLAGS


def docker_install() -> tuple[bool, str]:
    sysname = platform.system()
    if sysname == "Windows":
        if shutil.which("winget"):
            return _run_install(
                ["winget", "install", "--id", "Docker.DockerDesktop", *_WINGET_FLAGS]
            )
        return False, "Install manually from https://docker.com/products/docker-desktop"
    if sysname == "Darwin":
        if shutil.which("brew"):
            return _run_install(["brew", "install", "--cask", "docker"])
        return False, "Install manually from https://docker.com/products/docker-desktop"
    if sysname == "Linux":
        # Docker on Linux varies by distro (engine vs desktop). Send user to docs.
        return (
            False,
            "See https://docs.docker.com/engine/install/ for distro-specific steps",
        )
    return False, f"Unsupported platform: {sysname}"


def podman_install() -> tuple[bool, str]:
    sysname = platform.system()
    if sysname == "Windows":
        if shutil.which("winget"):
            return _run_install(
                ["winget", "install", "--id", "RedHat.Podman", *_WINGET_FLAGS]
            )
        return False, "Install manually from https://podman.io"
    if sysname == "Darwin":
        if shutil.which("brew"):
            return _run_install(["brew", "install", "podman"])
        return False, "Install manually from https://podman.io"
    if sysname == "Linux":
        if shutil.which("apt-get"):
            return _run_install(["sudo", "apt-get", "install", "-y", "podman"])
        if shutil.which("dnf"):
            return _run_install(["sudo", "dnf", "install", "-y", "podman"])
        if shutil.which("pacman"):
            return _run_install(["sudo", "pacman", "-S", "--noconfirm", "podman"])
        return False, "Install via your distro's package manager"
    return False, f"Unsupported platform: {sysname}"


def openshift_install() -> tuple[bool, str]:
    sysname = platform.system()
    if sysname == "Windows":
        if shutil.which("winget"):
            return _run_install(
                ["winget", "install", "--id", "RedHat.OpenShift-Client", *_WINGET_FLAGS]
            )
        return (
            False,
            "Install manually from https://mirror.openshift.com/pub/openshift-v4/clients/ocp/latest/",
        )
    if sysname == "Darwin":
        if shutil.which("brew"):
            return _run_install(["brew", "install", "openshift-cli"])
        return (
            False,
            "Install manually from https://mirror.openshift.com/pub/openshift-v4/clients/ocp/latest/",
        )
    if sysname == "Linux":
        return (
            False,
            "Download the `oc` client from https://mirror.openshift.com/pub/openshift-v4/clients/ocp/latest/",
        )
    return False, f"Unsupported platform: {sysname}"


def kubectl_install() -> tuple[bool, str]:
    sysname = platform.system()
    if sysname == "Windows":
        if shutil.which("winget"):
            return _run_install(
                ["winget", "install", "--id", "Kubernetes.kubectl", *_WINGET_FLAGS]
            )
        return False, "Install manually from https://kubernetes.io/docs/tasks/tools/"
    if sysname == "Darwin":
        if shutil.which("brew"):
            return _run_install(["brew", "install", "kubectl"])
        return False, "Install manually from https://kubernetes.io/docs/tasks/tools/"
    if sysname == "Linux":
        if shutil.which("apt-get"):
            return _run_install(["sudo", "apt-get", "install", "-y", "kubectl"])
        if shutil.which("dnf"):
            return _run_install(["sudo", "dnf", "install", "-y", "kubectl"])
        if shutil.which("pacman"):
            return _run_install(["sudo", "pacman", "-S", "--noconfirm", "kubectl"])
        return False, "Install manually from https://kubernetes.io/docs/tasks/tools/"
    return False, f"Unsupported platform: {sysname}"
