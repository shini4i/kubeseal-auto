"""Fixtures for end-to-end tests.

These fixtures provide a shared working directory, kind cluster context,
and paths to artifacts produced by sequential e2e test flows.
"""

import os
import subprocess
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
def spawn_env() -> dict[str, str]:
    """Build an environment dict suitable for pexpect spawns.

    Suppresses Rich/ANSI formatting and prevents line-wrapping
    so that pexpect pattern matching is reliable.
    """
    env = os.environ.copy()
    env.update(
        {
            "TERM": "dumb",
            "COLUMNS": "200",
            "NO_COLOR": "1",
        }
    )
    return env
