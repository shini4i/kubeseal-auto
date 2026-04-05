"""Tests for debug.py module."""

import logging

import pytest

from kubeseal_auto.debug import configure_debug, ic, logger


@pytest.fixture(autouse=True)
def _reset_logger():
    """Reset logger state between tests."""
    original_level = logger.level
    original_handlers = logger.handlers[:]
    original_propagate = logger.propagate
    yield
    logger.setLevel(original_level)
    logger.handlers = original_handlers
    logger.propagate = original_propagate


class TestConfigureDebug:
    """Tests for configure_debug function."""

    def test_enable_debug(self):
        """Test enabling debug sets log level to DEBUG."""
        configure_debug(enabled=True)
        assert logger.level == logging.DEBUG

    def test_disable_debug(self):
        """Test disabling debug sets log level to WARNING."""
        configure_debug(enabled=False)
        assert logger.level == logging.WARNING

    def test_enable_adds_handler(self):
        """Test enabling debug adds a handler if none exist."""
        logger.handlers.clear()
        configure_debug(enabled=True)
        assert len(logger.handlers) == 1

    def test_enable_does_not_duplicate_handlers(self):
        """Test enabling debug twice doesn't add duplicate handlers."""
        logger.handlers.clear()
        configure_debug(enabled=True)
        configure_debug(enabled=True)
        assert len(logger.handlers) == 1


class TestIcFunction:
    """Tests for ic() debug function."""

    def test_ic_with_value_when_debug_enabled(self, caplog):
        """Test ic() logs value when debug is enabled."""
        configure_debug(enabled=True)
        logger.propagate = True

        with caplog.at_level(logging.DEBUG, logger="kubeseal_auto"):
            ic("test_value")

        assert "test_value" in caplog.text

    def test_ic_silent_when_debug_disabled(self, caplog):
        """Test ic() produces no output when debug is disabled."""
        configure_debug(enabled=False)
        logger.propagate = True

        # Don't override logger level — let configure_debug's WARNING level suppress output
        with caplog.at_level(logging.WARNING, logger="kubeseal_auto"):
            ic("should_not_appear")

        assert "should_not_appear" not in caplog.text

    def test_ic_bare_call(self, caplog):
        """Test ic() with no arguments logs call location."""
        configure_debug(enabled=True)
        logger.propagate = True

        with caplog.at_level(logging.DEBUG, logger="kubeseal_auto"):
            ic()

        assert "ic|" in caplog.text
