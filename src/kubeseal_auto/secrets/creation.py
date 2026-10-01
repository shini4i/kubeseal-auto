"""Secret creation functions.

This module provides functions for creating different types of
Kubernetes secrets (generic, TLS, docker-registry).
"""

from pathlib import Path

import click

from kubeseal_auto import console
from kubeseal_auto.debug import ic
from kubeseal_auto.models import SecretParams
from kubeseal_auto.secrets.command import run_to_file
from kubeseal_auto.secrets.prompts import collect_secret_entries, prompt_docker_credentials

# CLI flag constants for kubectl commands
_DRY_RUN_CLIENT = "--dry-run=client"


def create_generic_secret(secret_params: SecretParams, output_path: Path) -> None:
    """Generate a temporary generic secret YAML file from user-provided entries.

    Prompts user for key=value pairs (literals) or filenames. Each entry
    is processed and passed to kubectl to create a secret.

    Args:
        secret_params: SecretParams containing name and namespace.
        output_path: Path where the temporary secret YAML will be written.

    Raises:
        click.ClickException: If kubectl is not found or fails.

    """
    entries = collect_secret_entries()

    ic(entries)
    console.step("Generating temporary generic secret yaml file")

    cmd: list[str] = [
        "kubectl",
        "create",
        "secret",
        "generic",
        secret_params.name,
        "--namespace",
        secret_params.namespace,
        _DRY_RUN_CLIENT,
        "-o",
        "yaml",
        *entries,
    ]

    ic(cmd)

    run_to_file(cmd, output_path, "Failed to create generic secret")


def create_tls_secret(secret_params: SecretParams, output_path: Path) -> None:
    """Generate a temporary TLS secret YAML file.

    Expects tls.key and tls.crt files to exist in the current directory.

    Args:
        secret_params: SecretParams containing name and namespace.
        output_path: Path where the temporary secret YAML will be written.

    Raises:
        click.ClickException: If tls.key or tls.crt files do not exist,
            or kubectl is not found or fails.

    """
    key_file = Path("tls.key")
    cert_file = Path("tls.crt")

    missing_files = []
    if not key_file.exists():
        missing_files.append("tls.key")
    if not cert_file.exists():
        missing_files.append("tls.crt")

    if missing_files:
        raise click.ClickException(f"Required TLS file(s) not found in current directory: {', '.join(missing_files)}")

    console.step("Generating temporary TLS secret yaml file")
    cmd: list[str] = [
        "kubectl",
        "create",
        "secret",
        "tls",
        secret_params.name,
        "--namespace",
        secret_params.namespace,
        "--key",
        str(key_file),
        "--cert",
        str(cert_file),
        _DRY_RUN_CLIENT,
        "-o",
        "yaml",
    ]
    ic(cmd)

    run_to_file(cmd, output_path, "Failed to create TLS secret")


def create_regcred_secret(secret_params: SecretParams, output_path: Path) -> None:
    """Generate a temporary docker-registry secret YAML file.

    Prompts user for Docker registry credentials.

    Args:
        secret_params: SecretParams containing name and namespace.
        output_path: Path where the temporary secret YAML will be written.

    Raises:
        click.ClickException: If kubectl is not found or fails.

    """
    console.step("Generating temporary docker-registry secret yaml file")

    docker_server, docker_username, docker_password = prompt_docker_credentials()

    cmd: list[str] = [
        "kubectl",
        "create",
        "secret",
        "docker-registry",
        secret_params.name,
        "--namespace",
        secret_params.namespace,
        f"--docker-server={docker_server}",
        f"--docker-username={docker_username}",
        f"--docker-password={docker_password}",
        _DRY_RUN_CLIENT,
        "-o",
        "yaml",
    ]

    run_to_file(cmd, output_path, "Failed to create docker-registry secret")
