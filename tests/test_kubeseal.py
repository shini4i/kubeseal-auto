from unittest.mock import MagicMock, mock_open, patch

import pytest

from kubeseal_auto.exceptions import SecretParsingError
from kubeseal_auto.kubeseal import Kubeseal


@patch("subprocess.run")
@patch("kubernetes.config.load_kube_config")
@patch("kubernetes.config.list_kube_config_contexts")
@patch("kubernetes.client.AppsV1Api.list_deployment_for_all_namespaces")
@patch("kubernetes.client.CoreV1Api.list_namespace")
@patch("kubeseal_auto.cluster.Cluster._find_sealed_secrets_controller")
def test_create_generic_secret(
    mock_find_controller,
    mock_list_namespace,
    mock_list_deployment,
    mock_list_kube_config_contexts,
    mock_load_kube_config,
    mock_subprocess_run,
):
    mock_list_kube_config_contexts.return_value = ([{"name": "context1"}], {"name": "context2"})
    mock_list_deployment.return_value.items = []
    mock_list_namespace.return_value.items = []
    mock_find_controller.return_value = {
        "name": "sealed-secrets-controller",
        "namespace": "kube-system",
        "version": "v0.12.0",
    }
    kubeseal = Kubeseal(select_context=False)
    secret_params = {"name": "test-secret", "namespace": "default", "type": "generic"}
    secrets_input = "key1=value1\nkey2=value2"

    with patch("questionary.text") as mock_questionary_text, patch("builtins.open", mock_open()):
        mock_questionary_text.return_value.unsafe_ask.return_value = secrets_input
        kubeseal.create_generic_secret(secret_params)
        mock_subprocess_run.assert_called_once()
        cmd = mock_subprocess_run.call_args[0][0]
        assert cmd[0] == "kubectl"
        assert cmd[1] == "create"
        assert cmd[2] == "secret"
        assert cmd[3] == "generic"
        assert cmd[4] == "test-secret"
        assert "--namespace" in cmd
        assert "default" in cmd
        assert "--from-literal=key1=value1" in cmd
        assert "--from-literal=key2=value2" in cmd


@patch("subprocess.run")
@patch("kubernetes.config.load_kube_config")
@patch("kubernetes.config.list_kube_config_contexts")
@patch("kubernetes.client.AppsV1Api.list_deployment_for_all_namespaces")
@patch("kubernetes.client.CoreV1Api.list_namespace")
@patch("kubeseal_auto.cluster.Cluster._find_sealed_secrets_controller")
def test_create_tls_secret(
    mock_find_controller,
    mock_list_namespace,
    mock_list_deployment,
    mock_list_kube_config_contexts,
    mock_load_kube_config,
    mock_subprocess_run,
):
    mock_list_kube_config_contexts.return_value = ([{"name": "context1"}], {"name": "context2"})
    mock_list_deployment.return_value.items = []
    mock_list_namespace.return_value.items = []
    mock_find_controller.return_value = {
        "name": "sealed-secrets-controller",
        "namespace": "kube-system",
        "version": "v0.12.0",
    }
    kubeseal = Kubeseal(select_context=False)
    secret_params = {"name": "test-tls-secret", "namespace": "default", "type": "tls"}

    with patch("builtins.open", mock_open()):
        kubeseal.create_tls_secret(secret_params)
        mock_subprocess_run.assert_called_once()
        cmd = mock_subprocess_run.call_args[0][0]
        assert cmd[0] == "kubectl"
        assert cmd[1] == "create"
        assert cmd[2] == "secret"
        assert cmd[3] == "tls"
        assert cmd[4] == "test-tls-secret"
        assert "--namespace" in cmd
        assert "default" in cmd
        assert "--key" in cmd
        assert "tls.key" in cmd
        assert "--cert" in cmd
        assert "tls.crt" in cmd
        assert "--dry-run=client" in cmd
        assert "-o" in cmd
        assert "yaml" in cmd


@patch("subprocess.run")
@patch("kubernetes.config.load_kube_config")
@patch("kubernetes.config.list_kube_config_contexts")
@patch("kubernetes.client.AppsV1Api.list_deployment_for_all_namespaces")
@patch("kubernetes.client.CoreV1Api.list_namespace")
@patch("kubeseal_auto.cluster.Cluster._find_sealed_secrets_controller")
def test_create_regcred_secret(
    mock_find_controller,
    mock_list_namespace,
    mock_list_deployment,
    mock_list_kube_config_contexts,
    mock_load_kube_config,
    mock_subprocess_run,
):
    mock_list_kube_config_contexts.return_value = ([{"name": "context1"}], {"name": "context2"})
    mock_list_deployment.return_value.items = []
    mock_list_namespace.return_value.items = []
    mock_find_controller.return_value = {
        "name": "sealed-secrets-controller",
        "namespace": "kube-system",
        "version": "v0.12.0",
    }
    kubeseal = Kubeseal(select_context=False)
    secret_params = {"name": "test-regcred-secret", "namespace": "default", "type": "docker-registry"}

    docker_server = "https://index.docker.io/v1/"
    docker_username = "testuser"
    docker_password = "testpassword"

    with patch("questionary.text") as mock_questionary_text, patch("builtins.open", mock_open()):
        mock_questionary_text_instance = MagicMock()
        mock_questionary_text.return_value = mock_questionary_text_instance
        mock_questionary_text_instance.unsafe_ask.side_effect = [docker_server, docker_username, docker_password]

        kubeseal.create_regcred_secret(secret_params)
        mock_subprocess_run.assert_called_once()
        cmd = mock_subprocess_run.call_args[0][0]
        assert cmd[0] == "kubectl"
        assert cmd[1] == "create"
        assert cmd[2] == "secret"
        assert cmd[3] == "docker-registry"
        assert cmd[4] == "test-regcred-secret"
        assert "--namespace" in cmd
        assert "default" in cmd
        assert f"--docker-server={docker_server}" in cmd
        assert f"--docker-username={docker_username}" in cmd
        assert f"--docker-password={docker_password}" in cmd
        assert "--dry-run=client" in cmd


@patch("subprocess.run")
@patch("kubernetes.config.load_kube_config")
@patch("kubernetes.config.list_kube_config_contexts")
@patch("kubernetes.client.AppsV1Api.list_deployment_for_all_namespaces")
@patch("kubernetes.client.CoreV1Api.list_namespace")
@patch("kubeseal_auto.cluster.Cluster._find_sealed_secrets_controller")
def test_seal(
    mock_find_controller,
    mock_list_namespace,
    mock_list_deployment,
    mock_list_kube_config_contexts,
    mock_load_kube_config,
    mock_subprocess_run,
):
    mock_list_kube_config_contexts.return_value = ([{"name": "context1"}], {"name": "context2"})
    mock_list_deployment.return_value.items = []
    mock_list_namespace.return_value.items = []
    mock_find_controller.return_value = {
        "name": "sealed-secrets-controller",
        "namespace": "kube-system",
        "version": "v0.12.0",
    }
    kubeseal = Kubeseal(select_context=False)
    secret_name = "test-secret"

    # Mock the open function to simulate the presence of the file
    with patch("builtins.open", mock_open(read_data="apiVersion: v1\nkind: Secret\nmetadata:\n  name: test-secret")):
        kubeseal.seal(secret_name)
        mock_subprocess_run.assert_called_once()
        cmd = mock_subprocess_run.call_args[0][0]
        assert kubeseal.binary in cmd[0]
        assert "--format=yaml" in cmd
        assert f"--context={kubeseal.current_context_name}" in cmd
        assert f"--controller-namespace={kubeseal.controller_namespace}" in cmd
        assert f"--controller-name={kubeseal.controller_name}" in cmd


@patch("kubeseal_auto.cluster.Cluster.get_all_namespaces", return_value=["default", "kube-system"])
@patch("kubernetes.config.load_kube_config")
@patch("kubernetes.config.list_kube_config_contexts")
@patch("kubeseal_auto.cluster.Cluster._find_sealed_secrets_controller")
def test_parse_existing_secret_success(
    mock_find_controller, mock_list_kube_config_contexts, mock_load_kube_config, mock_get_all_namespaces
):
    mock_list_kube_config_contexts.return_value = ([{"name": "context1"}], {"name": "context2"})
    mock_find_controller.return_value = {
        "name": "sealed-secrets-controller",
        "namespace": "kube-system",
        "version": "v0.12.0",
    }
    kubeseal = Kubeseal(select_context=False)
    with patch("builtins.open", mock_open(read_data="apiVersion: v1\nkind: Secret\nmetadata:\n  name: test-secret")):
        secret = kubeseal.parse_existing_secret("test-secret.yaml")
        assert secret["kind"] == "Secret"
        assert secret["metadata"]["name"] == "test-secret"


@patch("kubeseal_auto.cluster.Cluster.get_all_namespaces", return_value=["default", "kube-system"])
@patch("kubernetes.config.load_kube_config")
@patch("kubernetes.config.list_kube_config_contexts")
@patch("kubeseal_auto.cluster.Cluster._find_sealed_secrets_controller")
def test_parse_existing_secret_file_not_found(
    mock_find_controller, mock_list_kube_config_contexts, mock_load_kube_config, mock_get_all_namespaces
):
    mock_list_kube_config_contexts.return_value = ([{"name": "context1"}], {"name": "context2"})
    mock_find_controller.return_value = {
        "name": "sealed-secrets-controller",
        "namespace": "kube-system",
        "version": "v0.12.0",
    }
    kubeseal = Kubeseal(select_context=False)
    with pytest.raises(SecretParsingError) as exc_info:
        kubeseal.parse_existing_secret("nonexistent-secret.yaml")
    assert "does not exist" in str(exc_info.value)
