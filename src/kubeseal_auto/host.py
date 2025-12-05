"""Host system utilities for kubeseal-auto.

This module provides the Host class for managing kubeseal binary
downloads and platform detection.
"""

import os
import platform
import re
import tarfile
import tempfile

import click
import requests
from icecream import ic

from kubeseal_auto.exceptions import BinaryNotFoundError, UnsupportedPlatformError

# Semantic version pattern for validation
_SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+(?:-[\w.]+)?(?:\+[\w.]+)?$")


def normalize_version(version: str) -> str:
    """Normalize a version string by removing a leading 'v' prefix if present.

    This is a module-level utility for consistent version normalization
    across the codebase.

    Args:
        version: The version string (e.g., 'v0.26.0' or '0.26.0').

    Returns:
        The version string without leading 'v' (e.g., '0.26.0').

    Raises:
        ValueError: If version is None, empty, or doesn't match semantic versioning.
    """
    if not version:
        raise ValueError("Version string cannot be None or empty")

    # Remove only a single leading 'v' if present
    normalized = version[1:] if version.startswith("v") else version

    if not normalized:
        raise ValueError(f"Invalid version string: '{version}' results in empty version after normalization")

    if not _SEMVER_PATTERN.match(normalized):
        raise ValueError(f"Invalid version format: '{normalized}' does not match semantic versioning pattern")

    return normalized


class Host:
    """Manages host system operations for kubeseal binary management.

    This class handles platform detection and kubeseal binary downloads
    from the sealed-secrets GitHub releases.

    Attributes:
        base_url: Base URL for sealed-secrets releases.
        bin_location: Local directory for storing kubeseal binaries.
        cpu_type: Detected CPU architecture (amd64 or arm64).
        system: Detected operating system (linux or darwin).
    """

    def __init__(self) -> None:
        """Initialize Host with platform detection."""
        self.base_url: str = "https://github.com/bitnami-labs/sealed-secrets/releases/download"
        self.bin_location: str = os.path.join(
            os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share")),
            "kubeseal-auto",
            "bin",
        )
        self.cpu_type: str = self._get_cpu_type()
        self.system: str = self._get_system_type()

    @staticmethod
    def _get_cpu_type() -> str:
        """Detect and return the CPU architecture.

        Returns:
            The CPU type as a string ('amd64' or 'arm64').

        Raises:
            UnsupportedPlatformError: If the CPU architecture is not supported.
        """
        match platform.machine():
            case "x86_64":
                return "amd64"
            case "arm64" | "aarch64":
                return "arm64"
            case _:
                raise UnsupportedPlatformError(f"Unsupported CPU architecture: {platform.machine()}")

    @staticmethod
    def _get_system_type() -> str:
        """Detect and return the operating system type.

        Returns:
            The OS type as a string ('linux' or 'darwin').

        Raises:
            UnsupportedPlatformError: If the operating system is not supported.
        """
        match platform.system():
            case "Linux":
                return "linux"
            case "Darwin":
                return "darwin"
            case _:
                raise UnsupportedPlatformError(f"Unsupported operating system: {platform.system()}")

    @staticmethod
    def _normalize_version(version: str) -> str:
        """Normalize a version string by removing the 'v' prefix if present.

        This method delegates to the module-level normalize_version function.

        Args:
            version: The version string (e.g., 'v0.26.0' or '0.26.0').

        Returns:
            The version string without 'v' prefix (e.g., '0.26.0').

        Raises:
            ValueError: If version is None, empty, or doesn't match semantic versioning.
        """
        return normalize_version(version)

    def _download_kubeseal_binary(self, version: str) -> None:
        """Download the kubeseal binary for the specified version.

        Args:
            version: The version of kubeseal to download (may include 'v' prefix).

        Raises:
            BinaryNotFoundError: If the requested version is not available.
            ValueError: If version format is invalid.
        """
        click.echo("Downloading kubeseal binary")

        normalized = self._normalize_version(version)
        url = f"{self.base_url}/v{normalized}/kubeseal-{normalized}-{self.system}-{self.cpu_type}.tar.gz"
        ic(url)
        local_path = os.path.join(
            tempfile.gettempdir(),
            f"kubeseal-{normalized}-{self.system}-{self.cpu_type}.tar.gz",
        )
        ic(local_path)

        if not os.path.exists(self.bin_location):
            os.makedirs(self.bin_location)

        click.echo(f"Downloading {url}")
        with requests.get(url, timeout=60) as r:
            if r.status_code == 404:
                raise BinaryNotFoundError(f"kubeseal version {normalized} is not available for download")
            r.raise_for_status()
            with open(local_path, "wb") as f:
                f.write(r.content)

        try:
            with tarfile.open(local_path, "r:gz") as tar:
                self._safe_extract_kubeseal(tar, normalized)
        finally:
            # Always clean up the temporary tarball, even if extraction fails
            try:
                if os.path.exists(local_path):
                    os.remove(local_path)
            except OSError:
                pass  # Suppress removal errors to not mask original exception

    @staticmethod
    def _find_kubeseal_member(tar: tarfile.TarFile) -> tarfile.TarInfo | None:
        """Find the kubeseal binary member in a tar archive.

        Args:
            tar: The open TarFile object to search.

        Returns:
            The TarInfo for the kubeseal binary if found, None otherwise.
        """
        for member in tar.getmembers():
            if member.name == "kubeseal" and member.isfile():
                return member
        return None

    def _safe_extract_kubeseal(self, tar: tarfile.TarFile, version: str) -> None:
        """Safely extract the kubeseal binary from a tar archive.

        Uses tarfile.data_filter when available (Python 3.12+) for enhanced
        security against path traversal attacks. Falls back to manual safe
        checks for older Python versions.

        Args:
            tar: The open TarFile object to extract from.
            version: The version string for naming the extracted binary.

        Raises:
            ValueError: If the kubeseal binary is not found in the archive
                       or if path traversal is detected.
        """
        member = self._find_kubeseal_member(tar)
        if member is None:
            raise ValueError(f"kubeseal binary not found in archive for version {version}")

        target_name = f"kubeseal-{version}"
        member.name = target_name

        # Check if data_filter is available (Python 3.12+)
        if hasattr(tarfile, "data_filter"):
            # Use the safe data_filter for extraction
            tar.extract(member, path=self.bin_location, filter="data")
        else:
            # Fallback for Python < 3.12: manual safe extraction
            # Verify the extraction path stays within bin_location
            extract_path = os.path.realpath(os.path.join(self.bin_location, target_name))
            bin_location_real = os.path.realpath(self.bin_location)
            if not extract_path.startswith(bin_location_real + os.sep):
                raise ValueError(f"Path traversal detected: {extract_path}")

            tar.extract(member, path=self.bin_location)

    def get_binary_path(self, version: str) -> str:
        """Get the path to the kubeseal binary for the specified version.

        Args:
            version: The version of kubeseal (may include 'v' prefix).

        Returns:
            The full path to the kubeseal binary.
        """
        normalized = self._normalize_version(version)
        return f"{self.bin_location}/kubeseal-{normalized}"

    def ensure_kubeseal_binary(self, version: str) -> None:
        """Ensure the kubeseal binary for the specified version exists.

        Downloads the binary if it doesn't exist locally.

        Args:
            version: The version of kubeseal to ensure (may include 'v' prefix).

        Raises:
            BinaryNotFoundError: If the binary cannot be downloaded.
            ValueError: If version format is invalid.
        """
        binary_path = self.get_binary_path(version)
        if not os.path.exists(binary_path):
            click.echo(f"kubeseal binary not found at {binary_path}")
            self._download_kubeseal_binary(version)
