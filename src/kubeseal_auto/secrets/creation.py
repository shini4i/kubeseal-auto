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

# Error message constants
_ERR_KUBECTL_NOT_FOUND = "kubectl not found; please install kubectl and ensure it's on PATH"
_ERR_OUTPUT_PATH = "Cannot write to output path '{path}': {reason}"
_ERR_SECRET_CREATION = "Failed to create {secret_type} secret (exit code {code}){details}"


def _kubectl_error(msg: str) -> click.ClickException:
    """Create a ClickException for kubectl-related errors.

    Args:
        msg: The error message.

    Returns:
        A ClickException with the formatted message.

    """
    return click.ClickException(msg)


def _run_kubectl_write_output(
    cmd: list[str],
    output_path: Path,
    secret_type: str,
    *,
    input_data: bytes | None = None,
) -> None:
    """Run a kubectl command and write its stdout to a file.

    Args:
        cmd: The kubectl command to execute.
        output_path: Path where the command output will be written.
        secret_type: Type of secret being created (for error messages).
        input_data: Optional bytes to pass to stdin.

    Raises:
        click.ClickException: If output path is invalid, kubectl is not found,
            or the command fails.

    """
    try:
        f = output_path.open("w")
    except OSError as err:
        raise _kubectl_error(
            _ERR_OUTPUT_PATH.format(path=output_path, reason=err.strerror)
        ) from err

    with f:
        try:
            subprocess.run(
                cmd,
                input=input_data,
                stdout=f,
                stderr=subprocess.PIPE,
                check=True,
            )
        except FileNotFoundError as err:
            raise _kubectl_error(_ERR_KUBECTL_NOT_FOUND) from err
        except subprocess.CalledProcessError as err:
            stderr_msg = err.stderr.decode().strip() if err.stderr else ""
            error_details = f" - {stderr_msg}" if stderr_msg else ""
            raise _kubectl_error(
                _ERR_SECRET_CREATION.format(
                    secret_type=secret_type, code=err.returncode, details=error_details
                )
            ) from err


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

    _run_kubectl_write_output(cmd, output_path, "generic")


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

    _run_kubectl_write_output(cmd, output_path, "TLS")


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

    _run_kubectl_write_output(
        cmd, output_path, "docker-registry", input_data=docker_password.encode()
    )
