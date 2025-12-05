"""Kubernetes cluster interaction utilities.

This module provides the Cluster class for interacting with Kubernetes
clusters, finding SealedSecrets controllers, and managing namespaces.
"""

from typing import Any

import click
import questionary
from icecream import ic
from kubernetes import client, config
from kubernetes.config.config_exception import ConfigException
from urllib3.exceptions import MaxRetryError

from kubeseal_auto import console
from kubeseal_auto.exceptions import ClusterConnectionError, ControllerNotFoundError
from kubeseal_auto.host import Host, normalize_version
from kubeseal_auto.models import ControllerInfo
from kubeseal_auto.styles import POINTER, PROMPT_STYLE, QMARK


class Cluster:
    """Manages Kubernetes cluster interactions for sealed-secrets operations.

    This class handles cluster context selection, controller discovery,
    and namespace management.

    Attributes:
        context: The active Kubernetes context name.
        host: Host instance for binary management.
        controller: ControllerInfo containing controller metadata.

    """

    def __init__(self, *, select_context: bool) -> None:
        """Initialize Cluster with context selection.

        Args:
            select_context: If True, prompt user to select a context.
                           If False, use the current context.
                           Must be passed as a keyword argument.

        """
        self.context: str = self._set_context(select_context=select_context)
        config.load_kube_config(context=self.context)
        self.host: Host = Host()
        self.controller: ControllerInfo = self._find_sealed_secrets_controller()

    @staticmethod
    def _set_context(*, select_context: bool) -> str:
        """Set the Kubernetes context to use.

        Args:
            select_context: If True, prompt user to select a context.
                           Must be passed as a keyword argument.

        Returns:
            The selected or current context name.

        Raises:
            ClusterConnectionError: If kubeconfig is invalid or missing.
            click.Abort: If user cancels context selection.

        """
        try:
            contexts, current_context = config.list_kube_config_contexts()
        except ConfigException as e:
            raise ClusterConnectionError(f"Invalid or missing kubeconfig: {e}") from e
        if select_context:
            context_names: list[str] = [context["name"] for context in contexts]
            context: str | None = questionary.select(
                "Select context to work with",
                choices=context_names,
                style=PROMPT_STYLE,
                pointer=POINTER,
                qmark=QMARK,
            ).ask()
            if context is None:
                console.warning("Context selection cancelled.")
                raise click.Abort()
        else:
            context = str(current_context["name"])
        console.action(f"Working with {console.highlight(context)} cluster")
        return context

    @staticmethod
    def get_all_namespaces() -> list[str]:
        """Get all namespaces in the cluster.

        Returns:
            List of namespace names.

        """
        ns_list = [ns.metadata.name for ns in client.CoreV1Api().list_namespace().items]
        ic(ns_list)

        return ns_list

    @staticmethod
    def _find_sealed_secrets_controller() -> ControllerInfo:
        """Find the SealedSecrets controller in the cluster.

        Searches for services with the 'app.kubernetes.io/name=sealed-secrets' label.

        Returns:
            ControllerInfo with controller name, namespace, and version.

        Raises:
            ClusterConnectionError: If the cluster is unreachable.
            ControllerNotFoundError: If no SealedSecrets controller is found.

        """
        with console.spinner("Searching for SealedSecrets controller..."):
            core_v1_api = client.CoreV1Api()

            try:
                found_services: list[Any] = core_v1_api.list_service_for_all_namespaces(
                    label_selector="app.kubernetes.io/name=sealed-secrets"
                ).items
            except MaxRetryError as e:
                raise ClusterConnectionError(
                    f"Failed to connect to the Kubernetes cluster: {e.reason}"
                ) from e

            # Further filter out metrics services
            found_services = [svc for svc in found_services if "metrics" not in svc.metadata.name]

        if not found_services:
            console.error("No controller found")
            raise ControllerNotFoundError("SealedSecrets controller not found in the cluster")

        service = found_services[0]
        version: str = service.metadata.labels.get("app.kubernetes.io/version", "")

        if len(found_services) > 1:
            console.warning(
                f"Multiple services found. Using [yellow]{service.metadata.name}[/yellow] "
                f"in [yellow]{service.metadata.namespace}[/yellow]."
            )

        console.success(
            f"Found controller: {console.highlight(f'{service.metadata.namespace}/{service.metadata.name}')}"
        )
        console.info(f"Controller version: {console.highlight(version)}")

        return ControllerInfo(
            name=service.metadata.name,
            namespace=service.metadata.namespace,
            version=version,
        )

    def find_latest_sealed_secrets_controller_certificate(self) -> str:
        """Find the latest TLS certificate secret for the controller.

        Returns:
            The name of the latest sealed-secrets TLS certificate secret.

        """
        res = client.CoreV1Api().list_namespaced_secret(self.controller.namespace)
        secrets: list[dict[str, Any]] = []
        for secret in res.items:
            if "sealed-secrets" in secret.metadata.name and secret.type == "kubernetes.io/tls":
                secrets.append({"name": secret.metadata.name, "timestamp": secret.metadata.creation_timestamp})

        ic(secrets)

        if not secrets:
            raise ControllerNotFoundError("No sealed-secrets TLS certificates found in the cluster")

        secrets.sort(key=lambda x: x["timestamp"])
        return str(secrets[-1]["name"])

    def ensure_kubeseal_version(self, version: str) -> None:
        """Ensure the kubeseal binary for the specified version is available.

        Args:
            version: The version of kubeseal to ensure.

        """
        self.host.ensure_kubeseal_binary(version=version)

    def get_kubeseal_binary_path(self, version: str) -> str:
        """Get the path to the kubeseal binary for the specified version.

        Args:
            version: The version of kubeseal.

        Returns:
            The full path to the kubeseal binary as a string.

        """
        return str(self.host.get_binary_path(version=version))

    @property
    def controller_name(self) -> str:
        """The SealedSecrets controller name."""
        return self.controller.name

    @property
    def controller_namespace(self) -> str:
        """The namespace where the controller is deployed."""
        return self.controller.namespace

    @property
    def controller_version(self) -> str:
        """The controller version without the 'v' prefix.

        Returns:
            The normalized version string, or an empty string if the
            controller lacks the app.kubernetes.io/version label.

        Raises:
            ValueError: If the version is present but has an invalid format.

        """
        if not self.controller.version:
            return ""
        return normalize_version(self.controller.version)

    def __repr__(self) -> str:
        """Return a detailed string representation for debugging."""
        return (
            f"Cluster(context={self.context!r}, "
            f"controller={self.controller!r})"
        )
