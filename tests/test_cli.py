"""Tests for cli.py module."""

from unittest.mock import MagicMock, patch

import click
import pytest
from click.testing import CliRunner

from kubeseal_auto import __version__
from kubeseal_auto.cli import cli, create_new_secret, edit_secret
from kubeseal_auto.exceptions import SecretParsingError
from kubeseal_auto.models import SecretParams, SecretType


class TestCliVersion:
    """Tests for version command."""

    def test_version_flag(self):
        """Test --version flag prints version."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])

        assert result.exit_code == 0
        assert __version__ in result.output

    def test_version_short_flag(self):
        """Test -v flag prints version."""
        runner = CliRunner()
        result = runner.invoke(cli, ["-v"])

        assert result.exit_code == 0
        assert __version__ in result.output


class TestCliHelp:
    """Tests for help output."""

    def test_help_flag(self):
        """Test --help flag shows help text."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "Automate the process of sealing secrets" in result.output
        assert "--version" in result.output
        assert "--debug" in result.output
        assert "--select" in result.output
        assert "--fetch" in result.output
        assert "--cert" in result.output
        assert "--edit" in result.output
        assert "--re-encrypt" in result.output
        assert "--backup" in result.output


class TestCliDetachedMode:
    """Tests for detached mode operations."""

    def test_cert_option_enables_detached_mode(self):
        """Test that --cert option enables detached mode."""
        runner = CliRunner()

        with (
            patch("kubeseal_auto.cli.Kubeseal") as mock_kubeseal,
            patch("kubeseal_auto.cli.create_new_secret"),
        ):
            mock_instance = MagicMock()
            mock_instance.__enter__ = MagicMock(return_value=mock_instance)
            mock_instance.__exit__ = MagicMock(return_value=False)
            mock_kubeseal.return_value = mock_instance

            result = runner.invoke(cli, ["--cert", "test-cert.crt"])

            assert result.exit_code == 0
            mock_kubeseal.assert_called_once_with(certificate="test-cert.crt", select_context=False)


class TestCliFetch:
    """Tests for certificate fetch operation."""

    def test_fetch_calls_fetch_certificate(self):
        """Test --fetch option calls fetch_certificate method."""
        runner = CliRunner()

        with patch("kubeseal_auto.cli.Kubeseal") as mock_kubeseal:
            mock_instance = MagicMock()
            mock_instance.__enter__ = MagicMock(return_value=mock_instance)
            mock_instance.__exit__ = MagicMock(return_value=False)
            mock_kubeseal.return_value = mock_instance

            result = runner.invoke(cli, ["--fetch"])

            assert result.exit_code == 0
            mock_instance.fetch_certificate.assert_called_once()


class TestCliBackup:
    """Tests for backup operation."""

    def test_backup_calls_backup_method(self):
        """Test --backup option calls backup method."""
        runner = CliRunner()

        with patch("kubeseal_auto.cli.Kubeseal") as mock_kubeseal:
            mock_instance = MagicMock()
            mock_instance.__enter__ = MagicMock(return_value=mock_instance)
            mock_instance.__exit__ = MagicMock(return_value=False)
            mock_kubeseal.return_value = mock_instance

            result = runner.invoke(cli, ["--backup"])

            assert result.exit_code == 0
            mock_instance.backup.assert_called_once()


class TestCliReencrypt:
    """Tests for re-encryption operation."""

    def test_reencrypt_calls_reencrypt_method(self):
        """Test --re-encrypt option calls reencrypt method."""
        runner = CliRunner()

        with patch("kubeseal_auto.cli.Kubeseal") as mock_kubeseal:
            mock_instance = MagicMock()
            mock_instance.__enter__ = MagicMock(return_value=mock_instance)
            mock_instance.__exit__ = MagicMock(return_value=False)
            mock_kubeseal.return_value = mock_instance

            result = runner.invoke(cli, ["--re-encrypt", "/path/to/secrets"])

            assert result.exit_code == 0
            mock_instance.reencrypt.assert_called_once_with(src="/path/to/secrets")


class TestCliEdit:
    """Tests for edit operation."""

    def test_edit_calls_edit_secret(self):
        """Test --edit option calls edit_secret function."""
        runner = CliRunner()

        with (
            patch("kubeseal_auto.cli.Kubeseal") as mock_kubeseal,
            patch("kubeseal_auto.cli.edit_secret") as mock_edit,
        ):
            mock_instance = MagicMock()
            mock_instance.__enter__ = MagicMock(return_value=mock_instance)
            mock_instance.__exit__ = MagicMock(return_value=False)
            mock_kubeseal.return_value = mock_instance

            result = runner.invoke(cli, ["--edit", "secret.yaml"])

            assert result.exit_code == 0
            mock_edit.assert_called_once()


class TestCliDebug:
    """Tests for debug mode."""

    def test_debug_flag_enables_icecream(self):
        """Test --debug flag keeps icecream enabled."""
        runner = CliRunner()

        with (
            patch("kubeseal_auto.cli.Kubeseal") as mock_kubeseal,
            patch("kubeseal_auto.cli.create_new_secret"),
            patch("kubeseal_auto.cli.ic") as mock_ic,
        ):
            mock_instance = MagicMock()
            mock_instance.__enter__ = MagicMock(return_value=mock_instance)
            mock_instance.__exit__ = MagicMock(return_value=False)
            mock_kubeseal.return_value = mock_instance

            result = runner.invoke(cli, ["--debug"])

            assert result.exit_code == 0
            # ic.disable() should not be called when debug is enabled
            mock_ic.disable.assert_not_called()


class TestCreateNewSecret:
    """Tests for create_new_secret function."""

    def test_create_generic_secret(self):
        """Test creating a generic secret."""
        mock_kubeseal = MagicMock()
        secret_params = SecretParams(
            name="test-secret",
            namespace="default",
            secret_type=SecretType.GENERIC,
        )
        mock_kubeseal.collect_parameters.return_value = secret_params

        create_new_secret(mock_kubeseal)

        mock_kubeseal.create_generic_secret.assert_called_once()
        mock_kubeseal.seal.assert_called_once_with(secret_params=secret_params)

    def test_create_tls_secret(self):
        """Test creating a TLS secret."""
        mock_kubeseal = MagicMock()
        secret_params = SecretParams(
            name="tls-secret",
            namespace="default",
            secret_type=SecretType.TLS,
        )
        mock_kubeseal.collect_parameters.return_value = secret_params

        create_new_secret(mock_kubeseal)

        mock_kubeseal.create_tls_secret.assert_called_once()
        mock_kubeseal.seal.assert_called_once_with(secret_params=secret_params)

    def test_create_docker_registry_secret(self):
        """Test creating a docker-registry secret."""
        mock_kubeseal = MagicMock()
        secret_params = SecretParams(
            name="regcred",
            namespace="default",
            secret_type=SecretType.DOCKER_REGISTRY,
        )
        mock_kubeseal.collect_parameters.return_value = secret_params

        create_new_secret(mock_kubeseal)

        mock_kubeseal.create_regcred_secret.assert_called_once()
        mock_kubeseal.seal.assert_called_once_with(secret_params=secret_params)


class TestEditSecret:
    """Tests for edit_secret function."""

    def test_edit_secret_success(self):
        """Test successfully editing a secret."""
        mock_kubeseal = MagicMock()
        mock_kubeseal.parse_existing_secret.return_value = {
            "metadata": {
                "name": "existing-secret",
                "namespace": "default",
            }
        }

        edit_secret(mock_kubeseal, "secret.yaml")

        mock_kubeseal.parse_existing_secret.assert_called_once_with("secret.yaml")
        mock_kubeseal.create_generic_secret.assert_called_once()
        mock_kubeseal.merge.assert_called_once_with("secret.yaml")

    def test_edit_secret_file_not_found(self):
        """Test error when secret file is not found."""
        mock_kubeseal = MagicMock()
        mock_kubeseal.parse_existing_secret.side_effect = SecretParsingError("File not found")

        with pytest.raises(click.ClickException, match="File not found"):
            edit_secret(mock_kubeseal, "nonexistent.yaml")

    def test_edit_secret_empty_file(self):
        """Test error when secret file is empty."""
        mock_kubeseal = MagicMock()
        mock_kubeseal.parse_existing_secret.return_value = None

        with pytest.raises(click.ClickException, match="empty"):
            edit_secret(mock_kubeseal, "empty.yaml")


class TestCliSelect:
    """Tests for context selection."""

    def test_select_flag_passed_to_kubeseal(self):
        """Test --select flag is passed to Kubeseal."""
        runner = CliRunner()

        with (
            patch("kubeseal_auto.cli.Kubeseal") as mock_kubeseal,
            patch("kubeseal_auto.cli.create_new_secret"),
        ):
            mock_instance = MagicMock()
            mock_instance.__enter__ = MagicMock(return_value=mock_instance)
            mock_instance.__exit__ = MagicMock(return_value=False)
            mock_kubeseal.return_value = mock_instance

            result = runner.invoke(cli, ["--select"])

            assert result.exit_code == 0
            mock_kubeseal.assert_called_once_with(certificate=None, select_context=True)
