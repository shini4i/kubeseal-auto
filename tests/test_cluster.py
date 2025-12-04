"""Tests for cluster.py module."""

from unittest.mock import MagicMock, patch

import pytest

from kubeseal_auto.cluster import Cluster
from kubeseal_auto.exceptions import ControllerNotFoundError


class TestClusterContextSelection:
    """Tests for context selection functionality."""

    def test_set_context_without_selection(self, mock_kube_contexts, mock_kube_config):
        """Test using current context without selection."""
        with patch.object(Cluster, "_find_sealed_secrets_controller") as mock_controller, patch.object(
            Cluster, "get_all_namespaces"
        ):
            mock_controller.return_value = {
                "name": "sealed-secrets",
                "namespace": "kube-system",
                "version": "v0.26.0",
            }

            cluster = Cluster(select_context=False)

            assert cluster.context == "test-context"

    def test_set_context_with_selection(self, mock_kube_config):
        """Test prompting user for context selection."""
        with (
            patch("kubernetes.config.list_kube_config_contexts") as mock_contexts,
            patch("questionary.select") as mock_select,
            patch.object(Cluster, "_find_sealed_secrets_controller") as mock_controller,
            patch.object(Cluster, "get_all_namespaces"),
        ):
            mock_contexts.return_value = (
                [{"name": "context1"}, {"name": "context2"}, {"name": "context3"}],
                {"name": "context1"},
            )
            mock_select.return_value.ask.return_value = "context2"
            mock_controller.return_value = {
                "name": "sealed-secrets",
                "namespace": "kube-system",
                "version": "v0.26.0",
            }

            cluster = Cluster(select_context=True)

            assert cluster.context == "context2"
            mock_select.assert_called_once()


class TestClusterControllerDiscovery:
    """Tests for SealedSecrets controller discovery."""

    def test_find_controller_success(self, mock_kube_contexts, mock_kube_config):
        """Test successfully finding a controller."""
        with patch("kubernetes.client.CoreV1Api") as mock_api:
            api_instance = MagicMock()
            mock_api.return_value = api_instance

            # Mock service
            service = MagicMock()
            service.metadata.name = "sealed-secrets-controller"
            service.metadata.namespace = "kube-system"
            service.metadata.labels = {"app.kubernetes.io/version": "v0.26.0"}
            api_instance.list_service_for_all_namespaces.return_value.items = [service]
            api_instance.list_namespace.return_value.items = []

            cluster = Cluster(select_context=False)

            assert cluster.controller["name"] == "sealed-secrets-controller"
            assert cluster.controller["namespace"] == "kube-system"
            assert cluster.controller["version"] == "v0.26.0"

    def test_find_controller_not_found(self, mock_kube_contexts, mock_kube_config):
        """Test error when controller is not found."""
        with patch("kubernetes.client.CoreV1Api") as mock_api:
            api_instance = MagicMock()
            mock_api.return_value = api_instance
            api_instance.list_service_for_all_namespaces.return_value.items = []

            with pytest.raises(ControllerNotFoundError) as exc_info:
                Cluster(select_context=False)

            assert "not found" in str(exc_info.value)

    def test_find_controller_filters_metrics(self, mock_kube_contexts, mock_kube_config):
        """Test that metrics services are filtered out."""
        with patch("kubernetes.client.CoreV1Api") as mock_api:
            api_instance = MagicMock()
            mock_api.return_value = api_instance

            # Create services - one metrics, one controller
            metrics_service = MagicMock()
            metrics_service.metadata.name = "sealed-secrets-metrics"
            metrics_service.metadata.namespace = "kube-system"
            metrics_service.metadata.labels = {"app.kubernetes.io/version": "v0.26.0"}

            controller_service = MagicMock()
            controller_service.metadata.name = "sealed-secrets-controller"
            controller_service.metadata.namespace = "kube-system"
            controller_service.metadata.labels = {"app.kubernetes.io/version": "v0.26.0"}

            api_instance.list_service_for_all_namespaces.return_value.items = [metrics_service, controller_service]
            api_instance.list_namespace.return_value.items = []

            cluster = Cluster(select_context=False)

            # Should select the controller, not the metrics service
            assert cluster.controller["name"] == "sealed-secrets-controller"


class TestClusterNamespaces:
    """Tests for namespace operations."""

    def test_get_all_namespaces(self, mock_kube_contexts, mock_kube_config, mock_controller):
        """Test retrieving all namespaces."""
        with patch("kubernetes.client.CoreV1Api") as mock_api:
            api_instance = MagicMock()
            mock_api.return_value = api_instance

            ns1 = MagicMock()
            ns1.metadata.name = "default"
            ns2 = MagicMock()
            ns2.metadata.name = "kube-system"
            ns3 = MagicMock()
            ns3.metadata.name = "monitoring"

            api_instance.list_namespace.return_value.items = [ns1, ns2, ns3]

            namespaces = Cluster.get_all_namespaces()

            assert "default" in namespaces
            assert "kube-system" in namespaces
            assert "monitoring" in namespaces
            assert len(namespaces) == 3


class TestClusterGetters:
    """Tests for getter methods."""

    def test_get_controller_name(self, mock_kube_contexts, mock_kube_config, mock_controller, mock_namespaces):
        """Test getting controller name."""
        cluster = Cluster(select_context=False)
        assert cluster.get_controller_name() == "sealed-secrets-controller"

    def test_get_controller_namespace(self, mock_kube_contexts, mock_kube_config, mock_controller, mock_namespaces):
        """Test getting controller namespace."""
        cluster = Cluster(select_context=False)
        assert cluster.get_controller_namespace() == "kube-system"

    def test_get_controller_version(self, mock_kube_contexts, mock_kube_config, mock_controller, mock_namespaces):
        """Test getting controller version."""
        cluster = Cluster(select_context=False)
        # Version is "v0.26.0", split removes "v" prefix
        assert cluster.get_controller_version() == "0.26.0"

    def test_get_context(self, mock_kube_contexts, mock_kube_config, mock_controller, mock_namespaces):
        """Test getting current context."""
        cluster = Cluster(select_context=False)
        assert cluster.get_context() == "test-context"


class TestClusterCertificateDiscovery:
    """Tests for certificate discovery."""

    def test_find_latest_certificate(self, mock_kube_contexts, mock_kube_config, mock_controller, mock_namespaces):
        """Test finding the latest controller certificate."""
        cluster = Cluster(select_context=False)

        with patch("kubernetes.client.CoreV1Api") as mock_api:
            api_instance = MagicMock()
            mock_api.return_value = api_instance

            # Create mock secrets with different timestamps
            from datetime import datetime, timedelta

            secret1 = MagicMock()
            secret1.metadata.name = "sealed-secrets-key-old"
            secret1.metadata.creation_timestamp = datetime.now() - timedelta(days=30)
            secret1.type = "kubernetes.io/tls"

            secret2 = MagicMock()
            secret2.metadata.name = "sealed-secrets-key-new"
            secret2.metadata.creation_timestamp = datetime.now()
            secret2.type = "kubernetes.io/tls"

            secret3 = MagicMock()
            secret3.metadata.name = "other-secret"
            secret3.metadata.creation_timestamp = datetime.now()
            secret3.type = "Opaque"

            api_instance.list_namespaced_secret.return_value.items = [secret1, secret2, secret3]

            result = cluster.find_latest_sealed_secrets_controller_certificate()

            assert result == "sealed-secrets-key-new"
