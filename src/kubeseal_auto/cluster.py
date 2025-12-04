"""Kubernetes cluster interaction utilities.

This module provides the Cluster class for interacting with Kubernetes
clusters, finding SealedSecrets controllers, and managing namespaces.
"""

from typing import Any

import click
import questionary
from colorama import Fore
from icecream import ic
from kubernetes import client, config

from kubeseal_auto.exceptions import ControllerNotFoundError
from kubeseal_auto.host import Host


class Cluster:
    """Manages Kubernetes cluster interactions for sealed-secrets operations.

    This class handles cluster context selection, controller discovery,
    and namespace management.

    Attributes:
        context: The active Kubernetes context name.
        host: Host instance for binary management.
        controller: Dictionary containing controller metadata (name, namespace, version).
    """

    def __init__(self, select_context: bool) -> None:
        """Initialize Cluster with context selection.

        Args:
            select_context: If True, prompt user to select a context.
                           If False, use the current context.
        """
        self.context: str = self._set_context(select_context=select_context)
        config.load_kube_config(context=self.context)
        self.host: Host = Host()
        self.controller: dict[str, str] = self._find_sealed_secrets_controller()

    @staticmethod
    def _set_context(select_context: bool) -> str:
        """Set the Kubernetes context to use.

        Args:
            select_context: If True, prompt user to select a context.

        Returns:
            The selected or current context name.
        """
        contexts, current_context = config.list_kube_config_contexts()
        if select_context:
            context_names: list[str] = [context["name"] for context in contexts]
            context: str = questionary.select("Select context to work with", choices=context_names).ask()
        else:
            context = str(current_context["name"])
        click.echo(f"===> Working with [{Fore.CYAN}{context}{Fore.RESET}] cluster")
        return context

    @staticmethod
    def get_all_namespaces() -> list[str]:
        """Get all namespaces in the cluster.

        Returns:
            List of namespace names.
        """
        ns_list: list[str] = []

        for ns in client.CoreV1Api().list_namespace().items:
            ns_list.append(ns.metadata.name)
        ic(ns_list)

        return ns_list

    @staticmethod
    def _find_sealed_secrets_controller() -> dict[str, str]:
        """Find the SealedSecrets controller in the cluster.

        Searches for services with the 'app.kubernetes.io/name=sealed-secrets' label.

        Returns:
            Dictionary with controller 'name', 'namespace', and 'version'.

        Raises:
            ControllerNotFoundError: If no SealedSecrets controller is found.
        """
        click.echo("===> Searching for SealedSecrets controller service...")

        core_v1_api = client.CoreV1Api()

        found_services: list[Any] = core_v1_api.list_service_for_all_namespaces(
            label_selector="app.kubernetes.io/name=sealed-secrets"
        ).items

        # Further filter out metrics services
        found_services = [svc for svc in found_services if "metrics" not in svc.metadata.name]

        if not found_services:
            click.echo("===> No controller found")
            raise ControllerNotFoundError("SealedSecrets controller not found in the cluster")

        service = found_services[0]
        version: str = service.metadata.labels.get("app.kubernetes.io/version", "")

        if len(found_services) > 1:
            click.echo(
                f"===> Warning: Multiple services found. Using [{Fore.YELLOW}{service.metadata.name}{Fore.RESET}] "
                f"in [{Fore.YELLOW}{service.metadata.namespace}{Fore.RESET}]."
            )

        click.echo(
            "===> Found the following controller: "
            f"[{Fore.CYAN}{service.metadata.namespace}/{service.metadata.name}{Fore.RESET}]\n"
            "===> Controller version: "
            f"[{Fore.CYAN}{version}{Fore.RESET}]"
        )

        return {
            "name": service.metadata.name,
            "namespace": service.metadata.namespace,
            "version": version,
        }

    def find_latest_sealed_secrets_controller_certificate(self) -> str:
        """Find the latest TLS certificate secret for the controller.

        Returns:
            The name of the latest sealed-secrets TLS certificate secret.
        """
        res = client.CoreV1Api().list_namespaced_secret(self.controller.get("namespace"))
        secrets: list[dict[str, Any]] = []
        for secret in res.items:
            if "sealed-secrets" in secret.metadata.name and secret.type == "kubernetes.io/tls":
                secrets.append({"name": secret.metadata.name, "timestamp": secret.metadata.creation_timestamp})

        ic(secrets)

        if secrets:
            secrets.sort(key=lambda x: x["timestamp"])

        return str(secrets[-1]["name"])

    def ensure_kubeseal_version(self, version: str) -> None:
        """Ensure the kubeseal binary for the specified version is available.

        Args:
            version: The version of kubeseal to ensure.
        """
        self.host.ensure_kubeseal_binary(version=version)

    def get_controller_name(self) -> str:
        """Get the SealedSecrets controller name.

        Returns:
            The controller service name.
        """
        return self.controller["name"]

    def get_controller_namespace(self) -> str:
        """Get the SealedSecrets controller namespace.

        Returns:
            The namespace where the controller is deployed.
        """
        return self.controller["namespace"]

    def get_controller_version(self) -> str:
        """Get the SealedSecrets controller version.

        Returns:
            The controller version without the 'v' prefix.
        """
        return self.controller["version"].split("v")[-1]

    def get_context(self) -> str:
        """Get the current Kubernetes context name.

        Returns:
            The active context name.
        """
        return self.context
