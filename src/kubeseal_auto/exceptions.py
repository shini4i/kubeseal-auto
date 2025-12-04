"""Custom exceptions for kubeseal-auto.

This module defines the exception hierarchy used throughout the application
to provide meaningful error messages and proper error handling.
"""


class KubesealError(Exception):
    """Base exception for all kubeseal-auto errors.

    All custom exceptions in this package inherit from this class,
    allowing callers to catch all kubeseal-auto errors with a single
    except clause if desired.
    """

    pass


class ClusterConnectionError(KubesealError):
    """Raised when connection to the Kubernetes cluster fails.

    This can occur when:
    - The kubeconfig is invalid or missing
    - The cluster is unreachable
    - Authentication fails
    """

    pass


class ControllerNotFoundError(KubesealError):
    """Raised when the SealedSecrets controller is not found in the cluster.

    This typically means:
    - The sealed-secrets controller is not installed
    - The controller is installed but not properly labeled
    - The user doesn't have permission to list services
    """

    pass


class BinaryNotFoundError(KubesealError):
    """Raised when a required binary (kubeseal, kubectl) is not found.

    This can occur when:
    - The binary is not installed
    - The binary is not in the system PATH
    - The required version cannot be downloaded
    """

    pass


class UnsupportedPlatformError(KubesealError):
    """Raised when the current platform is not supported.

    kubeseal-auto supports:
    - Operating systems: Linux, macOS (Darwin)
    - CPU architectures: x86_64 (amd64), arm64
    """

    pass


class SecretParsingError(KubesealError):
    """Raised when parsing a secret file fails.

    This can occur when:
    - The file does not exist
    - The file is not valid YAML
    - The YAML does not represent a valid Kubernetes secret
    """

    pass
