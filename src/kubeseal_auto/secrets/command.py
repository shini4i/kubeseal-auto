"""Helpers for running kubectl/kubeseal commands.

This module is the single place where external commands are run, so
every caller reports a missing binary or a failed command the same way.
"""

import os
import re
import subprocess  # nosec B404 - subprocess wraps the kubeseal/kubectl binaries; calls pass argv lists, never shell=True
from pathlib import Path
from typing import TextIO

import click

_UNSAFE_FILENAME_CHARS = re.compile(r"[^\w.-]", re.ASCII)


def safe_filename(name: str) -> str:
    """Turn an arbitrary name into a single flat filename component.

    Kubernetes context names may contain characters that are not valid in
    a filename, such as the ``/`` and ``:`` in EKS ARNs.

    Args:
        name: The name to convert, typically a Kubernetes context name.

    Returns:
        The name with every character outside ``[A-Za-z0-9_.-]`` replaced by ``_``.

    """
    return _UNSAFE_FILENAME_CHARS.sub("_", name)


def run_command(
    cmd: list[str],
    failure_message: str,
    *,
    stdin_path: Path | None = None,
    stdout: TextIO | None = None,
) -> None:
    """Run a command and turn its failures into readable CLI errors.

    Args:
        cmd: The command to execute; ``cmd[0]`` is the binary name.
        failure_message: Message prefix used when the command exits non-zero,
            e.g. ``"Failed to seal secret"``.
        stdin_path: Optional file whose content is passed to the command's stdin.
        stdout: Optional open file that receives the command's stdout.
            When omitted, stdout goes to the terminal.

    Raises:
        click.ClickException: If the input file cannot be read, the binary is not
            found, or the command exits non-zero.

    """
    try:
        input_data = stdin_path.read_bytes() if stdin_path else None
    except OSError as err:
        raise click.ClickException(f"Cannot read input file '{stdin_path}': {err.strerror}") from err

    try:
        subprocess.run(cmd, input=input_data, stdout=stdout, stderr=subprocess.PIPE, check=True)  # nosec B603 - fixed kubeseal/kubectl argv list, no shell, no untrusted command input
    except FileNotFoundError as err:
        raise click.ClickException(f"{cmd[0]} not found; please install it and ensure it's on PATH") from err
    except subprocess.CalledProcessError as err:
        stderr_msg = err.stderr.decode(errors="replace").strip() if err.stderr else ""
        error_details = f": {stderr_msg}" if stderr_msg else ""
        raise click.ClickException(f"{failure_message} (exit code {err.returncode}){error_details}") from err


def run_to_file(
    cmd: list[str],
    output_path: Path,
    failure_message: str,
    *,
    stdin_path: Path | None = None,
    private: bool = False,
) -> None:
    """Run a command and write its stdout to a file.

    The output file is removed if the command cannot be started or fails.

    Args:
        cmd: The command to execute; ``cmd[0]`` is the binary name.
        output_path: Path where the command's stdout is written.
        failure_message: Message prefix used when the command exits non-zero.
        stdin_path: Optional file whose content is passed to the command's stdin.
        private: If True, the output file is readable and writable only by its
            owner (mode 0600), including when it already exists. Use this for
            files holding private keys.

    Raises:
        click.ClickException: If the output path cannot be opened, the input file
            cannot be read, the binary is not found, or the command exits non-zero.

    """
    try:
        if private:
            fd = os.open(output_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            # The creation mode above does not apply to a file that already exists.
            os.fchmod(fd, 0o600)
            stdout_f = os.fdopen(fd, "w", encoding="utf-8")
        else:
            stdout_f = output_path.open("w", encoding="utf-8")
    except OSError as err:
        raise click.ClickException(f"Cannot write to output path '{output_path}': {err.strerror}") from err

    try:
        with stdout_f:
            run_command(cmd, failure_message, stdin_path=stdin_path, stdout=stdout_f)
    except click.ClickException:
        output_path.unlink(missing_ok=True)
        raise
