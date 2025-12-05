"""Data models for kubeseal-auto.

This module provides type-safe data structures for the application,
replacing loosely-typed dictionaries with proper Python data classes.
"""

from dataclasses import dataclass
from enum import Enum
from typing import NamedTuple


class SecretType(str, Enum):
    """Supported Kubernetes secret types.

    Inherits from str to allow direct use in string contexts
    (e.g., command-line arguments, YAML output).
    """

    GENERIC = "generic"
    TLS = "tls"
    DOCKER_REGISTRY = "docker-registry"


class ControllerInfo(NamedTuple):
    """Information about the SealedSecrets controller.

    Attributes:
        name: The controller service name.
        namespace: The namespace where the controller is deployed.
        version: The controller version string (may include 'v' prefix).

    """

    name: str
    namespace: str
    version: str


@dataclass(frozen=True, slots=True)
class SecretParams:
    """Parameters for creating a sealed secret.

    Attributes:
        name: The name of the secret.
        namespace: The Kubernetes namespace for the secret.
        secret_type: The type of secret to create.

    """

    name: str
    namespace: str
    secret_type: SecretType
