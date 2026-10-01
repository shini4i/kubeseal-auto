"""Tests for secrets/sealing.py module."""

import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import patch

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

_RUN = "kubeseal_auto.secrets.command.subprocess.run"

_SECRET_PARAMS = SecretParams(
    name="test-secret",
    namespace="default",
    secret_type=SecretType.GENERIC,
)


def _write_stdout(text: str) -> Any:
    """Build a subprocess.run side effect that writes text to the stdout file."""

    def side_effect(*_args: Any, **kwargs: Any) -> None:
        kwargs["stdout"].write(text)

    return side_effect


class TestSealSecret:
    """Tests for seal_secret function."""

    def test_seal_secret_success(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that the sealed secret is written to <name>.yaml in the current directory."""
        monkeypatch.chdir(tmp_path)
        temp_file = tmp_path / "temp_secret.yaml"
        temp_file.write_text("apiVersion: v1\nkind: Secret\n")

        with (
            patch(_RUN, side_effect=_write_stdout("kind: SealedSecret\n")) as mock_run,
            patch("kubeseal_auto.secrets.sealing.append_argo_annotation"),
        ):
            seal_secret(
                secret_params=_SECRET_PARAMS,
                temp_file_path=temp_file,
                kubeseal_cmd=["kubeseal", "--format=yaml"],
            )

            mock_run.assert_called_once()
            assert mock_run.call_args.kwargs["input"] == temp_file.read_bytes()

        assert (tmp_path / "test-secret.yaml").read_text() == "kind: SealedSecret\n"

    def test_seal_secret_raises_on_failure(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that seal_secret raises ClickException and removes partial output on failure."""
        monkeypatch.chdir(tmp_path)
        temp_file = tmp_path / "temp_secret.yaml"
        temp_file.write_text("apiVersion: v1\nkind: Secret\n")
        error = subprocess.CalledProcessError(returncode=1, cmd=["kubeseal"], stderr=b"error: certificate expired")

        with (
            patch(_RUN, side_effect=error),
            pytest.raises(click.ClickException, match="Failed to seal secret"),
        ):
            seal_secret(
                secret_params=_SECRET_PARAMS,
                temp_file_path=temp_file,
                kubeseal_cmd=["kubeseal", "--format=yaml"],
            )

        assert not (tmp_path / "test-secret.yaml").exists()


class TestMergeSecret:
    """Tests for merge_secret function."""

    def test_merge_secret_success(self, tmp_path: Path) -> None:
        """Test successful secret merging."""
        temp_file = tmp_path / "temp_secret.yaml"
        temp_file.write_text("apiVersion: v1\nkind: Secret\n")

        with (
            patch(_RUN) as mock_run,
            patch("kubeseal_auto.secrets.sealing.append_argo_annotation"),
        ):
            merge_secret(
                secret_name="existing-secret.yaml",
                temp_file_path=temp_file,
                kubeseal_cmd=["kubeseal", "--format=yaml"],
            )

            cmd = mock_run.call_args[0][0]
            assert cmd[-2:] == ["--merge-into", "existing-secret.yaml"]
            assert mock_run.call_args.kwargs["input"] == temp_file.read_bytes()

    def test_merge_secret_failure(self, tmp_path: Path) -> None:
        """Test error handling when merge fails."""
        temp_file = tmp_path / "temp_secret.yaml"
        temp_file.write_text("apiVersion: v1\nkind: Secret\n")
        error = subprocess.CalledProcessError(returncode=1, cmd=["kubeseal"], stderr=b"merge failed")

        with (
            patch(_RUN, side_effect=error),
            pytest.raises(click.ClickException, match="Failed to merge secret"),
        ):
            merge_secret(
                secret_name="existing.yaml",
                temp_file_path=temp_file,
                kubeseal_cmd=["kubeseal", "--format=yaml"],
            )


class TestReencryptSecrets:
    """Tests for reencrypt_secrets function."""

    original_content = "apiVersion: bitnami.com/v1alpha1\nkind: SealedSecret\noriginal: true\n"

    def test_reencrypt_no_secrets_found(self, tmp_path: Path) -> None:
        """Test warning when no SealedSecrets are found and no subprocess is spawned."""
        with (
            patch("kubeseal_auto.secrets.sealing._find_sealed_secrets", return_value=[]),
            patch(_RUN) as mock_run,
        ):
            reencrypt_secrets(src=str(tmp_path), kubeseal_cmd=["kubeseal"])
            mock_run.assert_not_called()

    def test_reencrypt_success(self, tmp_path: Path) -> None:
        """Test that the file is replaced with re-encrypted output and no helper files remain."""
        secret_file = tmp_path / "secret.yaml"
        secret_file.write_text(self.original_content)

        with (
            patch("kubeseal_auto.secrets.sealing._find_sealed_secrets", return_value=[secret_file]),
            patch(_RUN, side_effect=_write_stdout("reencrypted\n")),
            patch("kubeseal_auto.secrets.sealing.append_argo_annotation"),
        ):
            reencrypt_secrets(src=str(tmp_path), kubeseal_cmd=["kubeseal", "--format=yaml"])

        assert secret_file.read_text() == "reencrypted\n"
        assert sorted(p.name for p in tmp_path.iterdir()) == ["secret.yaml"]

    @pytest.mark.parametrize(
        ("side_effect", "message"),
        [
            (subprocess.CalledProcessError(returncode=1, cmd=["kubeseal"], stderr=b"re-encrypt failed"), "Failed to re-encrypt"),
            (FileNotFoundError(), "kubeseal not found"),
        ],
        ids=["command-fails", "binary-missing"],
    )
    def test_reencrypt_failure_restores_backup(self, tmp_path: Path, side_effect: Exception, message: str) -> None:
        """Test that the original file is restored and no helper files remain on any failure."""
        secret_file = tmp_path / "secret.yaml"
        secret_file.write_text(self.original_content)

        with (
            patch("kubeseal_auto.secrets.sealing._find_sealed_secrets", return_value=[secret_file]),
            patch(_RUN, side_effect=side_effect),
            pytest.raises(click.ClickException, match=message),
        ):
            reencrypt_secrets(src=str(tmp_path), kubeseal_cmd=["kubeseal", "--format=yaml"])

        assert secret_file.read_text() == self.original_content
        assert sorted(p.name for p in tmp_path.iterdir()) == ["secret.yaml"]


class TestFetchCertificate:
    """Tests for fetch_certificate function."""

    def test_fetch_certificate_success(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test successful certificate fetch."""
        monkeypatch.chdir(tmp_path)

        with patch(_RUN, side_effect=_write_stdout("CERT\n")) as mock_run:
            fetch_certificate(
                binary="kubeseal",
                controller_namespace="kube-system",
                controller_name="sealed-secrets",
                context_name="test-context",
            )

            assert "--fetch-cert" in mock_run.call_args[0][0]

        assert (tmp_path / "test-context-kubeseal-cert.crt").read_text() == "CERT\n"

    def test_fetch_certificate_failure(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test error handling when certificate fetch fails."""
        monkeypatch.chdir(tmp_path)
        error = subprocess.CalledProcessError(returncode=1, cmd=["kubeseal"], stderr=b"connection refused")

        with (
            patch(_RUN, side_effect=error),
            pytest.raises(click.ClickException, match="Failed to fetch certificate"),
        ):
            fetch_certificate(
                binary="kubeseal",
                controller_namespace="kube-system",
                controller_name="sealed-secrets",
                context_name="test-context",
            )

        assert not (tmp_path / "test-context-kubeseal-cert.crt").exists()

    def test_fetch_certificate_eks_context_writes_flat_filename(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that an EKS ARN context name produces a writable file in the current directory."""
        monkeypatch.chdir(tmp_path)

        with patch(_RUN) as mock_run:
            fetch_certificate(
                binary="kubeseal",
                controller_namespace="kube-system",
                controller_name="sealed-secrets",
                context_name="arn:aws:eks:us-east-1:123456789012:cluster/prod",
            )

            assert "--context=arn:aws:eks:us-east-1:123456789012:cluster/prod" in mock_run.call_args[0][0]

        assert (tmp_path / "arn_aws_eks_us-east-1_123456789012_cluster_prod-kubeseal-cert.crt").exists()


class TestBackupControllerSecret:
    """Tests for backup_controller_secret function."""

    def test_backup_success(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test successful backup of controller secret."""
        monkeypatch.chdir(tmp_path)

        with patch(_RUN, side_effect=_write_stdout("kind: Secret\n")):
            backup_controller_secret(
                controller_namespace="kube-system",
                secret_name="sealed-secrets-key",
                context_name="test-context",
            )

        assert (tmp_path / "test-context-secret-backup.yaml").read_text() == "kind: Secret\n"

    def test_backup_failure(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test error handling when backup fails."""
        monkeypatch.chdir(tmp_path)
        error = subprocess.CalledProcessError(returncode=1, cmd=["kubectl"], stderr=b"not found")

        with (
            patch(_RUN, side_effect=error),
            pytest.raises(click.ClickException, match="Failed to backup secret"),
        ):
            backup_controller_secret(
                controller_namespace="kube-system",
                secret_name="sealed-secrets-key",
                context_name="test-context",
            )

        assert not (tmp_path / "test-context-secret-backup.yaml").exists()

    def test_backup_eks_context_writes_flat_filename(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that an EKS ARN context name produces a writable backup file."""
        monkeypatch.chdir(tmp_path)

        with patch(_RUN):
            backup_controller_secret(
                controller_namespace="kube-system",
                secret_name="sealed-secrets-key",
                context_name="arn:aws:eks:us-east-1:123456789012:cluster/prod",
            )

        assert (tmp_path / "arn_aws_eks_us-east-1_123456789012_cluster_prod-secret-backup.yaml").exists()

    def test_backup_missing_kubectl(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that a missing kubectl binary gives a readable error instead of a traceback."""
        monkeypatch.chdir(tmp_path)

        with (
            patch(_RUN, side_effect=FileNotFoundError),
            pytest.raises(click.ClickException, match="kubectl not found"),
        ):
            backup_controller_secret(
                controller_namespace="kube-system",
                secret_name="sealed-secrets-key",
                context_name="test-context",
            )

        assert not (tmp_path / "test-context-secret-backup.yaml").exists()


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


class TestBackupContextAndPermissions:
    """Tests for backup_controller_secret context targeting and file permissions."""

    def test_backup_targets_given_context(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that kubectl is pointed at the selected context, not kubectl's current-context."""
        monkeypatch.chdir(tmp_path)

        with patch(_RUN) as mock_run:
            backup_controller_secret(
                controller_namespace="kube-system",
                secret_name="sealed-secrets-key",
                context_name="cluster-b",
            )

        assert "--context=cluster-b" in mock_run.call_args[0][0]

    def test_backup_file_is_owner_only(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that the private-key backup is readable only by its owner."""
        monkeypatch.chdir(tmp_path)

        with patch(_RUN):
            backup_controller_secret(
                controller_namespace="kube-system",
                secret_name="sealed-secrets-key",
                context_name="test-context",
            )

        assert (tmp_path / "test-context-secret-backup.yaml").stat().st_mode & 0o777 == 0o600
