"""Tests for secrets/sealing.py module."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import click
import pytest

from kubeseal_auto.models import SecretParams, SecretType
from kubeseal_auto.secrets.sealing import (
    _find_sealed_secrets,
    backup_controller_secret,
    fetch_certificate,
    merge_secret,
    reencrypt_secrets,
    seal_secret,
)


class TestSealSecret:
    """Tests for seal_secret function."""

    def test_seal_secret_success(self, tmp_path: Path) -> None:
        """Test successful secret sealing."""
        temp_file = tmp_path / "temp_secret.yaml"
        temp_file.write_text("apiVersion: v1\nkind: Secret\n")

        secret_params = SecretParams(
            name="test-secret",
            namespace="default",
            secret_type=SecretType.GENERIC,
        )

        with (
            patch("subprocess.run") as mock_run,
            patch("kubeseal_auto.secrets.sealing.append_argo_annotation"),
            patch("builtins.open", mock_open(read_data=temp_file.read_text())),
        ):
            mock_run.return_value = MagicMock(returncode=0)

            seal_secret(
                secret_params=secret_params,
                temp_file_path=temp_file,
                kubeseal_cmd=["kubeseal", "--format=yaml"],
            )

            mock_run.assert_called_once()

    def test_seal_secret_raises_on_failure(self, tmp_path: Path) -> None:
        """Test that seal_secret raises ClickException on subprocess failure."""
        temp_file = tmp_path / "temp_secret.yaml"
        temp_file.write_text("apiVersion: v1\nkind: Secret\n")

        secret_params = SecretParams(
            name="test-secret",
            namespace="default",
            secret_type=SecretType.GENERIC,
        )

        with (
            patch("subprocess.run") as mock_run,
            patch("builtins.open", mock_open(read_data="")),
        ):
            mock_run.side_effect = subprocess.CalledProcessError(
                returncode=1, cmd=["kubeseal"], stderr=b"error: certificate expired"
            )

            with pytest.raises(click.ClickException, match="Failed to seal secret"):
                seal_secret(
                    secret_params=secret_params,
                    temp_file_path=temp_file,
                    kubeseal_cmd=["kubeseal", "--format=yaml"],
                )


class TestMergeSecret:
    """Tests for merge_secret function."""

    def test_merge_secret_success(self, tmp_path: Path) -> None:
        """Test successful secret merging."""
        temp_file = tmp_path / "temp_secret.yaml"
        temp_file.write_text("apiVersion: v1\nkind: Secret\n")

        with (
            patch("subprocess.run") as mock_run,
            patch("kubeseal_auto.secrets.sealing.append_argo_annotation"),
            patch("builtins.open", mock_open(read_data="")),
        ):
            mock_run.return_value = MagicMock(returncode=0)

            merge_secret(
                secret_name="existing-secret.yaml",
                temp_file_path=temp_file,
                kubeseal_cmd=["kubeseal", "--format=yaml"],
            )

            # Verify --merge-into flag was added
            call_args = mock_run.call_args
            cmd = call_args[0][0]
            assert "--merge-into" in cmd
            assert "existing-secret.yaml" in cmd

    def test_merge_secret_failure(self, tmp_path: Path) -> None:
        """Test error handling when merge fails."""
        temp_file = tmp_path / "temp_secret.yaml"
        temp_file.write_text("apiVersion: v1\nkind: Secret\n")

        with (
            patch("subprocess.run") as mock_run,
            patch("builtins.open", mock_open(read_data="")),
        ):
            mock_run.side_effect = subprocess.CalledProcessError(
                returncode=1, cmd=["kubeseal"], stderr=b"merge failed"
            )

            with pytest.raises(click.ClickException, match="Failed to merge secret"):
                merge_secret(
                    secret_name="existing.yaml",
                    temp_file_path=temp_file,
                    kubeseal_cmd=["kubeseal", "--format=yaml"],
                )


class TestReencryptSecrets:
    """Tests for reencrypt_secrets function."""

    def test_reencrypt_no_secrets_found(self, tmp_path: Path) -> None:
        """Test warning when no SealedSecrets are found and no subprocess is spawned."""
        with (
            patch("kubeseal_auto.secrets.sealing._find_sealed_secrets", return_value=[]),
            patch("subprocess.run") as mock_run,
        ):
            reencrypt_secrets(src=str(tmp_path), kubeseal_cmd=["kubeseal"])
            mock_run.assert_not_called()

    def test_reencrypt_success(self, tmp_path: Path) -> None:
        """Test successful re-encryption of secrets."""
        secret_file = tmp_path / "secret.yaml"
        secret_file.write_text("apiVersion: bitnami.com/v1alpha1\nkind: SealedSecret\n")

        with (
            patch("kubeseal_auto.secrets.sealing._find_sealed_secrets", return_value=[secret_file]),
            patch("subprocess.run") as mock_run,
            patch("kubeseal_auto.secrets.sealing.append_argo_annotation"),
        ):
            mock_run.return_value = MagicMock(returncode=0)

            reencrypt_secrets(
                src=str(tmp_path),
                kubeseal_cmd=["kubeseal", "--format=yaml"],
            )

            mock_run.assert_called_once()

    def test_reencrypt_failure_restores_backup(self, tmp_path: Path) -> None:
        """Test that original file is restored from backup on failure."""
        secret_file = tmp_path / "secret.yaml"
        original_content = "apiVersion: bitnami.com/v1alpha1\nkind: SealedSecret\noriginal: true\n"
        secret_file.write_text(original_content)

        with (
            patch("kubeseal_auto.secrets.sealing._find_sealed_secrets", return_value=[secret_file]),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.side_effect = subprocess.CalledProcessError(
                returncode=1, cmd=["kubeseal"], stderr=b"re-encrypt failed"
            )

            with pytest.raises(click.ClickException, match="Failed to re-encrypt"):
                reencrypt_secrets(
                    src=str(tmp_path),
                    kubeseal_cmd=["kubeseal", "--format=yaml"],
                )

            # Original content should be restored
            assert secret_file.read_text() == original_content


class TestFetchCertificate:
    """Tests for fetch_certificate function."""

    def test_fetch_certificate_success(self) -> None:
        """Test successful certificate fetch."""
        with (
            patch("subprocess.run") as mock_run,
            patch("builtins.open", mock_open()),
        ):
            mock_run.return_value = MagicMock(returncode=0)

            fetch_certificate(
                binary="kubeseal",
                controller_namespace="kube-system",
                controller_name="sealed-secrets",
                context_name="test-context",
            )

            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]
            assert "--fetch-cert" in call_args

    def test_fetch_certificate_failure(self) -> None:
        """Test error handling when certificate fetch fails."""
        with (
            patch("subprocess.run") as mock_run,
            patch("builtins.open", mock_open()),
        ):
            mock_run.side_effect = subprocess.CalledProcessError(
                returncode=1, cmd=["kubeseal"], stderr=b"connection refused"
            )

            with pytest.raises(click.ClickException, match="Failed to fetch certificate"):
                fetch_certificate(
                    binary="kubeseal",
                    controller_namespace="kube-system",
                    controller_name="sealed-secrets",
                    context_name="test-context",
                )


class TestBackupControllerSecret:
    """Tests for backup_controller_secret function."""

    def test_backup_success(self) -> None:
        """Test successful backup of controller secret."""
        with (
            patch("subprocess.run") as mock_run,
            patch("builtins.open", mock_open()),
        ):
            mock_run.return_value = MagicMock(returncode=0)

            backup_controller_secret(
                controller_namespace="kube-system",
                secret_name="sealed-secrets-key",
                context_name="test-context",
            )

            mock_run.assert_called_once()

    def test_backup_failure(self) -> None:
        """Test error handling when backup fails."""
        with (
            patch("subprocess.run") as mock_run,
            patch("builtins.open", mock_open()),
        ):
            mock_run.side_effect = subprocess.CalledProcessError(
                returncode=1, cmd=["kubectl"], stderr=b"not found"
            )

            with pytest.raises(click.ClickException, match="Failed to backup secret"):
                backup_controller_secret(
                    controller_namespace="kube-system",
                    secret_name="sealed-secrets-key",
                    context_name="test-context",
                )


class TestFindSealedSecrets:
    """Tests for _find_sealed_secrets function."""

    def test_find_sealed_secrets(self, tmp_path: Path) -> None:
        """Test finding SealedSecret files in a directory."""
        sealed = tmp_path / "sealed.yaml"
        sealed.write_text("apiVersion: bitnami.com/v1alpha1\nkind: SealedSecret\nmetadata:\n  name: test\n")

        regular = tmp_path / "regular.yaml"
        regular.write_text("apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: test\n")

        invalid = tmp_path / "invalid.yaml"
        invalid.write_text("not: valid: yaml: [")

        result = _find_sealed_secrets(str(tmp_path))

        assert len(result) == 1
        assert result[0].name == "sealed.yaml"

    def test_find_sealed_secrets_empty_directory(self, tmp_path: Path) -> None:
        """Test with empty directory."""
        result = _find_sealed_secrets(str(tmp_path))
        assert result == []
