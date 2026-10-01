"""Secret sealing operations.

This module provides functions for sealing, merging, re-encrypting,
and backing up sealed secrets using the kubeseal binary.
"""

import shutil
from pathlib import Path

import click

from kubeseal_auto import console
from kubeseal_auto.debug import ic
from kubeseal_auto.exceptions import SecretParsingError
from kubeseal_auto.models import SecretParams
from kubeseal_auto.secrets.command import run_command, run_to_file, safe_filename
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
            if secret is not None and secret.get("kind") == "SealedSecret":
                secrets.append(path.absolute())
        except SecretParsingError:
            # Invalid or unreadable YAML file, skip
            continue
    return secrets


def seal_secret(
    secret_params: SecretParams,
    temp_file_path: Path,
    kubeseal_cmd: list[str],
) -> None:
    """Seal a secret using kubeseal.

    Reads the temporary secret file and writes ``<name>.yaml`` in the
    current directory.

    Args:
        secret_params: SecretParams containing name, namespace, and secret_type.
        temp_file_path: Path to the temporary unsealed secret file.
        kubeseal_cmd: Base kubeseal command with appropriate flags.

    Raises:
        click.ClickException: If the output file cannot be written or kubeseal fails.

    """
    console.step("Sealing secret")
    ic(kubeseal_cmd)

    output_file = Path(f"{secret_params.name}.yaml")

    with console.spinner("Sealing secret with kubeseal..."):
        run_to_file(kubeseal_cmd, output_file, "Failed to seal secret with kubeseal", stdin_path=temp_file_path)
        append_argo_annotation(filename=str(output_file))

    console.newline()
    console.summary_panel(
        "Sealed Secret Created",
        {
            "Name": secret_params.name,
            "Namespace": secret_params.namespace,
            "Type": secret_params.secret_type.value,
            "Output": str(output_file),
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
        click.ClickException: If kubeseal is not found or fails.

    """
    console.action(f"Updating {console.highlight(secret_name)}")

    cmd = [*kubeseal_cmd, "--merge-into", secret_name]
    ic(cmd)

    run_command(cmd, "Failed to merge secret with kubeseal", stdin_path=temp_file_path)

    append_argo_annotation(filename=secret_name)
    console.success("Done")


def reencrypt_secrets(src: str, kubeseal_cmd: list[str]) -> None:
    """Re-encrypt existing SealedSecret files using the newest encryption certificate.

    Each file is restored to its original content if kubeseal fails. If adding
    the ArgoCD annotation fails afterwards, the original stays in
    ``<file>_backup`` and the error names that path.

    Args:
        src: Path to the directory containing SealedSecret files.
        kubeseal_cmd: Base kubeseal command with appropriate flags.

    Raises:
        click.ClickException: If kubeseal is not found or fails for any file,
            or the ArgoCD annotation cannot be added.

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
                run_to_file(cmd, output_tmp, f"Failed to re-encrypt {secret}", stdin_path=secret)
            except click.ClickException:
                backup_path.replace(secret)
                raise

            # Atomic replace on success
            output_tmp.replace(secret)
            try:
                append_argo_annotation(str(secret))
            except (SecretParsingError, OSError) as err:
                raise click.ClickException(f"Failed to annotate {secret}: {err}. Original kept at {backup_path}") from err
            backup_path.unlink()
            progress.update(task, advance=1)


def fetch_certificate(
    binary: str,
    controller_namespace: str,
    controller_name: str,
    context_name: str,
) -> None:
    """Download the kubeseal encryption certificate from the cluster.

    This certificate can be used in the future to encrypt secrets
    without direct access to the cluster (detached mode). It is saved as
    ``<context>-kubeseal-cert.crt``, with characters that are invalid in a
    filename replaced by ``_``.

    Args:
        binary: Path to the kubeseal binary.
        controller_namespace: Namespace of the SealedSecrets controller.
        controller_name: Name of the SealedSecrets controller.
        context_name: Kubernetes context name.

    Raises:
        click.ClickException: If the output file cannot be written or kubeseal fails.

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

    output_file = Path(f"{safe_filename(context_name)}-kubeseal-cert.crt")
    run_to_file(cmd, output_file, "Failed to fetch certificate from kubeseal")

    console.success(f"Saved to {console.highlight(str(output_file))}")


def backup_controller_secret(
    controller_namespace: str,
    secret_name: str,
    context_name: str,
) -> None:
    """Create a backup of the SealedSecret controller's encryption secret.

    The backup is saved as ``<context>-secret-backup.yaml``, with characters
    that are invalid in a filename replaced by ``_``. The file holds the
    controller's private key, so it is readable only by its owner (mode 0600).

    Args:
        controller_namespace: Namespace of the SealedSecrets controller.
        secret_name: Name of the secret to backup.
        context_name: Kubernetes context to read the secret from; also used
            in the output filename.

    Raises:
        click.ClickException: If the output file cannot be written or kubectl fails.

    """
    cmd: list[str] = [
        "kubectl",
        f"--context={context_name}",
        "get",
        "secret",
        "-n",
        controller_namespace,
        secret_name,
        "-o",
        "yaml",
    ]
    ic(cmd)

    output_file = Path(f"{safe_filename(context_name)}-secret-backup.yaml")
    run_to_file(cmd, output_file, "Failed to backup secret", private=True)

    console.success(f"Saved to {console.highlight(str(output_file))}")
