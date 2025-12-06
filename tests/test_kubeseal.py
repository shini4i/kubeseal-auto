"""Tests for kubeseal.py module."""

from unittest.mock import MagicMock, mock_open, patch

import click
import pytest

from kubeseal_auto.core.kubeseal import Kubeseal
from kubeseal_auto.exceptions import SecretParsingError
from kubeseal_auto.models import SecretParams, SecretType
from kubeseal_auto.secrets.prompts import validate_k8s_name


class TestValidateK8sName:
    """Tests for Kubernetes name validation."""

    def test_valid_simple_name(self):
        """Test valid simple name."""
        assert validate_k8s_name("my-secret") is True

    def test_valid_name_with_dots(self):
        """Test valid name with dots."""
        assert validate_k8s_name("my.secret.name") is True

    def test_valid_name_with_numbers(self):
        """Test valid name with numbers."""
        assert validate_k8s_name("secret123") is True

    def test_empty_name(self):
        """Test empty name returns error."""
        result = validate_k8s_name("")
        assert isinstance(result, str)
        assert "empty" in result.lower()

    def test_name_too_long(self):
        """Test name exceeding max length."""
        long_name = "a" * 254
        result = validate_k8s_name(long_name)
        assert isinstance(result, str)
        assert "253" in result

    def test_name_with_uppercase(self):
        """Test name with uppercase letters is invalid."""
        result = validate_k8s_name("MySecret")
        assert isinstance(result, str)
        assert "lowercase" in result.lower()

    def test_name_starting_with_hyphen(self):
        """Test name starting with hyphen is invalid."""
        result = validate_k8s_name("-my-secret")
        assert isinstance(result, str)

    def test_name_ending_with_hyphen(self):
        """Test name ending with hyphen is invalid."""
        result = validate_k8s_name("my-secret-")
        assert isinstance(result, str)

    def test_name_with_underscore(self):
        """Test name with underscore is invalid."""
        result = validate_k8s_name("my_secret")
        assert isinstance(result, str)


class TestKubesealSecretCreation:
    """Tests for secret creation methods."""

    def test_create_generic_secret(self, kubeseal_mocks, mock_subprocess):  # noqa: ARG002
        """Test creating a generic secret with key-value pairs."""
        kubeseal = Kubeseal(select_context=False)
        secret_params = SecretParams(name="test-secret", namespace="default", secret_type=SecretType.GENERIC)

        with (
            patch("questionary.select") as mock_select,
            patch("questionary.text") as mock_text,
            patch("builtins.open", mock_open()),
        ):
            # Simulate: literal -> key1=value1, literal -> key2=value2, done
            mock_select.return_value.unsafe_ask.side_effect = ["literal", "literal", "done"]
            mock_text.return_value.unsafe_ask.side_effect = ["key1=value1", "key2=value2"]
            kubeseal.create_generic_secret(secret_params)

            mock_subprocess.assert_called_once()
            cmd = mock_subprocess.call_args[0][0]
            assert cmd[0] == "kubectl"
            assert cmd[1] == "create"
            assert cmd[2] == "secret"
            assert cmd[3] == "generic"
            assert cmd[4] == "test-secret"
            assert "--namespace" in cmd
            assert "default" in cmd
            assert "--from-literal=key1=value1" in cmd
            assert "--from-literal=key2=value2" in cmd

    def test_create_generic_secret_with_file(self, kubeseal_mocks, mock_subprocess):  # noqa: ARG002
        """Test creating a generic secret from file."""
        kubeseal = Kubeseal(select_context=False)
        secret_params = SecretParams(name="test-secret", namespace="default", secret_type=SecretType.GENERIC)

        with (
            patch("questionary.select") as mock_select,
            patch("questionary.path") as mock_path,
            patch("builtins.open", mock_open()),
            patch("kubeseal_auto.secrets.prompts.Path.exists", return_value=True),
        ):
            # Simulate: file -> config.json, done
            mock_select.return_value.unsafe_ask.side_effect = ["file", "done"]
            mock_path.return_value.unsafe_ask.return_value = "config.json"
            kubeseal.create_generic_secret(secret_params)

            mock_subprocess.assert_called_once()
            cmd = mock_subprocess.call_args[0][0]
            assert "--from-file=config.json" in cmd

    def test_create_generic_secret_bulk_literals(self, kubeseal_mocks, mock_subprocess):  # noqa: ARG002
        """Test creating a generic secret with bulk literals."""
        kubeseal = Kubeseal(select_context=False)
        secret_params = SecretParams(name="test-secret", namespace="default", secret_type=SecretType.GENERIC)

        with (
            patch("questionary.select") as mock_select,
            patch("questionary.text") as mock_text,
            patch("builtins.open", mock_open()),
        ):
            # Simulate: bulk -> multiline input, done
            mock_select.return_value.unsafe_ask.side_effect = ["bulk", "done"]
            mock_text.return_value.unsafe_ask.return_value = "key1=value1\nkey2=value2\nkey3=value3"
            kubeseal.create_generic_secret(secret_params)

            mock_subprocess.assert_called_once()
            cmd = mock_subprocess.call_args[0][0]
            assert "--from-literal=key1=value1" in cmd
            assert "--from-literal=key2=value2" in cmd
            assert "--from-literal=key3=value3" in cmd

    def test_create_generic_secret_mixed_entries(self, kubeseal_mocks, mock_subprocess):  # noqa: ARG002
        """Test creating a generic secret with mixed entry types."""
        kubeseal = Kubeseal(select_context=False)
        secret_params = SecretParams(name="test-secret", namespace="default", secret_type=SecretType.GENERIC)

        with (
            patch("questionary.select") as mock_select,
            patch("questionary.text") as mock_text,
            patch("questionary.path") as mock_path,
            patch("builtins.open", mock_open()),
            patch("kubeseal_auto.secrets.prompts.Path.exists", return_value=True),
        ):
            # Simulate: literal, file, bulk, done
            mock_select.return_value.unsafe_ask.side_effect = ["literal", "file", "bulk", "done"]
            mock_text.return_value.unsafe_ask.side_effect = ["single=value", "bulk1=val1\nbulk2=val2"]
            mock_path.return_value.unsafe_ask.return_value = "data.json"
            kubeseal.create_generic_secret(secret_params)

            mock_subprocess.assert_called_once()
            cmd = mock_subprocess.call_args[0][0]
            assert "--from-literal=single=value" in cmd
            assert "--from-file=data.json" in cmd
            assert "--from-literal=bulk1=val1" in cmd
            assert "--from-literal=bulk2=val2" in cmd

    def test_create_tls_secret(self, kubeseal_mocks, mock_subprocess):  # noqa: ARG002
        """Test creating a TLS secret."""
        kubeseal = Kubeseal(select_context=False)
        secret_params = SecretParams(name="test-tls-secret", namespace="default", secret_type=SecretType.TLS)

        with (
            patch("builtins.open", mock_open()),
            patch("kubeseal_auto.secrets.creation.Path.exists", return_value=True),
        ):
            kubeseal.create_tls_secret(secret_params)

            mock_subprocess.assert_called_once()
            cmd = mock_subprocess.call_args[0][0]
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

    def test_create_regcred_secret(self, kubeseal_mocks, mock_subprocess):  # noqa: ARG002
        """Test creating a docker-registry secret."""
        kubeseal = Kubeseal(select_context=False)
        secret_params = SecretParams(
            name="test-regcred-secret", namespace="default", secret_type=SecretType.DOCKER_REGISTRY
        )

        docker_server = "https://index.docker.io/v1/"
        docker_username = "testuser"
        docker_password = "testpassword"  # noqa: S105

        with (
            patch("questionary.text") as mock_questionary_text,
            patch("questionary.password") as mock_questionary_password,
            patch("builtins.open", mock_open()),
        ):
            mock_questionary_text_instance = MagicMock()
            mock_questionary_text.return_value = mock_questionary_text_instance
            mock_questionary_text_instance.unsafe_ask.side_effect = [docker_server, docker_username]

            mock_questionary_password_instance = MagicMock()
            mock_questionary_password.return_value = mock_questionary_password_instance
            mock_questionary_password_instance.unsafe_ask.return_value = docker_password

            kubeseal.create_regcred_secret(secret_params)

            mock_subprocess.assert_called_once()
            cmd = mock_subprocess.call_args[0][0]
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

    def test_create_tls_secret_missing_files(self, kubeseal_mocks):  # noqa: ARG002
        """Test creating a TLS secret with missing files raises ClickException."""
        kubeseal = Kubeseal(select_context=False)
        secret_params = SecretParams(name="test-tls-secret", namespace="default", secret_type=SecretType.TLS)

        with pytest.raises(click.ClickException) as exc_info:
            kubeseal.create_tls_secret(secret_params)

        assert "Required TLS file(s) not found" in str(exc_info.value)

    def test_create_generic_secret_file_not_found(self, kubeseal_mocks):  # noqa: ARG002
        """Test creating a generic secret with non-existent file raises ClickException."""
        kubeseal = Kubeseal(select_context=False)
        secret_params = SecretParams(name="test-secret", namespace="default", secret_type=SecretType.GENERIC)

        with (
            patch("questionary.select") as mock_select,
            patch("questionary.path") as mock_path,
            pytest.raises(click.ClickException) as exc_info,
        ):
            mock_select.return_value.unsafe_ask.side_effect = ["file", "done"]
            mock_path.return_value.unsafe_ask.return_value = "nonexistent.json"
            kubeseal.create_generic_secret(secret_params)

        assert "File not found: nonexistent.json" in str(exc_info.value)


class TestKubesealSealing:
    """Tests for secret sealing methods."""

    def test_seal(self, kubeseal_mocks, mock_subprocess):  # noqa: ARG002
        """Test sealing a secret."""
        kubeseal = Kubeseal(select_context=False)
        secret_params = SecretParams(name="test-secret", namespace="default", secret_type=SecretType.GENERIC)

        with patch(
            "builtins.open", mock_open(read_data="apiVersion: v1\nkind: Secret\nmetadata:\n  name: test-secret")
        ):
            kubeseal.seal(secret_params=secret_params)

            mock_subprocess.assert_called_once()
            cmd = mock_subprocess.call_args[0][0]
            assert kubeseal.binary in cmd[0]
            assert "--format=yaml" in cmd
            assert f"--context={kubeseal.current_context_name}" in cmd
            assert f"--controller-namespace={kubeseal.controller_namespace}" in cmd
            assert f"--controller-name={kubeseal.controller_name}" in cmd

    def test_seal_detached_mode(self, mock_subprocess):
        """Test sealing a secret in detached mode."""
        kubeseal = Kubeseal(select_context=False, certificate="test-cert.crt")
        secret_params = SecretParams(name="test-secret", namespace="default", secret_type=SecretType.GENERIC)

        with patch(
            "builtins.open", mock_open(read_data="apiVersion: v1\nkind: Secret\nmetadata:\n  name: test-secret")
        ):
            kubeseal.seal(secret_params=secret_params)

            mock_subprocess.assert_called_once()
            cmd = mock_subprocess.call_args[0][0]
            assert "--cert=test-cert.crt" in cmd

    def test_merge(self, kubeseal_mocks, mock_subprocess, sample_secret_yaml):  # noqa: ARG002
        """Test merging secrets into an existing sealed secret."""
        kubeseal = Kubeseal(select_context=False)
        secret_name = "existing-secret.yaml"

        with patch("builtins.open", mock_open(read_data=sample_secret_yaml)):
            kubeseal.merge(secret_name)

            mock_subprocess.assert_called_once()
            cmd = mock_subprocess.call_args[0][0]
            assert "--merge-into" in cmd
            assert secret_name in cmd


class TestKubesealParsing:
    """Tests for secret parsing methods."""

    def test_parse_existing_secret_success(self, kubeseal_mocks, sample_secret_yaml):  # noqa: ARG002
        """Test successfully parsing an existing secret."""
        kubeseal = Kubeseal(select_context=False)

        with patch("builtins.open", mock_open(read_data=sample_secret_yaml)):
            secret = kubeseal.parse_existing_secret("test-secret.yaml")

            assert secret["kind"] == "Secret"
            assert secret["metadata"]["name"] == "test-secret"
            assert secret["metadata"]["namespace"] == "default"

    def test_parse_existing_secret_file_not_found(self, kubeseal_mocks):  # noqa: ARG002
        """Test parsing a non-existent secret file."""
        kubeseal = Kubeseal(select_context=False)

        with pytest.raises(SecretParsingError) as exc_info:
            kubeseal.parse_existing_secret("nonexistent-secret.yaml")

        assert "does not exist" in str(exc_info.value)

    def test_parse_existing_secret_multi_document(self, kubeseal_mocks):  # noqa: ARG002
        """Test parsing a multi-document YAML file raises error."""
        kubeseal = Kubeseal(select_context=False)
        multi_doc_yaml = "---\napiVersion: v1\nkind: Secret\n---\napiVersion: v1\nkind: Secret\n"

        with (
            patch("builtins.open", mock_open(read_data=multi_doc_yaml)),
            pytest.raises(SecretParsingError) as exc_info,
        ):
            kubeseal.parse_existing_secret("multi-doc.yaml")

        assert "multiple YAML documents" in str(exc_info.value)

    def test_parse_existing_secret_empty_file(self, kubeseal_mocks):  # noqa: ARG002
        """Test parsing an empty file returns None."""
        kubeseal = Kubeseal(select_context=False)

        with patch("builtins.open", mock_open(read_data="")):
            result = kubeseal.parse_existing_secret("empty.yaml")

        assert result is None

    def test_parse_existing_secret_malformed_yaml(self, kubeseal_mocks):  # noqa: ARG002
        """Test parsing malformed YAML raises SecretParsingError."""
        kubeseal = Kubeseal(select_context=False)
        malformed_yaml = "apiVersion: v1\nkind: Secret\nmetadata: [:"

        with (
            patch("builtins.open", mock_open(read_data=malformed_yaml)),
            pytest.raises(SecretParsingError) as exc_info,
        ):
            kubeseal.parse_existing_secret("malformed.yaml")

        assert "malformed YAML" in str(exc_info.value)

    def test_parse_existing_secret_list_yaml(self, kubeseal_mocks):  # noqa: ARG002
        """Test parsing a YAML file with a list raises SecretParsingError."""
        kubeseal = Kubeseal(select_context=False)
        list_yaml = "- kind: SealedSecret\n  metadata:\n    name: test\n"

        with (
            patch("builtins.open", mock_open(read_data=list_yaml)),
            pytest.raises(SecretParsingError) as exc_info,
        ):
            kubeseal.parse_existing_secret("list.yaml")

        assert "does not contain a valid YAML mapping" in str(exc_info.value)


class TestKubesealDetachedMode:
    """Tests for detached mode operations."""

    def test_init_detached_mode(self):
        """Test initializing Kubeseal in detached mode."""
        kubeseal = Kubeseal(select_context=False, certificate="test-cert.crt")

        assert kubeseal.detached_mode is True
        assert kubeseal.certificate == "test-cert.crt"
        assert kubeseal.binary == "kubeseal"

    def test_init_connected_mode(self, kubeseal_mocks):  # noqa: ARG002
        """Test initializing Kubeseal in connected mode."""
        kubeseal = Kubeseal(select_context=False)

        assert kubeseal.detached_mode is False
        assert kubeseal.controller_name == "sealed-secrets-controller"
        assert kubeseal.controller_namespace == "kube-system"


class TestKubesealCollectParameters:
    """Tests for parameter collection."""

    def test_collect_parameters_connected_mode(self, kubeseal_mocks):  # noqa: ARG002
        """Test collecting parameters in connected mode."""
        kubeseal = Kubeseal(select_context=False)

        with (
            patch("questionary.autocomplete") as mock_autocomplete,
            patch("questionary.select") as mock_select,
            patch("questionary.text") as mock_text,
        ):
            mock_autocomplete.return_value.unsafe_ask.return_value = "default"
            mock_select.return_value.unsafe_ask.return_value = "generic"
            mock_text.return_value.unsafe_ask.return_value = "my-secret"

            params = kubeseal.collect_parameters()

            assert params.namespace == "default"
            assert params.secret_type == SecretType.GENERIC
            assert params.name == "my-secret"

    def test_collect_parameters_detached_mode(self):
        """Test collecting parameters in detached mode."""
        kubeseal = Kubeseal(select_context=False, certificate="test-cert.crt")

        with (
            patch("questionary.select") as mock_select,
            patch("questionary.text") as mock_text,
        ):
            mock_text.return_value.unsafe_ask.side_effect = ["custom-namespace", "my-secret"]
            mock_select.return_value.unsafe_ask.return_value = "generic"

            params = kubeseal.collect_parameters()

            assert params.namespace == "custom-namespace"
            assert params.secret_type == SecretType.GENERIC
            assert params.name == "my-secret"
