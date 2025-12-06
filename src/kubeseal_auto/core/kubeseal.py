"""Kubeseal facade class.

This module provides the Kubeseal class which serves as the main entry point
for all sealed secrets operations, coordinating between the various
specialized modules.
"""

import contextlib
import shutil
from pathlib import Path
from tempfile import NamedTemporaryFile

import click

from kubeseal_auto import console
from kubeseal_auto.core.cluster import Cluster
from kubeseal_auto.exceptions import BinaryNotFoundError
from kubeseal_auto.models import SecretParams
from kubeseal_auto.secrets.creation import (
    create_generic_secret,
    create_regcred_secret,
    create_tls_secret,
)
from kubeseal_auto.secrets.parsing import parse_secret_file
from kubeseal_auto.secrets.prompts import collect_secret_parameters
from kubeseal_auto.secrets.sealing import (
    backup_controller_secret,
    fetch_certificate,
    merge_secret,
    reencrypt_secrets,
    seal_secret,
)

# CLI flag constant for kubeseal commands
_FORMAT_YAML = "--format=yaml"


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

    """

    def __init__(self, *, select_context: bool, certificate: str | None = None) -> None:
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
            self.controller_name = self.cluster.controller_name
            self.controller_namespace = self.cluster.controller_namespace
            self.current_context_name = self.cluster.context
            self.namespaces_list = self.cluster.get_all_namespaces()

            try:
                version = self.cluster.controller_version
                if version:
                    self.cluster.ensure_kubeseal_version(version)
                    self.binary = self.cluster.get_kubeseal_binary_path(version)
                else:
                    console.warning("Controller version label not found")
                    self._fallback_to_system_binary()
            except (BinaryNotFoundError, ValueError) as exc:
                console.warning(
                    f"Failed to resolve controller version ({exc}); falling back to system kubeseal binary",
                )
                self._fallback_to_system_binary()

        # Create temp file with delete=False for Windows compatibility
        # Close immediately to avoid file locking issues when reopening
        temp_file = NamedTemporaryFile(delete=False)
        self._temp_file_path: Path = Path(temp_file.name)
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

    def __repr__(self) -> str:
        """Return a detailed string representation for debugging."""
        if self.detached_mode:
            return f"Kubeseal(detached_mode=True, certificate={self.certificate!r})"
        return f"Kubeseal(context={self.current_context_name!r}, controller={self.controller_name!r})"

    def __del__(self) -> None:
        """Ensure temp file cleanup if context manager wasn't used."""
        self._cleanup_temp_file()

    def _cleanup_temp_file(self) -> None:
        """Remove the temporary file if it exists."""
        if hasattr(self, "_temp_file_path"):
            with contextlib.suppress(OSError):
                self._temp_file_path.unlink(missing_ok=True)

    def _fallback_to_system_binary(self) -> None:
        """Fall back to system-installed kubeseal binary.

        Raises:
            BinaryNotFoundError: If kubeseal is not found in PATH.

        """
        system_binary = shutil.which("kubeseal")
        if system_binary is None:
            raise BinaryNotFoundError(
                "kubeseal binary not found. Please install kubeseal or ensure it's in your PATH. "
                "See: https://github.com/bitnami-labs/sealed-secrets#installation"
            )
        console.warning("Falling back to the default kubeseal binary")
        self.binary = system_binary

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
            cmd.extend(
                [
                    f"--context={self.current_context_name}",
                    f"--controller-namespace={self.controller_namespace}",
                    f"--controller-name={self.controller_name}",
                ]
            )

        if extra_args:
            cmd.extend(extra_args)

        return cmd

    def collect_parameters(self) -> SecretParams:
        """Interactively collect parameters for creating a new secret.

        Returns:
            SecretParams with namespace, secret_type, and name.

        """
        return collect_secret_parameters(
            namespaces=self.namespaces_list,
            detached_mode=self.detached_mode,
        )

    def create_generic_secret(self, secret_params: SecretParams) -> None:
        """Generate a temporary generic secret YAML file from user-provided entries.

        Args:
            secret_params: SecretParams containing name and namespace.

        """
        create_generic_secret(secret_params, self._temp_file_path)

    def create_tls_secret(self, secret_params: SecretParams) -> None:
        """Generate a temporary TLS secret YAML file.

        Args:
            secret_params: SecretParams containing name and namespace.

        """
        create_tls_secret(secret_params, self._temp_file_path)

    def create_regcred_secret(self, secret_params: SecretParams) -> None:
        """Generate a temporary docker-registry secret YAML file.

        Args:
            secret_params: SecretParams containing name and namespace.

        """
        create_regcred_secret(secret_params, self._temp_file_path)

    def seal(self, secret_params: SecretParams) -> None:
        """Seal a secret using kubeseal.

        Args:
            secret_params: SecretParams containing name, namespace, and secret_type.

        """
        seal_secret(
            secret_params=secret_params,
            temp_file_path=self._temp_file_path,
            kubeseal_cmd=self._build_kubeseal_cmd(),
        )

    def merge(self, secret_name: str) -> None:
        """Merge new secret entries into an existing sealed secret file.

        Args:
            secret_name: Path to the existing sealed secret file to update.

        """
        merge_secret(
            secret_name=secret_name,
            temp_file_path=self._temp_file_path,
            kubeseal_cmd=self._build_kubeseal_cmd(),
        )

    def reencrypt(self, src: str) -> None:
        """Re-encrypt existing SealedSecret files using the newest encryption certificate.

        Args:
            src: Path to the directory containing SealedSecret files.

        """
        reencrypt_secrets(src=src, kubeseal_cmd=self._build_kubeseal_cmd())

    def fetch_certificate(self) -> None:
        """Download the kubeseal encryption certificate from the cluster.

        Raises:
            click.ClickException: If called in detached mode.

        """
        if self.cluster is None:
            raise click.ClickException("Fetching certificate is not available in detached mode")

        fetch_certificate(
            binary=self.binary,
            controller_namespace=self.controller_namespace,
            controller_name=self.controller_name,
            context_name=self.current_context_name,
        )

    def backup(self) -> None:
        """Create a backup of the latest SealedSecret controller's encryption secret.

        Raises:
            click.ClickException: If called in detached mode.

        """
        if self.cluster is None:
            raise click.ClickException("Backup is not available in detached mode")

        secret = self.cluster.find_latest_sealed_secrets_controller_certificate()
        backup_controller_secret(
            controller_namespace=self.controller_namespace,
            secret_name=secret,
            context_name=self.current_context_name,
        )

    @staticmethod
    def parse_existing_secret(secret_name: str) -> dict | None:
        """Parse a YAML secret file.

        Args:
            secret_name: Path to the secret file.

        Returns:
            The parsed YAML document as a dictionary, or None if empty.

        """
        return parse_secret_file(secret_name)
