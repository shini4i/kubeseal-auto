"""Kubeseal wrapper for creating and managing sealed secrets.

This module provides the Kubeseal class which wraps the kubeseal binary
to create, seal, and manage Kubernetes sealed secrets.
"""

import os
import shutil
import subprocess
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import click
import questionary
import yaml
from colorama import Fore
from icecream import ic

from kubeseal_auto.cluster import Cluster
from kubeseal_auto.exceptions import BinaryNotFoundError, SecretParsingError


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
        temp_file: Temporary file for intermediate secret storage.
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
            click.echo("===> Working in a detached mode")
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
                click.echo("==> Falling back to the default kubeseal binary")

        self.temp_file: Any = NamedTemporaryFile()

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
            namespace = questionary.text("Provide namespace for the new secret").unsafe_ask()
        else:
            namespace = questionary.select(
                "Select namespace for the new secret", choices=self.namespaces_list
            ).unsafe_ask()
        secret_type = questionary.select(
            "Select secret type to create", choices=["generic", "tls", "docker-registry"]
        ).unsafe_ask()
        secret_name = questionary.text("Provide name for the new secret").unsafe_ask()

        return {"namespace": namespace, "type": secret_type, "name": secret_name}

    def create_generic_secret(self, secret_params: dict[str, str]) -> None:
        """Generate a temporary generic secret YAML file from user-provided entries.

        Prompts user for key=value pairs (literals) or filenames. Each entry
        is processed and passed to kubectl to create a secret.

        Args:
            secret_params: Dictionary containing 'name' and 'namespace' keys.
        """
        click.echo(
            "===> Provide literal entry/entries one per line: "
            f"[{Fore.CYAN}literal{Fore.RESET}] key=value "
            f"[{Fore.CYAN}file{Fore.RESET}] filename"
        )

        secrets = questionary.text("Secret Entries one per line", multiline=True).unsafe_ask()
        ic(secrets)

        click.echo("===> Generating a temporary generic secret yaml file")

        cmd: list[str] = [
            "kubectl",
            "create",
            "secret",
            "generic",
            secret_params["name"],
            "--namespace",
            secret_params["namespace"],
            "--dry-run=client",
            "-o",
            "yaml",
        ]

        for secret in secrets.splitlines():
            secret = secret.strip()
            if not secret:
                continue
            if "=" in secret:
                cmd.append(f"--from-literal={secret}")
            else:
                cmd.append(f"--from-file={secret}")

        ic(cmd)

        with open(self.temp_file.name, "w") as f:
            subprocess.run(cmd, stdout=f, check=True)

    def create_tls_secret(self, secret_params: dict[str, str]) -> None:
        """Generate a temporary TLS secret YAML file.

        Expects tls.key and tls.crt files to exist in the current directory.

        Args:
            secret_params: Dictionary containing 'name' and 'namespace' keys.
        """
        click.echo("===> Generating a temporary tls secret yaml file")
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
            "--dry-run=client",
            "-o",
            "yaml",
        ]
        ic(cmd)

        with open(self.temp_file.name, "w") as f:
            subprocess.run(cmd, stdout=f, check=True)

    def create_regcred_secret(self, secret_params: dict[str, str]) -> None:
        """Generate a temporary docker-registry secret YAML file.

        Prompts user for Docker registry credentials.

        Args:
            secret_params: Dictionary containing 'name' and 'namespace' keys.
        """
        click.echo("===> Generating a temporary docker-registry secret yaml file")

        docker_server = questionary.text("Provide docker-server").unsafe_ask()
        docker_username = questionary.text("Provide docker-username").unsafe_ask()
        docker_password = questionary.password("Provide docker-password").unsafe_ask()

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
            "--dry-run=client",
            "-o",
            "yaml",
        ]
        # Don't log cmd as it contains sensitive docker credentials

        with open(self.temp_file.name, "w") as f:
            subprocess.run(cmd, stdout=f, check=True)

    def seal(self, secret_name: str) -> None:
        """Seal a secret using kubeseal.

        Reads the temporary secret file and outputs a sealed secret YAML file.

        Args:
            secret_name: Name for the output sealed secret file (without .yaml extension).
        """
        click.echo("===> Sealing generated secret file")
        if self.detached_mode:
            cmd: list[str] = [self.binary, "--format=yaml", f"--cert={self.certificate}"]
        else:
            cmd = [
                self.binary,
                "--format=yaml",
                f"--context={self.current_context_name}",
                f"--controller-namespace={self.controller_namespace}",
                f"--controller-name={self.controller_name}",
            ]
        ic(cmd)

        output_file = f"{secret_name}.yaml"
        with open(self.temp_file.name) as stdin_f, open(output_file, "w") as stdout_f:
            subprocess.run(cmd, stdin=stdin_f, stdout=stdout_f, check=True)

        self.append_argo_annotation(filename=output_file)
        click.echo("===> Done")

    @staticmethod
    def parse_existing_secret(secret_name: str) -> dict[str, Any] | None:
        """Parse a YAML secret file.

        Args:
            secret_name: Path to the secret file.

        Returns:
            The parsed YAML document as a dictionary, or None if empty.

        Raises:
            SecretParsingError: If the file does not exist or contains multiple documents.
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

    def merge(self, secret_name: str) -> None:
        """Merge new secret entries into an existing sealed secret file.

        Args:
            secret_name: Path to the existing sealed secret file to update.
        """
        click.echo(f"===> Updating {secret_name}")
        if self.detached_mode:
            cmd: list[str] = [self.binary, "--format=yaml", "--merge-into", secret_name, f"--cert={self.certificate}"]
        else:
            cmd = [
                self.binary,
                "--format=yaml",
                "--merge-into",
                secret_name,
                f"--context={self.current_context_name}",
                f"--controller-namespace={self.controller_namespace}",
                f"--controller-name={self.controller_name}",
            ]
        ic(cmd)

        with open(self.temp_file.name) as stdin_f:
            subprocess.run(cmd, stdin=stdin_f, check=True)

        self.append_argo_annotation(filename=secret_name)
        click.echo("===> Done")

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

        click.echo("===> Appending ArgoCD related annotations")

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
        """
        click.echo("===> Downloading certificate for kubeseal...")
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

        click.echo(f"===> Saved to {Fore.CYAN}{output_file}")

    def reencrypt(self, src: str) -> None:
        """Re-encrypt existing SealedSecret files using the newest encryption certificate.

        Args:
            src: Path to the directory containing SealedSecret files.
        """
        for secret in self._find_sealed_secrets(src):
            click.echo(f"Re-encrypting {secret}")
            backup_file = f"{secret}_backup"
            output_tmp = f"{secret}_new"

            # Create backup of original file
            shutil.copy2(secret, backup_file)

            cmd: list[str] = [
                self.binary,
                "--format=yaml",
                f"--context={self.current_context_name}",
                "--controller-namespace",
                self.controller_namespace,
                "--controller-name",
                self.controller_name,
                "--re-encrypt",
            ]
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
