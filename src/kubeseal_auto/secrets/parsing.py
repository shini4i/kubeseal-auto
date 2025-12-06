"""Secret file parsing and annotation utilities.

This module provides functions for parsing YAML secret files
and appending ArgoCD annotations.
"""

from typing import Any

import yaml

from kubeseal_auto import console
from kubeseal_auto.exceptions import SecretParsingError


def parse_secret_file(secret_path: str) -> dict[str, Any] | None:
    """Parse a YAML secret file.

    Args:
        secret_path: Path to the secret file.

    Returns:
        The parsed YAML document as a dictionary, or None if empty.

    Raises:
        SecretParsingError: If the file does not exist, contains multiple
            documents, contains malformed/invalid YAML, or is not a YAML mapping.

    """
    try:
        with open(secret_path) as stream:
            docs = [doc for doc in yaml.safe_load_all(stream) if doc is not None]
            if len(docs) > 1:
                raise SecretParsingError(
                    f"File '{secret_path}' contains multiple YAML documents. Only single document files are supported."
                )
            if not docs:
                return None
            result = docs[0]
            if not isinstance(result, dict):
                raise SecretParsingError(
                    f"File '{secret_path}' does not contain a valid YAML mapping. "
                    "Expected a Kubernetes resource document."
                )
            return result
    except FileNotFoundError as err:
        raise SecretParsingError(f"Secret file '{secret_path}' does not exist") from err
    except yaml.YAMLError as err:
        raise SecretParsingError(f"Secret file '{secret_path}' contains malformed YAML: {err}") from err


def append_argo_annotation(filename: str) -> None:
    """Append ArgoCD sync annotations to a sealed secret file.

    This allows ArgoCD to process repositories with SealedSecrets
    before the controller is deployed in the cluster.

    Args:
        filename: Path to the sealed secret YAML file.

    """
    secret = parse_secret_file(filename)
    if secret is None:
        return

    console.step("Appending ArgoCD annotations")

    annotations: dict[str, str] = secret["metadata"].setdefault("annotations", {})

    sync_key = "argocd.argoproj.io/sync-options"
    skip_option_value = "SkipDryRunOnMissingResource=true"

    current_sync_options_str = annotations.get(sync_key, "")

    # Split, strip whitespace from each option, and filter out any empty strings
    # that might arise from consecutive commas or leading/trailing commas.
    options_list = [opt.strip() for opt in current_sync_options_str.split(",") if opt.strip()]

    # Filter out any pre-existing "SkipDryRunOnMissingResource=" option
    # to ensure we don't duplicate it or have conflicting values.
    filtered_options = [opt for opt in options_list if not opt.startswith("SkipDryRunOnMissingResource=")]

    # Add the desired option to the beginning of the list.
    final_options = [skip_option_value, *filtered_options]

    annotations[sync_key] = ",".join(final_options)

    with open(filename, "w") as stream:
        yaml.safe_dump(secret, stream)
