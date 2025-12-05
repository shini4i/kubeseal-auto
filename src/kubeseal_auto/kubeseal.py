"""Kubeseal wrapper for creating and managing sealed secrets.

This module provides the Kubeseal class which wraps the kubeseal binary
to create, seal, and manage Kubernetes sealed secrets.
"""

import contextlib
import os
import re
import shutil
import subprocess
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import click
import questionary
import yaml
from icecream import ic

from kubeseal_auto import console
from kubeseal_auto.cluster import Cluster
from kubeseal_auto.exceptions import BinaryNotFoundError, SecretParsingError
from kubeseal_auto.styles import POINTER, PROMPT_STYLE, QMARK

# Kubernetes DNS subdomain name validation (RFC 1123)
_DNS_SUBDOMAIN_MAX_LENGTH = 253
_DNS_SUBDOMAIN_PATTERN = r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?(\.[a-z0-9]([-a-z0-9]*[a-z0-9])?)*$"

# CLI flag constants for kubectl and kubeseal commands
_DRY_RUN_CLIENT = "--dry-run=client"
_FORMAT_YAML = "--format=yaml"

def _validate_k8s_name(name: str) -> bool | str:
    """Validate a Kubernetes resource name (DNS subdomain).

    Args:
        name: The name to validate.

    Returns:
        True if valid, or an error message string if invalid.

    """
    if not name:
        return "Name cannot be empty"
    if len(name) > _DNS_SUBDOMAIN_MAX_LENGTH:
        return f"Name must be {_DNS_SUBDOMAIN_MAX_LENGTH} characters or less"
    if not re.match(_DNS_SUBDOMAIN_PATTERN, name):
        return "Name must consist of lowercase alphanumeric characters, '-' or '.', and must start and end with an alphanumeric character"
    return True


class Kubeseal:
    """Wrapper for kubeseal binary operations.

    This class provides methods for creating, sealing, and managing
    Kubernetes secrets using the kubeseal binary.

    Attributes:
        detached_mode: Whether operating without direct cluster access.
        binary: Path to the kubeseal binary.
        certificate: Path to the certificate file (detached mode only).
        cluster: Cluster instance for cluster operations.
        controller_name: Name of the SealedSecrets controller.
        controller_namespace: Namespace of the SealedSecrets controller.
        current_context_name: Current Kubernetes context name.
        namespaces_list: List of available namespaces.
        _temp_file_path: Path to temporary file for intermediate secret storage.

    """

    def __init__(self, select_context: bool, certificate: str | None = None) -> None:
        """Initialize Kubeseal with cluster connection or certificate.

        Args:
            select_context: If True, prompt user to select a Kubernetes context.
            certificate: Path to certificate file for detached mode. If provided,
                        operates without connecting to a cluster.

        """
        self.detached_mode: bool = False
        self.binary: str = "kubeseal"
        self.certificate: str | None = None
        self.cluster: Cluster | None = None
        self.controller_name: str = ""
        self.controller_namespace: str = ""
        self.current_context_name: str = ""
        self.namespaces_list: list[str] = []

        if certificate is not None:
            console.info("Working in detached mode")
            self.detached_mode = True
            self.certificate = certificate
        else:
            self.cluster = Cluster(select_context=select_context)
            self.controller_name = self.cluster.get_controller_name()
            self.controller_namespace = self.cluster.get_controller_namespace()
            self.current_context_name = self.cluster.get_context()
            self.namespaces_list = self.cluster.get_all_namespaces()
            version = self.cluster.get_controller_version()

            try:
                self.cluster.ensure_kubeseal_version(version)
                self.binary = self.cluster.get_kubeseal_binary_path(version)
            except BinaryNotFoundError:
                system_binary = shutil.which("kubeseal")
                if system_binary is None:
                    raise BinaryNotFoundError(
                        "kubeseal binary not found. Please install kubeseal or ensure it's in your PATH. "
                        "See: https://github.com/bitnami-labs/sealed-secrets#installation"
                    ) from None
                console.warning("Falling back to the default kubeseal binary")
                self.binary = system_binary

        # Create temp file with delete=False for Windows compatibility
        # Close immediately to avoid file locking issues when reopening
        temp_file = NamedTemporaryFile(delete=False)
        self._temp_file_path: str = temp_file.name
        temp_file.close()

    def __enter__(self) -> "Kubeseal":
        """Enter context manager.

        Returns:
            The Kubeseal instance.

        """
        return self

    def __exit__(self, exc_type: type | None, exc_val: Exception | None, exc_tb: object) -> None:
        """Exit context manager and clean up resources.

        Args:
            exc_type: Exception type if an exception was raised.
            exc_val: Exception value if an exception was raised.
            exc_tb: Exception traceback if an exception was raised.

        """
        self._cleanup_temp_file()

    def _cleanup_temp_file(self) -> None:
        """Remove the temporary file if it exists."""
        if hasattr(self, "_temp_file_path") and os.path.exists(self._temp_file_path):
            with contextlib.suppress(OSError):
                os.unlink(self._temp_file_path)

    def _build_kubeseal_cmd(self, extra_args: list[str] | None = None) -> list[str]:
        """Build a kubeseal command with common flags.

        Constructs the base kubeseal command with appropriate flags for either
        detached mode (using certificate) or connected mode (using controller info).

        Args:
            extra_args: Additional arguments to append to the command.

        Returns:
            List of command arguments ready for subprocess execution.

        """
        cmd: list[str] = [self.binary, _FORMAT_YAML]

        if self.detached_mode:
            cmd.append(f"--cert={self.certificate}")
        else:
            cmd.extend([
                f"--context={self.current_context_name}",
                f"--controller-namespace={self.controller_namespace}",
                f"--controller-name={self.controller_name}",
            ])

        if extra_args:
            cmd.extend(extra_args)

        return cmd

    def _find_sealed_secrets(self, src: str) -> list[Path]:
        """Find all SealedSecret files in a directory.

        Args:
            src: Path to the directory to search.

        Returns:
            List of paths to SealedSecret YAML files.

        """
        secrets: list[Path] = []
        for path in Path(src).rglob("*.yaml"):
            try:
                secret = self.parse_existing_secret(str(path.absolute()))
                if secret is not None and secret["kind"] == "SealedSecret":
                    secrets.append(path.absolute())
            except (KeyError, SecretParsingError):
                # Not a SealedSecret or invalid file, skip
                continue
        return secrets

    def collect_parameters(self) -> dict[str, str]:
        """Interactively collect parameters for creating a new secret.

        Returns:
            Dictionary with 'namespace', 'type', and 'name' keys.

        """
        if self.detached_mode:
            namespace = questionary.text(
                "Provide namespace for the new secret",
                validate=_validate_k8s_name,
                style=PROMPT_STYLE,
                qmark=QMARK,
            ).unsafe_ask()
        else:
            # Use autocomplete for namespace selection with type-ahead filtering
            namespace = questionary.autocomplete(
                "Select or type namespace (Tab to show options)",
                choices=self.namespaces_list,
                validate=_validate_k8s_name,
                style=PROMPT_STYLE,
                qmark=QMARK,
            ).unsafe_ask()
        secret_type = questionary.select(
            "Select secret type to create",
            choices=["generic", "tls", "docker-registry"],
            style=PROMPT_STYLE,
            pointer=POINTER,
            qmark=QMARK,
        ).unsafe_ask()
        secret_name = questionary.text(
            "Provide name for the new secret",
            validate=_validate_k8s_name,
            style=PROMPT_STYLE,
            qmark=QMARK,
        ).unsafe_ask()

        return {"namespace": namespace, "type": secret_type, "name": secret_name}

    def _prompt_literal_entry(self) -> str:
        """Prompt for a single literal key=value entry.

        Returns:
            The kubectl argument for the literal entry.

        """
        entry = questionary.text(
            "Enter key=value",
            validate=lambda x: True if "=" in x else "Must be in key=value format",
            style=PROMPT_STYLE,
            qmark=QMARK,
        ).unsafe_ask()
        console.success(f"Added literal: {console.highlight(entry.split('=')[0])}")
        return f"--from-literal={entry}"

    def _prompt_bulk_literals(self) -> list[str]:
        """Prompt for bulk literal entries (one per line).

        Returns:
            List of kubectl arguments for literal entries.

        """
        bulk_input = questionary.text(
            "Enter key=value pairs (one per line, Esc+Enter to finish)",
            multiline=True,
            style=PROMPT_STYLE,
            qmark=QMARK,
        ).unsafe_ask()

        entries = [
            f"--from-literal={line.strip()}"
            for line in bulk_input.splitlines()
            if line.strip() and "=" in line
        ]

        if entries:
            console.success(f"Added {console.highlight(str(len(entries)))} literal(s)")
        return entries

    def _prompt_file_entry(self) -> str:
        """Prompt for a file entry.

        Returns:
            The kubectl argument for the file entry.

        """
        entry = questionary.path(
            "Select file",
            style=PROMPT_STYLE,
            qmark=QMARK,
        ).unsafe_ask()
        console.success(f"Added file: {console.highlight(entry)}")
        return f"--from-file={entry}"

    def _collect_secret_entries(self) -> list[str]:
        """Interactively collect secret entries from user.

        Returns:
            List of kubectl arguments for all entries.

        """
        entries: list[str] = []

        while True:
            if entries:
                console.info(f"Current entries: {console.highlight(str(len(entries)))}")

            entry_type = questionary.select(
                "Add secret entry",
                choices=[
                    {"name": "📝 Literal (key=value)", "value": "literal"},
                    {"name": "📝 Bulk literals (one per line)", "value": "bulk"},
                    {"name": "📁 From file", "value": "file"},
                    {"name": "✓ Done adding entries", "value": "done", "disabled": not entries},
                ],
                style=PROMPT_STYLE,
                pointer=POINTER,
                qmark=QMARK,
            ).unsafe_ask()

            if entry_type == "done":
                break
            if entry_type == "literal":
                entries.append(self._prompt_literal_entry())
            elif entry_type == "bulk":
                entries.extend(self._prompt_bulk_literals())
            else:
                entries.append(self._prompt_file_entry())

        return entries

    def create_generic_secret(self, secret_params: dict[str, str]) -> None:
        """Generate a temporary generic secret YAML file from user-provided entries.

        Prompts user for key=value pairs (literals) or filenames. Each entry
        is processed and passed to kubectl to create a secret.

        Args:
            secret_params: Dictionary containing 'name' and 'namespace' keys.

        """
        entries = self._collect_secret_entries()

        ic(entries)
        console.step("Generating temporary generic secret yaml file")

        cmd: list[str] = [
            "kubectl",
            "create",
            "secret",
            "generic",
            secret_params["name"],
            "--namespace",
            secret_params["namespace"],
            _DRY_RUN_CLIENT,
            "-o",
            "yaml",
            *entries,
        ]

        ic(cmd)

        with open(self._temp_file_path, "w") as f:
            subprocess.run(cmd, stdout=f, check=True)

    def create_tls_secret(self, secret_params: dict[str, str]) -> None:
        """Generate a temporary TLS secret YAML file.

        Expects tls.key and tls.crt files to exist in the current directory.

        Args:
            secret_params: Dictionary containing 'name' and 'namespace' keys.

        """
        console.step("Generating temporary TLS secret yaml file")
        cmd: list[str] = [
            "kubectl",
            "create",
            "secret",
            "tls",
            secret_params["name"],
            "--namespace",
            secret_params["namespace"],
            "--key",
            "tls.key",
            "--cert",
            "tls.crt",
            _DRY_RUN_CLIENT,
            "-o",
            "yaml",
        ]
        ic(cmd)

        with open(self._temp_file_path, "w") as f:
            subprocess.run(cmd, stdout=f, check=True)

    def create_regcred_secret(self, secret_params: dict[str, str]) -> None:
        """Generate a temporary docker-registry secret YAML file.

        Prompts user for Docker registry credentials.

        Args:
            secret_params: Dictionary containing 'name' and 'namespace' keys.

        """
        console.step("Generating temporary docker-registry secret yaml file")

        docker_server = questionary.text(
            "Provide docker-server",
            style=PROMPT_STYLE,
            qmark=QMARK,
        ).unsafe_ask()
        docker_username = questionary.text(
            "Provide docker-username",
            style=PROMPT_STYLE,
            qmark=QMARK,
        ).unsafe_ask()
        docker_password = questionary.password(
            "Provide docker-password",
            style=PROMPT_STYLE,
            qmark=QMARK,
        ).unsafe_ask()

        cmd: list[str] = [
            "kubectl",
            "create",
            "secret",
            "docker-registry",
            secret_params["name"],
            "--namespace",
            secret_params["namespace"],
            f"--docker-server={docker_server}",
            f"--docker-username={docker_username}",
            f"--docker-password={docker_password}",
            _DRY_RUN_CLIENT,
            "-o",
            "yaml",
        ]
        # Don't log cmd as it contains sensitive docker credentials

        with open(self._temp_file_path, "w") as f:
            subprocess.run(cmd, stdout=f, check=True)

    def seal(self, secret_params: dict[str, str]) -> None:
        """Seal a secret using kubeseal.

        Reads the temporary secret file and outputs a sealed secret YAML file.

        Args:
            secret_params: Dictionary containing 'name', 'namespace', and 'type' keys.

        """
        console.step("Sealing secret")

        cmd = self._build_kubeseal_cmd()
        ic(cmd)

        output_file = f"{secret_params['name']}.yaml"

        with console.spinner("Sealing secret with kubeseal..."):
            with open(self._temp_file_path) as stdin_f, open(output_file, "w") as stdout_f:
                subprocess.run(cmd, stdin=stdin_f, stdout=stdout_f, check=True)
            self.append_argo_annotation(filename=output_file)

        console.newline()
        console.summary_panel(
            "Sealed Secret Created",
            {
                "Name": secret_params["name"],
                "Namespace": secret_params["namespace"],
                "Type": secret_params["type"],
                "Output": output_file,
            },
        )

    @staticmethod
    def parse_existing_secret(secret_name: str) -> dict[str, Any] | None:
        """Parse a YAML secret file.

        Args:
            secret_name: Path to the secret file.

        Returns:
            The parsed YAML document as a dictionary, or None if empty.

        Raises:
            SecretParsingError: If the file does not exist, contains multiple
                documents, or contains malformed/invalid YAML.

        """
        try:
            with open(secret_name) as stream:
                docs = [doc for doc in yaml.safe_load_all(stream) if doc is not None]
                if len(docs) > 1:
                    raise SecretParsingError(
                        f"File '{secret_name}' contains multiple YAML documents. "
                        "Only single document files are supported."
                    )
                return docs[0] if docs else None
        except FileNotFoundError as err:
            raise SecretParsingError(f"Secret file '{secret_name}' does not exist") from err
        except yaml.YAMLError as err:
            raise SecretParsingError(f"Secret file '{secret_name}' contains malformed YAML: {err}") from err

    def merge(self, secret_name: str) -> None:
        """Merge new secret entries into an existing sealed secret file.

        Args:
            secret_name: Path to the existing sealed secret file to update.

        """
        console.action(f"Updating {console.highlight(secret_name)}")
        cmd = self._build_kubeseal_cmd(extra_args=["--merge-into", secret_name])
        ic(cmd)

        with open(self._temp_file_path) as stdin_f:
            subprocess.run(cmd, stdin=stdin_f, check=True)

        self.append_argo_annotation(filename=secret_name)
        console.success("Done")

    def append_argo_annotation(self, filename: str) -> None:
        """Append ArgoCD sync annotations to a sealed secret file.

        This allows ArgoCD to process repositories with SealedSecrets
        before the controller is deployed in the cluster.

        Args:
            filename: Path to the sealed secret YAML file.

        """
        secret = self.parse_existing_secret(filename)
        if secret is None:
            return

        console.step("Appending ArgoCD annotations")

        annotations: dict[str, str] = secret["metadata"].setdefault("annotations", {})

        sync_key = "argocd.argoproj.io/sync-options"
        skip_option_value = "SkipDryRunOnMissingResource=true"

        current_sync_options_str = annotations.get(sync_key, "")

        # Split, strip whitespace from each option, and filter out any empty strings
        # that might arise from consecutive commas or leading/trailing commas.
        options_list = [opt.strip() for opt in current_sync_options_str.split(",") if opt.strip()]

        # Filter out any pre-existing "SkipDryRunOnMissingResource=" option
        # to ensure we don't duplicate it or have conflicting values.
        filtered_options = [opt for opt in options_list if not opt.startswith("SkipDryRunOnMissingResource=")]

        # Add the desired option to the beginning of the list.
        final_options = [skip_option_value, *filtered_options]

        annotations[sync_key] = ",".join(final_options)

        with open(filename, "w") as stream:
            yaml.safe_dump(secret, stream)

    def fetch_certificate(self) -> None:
        """Download the kubeseal encryption certificate from the cluster.

        This certificate can be used in the future to encrypt secrets
        without direct access to the cluster (detached mode).

        Raises:
            click.ClickException: If called in detached mode.

        """
        if self.cluster is None:
            raise click.ClickException("Fetching certificate is not available in detached mode")

        console.action("Downloading certificate for kubeseal...")
        cmd: list[str] = [
            self.binary,
            "--controller-namespace",
            self.controller_namespace,
            f"--context={self.current_context_name}",
            "--controller-name",
            self.controller_name,
            "--fetch-cert",
        ]
        ic(cmd)

        output_file = f"{self.current_context_name}-kubeseal-cert.crt"
        with open(output_file, "w") as f:
            subprocess.run(cmd, stdout=f, check=True)

        console.success(f"Saved to {console.highlight(output_file)}")

    def reencrypt(self, src: str) -> None:
        """Re-encrypt existing SealedSecret files using the newest encryption certificate.

        Args:
            src: Path to the directory containing SealedSecret files.

        """
        secrets = self._find_sealed_secrets(src)
        if not secrets:
            console.warning("No SealedSecret files found")
            return

        with console.create_task_progress() as progress:
            task = progress.add_task("Re-encrypting secrets", total=len(secrets))
            for secret in secrets:
                backup_file = f"{secret}_backup"
                output_tmp = f"{secret}_new"

                # Create backup of original file
                shutil.copy2(secret, backup_file)

                cmd = self._build_kubeseal_cmd(extra_args=["--re-encrypt"])
                ic(cmd)

                try:
                    with open(str(secret)) as stdin_f, open(output_tmp, "w") as stdout_f:
                        subprocess.run(cmd, stdin=stdin_f, stdout=stdout_f, check=True)
                    # Atomic replace on success
                    os.replace(output_tmp, str(secret))
                    os.remove(backup_file)
                except subprocess.CalledProcessError:
                    # Restore from backup on failure
                    if os.path.exists(backup_file):
                        os.replace(backup_file, str(secret))
                    if os.path.exists(output_tmp):
                        os.remove(output_tmp)
                    raise

                self.append_argo_annotation(str(secret))
                progress.update(task, advance=1)

    def backup(self) -> None:
        """Create a backup of the latest SealedSecret controller's encryption secret."""
        if self.cluster is None:
            raise click.ClickException("Backup is not available in detached mode")

        secret = self.cluster.find_latest_sealed_secrets_controller_certificate()
        cmd: list[str] = ["kubectl", "get", "secret", "-n", self.controller_namespace, secret, "-o", "yaml"]
        ic(cmd)

        output_file = f"{self.current_context_name}-secret-backup.yaml"
        with open(output_file, "w") as f:
            subprocess.run(cmd, stdout=f, check=True)
