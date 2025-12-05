"""Tests for console.py module."""

from unittest.mock import patch

from kubeseal_auto import console


class TestConsoleOutput:
    """Tests for console output functions."""

    def test_info_message(self):
        """Test info message format."""
        with patch.object(console.console, "print") as mock_print:
            console.info("Test message")
            mock_print.assert_called_once()
            call_arg = mock_print.call_args[0][0]
            assert "ℹ" in call_arg
            assert "Test message" in call_arg

    def test_success_message(self):
        """Test success message format."""
        with patch.object(console.console, "print") as mock_print:
            console.success("Operation complete")
            mock_print.assert_called_once()
            call_arg = mock_print.call_args[0][0]
            assert "✓" in call_arg
            assert "Operation complete" in call_arg

    def test_warning_message(self):
        """Test warning message format."""
        with patch.object(console.console, "print") as mock_print:
            console.warning("Be careful")
            mock_print.assert_called_once()
            call_arg = mock_print.call_args[0][0]
            assert "⚠" in call_arg
            assert "Be careful" in call_arg

    def test_error_message(self):
        """Test error message format."""
        with patch.object(console.console, "print") as mock_print:
            console.error("Something failed")
            mock_print.assert_called_once()
            call_arg = mock_print.call_args[0][0]
            assert "✗" in call_arg
            assert "Something failed" in call_arg

    def test_action_message(self):
        """Test action message format."""
        with patch.object(console.console, "print") as mock_print:
            console.action("Doing something")
            mock_print.assert_called_once()
            call_arg = mock_print.call_args[0][0]
            assert "→" in call_arg
            assert "Doing something" in call_arg

    def test_step_message(self):
        """Test step message format."""
        with patch.object(console.console, "print") as mock_print:
            console.step("Sub-step here")
            mock_print.assert_called_once()
            call_arg = mock_print.call_args[0][0]
            assert "•" in call_arg
            assert "Sub-step here" in call_arg

    def test_highlight_returns_markup(self):
        """Test highlight returns Rich markup."""
        result = console.highlight("important")
        assert result == "[highlight]important[/highlight]"

    def test_newline(self):
        """Test newline prints empty line."""
        with patch.object(console.console, "print") as mock_print:
            console.newline()
            mock_print.assert_called_once_with()


class TestConsoleSpinner:
    """Tests for spinner context manager."""

    def test_spinner_context_manager(self):
        """Test spinner works as context manager."""
        with patch.object(console.console, "status") as mock_status:
            mock_status.return_value.__enter__ = lambda x: None
            mock_status.return_value.__exit__ = lambda x, *args: None
            with console.spinner("Loading..."):
                pass
            mock_status.assert_called_once()


class TestConsoleProgress:
    """Tests for progress bar creation."""

    def test_create_download_progress(self):
        """Test download progress bar creation."""
        progress = console.create_download_progress()
        assert progress is not None

    def test_create_task_progress(self):
        """Test task progress bar creation."""
        progress = console.create_task_progress()
        assert progress is not None


class TestConsoleSummaryPanel:
    """Tests for summary panel."""

    def test_summary_panel(self):
        """Test summary panel renders."""
        with patch.object(console.console, "print") as mock_print:
            console.summary_panel("Test Summary", {"Key1": "Value1", "Key2": "Value2"})
            mock_print.assert_called_once()
