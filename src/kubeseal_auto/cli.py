#!/usr/bin/env python
"""Command-line interface for kubeseal-auto.

This module provides the main CLI entry point for the kubeseal-auto tool,
handling command-line argument parsing and orchestrating the various
secret management operations.
"""

import sys

import click
from icecream import ic

from kubeseal_auto import __version__, console
from kubeseal_auto.exceptions import ClusterConnectionError, SecretParsingError
from kubeseal_auto.kubeseal import Kubeseal
from kubeseal_auto.models import SecretParams, SecretType


def create_new_secret(kubeseal: Kubeseal) -> None:
    """Create a new sealed secret interactively.

    Collects secret parameters from the user and creates the appropriate
    type of secret (generic, tls, or docker-registry).

    Args:
        kubeseal: Kubeseal instance to use for secret creation.

    """
    secret_params = kubeseal.collect_parameters()
    ic(secret_params)

    match secret_params.secret_type:
        case SecretType.GENERIC:
            kubeseal.create_generic_secret(secret_params=secret_params)
        case SecretType.TLS:
            kubeseal.create_tls_secret(secret_params=secret_params)
        case SecretType.DOCKER_REGISTRY:
            kubeseal.create_regcred_secret(secret_params=secret_params)

    kubeseal.seal(secret_params=secret_params)


def edit_secret(kubeseal: Kubeseal, file: str) -> None:
    """Edit an existing sealed secret file.

    Parses the existing secret to get metadata, then allows adding
    or modifying key-value pairs.

    Args:
        kubeseal: Kubeseal instance to use for secret editing.
        file: Path to the existing sealed secret file.

    Raises:
        click.ClickException: If the secret file cannot be parsed.

    """
    try:
        secret = kubeseal.parse_existing_secret(file)
    except SecretParsingError as e:
        raise click.ClickException(str(e)) from None

    if secret is None:
        raise click.ClickException(f"Secret file '{file}' is empty")

    secret_params = SecretParams(
        name=secret["metadata"]["name"],
        namespace=secret["metadata"]["namespace"],
        secret_type=SecretType.GENERIC,
    )
    ic(secret_params)
    kubeseal.create_generic_secret(secret_params=secret_params)
    kubeseal.merge(file)


@click.command(help="Automate the process of sealing secrets for Kubernetes")
@click.option("--version", "-v", required=False, is_flag=True, help="print version")
@click.option("--debug", required=False, is_flag=True, help="print debug information")
@click.option("--select", required=False, is_flag=True, default=False, help="prompt for context select")
@click.option("--fetch", required=False, is_flag=True, help="download kubeseal encryption cert")
@click.option("--cert", "-c", required=False, help="certificate to seal secret with")
@click.option("--edit", "-e", required=False, help="SealedSecrets file to edit")
@click.option("--re-encrypt", required=False, help="path to directory with sealed secrets")
@click.option("--backup", required=False, is_flag=True, help="backups controllers encryption secret")
def cli(
    debug: bool,
    select: bool,
    fetch: bool,
    cert: str | None,
    edit: str | None,
    re_encrypt: str | None,
    backup: bool,
    version: bool,
) -> None:
    """Process CLI arguments and execute the appropriate action.

    Args:
        debug: Enable debug output.
        select: Prompt for Kubernetes context selection.
        fetch: Download kubeseal encryption certificate.
        cert: Path to certificate for detached mode.
        edit: Path to SealedSecrets file to edit.
        re_encrypt: Path to directory with secrets to re-encrypt.
        backup: Backup the controller's encryption secret.
        version: Print version and exit.

    """
    if not debug:
        ic.disable()

    if version:
        click.echo(__version__)
        return

    try:
        with Kubeseal(certificate=cert, select_context=select) as kubeseal:
            if fetch:
                kubeseal.fetch_certificate()
                return

            if backup:
                kubeseal.backup()
                return

            if re_encrypt:
                kubeseal.reencrypt(src=re_encrypt)
                return

            if edit:
                edit_secret(kubeseal=kubeseal, file=edit)
                return

            create_new_secret(kubeseal=kubeseal)
    except ClusterConnectionError as e:
        console.error(f"Cluster connection failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    cli()
