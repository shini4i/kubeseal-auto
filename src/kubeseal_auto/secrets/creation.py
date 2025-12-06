"""Secret creation functions.

This module provides functions for creating different types of
Kubernetes secrets (generic, TLS, docker-registry).
"""

import subprocess
from pathlib import Path

import click
from icecream import ic

from kubeseal_auto import console
from kubeseal_auto.models import SecretParams
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

    try:
        with open(output_path, "w") as f:
            subprocess.run(cmd, stdout=f, check=True)
    except subprocess.CalledProcessError as err:
        raise click.ClickException(f"Failed to create generic secret (exit code {err.returncode})") from err


def create_tls_secret(secret_params: SecretParams, output_path: Path) -> None:
    """Generate a temporary TLS secret YAML file.

    Expects tls.key and tls.crt files to exist in the current directory.

    Args:
        secret_params: SecretParams containing name and namespace.
        output_path: Path where the temporary secret YAML will be written.

    Raises:
        click.ClickException: If tls.key or tls.crt files do not exist.

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

    try:
        with open(output_path, "w") as f:
            subprocess.run(cmd, stdout=f, check=True)
    except subprocess.CalledProcessError as err:
        raise click.ClickException(f"Failed to create TLS secret (exit code {err.returncode})") from err


def create_regcred_secret(secret_params: SecretParams, output_path: Path) -> None:
    """Generate a temporary docker-registry secret YAML file.

    Prompts user for Docker registry credentials. The password is passed via
    stdin to avoid exposing it in process listings.

    Args:
        secret_params: SecretParams containing name and namespace.
        output_path: Path where the temporary secret YAML will be written.

    Raises:
        click.ClickException: If kubectl command fails.

    """
    console.step("Generating temporary docker-registry secret yaml file")

    docker_server, docker_username, docker_password = prompt_docker_credentials()

    # Password is passed via stdin to avoid exposure in process listings
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
        "--docker-password-stdin",
        _DRY_RUN_CLIENT,
        "-o",
        "yaml",
    ]
    # Don't log cmd even though password is now via stdin (username/server are still sensitive)

    try:
        with output_path.open("w") as f:
            subprocess.run(
                cmd,
                input=docker_password.encode(),
                stdout=f,
                stderr=subprocess.PIPE,
                check=True,
            )
    except subprocess.CalledProcessError as err:
        stderr_msg = err.stderr.decode().strip() if err.stderr else ""
        error_details = f" - {stderr_msg}" if stderr_msg else ""
        raise click.ClickException(f"Failed to create docker-registry secret (exit code {err.returncode}){error_details}") from err
