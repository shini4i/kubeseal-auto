"""Tests for kubeseal.py facade — fallback paths, guards, and cleanup."""

from unittest.mock import MagicMock, patch

import click
import pytest

from kubeseal_auto.core.kubeseal import Kubeseal
from kubeseal_auto.exceptions import BinaryNotFoundError


class TestKubesealFallbackToSystemBinary:
    """Tests for _fallback_to_system_binary."""

    def test_fallback_success(self, kubeseal_mocks: dict[str, MagicMock]) -> None:  # noqa: ARG002
        """Test fallback to system binary when version resolution fails."""
        with patch("shutil.which", return_value="/usr/bin/kubeseal"):
            kubeseal = Kubeseal(select_context=False)
            kubeseal._fallback_to_system_binary()

            assert kubeseal.binary == "/usr/bin/kubeseal"

    def test_fallback_binary_not_found(self, kubeseal_mocks: dict[str, MagicMock]) -> None:  # noqa: ARG002
        """Test BinaryNotFoundError when system kubeseal is missing."""
        kubeseal = Kubeseal(select_context=False)

        with (
            patch("shutil.which", return_value=None),
            pytest.raises(BinaryNotFoundError, match="kubeseal binary not found"),
        ):
            kubeseal._fallback_to_system_binary()

    def test_fallback_triggered_by_version_error(
        self, mock_kube_contexts: MagicMock, mock_kube_config: MagicMock, mock_namespaces: MagicMock  # noqa: ARG002
    ) -> None:
        """Test fallback is triggered when controller version resolution fails."""
        with (
            patch("kubeseal_auto.core.cluster.Cluster._find_sealed_secrets_controller") as mock_ctrl,
            patch("kubeseal_auto.core.host.Host.ensure_kubeseal_binary") as mock_ensure,
            patch("shutil.which", return_value="/usr/local/bin/kubeseal"),
        ):
            from kubeseal_auto.models import ControllerInfo

            mock_ctrl.return_value = ControllerInfo(
                name="sealed-secrets",
                namespace="kube-system",
                version="v0.26.0",
            )
            mock_ensure.side_effect = BinaryNotFoundError("download failed")

            kubeseal = Kubeseal(select_context=False)

            assert kubeseal.binary == "/usr/local/bin/kubeseal"


class TestKubesealDetachedModeGuards:
    """Tests for detached-mode guards on cluster-only operations."""

    def test_fetch_certificate_detached_mode_raises(self) -> None:
        """Test that fetch_certificate raises in detached mode."""
        kubeseal = Kubeseal(select_context=False, certificate="cert.crt")

        with pytest.raises(click.ClickException, match="not available in detached mode"):
            kubeseal.fetch_certificate()

    def test_backup_detached_mode_raises(self) -> None:
        """Test that backup raises in detached mode."""
        kubeseal = Kubeseal(select_context=False, certificate="cert.crt")

        with pytest.raises(click.ClickException, match="not available in detached mode"):
            kubeseal.backup()


class TestKubesealBuildCommand:
    """Tests for _build_kubeseal_cmd."""

    def test_build_cmd_connected_mode(self, kubeseal_mocks: dict[str, MagicMock]) -> None:  # noqa: ARG002
        """Test command building in connected mode."""
        kubeseal = Kubeseal(select_context=False)

        cmd = kubeseal._build_kubeseal_cmd()

        assert cmd[0] == kubeseal.binary
        assert "--format=yaml" in cmd
        assert any("--context=" in arg for arg in cmd)
        assert any("--controller-namespace=" in arg for arg in cmd)
        assert any("--controller-name=" in arg for arg in cmd)

    def test_build_cmd_detached_mode(self) -> None:
        """Test command building in detached mode."""
        kubeseal = Kubeseal(select_context=False, certificate="my-cert.crt")

        cmd = kubeseal._build_kubeseal_cmd()

        assert "--cert=my-cert.crt" in cmd
        assert not any("--context=" in arg for arg in cmd)

    def test_build_cmd_extra_args(self, kubeseal_mocks: dict[str, MagicMock]) -> None:  # noqa: ARG002
        """Test command building with extra arguments."""
        kubeseal = Kubeseal(select_context=False)

        cmd = kubeseal._build_kubeseal_cmd(extra_args=["--re-encrypt"])

        assert "--re-encrypt" in cmd


class TestKubesealCleanup:
    """Tests for temp file cleanup."""

    def test_context_manager_cleanup(self, kubeseal_mocks: dict[str, MagicMock]) -> None:  # noqa: ARG002
        """Test that context manager cleans up temp files."""
        with Kubeseal(select_context=False) as kubeseal:
            temp_path = kubeseal._temp_file_path
            assert temp_path.exists()

        assert not temp_path.exists()

    def test_cleanup_idempotent(self, kubeseal_mocks: dict[str, MagicMock]) -> None:  # noqa: ARG002
        """Test that cleanup can be called multiple times safely and removes the file."""
        kubeseal = Kubeseal(select_context=False)
        temp_path = kubeseal._temp_file_path
        assert temp_path.exists()

        kubeseal._cleanup_temp_file()
        assert not temp_path.exists()

        kubeseal._cleanup_temp_file()  # Should not raise
        assert not temp_path.exists()


class TestKubesealEmptyVersion:
    """Tests for empty version label handling."""

    def test_empty_version_falls_back_to_system(
        self, mock_kube_contexts: MagicMock, mock_kube_config: MagicMock, mock_namespaces: MagicMock  # noqa: ARG002
    ) -> None:
        """Test that empty controller version triggers system binary fallback."""
        with (
            patch("kubeseal_auto.core.cluster.Cluster._find_sealed_secrets_controller") as mock_ctrl,
            patch("shutil.which", return_value="/usr/bin/kubeseal"),
        ):
            from kubeseal_auto.models import ControllerInfo

            mock_ctrl.return_value = ControllerInfo(
                name="sealed-secrets",
                namespace="kube-system",
                version="",
            )

            kubeseal = Kubeseal(select_context=False)

            assert kubeseal.binary == "/usr/bin/kubeseal"
