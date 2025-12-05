"""Host system utilities for kubeseal-auto.

This module provides the Host class for managing kubeseal binary
downloads and platform detection.
"""

import os
import platform
import tarfile
import tempfile

import click
import requests
from icecream import ic

from kubeseal_auto.exceptions import BinaryNotFoundError, UnsupportedPlatformError


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

        Args:
            version: The version string (e.g., 'v0.26.0' or '0.26.0').

        Returns:
            The version string without 'v' prefix (e.g., '0.26.0').
        """
        return version.split("v")[-1]

    def _download_kubeseal_binary(self, version: str) -> None:
        """Download the kubeseal binary for the specified version.

        Args:
            version: The version of kubeseal to download (without 'v' prefix).

        Raises:
            BinaryNotFoundError: If the requested version is not available.
        """
        click.echo("Downloading kubeseal binary")

        url = f"{self.base_url}/v{version}/kubeseal-{version}-{self.system}-{self.cpu_type}.tar.gz"
        ic(url)
        local_path = os.path.join(
            tempfile.gettempdir(),
            f"kubeseal-{version}-{self.system}-{self.cpu_type}.tar.gz",
        )
        ic(local_path)

        if not os.path.exists(self.bin_location):
            os.makedirs(self.bin_location)

        click.echo(f"Downloading {url}")
        with requests.get(url, timeout=60) as r:
            if r.status_code == 404:
                raise BinaryNotFoundError(f"kubeseal version {version} is not available for download")
            r.raise_for_status()
            with open(local_path, "wb") as f:
                f.write(r.content)

        with tarfile.open(local_path, "r:gz") as tar:
            # Extract only the kubeseal binary, filtering for security
            for member in tar.getmembers():
                if member.name == "kubeseal" and member.isfile():
                    member.name = f"kubeseal-{version}"
                    tar.extract(member, path=self.bin_location)
                    break

        os.remove(local_path)

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
        """
        normalized = self._normalize_version(version)
        binary_path = self.get_binary_path(normalized)
        if not os.path.exists(binary_path):
            click.echo(f"kubeseal binary not found at {binary_path}")
            self._download_kubeseal_binary(normalized)
