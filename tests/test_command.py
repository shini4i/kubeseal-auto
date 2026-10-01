"""Tests for secrets/command.py module."""

import subprocess
from pathlib import Path
from unittest.mock import patch

import click
import pytest

from kubeseal_auto.secrets.command import run_command, run_to_file, safe_filename


class TestRunToFile:
    """Tests for run_to_file function."""

    def test_writes_stdout_to_file(self, tmp_path: Path) -> None:
        """Test that command stdout lands in the output file."""
        output = tmp_path / "out.txt"

        run_to_file(["echo", "hello"], output, "Failed to echo")

        assert output.read_text() == "hello\n"

    def test_passes_stdin_file(self, tmp_path: Path) -> None:
        """Test that stdin_path content is fed to the command."""
        source = tmp_path / "in.txt"
        source.write_text("piped\n")
        output = tmp_path / "out.txt"

        run_to_file(["cat"], output, "Failed to cat", stdin_path=source)

        assert output.read_text() == "piped\n"

    def test_unwritable_output_raises_click_exception(self, tmp_path: Path) -> None:
        """Test that an output path in a missing directory gives a readable error."""
        output = tmp_path / "missing-dir" / "out.txt"

        with pytest.raises(click.ClickException, match="Cannot write to output path"):
            run_to_file(["echo", "hello"], output, "Failed to echo")

    def test_missing_binary_raises_click_exception(self, tmp_path: Path) -> None:
        """Test that a missing binary is reported by name and leaves no output file."""
        output = tmp_path / "out.txt"

        with pytest.raises(click.ClickException, match="no-such-binary-xyz not found"):
            run_to_file(["no-such-binary-xyz"], output, "Failed to run")

        assert not output.exists()

    def test_unreadable_stdin_raises_click_exception_and_removes_output(self, tmp_path: Path) -> None:
        """Test that a missing stdin file gives a readable error and leaves no output file."""
        output = tmp_path / "out.txt"

        with pytest.raises(click.ClickException, match="Cannot read input file"):
            run_to_file(["cat"], output, "Failed to cat", stdin_path=tmp_path / "missing.txt")

        assert not output.exists()

    def test_command_failure_includes_stderr_and_removes_output(self, tmp_path: Path) -> None:
        """Test that a failing command reports exit code and stderr, then removes partial output."""
        output = tmp_path / "out.txt"
        error = subprocess.CalledProcessError(returncode=3, cmd=["kubectl"], stderr=b"forbidden")

        with (
            patch("kubeseal_auto.secrets.command.subprocess.run", side_effect=error),
            pytest.raises(click.ClickException, match=r"Failed to run \(exit code 3\): forbidden"),
        ):
            run_to_file(["kubectl"], output, "Failed to run")

        assert not output.exists()

    def test_command_failure_without_stderr(self, tmp_path: Path) -> None:
        """Test that a failure with empty stderr reports only the exit code."""
        error = subprocess.CalledProcessError(returncode=2, cmd=["kubectl"], stderr=b"")

        with (
            patch("kubeseal_auto.secrets.command.subprocess.run", side_effect=error),
            pytest.raises(click.ClickException) as exc_info,
        ):
            run_to_file(["kubectl"], tmp_path / "out.txt", "Failed to run")

        assert exc_info.value.message == "Failed to run (exit code 2)"


class TestRunCommand:
    """Tests for run_command function."""

    def test_feeds_stdin_and_leaves_stdout_on_terminal(self, tmp_path: Path) -> None:
        """Test that stdin_path bytes are passed as input and stdout is not captured."""
        source = tmp_path / "in.txt"
        source.write_text("secret yaml\n")

        with patch("kubeseal_auto.secrets.command.subprocess.run") as mock_run:
            run_command(["kubeseal"], "Failed", stdin_path=source)

        kwargs = mock_run.call_args.kwargs
        assert kwargs["input"] == b"secret yaml\n"
        assert kwargs["stdout"] is None
        assert kwargs["check"] is True


class TestSafeFilename:
    """Tests for safe_filename function."""

    def test_keeps_simple_names(self) -> None:
        """Test that names without special characters are unchanged."""
        assert safe_filename("kind-kind") == "kind-kind"
        assert safe_filename("gke_project_zone_name.prod") == "gke_project_zone_name.prod"

    def test_replaces_path_separators_and_colons(self) -> None:
        """Test that an EKS ARN context becomes a single flat filename."""
        assert (
            safe_filename("arn:aws:eks:us-east-1:123456789012:cluster/prod")
            == "arn_aws_eks_us-east-1_123456789012_cluster_prod"
        )


class TestRunToFilePrivate:
    """Tests for run_to_file with private=True."""

    def test_new_file_is_owner_only(self, tmp_path: Path) -> None:
        """Test that a new private output file is created with mode 0600."""
        output = tmp_path / "key.yaml"

        run_to_file(["echo", "key"], output, "Failed", private=True)

        assert output.stat().st_mode & 0o777 == 0o600

    def test_existing_file_is_tightened(self, tmp_path: Path) -> None:
        """Test that an existing world-readable file is narrowed to 0600 before writing."""
        output = tmp_path / "key.yaml"
        output.write_text("old")
        output.chmod(0o644)

        run_to_file(["echo", "key"], output, "Failed", private=True)

        assert output.stat().st_mode & 0o777 == 0o600
        assert output.read_text() == "key\n"
