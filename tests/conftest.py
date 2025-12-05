"""Shared test fixtures for kubeseal-auto tests."""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_kube_contexts():
    """Mock kubernetes config contexts."""
    with patch("kubernetes.config.list_kube_config_contexts") as mock:
        mock.return_value = ([{"name": "test-context"}], {"name": "test-context"})
        yield mock


@pytest.fixture
def mock_kube_config():
    """Mock kubernetes config loading."""
    with patch("kubernetes.config.load_kube_config") as mock:
        yield mock


@pytest.fixture
def mock_controller():
    """Mock SealedSecrets controller discovery."""
    with patch("kubeseal_auto.cluster.Cluster._find_sealed_secrets_controller") as mock:
        mock.return_value = {
            "name": "sealed-secrets-controller",
            "namespace": "kube-system",
            "version": "v0.26.0",
        }
        yield mock


@pytest.fixture
def mock_namespaces():
    """Mock namespace listing."""
    with patch("kubeseal_auto.cluster.Cluster.get_all_namespaces") as mock:
        mock.return_value = ["default", "kube-system", "monitoring"]
        yield mock


@pytest.fixture
def mock_core_v1_api():
    """Mock CoreV1Api for namespace listing."""
    with patch("kubernetes.client.CoreV1Api") as mock:
        api_instance = MagicMock()
        mock.return_value = api_instance
        # Mock namespace list
        ns_items = []
        for name in ["default", "kube-system", "monitoring"]:
            ns = MagicMock()
            ns.metadata.name = name
            ns_items.append(ns)
        api_instance.list_namespace.return_value.items = ns_items
        yield api_instance


@pytest.fixture
def mock_subprocess():
    """Mock subprocess.run for command execution."""
    with patch("subprocess.run") as mock:
        mock.return_value = MagicMock(returncode=0, stdout="", stderr="")
        yield mock


@pytest.fixture
def mock_host_binary():
    """Mock Host class to skip binary download."""
    with patch("kubeseal_auto.cluster.Host") as mock:
        host_instance = MagicMock()
        mock.return_value = host_instance
        yield host_instance


@pytest.fixture
def mock_host_ensure_binary():
    """Mock Host.ensure_kubeseal_binary to skip download."""
    with patch("kubeseal_auto.host.Host.ensure_kubeseal_binary") as mock:
        yield mock


@pytest.fixture
def kubeseal_mocks(mock_kube_contexts, mock_kube_config, mock_controller, mock_namespaces, mock_host_ensure_binary):
    """Combined fixture for creating a Kubeseal instance without cluster access.

    Note: This fixture is used for its side effects (setting up mocks).
    Tests that use it may not directly reference the returned dict.
    """
    return {
        "contexts": mock_kube_contexts,
        "config": mock_kube_config,
        "controller": mock_controller,
        "namespaces": mock_namespaces,
        "host_binary": mock_host_ensure_binary,
    }


@pytest.fixture
def cluster_mocks(mock_kube_contexts, mock_kube_config, mock_core_v1_api, mock_host_binary):
    """Combined fixture for creating a Cluster instance."""
    return {
        "contexts": mock_kube_contexts,
        "config": mock_kube_config,
        "core_api": mock_core_v1_api,
        "host": mock_host_binary,
    }


@pytest.fixture
def sample_secret_yaml():
    """Sample secret YAML content."""
    return """apiVersion: v1
kind: Secret
metadata:
  name: test-secret
  namespace: default
type: Opaque
data:
  username: dXNlcm5hbWU=
  password: cGFzc3dvcmQ=
"""


@pytest.fixture
def sample_sealed_secret_yaml():
    """Sample sealed secret YAML content."""
    return """apiVersion: bitnami.com/v1alpha1
kind: SealedSecret
metadata:
  name: test-secret
  namespace: default
spec:
  encryptedData:
    username: AgBy8hCi...
    password: AgBy8hCi...
"""
