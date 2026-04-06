"""Fixtures for end-to-end tests.

These fixtures provide a shared working directory, kind cluster context,
and paths to artifacts produced by sequential e2e test flows.
"""

import os
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

# Default kind cluster context name created by helm/kind-action
KIND_CONTEXT = "kind-chart-testing"


def _cluster_is_reachable() -> bool:
    """Check whether a Kubernetes cluster is reachable."""
    try:
        subprocess.run(
            ["kubectl", "cluster-info"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False
    return True


@pytest.fixture(autouse=True, scope="session")
def _require_cluster() -> None:
    """Skip the entire e2e session when no live cluster is available."""
    if not _cluster_is_reachable():
        pytest.skip("No reachable Kubernetes cluster — skipping e2e tests")


@pytest.fixture(scope="session")
def e2e_workdir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Create a shared temporary working directory for all e2e tests."""
    workdir: Path = tmp_path_factory.mktemp("e2e")
    return workdir


@pytest.fixture(scope="session")
def kind_context() -> str:
    """Return the kind cluster context name."""
    return KIND_CONTEXT


@pytest.fixture(scope="session")
def kubeseal_on_path() -> Iterator[None]:
    """Ensure a bare ``kubeseal`` symlink exists in the managed bin directory.

    kubeseal-auto stores downloaded binaries as ``kubeseal-{version}``
    under its managed bin directory.  Detached mode expects a bare
    ``kubeseal`` on PATH, so this fixture creates a symlink next to
    the versioned binary and removes it on teardown.

    Must be requested after a connected-mode test has already triggered
    the binary download.
    """
    xdg_data_home = os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))
    bin_dir = Path(xdg_data_home) / "kubeseal-auto" / "bin"

    if not bin_dir.is_dir():
        pytest.skip("kubeseal-auto managed bin directory does not exist — run a connected-mode test first")

    symlink = bin_dir / "kubeseal"
    created = False
    if not symlink.exists():
        versioned = sorted(bin_dir.glob("kubeseal-*"))
        if not versioned:
            pytest.skip("No versioned kubeseal binary found in managed bin directory")
        symlink.symlink_to(versioned[-1].name)
        created = True

    yield

    if created and symlink.is_symlink():
        symlink.unlink()


@pytest.fixture(scope="session")
def spawn_env() -> dict[str, str]:
    """Build an environment dict suitable for pexpect spawns.

    Suppresses Rich/ANSI formatting and prevents line-wrapping
    so that pexpect pattern matching is reliable. Also adds the
    kubeseal-auto managed binary directory to PATH so that detached
    mode can find a previously downloaded kubeseal binary.
    """
    env = os.environ.copy()

    # kubeseal-auto stores downloaded binaries under XDG_DATA_HOME/kubeseal-auto/bin/
    xdg_data_home = env.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))
    managed_bin_dir = str(Path(xdg_data_home) / "kubeseal-auto" / "bin")
    env["PATH"] = managed_bin_dir + os.pathsep + env.get("PATH", "")

    env.update(
        {
            "TERM": "dumb",
            "COLUMNS": "200",
            "NO_COLOR": "1",
        }
    )
    return env
