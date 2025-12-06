"""Secret sealing operations.

This module provides functions for sealing, merging, re-encrypting,
and backing up sealed secrets using the kubeseal binary.
"""

import contextlib
import shutil
import subprocess
from pathlib import Path

import click
from icecream import ic

from kubeseal_auto import console
from kubeseal_auto.exceptions import SecretParsingError
from kubeseal_auto.models import SecretParams
from kubeseal_auto.secrets.parsing import append_argo_annotation, parse_secret_file


def _find_sealed_secrets(src: str) -> list[Path]:
    """Find all SealedSecret files in a directory.

    Args:
        src: Path to the directory to search.

    Returns:
        List of paths to SealedSecret YAML files.

    """
    secrets: list[Path] = []
    for path in Path(src).rglob("*.yaml"):
        try:
            secret = parse_secret_file(str(path.absolute()))
            if secret is not None and secret["kind"] == "SealedSecret":
                secrets.append(path.absolute())
        except (KeyError, SecretParsingError):
            # Not a SealedSecret or invalid file, skip
            continue
    return secrets


def seal_secret(
    secret_params: SecretParams,
    temp_file_path: Path,
    kubeseal_cmd: list[str],
) -> None:
    """Seal a secret using kubeseal.

    Reads the temporary secret file and outputs a sealed secret YAML file.

    Args:
        secret_params: SecretParams containing name, namespace, and secret_type.
        temp_file_path: Path to the temporary unseal secret file.
        kubeseal_cmd: Base kubeseal command with appropriate flags.

    Raises:
        click.ClickException: If kubeseal command fails.

    """
    console.step("Sealing secret")
    ic(kubeseal_cmd)

    output_file = f"{secret_params.name}.yaml"

    try:
        with console.spinner("Sealing secret with kubeseal..."):
            with open(temp_file_path) as stdin_f, open(output_file, "w") as stdout_f:
                subprocess.run(kubeseal_cmd, stdin=stdin_f, stdout=stdout_f, check=True)
            append_argo_annotation(filename=output_file)
    except subprocess.CalledProcessError as err:
        # Clean up partial output file on failure
        with contextlib.suppress(OSError):
            Path(output_file).unlink(missing_ok=True)
        raise click.ClickException(f"Failed to seal secret with kubeseal (exit code {err.returncode})") from err

    console.newline()
    console.summary_panel(
        "Sealed Secret Created",
        {
            "Name": secret_params.name,
            "Namespace": secret_params.namespace,
            "Type": secret_params.secret_type.value,
            "Output": output_file,
        },
    )


def merge_secret(
    secret_name: str,
    temp_file_path: Path,
    kubeseal_cmd: list[str],
) -> None:
    """Merge new secret entries into an existing sealed secret file.

    Args:
        secret_name: Path to the existing sealed secret file to update.
        temp_file_path: Path to the temporary secret file with new entries.
        kubeseal_cmd: Base kubeseal command with appropriate flags.

    Raises:
        click.ClickException: If kubeseal command fails.

    """
    console.action(f"Updating {console.highlight(secret_name)}")

    cmd = [*kubeseal_cmd, "--merge-into", secret_name]
    ic(cmd)

    try:
        with open(temp_file_path) as stdin_f:
            subprocess.run(cmd, stdin=stdin_f, check=True)
    except subprocess.CalledProcessError as err:
        raise click.ClickException(f"Failed to merge secret with kubeseal (exit code {err.returncode})") from err

    append_argo_annotation(filename=secret_name)
    console.success("Done")


def reencrypt_secrets(src: str, kubeseal_cmd: list[str]) -> None:
    """Re-encrypt existing SealedSecret files using the newest encryption certificate.

    Args:
        src: Path to the directory containing SealedSecret files.
        kubeseal_cmd: Base kubeseal command with appropriate flags.

    """
    secrets = _find_sealed_secrets(src)
    if not secrets:
        console.warning("No SealedSecret files found")
        return

    cmd = [*kubeseal_cmd, "--re-encrypt"]

    with console.create_task_progress() as progress:
        task = progress.add_task("Re-encrypting secrets", total=len(secrets))
        for secret in secrets:
            backup_path = secret.with_suffix(secret.suffix + "_backup")
            output_tmp = secret.with_suffix(secret.suffix + "_new")

            # Create backup of original file
            shutil.copy2(secret, backup_path)

            ic(cmd)

            try:
                with secret.open() as stdin_f, output_tmp.open("w") as stdout_f:
                    subprocess.run(cmd, stdin=stdin_f, stdout=stdout_f, check=True)
                # Atomic replace on success
                output_tmp.replace(secret)
                backup_path.unlink()
            except subprocess.CalledProcessError as err:
                # Restore from backup on failure
                if backup_path.exists():
                    backup_path.replace(secret)
                with contextlib.suppress(OSError):
                    output_tmp.unlink(missing_ok=True)
                raise click.ClickException(f"Failed to re-encrypt {secret} (exit code {err.returncode})") from err

            append_argo_annotation(str(secret))
            progress.update(task, advance=1)


def fetch_certificate(
    binary: str,
    controller_namespace: str,
    controller_name: str,
    context_name: str,
) -> None:
    """Download the kubeseal encryption certificate from the cluster.

    This certificate can be used in the future to encrypt secrets
    without direct access to the cluster (detached mode).

    Args:
        binary: Path to the kubeseal binary.
        controller_namespace: Namespace of the SealedSecrets controller.
        controller_name: Name of the SealedSecrets controller.
        context_name: Kubernetes context name.

    Raises:
        click.ClickException: If kubeseal command fails.

    """
    console.action("Downloading certificate for kubeseal...")
    cmd: list[str] = [
        binary,
        "--controller-namespace",
        controller_namespace,
        f"--context={context_name}",
        "--controller-name",
        controller_name,
        "--fetch-cert",
    ]
    ic(cmd)

    output_file = f"{context_name}-kubeseal-cert.crt"
    try:
        with open(output_file, "w") as f:
            subprocess.run(cmd, stdout=f, check=True)
    except subprocess.CalledProcessError as err:
        # Clean up partial output file on failure
        with contextlib.suppress(OSError):
            Path(output_file).unlink(missing_ok=True)
        raise click.ClickException(f"Failed to fetch certificate from kubeseal (exit code {err.returncode})") from err

    console.success(f"Saved to {console.highlight(output_file)}")


def backup_controller_secret(
    controller_namespace: str,
    secret_name: str,
    context_name: str,
) -> None:
    """Create a backup of the SealedSecret controller's encryption secret.

    Args:
        controller_namespace: Namespace of the SealedSecrets controller.
        secret_name: Name of the secret to backup.
        context_name: Kubernetes context name (used for output filename).

    Raises:
        click.ClickException: If kubectl command fails.

    """
    cmd: list[str] = [
        "kubectl",
        "get",
        "secret",
        "-n",
        controller_namespace,
        secret_name,
        "-o",
        "yaml",
    ]
    ic(cmd)

    output_file = f"{context_name}-secret-backup.yaml"
    try:
        with open(output_file, "w") as f:
            subprocess.run(cmd, stdout=f, check=True)
    except subprocess.CalledProcessError as err:
        # Clean up partial output file on failure
        with contextlib.suppress(OSError):
            Path(output_file).unlink(missing_ok=True)
        raise click.ClickException(f"Failed to backup secret (exit code {err.returncode})") from err

    console.success(f"Saved to {console.highlight(output_file)}")
