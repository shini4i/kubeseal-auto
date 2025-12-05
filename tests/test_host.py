"""Tests for host.py module."""

import os
from unittest.mock import MagicMock, patch

import pytest

from kubeseal_auto.exceptions import BinaryNotFoundError, UnsupportedPlatformError
from kubeseal_auto.host import Host


class TestHostPlatformDetection:
    """Tests for platform detection."""

    def test_get_cpu_type_x86_64(self):
        """Test detection of x86_64 CPU."""
        with patch("kubeseal_auto.host.platform.machine", return_value="x86_64"):
            result = Host._get_cpu_type()
            assert result == "amd64"

    def test_get_cpu_type_arm64(self):
        """Test detection of arm64 CPU."""
        with patch("kubeseal_auto.host.platform.machine", return_value="arm64"):
            result = Host._get_cpu_type()
            assert result == "arm64"

    def test_get_cpu_type_aarch64(self):
        """Test detection of aarch64 CPU (common Linux ARM variant)."""
        with patch("kubeseal_auto.host.platform.machine", return_value="aarch64"):
            result = Host._get_cpu_type()
            assert result == "arm64"

    def test_get_cpu_type_unsupported(self):
        """Test error on unsupported CPU architecture."""
        with patch("kubeseal_auto.host.platform.machine", return_value="i386"):
            with pytest.raises(UnsupportedPlatformError) as exc_info:
                Host._get_cpu_type()
            assert "Unsupported CPU architecture" in str(exc_info.value)
            assert "i386" in str(exc_info.value)

    def test_get_system_type_linux(self):
        """Test detection of Linux system."""
        with patch("kubeseal_auto.host.platform.system", return_value="Linux"):
            result = Host._get_system_type()
            assert result == "linux"

    def test_get_system_type_darwin(self):
        """Test detection of macOS (Darwin) system."""
        with patch("kubeseal_auto.host.platform.system", return_value="Darwin"):
            result = Host._get_system_type()
            assert result == "darwin"

    def test_get_system_type_unsupported(self):
        """Test error on unsupported operating system."""
        with patch("kubeseal_auto.host.platform.system", return_value="Windows"):
            with pytest.raises(UnsupportedPlatformError) as exc_info:
                Host._get_system_type()
            assert "Unsupported operating system" in str(exc_info.value)
            assert "Windows" in str(exc_info.value)


class TestHostInit:
    """Tests for Host initialization."""

    def test_init_sets_correct_values(self):
        """Test that Host initializes with correct platform values."""
        with (
            patch("kubeseal_auto.host.platform.machine", return_value="x86_64"),
            patch("kubeseal_auto.host.platform.system", return_value="Linux"),
        ):
            host = Host()

            assert host.cpu_type == "amd64"
            assert host.system == "linux"
            # Verify XDG-compliant path structure (must match Host.__init__ exactly)
            expected_xdg_base = os.environ.get(
                "XDG_DATA_HOME", os.path.expanduser("~/.local/share")
            )
            expected_bin_path = os.path.join(expected_xdg_base, "kubeseal-auto", "bin")
            assert host.bin_location == expected_bin_path
            assert "github.com/bitnami-labs/sealed-secrets" in host.base_url


class TestHostBinaryManagement:
    """Tests for kubeseal binary management."""

    def test_ensure_kubeseal_binary_exists(self):
        """Test that no download is triggered when binary exists."""
        with (
            patch("kubeseal_auto.host.platform.machine", return_value="x86_64"),
            patch("kubeseal_auto.host.platform.system", return_value="Linux"),
            patch("os.path.exists", return_value=True),
        ):
            host = Host()

            with patch.object(host, "_download_kubeseal_binary") as mock_download:
                host.ensure_kubeseal_binary("0.26.0")
                mock_download.assert_not_called()

    def test_ensure_kubeseal_binary_downloads_when_missing(self):
        """Test that download is triggered when binary is missing."""
        with (
            patch("kubeseal_auto.host.platform.machine", return_value="x86_64"),
            patch("kubeseal_auto.host.platform.system", return_value="Linux"),
            patch("os.path.exists", return_value=False),
        ):
            host = Host()

            with patch.object(host, "_download_kubeseal_binary") as mock_download:
                host.ensure_kubeseal_binary("0.26.0")
                mock_download.assert_called_once_with("0.26.0")

    def test_ensure_kubeseal_binary_strips_v_prefix(self):
        """Test that version prefix 'v' is handled correctly.

        ensure_kubeseal_binary passes the version as-is to helper methods,
        which normalize internally.
        """
        with (
            patch("kubeseal_auto.host.platform.machine", return_value="x86_64"),
            patch("kubeseal_auto.host.platform.system", return_value="Linux"),
            patch("os.path.exists", return_value=False),
        ):
            host = Host()

            with patch.object(host, "_download_kubeseal_binary") as mock_download:
                host.ensure_kubeseal_binary("v0.26.0")
                # Version is passed as-is; _download_kubeseal_binary normalizes internally
                mock_download.assert_called_once_with("v0.26.0")

    def test_download_kubeseal_binary_success(self):
        """Test successful binary download."""
        with (
            patch("kubeseal_auto.host.platform.machine", return_value="x86_64"),
            patch("kubeseal_auto.host.platform.system", return_value="Linux"),
            patch("os.path.exists", return_value=False),
            patch("os.makedirs"),
            patch("os.rename"),
            patch("os.remove"),
        ):
            host = Host()

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.content = b"binary content"
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=False)

            with (
                patch("requests.get", return_value=mock_response),
                patch("builtins.open", MagicMock()),
                patch("tarfile.open") as mock_tarfile,
            ):
                mock_tar = MagicMock()
                mock_member = MagicMock()
                mock_member.name = "kubeseal"
                mock_member.isfile.return_value = True
                mock_tar.getmembers.return_value = [mock_member]
                mock_tar.__enter__ = MagicMock(return_value=mock_tar)
                mock_tar.__exit__ = MagicMock(return_value=False)
                mock_tarfile.return_value = mock_tar

                host._download_kubeseal_binary("0.26.0")

                # Verify tarfile extraction was called
                mock_tarfile.assert_called_once()
                mock_tar.extract.assert_called_once()

    def test_download_kubeseal_binary_version_not_found(self):
        """Test error when version is not available."""
        with (
            patch("kubeseal_auto.host.platform.machine", return_value="x86_64"),
            patch("kubeseal_auto.host.platform.system", return_value="Linux"),
            patch("os.path.exists", return_value=False),
            patch("os.makedirs"),
        ):
            host = Host()

            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=False)

            with (
                patch("requests.get", return_value=mock_response),
                pytest.raises(BinaryNotFoundError) as exc_info,
            ):
                host._download_kubeseal_binary("99.99.99")

            assert "not available" in str(exc_info.value)

    def test_download_creates_bin_directory(self):
        """Test that bin directory is created if it doesn't exist."""
        with (
            patch("kubeseal_auto.host.platform.machine", return_value="x86_64"),
            patch("kubeseal_auto.host.platform.system", return_value="Linux"),
        ):
            host = Host()

            # First call returns False (bin doesn't exist), second returns True (tar file)
            with (
                patch("os.path.exists", side_effect=[False, True]),
                patch("os.makedirs") as mock_makedirs,
                patch("os.rename"),
                patch("os.remove"),
            ):
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.content = b"binary content"
                mock_response.__enter__ = MagicMock(return_value=mock_response)
                mock_response.__exit__ = MagicMock(return_value=False)

                with (
                    patch("requests.get", return_value=mock_response),
                    patch("builtins.open", MagicMock()),
                    patch("tarfile.open") as mock_tarfile,
                ):
                    mock_tar = MagicMock()
                    mock_member = MagicMock()
                    mock_member.name = "kubeseal"
                    mock_member.isfile.return_value = True
                    mock_tar.getmembers.return_value = [mock_member]
                    mock_tar.__enter__ = MagicMock(return_value=mock_tar)
                    mock_tar.__exit__ = MagicMock(return_value=False)
                    mock_tarfile.return_value = mock_tar

                    host._download_kubeseal_binary("0.26.0")
                    mock_makedirs.assert_called_once()
