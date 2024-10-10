from unittest.mock import patch, MagicMock, mock_open

from kubeseal_auto.kubeseal import Kubeseal


@patch('subprocess.call')
@patch('kubernetes.config.load_kube_config')
@patch('kubernetes.config.list_kube_config_contexts')
@patch('kubernetes.client.AppsV1Api.list_deployment_for_all_namespaces')
@patch('kubernetes.client.CoreV1Api.list_namespace')
@patch('kubeseal_auto.cluster.Cluster._find_sealed_secrets_controller')
def test_create_generic_secret(mock_find_controller, mock_list_namespace, mock_list_deployment,
                               mock_list_kube_config_contexts, mock_load_kube_config, mock_subprocess_call):
    mock_list_kube_config_contexts.return_value = ([{'name': 'context1'}], {'name': 'context2'})
    mock_list_deployment.return_value.items = []
    mock_list_namespace.return_value.items = []
    mock_find_controller.return_value = {
        "name": "sealed-secrets-controller",
        "namespace": "kube-system",
        "version": "v0.12.0"
    }
    kubeseal = Kubeseal(select_context=False)
    secret_params = {
        "name": "test-secret",
        "namespace": "default",
        "type": "generic"
    }
    secrets_input = 'key1=value1\nkey2=value2'

    with patch('questionary.text') as mock_questionary_text:
        mock_questionary_text.return_value.unsafe_ask.return_value = secrets_input
        kubeseal.create_generic_secret(secret_params)
        mock_subprocess_call.assert_called_once()
        command = mock_subprocess_call.call_args[0][0]
        assert 'kubectl create secret generic test-secret' in command
        assert '--from-literal="key1=value1"' in command
        assert '--from-literal="key2=value2"' in command


@patch('subprocess.call')
@patch('kubernetes.config.load_kube_config')
@patch('kubernetes.config.list_kube_config_contexts')
@patch('kubernetes.client.AppsV1Api.list_deployment_for_all_namespaces')
@patch('kubernetes.client.CoreV1Api.list_namespace')
@patch('kubeseal_auto.cluster.Cluster._find_sealed_secrets_controller')
def test_create_tls_secret(mock_find_controller, mock_list_namespace, mock_list_deployment,
                           mock_list_kube_config_contexts, mock_load_kube_config, mock_subprocess_call):
    mock_list_kube_config_contexts.return_value = ([{'name': 'context1'}], {'name': 'context2'})
    mock_list_deployment.return_value.items = []
    mock_list_namespace.return_value.items = []
    mock_find_controller.return_value = {
        "name": "sealed-secrets-controller",
        "namespace": "kube-system",
        "version": "v0.12.0"
    }
    kubeseal = Kubeseal(select_context=False)
    secret_params = {
        "name": "test-tls-secret",
        "namespace": "default",
        "type": "tls"
    }

    kubeseal.create_tls_secret(secret_params)
    mock_subprocess_call.assert_called_once()
    command = mock_subprocess_call.call_args[0][0]
    assert 'kubectl create secret tls test-tls-secret' in command
    assert '--namespace default' in command
    assert '--key tls.key' in command
    assert '--cert tls.crt' in command
    assert '--dry-run=client -o yaml' in command


@patch('subprocess.call')
@patch('kubernetes.config.load_kube_config')
@patch('kubernetes.config.list_kube_config_contexts')
@patch('kubernetes.client.AppsV1Api.list_deployment_for_all_namespaces')
@patch('kubernetes.client.CoreV1Api.list_namespace')
@patch('kubeseal_auto.cluster.Cluster._find_sealed_secrets_controller')
def test_create_regcred_secret(mock_find_controller, mock_list_namespace, mock_list_deployment,
                               mock_list_kube_config_contexts, mock_load_kube_config, mock_subprocess_call):
    mock_list_kube_config_contexts.return_value = ([{'name': 'context1'}], {'name': 'context2'})
    mock_list_deployment.return_value.items = []
    mock_list_namespace.return_value.items = []
    mock_find_controller.return_value = {
        "name": "sealed-secrets-controller",
        "namespace": "kube-system",
        "version": "v0.12.0"
    }
    kubeseal = Kubeseal(select_context=False)
    secret_params = {
        "name": "test-regcred-secret",
        "namespace": "default",
        "type": "docker-registry"
    }

    docker_server = "https://index.docker.io/v1/"
    docker_username = "testuser"
    docker_password = "testpassword"

    with patch('questionary.text') as mock_questionary_text:
        mock_questionary_text_instance = MagicMock()
        mock_questionary_text.return_value = mock_questionary_text_instance
        mock_questionary_text_instance.unsafe_ask.side_effect = [docker_server, docker_username, docker_password]

        kubeseal.create_regcred_secret(secret_params)
        mock_subprocess_call.assert_called_once()
        command = mock_subprocess_call.call_args[0][0]
        assert 'kubectl create secret docker-registry test-regcred-secret' in command
        assert '--namespace default' in command
        assert f'--docker-server={docker_server}' in command
        assert f'--docker-username={docker_username}' in command
        assert f'--docker-password={docker_password}' in command
        assert '--dry-run=client -o yaml' in command


@patch('subprocess.call')
@patch('kubernetes.config.load_kube_config')
@patch('kubernetes.config.list_kube_config_contexts')
@patch('kubernetes.client.AppsV1Api.list_deployment_for_all_namespaces')
@patch('kubernetes.client.CoreV1Api.list_namespace')
@patch('kubeseal_auto.cluster.Cluster._find_sealed_secrets_controller')
def test_seal(mock_find_controller, mock_list_namespace, mock_list_deployment, mock_list_kube_config_contexts,
              mock_load_kube_config, mock_subprocess_call):
    mock_list_kube_config_contexts.return_value = ([{'name': 'context1'}], {'name': 'context2'})
    mock_list_deployment.return_value.items = []
    mock_list_namespace.return_value.items = []
    mock_find_controller.return_value = {
        "name": "sealed-secrets-controller",
        "namespace": "kube-system",
        "version": "v0.12.0"
    }
    kubeseal = Kubeseal(select_context=False)
    secret_name = "test-secret"

    # Mock the open function to simulate the presence of the file
    with patch('builtins.open', mock_open(read_data="apiVersion: v1\nkind: Secret\nmetadata:\n  name: test-secret")):
        kubeseal.seal(secret_name)
        mock_subprocess_call.assert_called_once()
        command = mock_subprocess_call.call_args[0][0]
        assert f"{kubeseal.binary} --format=yaml" in command
        assert f"--context={kubeseal.current_context_name}" in command
        assert f"--controller-namespace={kubeseal.controller_namespace}" in command
        assert f"--controller-name={kubeseal.controller_name}" in command
        assert f"< {kubeseal.temp_file.name}" in command
        assert f"> {secret_name}.yaml" in command


@patch('kubeseal_auto.cluster.Cluster.get_all_namespaces', return_value=['default', 'kube-system'])
@patch('kubernetes.config.load_kube_config')
@patch('kubernetes.config.list_kube_config_contexts')
@patch('kubeseal_auto.cluster.Cluster._find_sealed_secrets_controller')
def test_parse_existing_secret_success(mock_find_controller, mock_list_kube_config_contexts,
                                       mock_load_kube_config, mock_get_all_namespaces):
    mock_list_kube_config_contexts.return_value = ([{'name': 'context1'}], {'name': 'context2'})
    mock_find_controller.return_value = {
        "name": "sealed-secrets-controller",
        "namespace": "kube-system",
        "version": "v0.12.0"
    }
    kubeseal = Kubeseal(select_context=False)
    with patch('builtins.open', mock_open(read_data="apiVersion: v1\nkind: Secret\nmetadata:\n  name: test-secret")):
        secret = kubeseal.parse_existing_secret('test-secret.yaml')
        assert secret['kind'] == 'Secret'
        assert secret['metadata']['name'] == 'test-secret'


@patch('kubeseal_auto.cluster.Cluster.get_all_namespaces', return_value=['default', 'kube-system'])
@patch('kubernetes.config.load_kube_config')
@patch('kubernetes.config.list_kube_config_contexts')
@patch('kubeseal_auto.cluster.Cluster._find_sealed_secrets_controller')
def test_parse_existing_secret_file_not_found(mock_find_controller, mock_list_kube_config_contexts,
                                              mock_load_kube_config, mock_get_all_namespaces):
    mock_list_kube_config_contexts.return_value = ([{'name': 'context1'}], {'name': 'context2'})
    mock_find_controller.return_value = {
        "name": "sealed-secrets-controller",
        "namespace": "kube-system",
        "version": "v0.12.0"
    }
    kubeseal = Kubeseal(select_context=False)
    with patch('builtins.exit') as mock_exit:
        kubeseal.parse_existing_secret('nonexistent-secret.yaml')
        mock_exit.assert_called_once_with(1)
