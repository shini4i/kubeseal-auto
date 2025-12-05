"""kubeseal-auto: Interactive wrapper for kubeseal binary.

This package provides tools for creating and managing Kubernetes
SealedSecrets with an interactive CLI interface.

Example usage:
    from kubeseal_auto import Kubeseal

    # Create a Kubeseal instance with the current context
    kubeseal = Kubeseal(select_context=False)

    # Or use detached mode with a certificate
    kubeseal = Kubeseal(select_context=False, certificate="my-cert.crt")
"""

__version__ = "0.6.0"

from kubeseal_auto.cli import cli
from kubeseal_auto.cluster import Cluster
from kubeseal_auto.exceptions import (
    BinaryNotFoundError,
    ClusterConnectionError,
    ControllerNotFoundError,
    KubesealError,
    SecretParsingError,
    UnsupportedPlatformError,
)
from kubeseal_auto.kubeseal import Kubeseal

__all__ = [
    # Version
    "__version__",
    # Main CLI
    "cli",
    # Classes
    "Cluster",
    "Kubeseal",
    # Exceptions
    "KubesealError",
    "BinaryNotFoundError",
    "ClusterConnectionError",
    "ControllerNotFoundError",
    "SecretParsingError",
    "UnsupportedPlatformError",
]
