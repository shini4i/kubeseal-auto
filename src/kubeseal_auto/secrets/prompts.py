"""Interactive user prompts for secret creation.

This module provides functions for collecting secret parameters
and entries from users via interactive prompts.
"""

import re
from pathlib import Path

import click
import questionary

from kubeseal_auto import console
from kubeseal_auto.models import SecretParams, SecretType
from kubeseal_auto.styles import POINTER, PROMPT_STYLE, QMARK

# Kubernetes DNS subdomain name validation (RFC 1123)
_DNS_SUBDOMAIN_MAX_LENGTH = 253
_DNS_SUBDOMAIN_PATTERN = r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?(\.[a-z0-9]([-a-z0-9]*[a-z0-9])?)*$"


def validate_k8s_name(name: str) -> bool | str:
    """Validate a Kubernetes resource name (DNS subdomain).

    Args:
        name: The name to validate.

    Returns:
        True if valid, or an error message string if invalid.

    """
    if not name:
        return "Name cannot be empty"
    if len(name) > _DNS_SUBDOMAIN_MAX_LENGTH:
        return f"Name must be {_DNS_SUBDOMAIN_MAX_LENGTH} characters or less"
    if not re.match(_DNS_SUBDOMAIN_PATTERN, name):
        return "Name must consist of lowercase alphanumeric characters, '-' or '.', and must start and end with an alphanumeric character"
    return True


def collect_secret_parameters(
    namespaces: list[str],
    *,
    detached_mode: bool = False,
) -> SecretParams:
    """Interactively collect parameters for creating a new secret.

    Args:
        namespaces: List of available namespaces for autocomplete.
        detached_mode: If True, use text input instead of autocomplete for namespace.

    Returns:
        SecretParams with namespace, secret_type, and name.

    """
    if detached_mode:
        namespace = questionary.text(
            "Provide namespace for the new secret",
            validate=validate_k8s_name,
            style=PROMPT_STYLE,
            qmark=QMARK,
        ).unsafe_ask()
    else:
        # Use autocomplete for namespace selection with type-ahead filtering
        namespace = questionary.autocomplete(
            "Select or type namespace (Tab to show options)",
            choices=namespaces,
            validate=validate_k8s_name,
            style=PROMPT_STYLE,
            qmark=QMARK,
        ).unsafe_ask()

    secret_type_str = questionary.select(
        "Select secret type to create",
        choices=[t.value for t in SecretType],
        style=PROMPT_STYLE,
        pointer=POINTER,
        qmark=QMARK,
    ).unsafe_ask()

    secret_name = questionary.text(
        "Provide name for the new secret",
        validate=validate_k8s_name,
        style=PROMPT_STYLE,
        qmark=QMARK,
    ).unsafe_ask()

    return SecretParams(
        name=secret_name,
        namespace=namespace,
        secret_type=SecretType(secret_type_str),
    )


def _prompt_literal_entry() -> str:
    """Prompt for a single literal key=value entry.

    Returns:
        The kubectl argument for the literal entry.

    """
    entry = questionary.text(
        "Enter key=value",
        validate=lambda x: True if "=" in x else "Must be in key=value format",
        style=PROMPT_STYLE,
        qmark=QMARK,
    ).unsafe_ask()
    console.success(f"Added literal: {console.highlight(entry.split('=')[0])}")
    return f"--from-literal={entry}"


def _prompt_bulk_literals() -> list[str]:
    """Prompt for bulk literal entries (one per line).

    Returns:
        List of kubectl arguments for literal entries.

    """
    bulk_input = questionary.text(
        "Enter key=value pairs (one per line, Esc+Enter to finish)",
        multiline=True,
        style=PROMPT_STYLE,
        qmark=QMARK,
    ).unsafe_ask()

    entries = [f"--from-literal={line.strip()}" for line in bulk_input.splitlines() if line.strip() and "=" in line]

    skipped = sum(1 for line in bulk_input.splitlines() if line.strip() and "=" not in line)
    if skipped:
        console.warning(f"Skipped {skipped} line(s) missing '=' separator")

    if entries:
        console.success(f"Added {console.highlight(str(len(entries)))} literal(s)")
    return entries


def _prompt_file_entry() -> str:
    """Prompt for a file entry.

    Returns:
        The kubectl argument for the file entry.

    Raises:
        click.ClickException: If the selected file does not exist.

    """
    entry = questionary.path(
        "Select file",
        style=PROMPT_STYLE,
        qmark=QMARK,
    ).unsafe_ask()

    if not Path(entry).exists():
        raise click.ClickException(f"File not found: {entry}")

    console.success(f"Added file: {console.highlight(entry)}")
    return f"--from-file={entry}"


def collect_secret_entries() -> list[str]:
    """Interactively collect secret entries from user.

    Returns:
        List of kubectl arguments for all entries.

    """
    entries: list[str] = []

    while True:
        if entries:
            console.info(f"Current entries: {console.highlight(str(len(entries)))}")

        entry_type = questionary.select(
            "Add secret entry",
            choices=[
                {"name": "📝 Literal (key=value)", "value": "literal"},
                {"name": "📝 Bulk literals (one per line)", "value": "bulk"},
                {"name": "📁 From file", "value": "file"},
                {"name": "✓ Done adding entries", "value": "done", "disabled": not entries},
            ],
            style=PROMPT_STYLE,
            pointer=POINTER,
            qmark=QMARK,
        ).unsafe_ask()

        if entry_type == "done":
            break
        if entry_type == "literal":
            entries.append(_prompt_literal_entry())
        elif entry_type == "bulk":
            entries.extend(_prompt_bulk_literals())
        else:
            entries.append(_prompt_file_entry())

    return entries


def prompt_docker_credentials() -> tuple[str, str, str]:
    """Prompt for Docker registry credentials.

    Returns:
        Tuple of (server, username, password).

    """
    docker_server = questionary.text(
        "Provide docker-server",
        style=PROMPT_STYLE,
        qmark=QMARK,
    ).unsafe_ask()

    docker_username = questionary.text(
        "Provide docker-username",
        style=PROMPT_STYLE,
        qmark=QMARK,
    ).unsafe_ask()

    docker_password = questionary.password(
        "Provide docker-password",
        style=PROMPT_STYLE,
        qmark=QMARK,
    ).unsafe_ask()

    return docker_server, docker_username, docker_password
