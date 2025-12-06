"""Secrets management subpackage.

This package contains modules for secret creation, sealing, parsing,
and user interaction prompts.
"""

from kubeseal_auto.secrets.creation import create_generic_secret, create_regcred_secret, create_tls_secret
from kubeseal_auto.secrets.parsing import append_argo_annotation, parse_secret_file
from kubeseal_auto.secrets.prompts import collect_secret_entries, collect_secret_parameters
from kubeseal_auto.secrets.sealing import (
    backup_controller_secret,
    fetch_certificate,
    merge_secret,
    reencrypt_secrets,
    seal_secret,
)

__all__ = [
    # creation
    "create_generic_secret",
    "create_tls_secret",
    "create_regcred_secret",
    # parsing
    "parse_secret_file",
    "append_argo_annotation",
    # prompts
    "collect_secret_parameters",
    "collect_secret_entries",
    # sealing
    "seal_secret",
    "merge_secret",
    "reencrypt_secrets",
    "fetch_certificate",
    "backup_controller_secret",
]
