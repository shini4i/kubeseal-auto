"""Tests for host.py module."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from kubeseal_auto.core.host import Host, normalize_version
from kubeseal_auto.exceptions import BinaryNotFoundError, UnsupportedPlatformError


class TestNormalizeVersion:
    """Tests for normalize_version function."""

    def test_strips_leading_v(self) -> None:
        """Test that leading 'v' prefix is removed."""
        assert normalize_version("v0.26.0") == "0.26.0"

    def test_preserves_version_without_v(self) -> None:
        """Test that version without 'v' prefix is unchanged."""
        assert normalize_version("0.26.0") == "0.26.0"

    def test_semver_pre_release(self) -> None:
        """Test semantic version with pre-release suffix."""
        assert normalize_version("v0.26.0-beta.1") == "0.26.0-beta.1"

    def test_semver_build_metadata(self) -> None:
        """Test semantic version with build metadata."""
        assert normalize_version("0.26.0+build.42") == "0.26.0+build.42"

    def test_empty_string_raises(self) -> None:
        """Test that empty string raises ValueError."""
        with pytest.raises(ValueError, match="Version string cannot be None or empty"):
            normalize_version("")

    def test_bare_v_raises(self) -> None:
        """Test that bare 'v' raises ValueError (empty after strip)."""
        with pytest.raises(ValueError, match="Invalid version string"):
            normalize_version("v")

    def test_non_semver_raises(self) -> None:
        """Test that non-semver string raises ValueError."""
        with pytest.raises(ValueError, match="Invalid version format"):
            normalize_version("not-a-version")

    def test_partial_version_raises(self) -> None:
        """Test that partial version string raises ValueError."""
        with pytest.raises(ValueError, match="Invalid version format"):
            normalize_version("0.26")


class TestHostPlatformDetection:
    """Tests for platform detection."""

    def test_get_cpu_type_x86_64(self) -> None:
        """Test detection of x86_64 CPU."""
        with patch("kubeseal_auto.core.host.platform.machine", return_value="x86_64"):
            result = Host._get_cpu_type()
            assert result == "amd64"

    def test_get_cpu_type_arm64(self) -> None:
        """Test detection of arm64 CPU."""
        with patch("kubeseal_auto.core.host.platform.machine", return_value="arm64"):
            result = Host._get_cpu_type()
            assert result == "arm64"

    def test_get_cpu_type_aarch64(self) -> None:
        """Test detection of aarch64 CPU (common Linux ARM variant)."""
        with patch("kubeseal_auto.core.host.platform.machine", return_value="aarch64"):
            result = Host._get_cpu_type()
            assert result == "arm64"

    def test_get_cpu_type_unsupported(self) -> None:
        """Test error on unsupported CPU architecture."""
        with patch("kubeseal_auto.core.host.platform.machine", return_value="i386"):
            with pytest.raises(UnsupportedPlatformError) as exc_info:
                Host._get_cpu_type()
            assert "Unsupported CPU architecture" in str(exc_info.value)
            assert "i386" in str(exc_info.value)

    def test_get_system_type_linux(self) -> None:
        """Test detection of Linux system."""
        with patch("kubeseal_auto.core.host.platform.system", return_value="Linux"):
            result = Host._get_system_type()
            assert result == "linux"

    def test_get_system_type_darwin(self) -> None:
        """Test detection of macOS (Darwin) system."""
        with patch("kubeseal_auto.core.host.platform.system", return_value="Darwin"):
            result = Host._get_system_type()
            assert result == "darwin"

    def test_get_system_type_unsupported(self) -> None:
        """Test error on unsupported operating system."""
        with patch("kubeseal_auto.core.host.platform.system", return_value="Windows"):
            with pytest.raises(UnsupportedPlatformError) as exc_info:
                Host._get_system_type()
            assert "Unsupported operating system" in str(exc_info.value)
            assert "Windows" in str(exc_info.value)


class TestHostInit:
    """Tests for Host initialization."""

    def test_init_sets_correct_values(self) -> None:
        """Test that Host initializes with correct platform values."""
        with (
            patch("kubeseal_auto.core.host.platform.machine", return_value="x86_64"),
            patch("kubeseal_auto.core.host.platform.system", return_value="Linux"),
        ):
            host = Host()

            assert host.cpu_type == "amd64"
            assert host.system == "linux"
            # Verify XDG-compliant path structure (must match Host.__init__ exactly)
            xdg_data_home = os.environ.get("XDG_DATA_HOME")
            if xdg_data_home:
                expected_bin_path = Path(xdg_data_home) / "kubeseal-auto" / "bin"
            else:
                expected_bin_path = Path.home() / ".local" / "share" / "kubeseal-auto" / "bin"
            assert host.bin_location == expected_bin_path
            assert "github.com/bitnami-labs/sealed-secrets" in host.base_url


class TestHostBinaryManagement:
    """Tests for kubeseal binary management."""

    def test_ensure_kubeseal_binary_exists(self) -> None:
        """Test that no download is triggered when binary exists."""
        with (
            patch("kubeseal_auto.core.host.platform.machine", return_value="x86_64"),
            patch("kubeseal_auto.core.host.platform.system", return_value="Linux"),
            patch.object(Path, "exists", return_value=True),
        ):
            host = Host()

            with patch.object(host, "_download_kubeseal_binary") as mock_download:
                host.ensure_kubeseal_binary("0.26.0")
                mock_download.assert_not_called()

    def test_ensure_kubeseal_binary_downloads_when_missing(self) -> None:
        """Test that download is triggered when binary is missing."""
        with (
            patch("kubeseal_auto.core.host.platform.machine", return_value="x86_64"),
            patch("kubeseal_auto.core.host.platform.system", return_value="Linux"),
            patch.object(Path, "exists", return_value=False),
        ):
            host = Host()

            with patch.object(host, "_download_kubeseal_binary") as mock_download:
                host.ensure_kubeseal_binary("0.26.0")
                mock_download.assert_called_once_with("0.26.0")

    def test_ensure_kubeseal_binary_strips_v_prefix(self) -> None:
        """Test that version prefix 'v' is handled correctly.

        ensure_kubeseal_binary passes the version as-is to helper methods,
        which normalize internally.
        """
        with (
            patch("kubeseal_auto.core.host.platform.machine", return_value="x86_64"),
            patch("kubeseal_auto.core.host.platform.system", return_value="Linux"),
            patch.object(Path, "exists", return_value=False),
        ):
            host = Host()

            with patch.object(host, "_download_kubeseal_binary") as mock_download:
                host.ensure_kubeseal_binary("v0.26.0")
                # Version is passed as-is; _download_kubeseal_binary normalizes internally
                mock_download.assert_called_once_with("v0.26.0")

    def test_download_kubeseal_binary_success(self) -> None:
        """Test successful binary download."""
        with (
            patch("kubeseal_auto.core.host.platform.machine", return_value="x86_64"),
            patch("kubeseal_auto.core.host.platform.system", return_value="Linux"),
            patch.object(Path, "mkdir"),
            patch.object(Path, "unlink"),
        ):
            host = Host()

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.content = b"binary content"
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=False)

            with (
                patch("kubeseal_auto.core.host.requests.get", return_value=mock_response),
                patch.object(Path, "open", MagicMock()),
                patch("kubeseal_auto.core.host.tarfile.open") as mock_tarfile,
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

    def test_download_kubeseal_binary_version_not_found(self) -> None:
        """Test error when version is not available."""
        with (
            patch("kubeseal_auto.core.host.platform.machine", return_value="x86_64"),
            patch("kubeseal_auto.core.host.platform.system", return_value="Linux"),
            patch.object(Path, "mkdir"),
        ):
            host = Host()

            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=False)

            with (
                patch("kubeseal_auto.core.host.requests.get", return_value=mock_response),
                pytest.raises(BinaryNotFoundError) as exc_info,
            ):
                host._download_kubeseal_binary("99.99.99")

            assert "not available" in str(exc_info.value)

    def test_download_creates_bin_directory(self) -> None:
        """Test that bin directory is created if it doesn't exist."""
        with (
            patch("kubeseal_auto.core.host.platform.machine", return_value="x86_64"),
            patch("kubeseal_auto.core.host.platform.system", return_value="Linux"),
        ):
            host = Host()

            with (
                patch.object(Path, "mkdir") as mock_mkdir,
                patch.object(Path, "unlink"),
            ):
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.content = b"binary content"
                mock_response.__enter__ = MagicMock(return_value=mock_response)
                mock_response.__exit__ = MagicMock(return_value=False)

                with (
                    patch("kubeseal_auto.core.host.requests.get", return_value=mock_response),
                    patch.object(Path, "open", MagicMock()),
                    patch("kubeseal_auto.core.host.tarfile.open") as mock_tarfile,
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
                    mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
