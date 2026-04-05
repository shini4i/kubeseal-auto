"""Debug output utilities for kubeseal-auto.

This module provides an icecream-style debug function using Python's
built-in logging module, keeping the visual debugging UX without
requiring icecream as a runtime dependency.
"""

import inspect
import logging
import re
import textwrap

logger = logging.getLogger("kubeseal_auto")

# Match ic(variable) call sites to extract argument expressions
_IC_CALL_PATTERN = re.compile(r"\bic\((.+?)\)\s*$")


def _get_call_expression() -> str | None:
    """Extract the ic() argument expression from the calling source line.

    Returns:
        The argument expression string, or None if it cannot be determined.

    """
    frame = inspect.currentframe()
    if frame is None or frame.f_back is None or frame.f_back.f_back is None:
        return None

    caller = frame.f_back.f_back
    try:
        source_lines, start_line = inspect.getsourcelines(caller)
        line_index = caller.f_lineno - start_line
        if 0 <= line_index < len(source_lines):
            line = textwrap.dedent(source_lines[line_index]).strip()
            match = _IC_CALL_PATTERN.search(line)
            if match:
                return match.group(1)
    except (OSError, TypeError):
        pass
    return None


def ic(*args: object) -> None:
    """Log debug information in icecream-style format.

    When called with arguments, logs "ic| <expr>: <value>" where <expr>
    is the source expression passed to ic(). Falls back to plain repr
    if source inspection fails.

    Args:
        *args: Values to log with their source expressions.

    """
    if not logger.isEnabledFor(logging.DEBUG):
        return

    if not args:
        # Bare ic() call — log the call location
        frame = inspect.currentframe()
        if frame and frame.f_back:
            caller = frame.f_back
            logger.debug("ic| %s:%d", caller.f_code.co_filename, caller.f_lineno)
        return

    expr = _get_call_expression()
    if expr and len(args) == 1:
        logger.debug("ic| %s: %r", expr, args[0])
    else:
        for arg in args:
            logger.debug("ic| %r", arg)


def configure_debug(enabled: bool) -> None:
    """Configure debug logging.

    Args:
        enabled: If True, set log level to DEBUG with formatted output.
                If False, set log level to WARNING (suppressing debug output).

    """
    if enabled:
        logger.setLevel(logging.DEBUG)
        # Add a stderr handler if the logger has none yet
        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter("%(message)s"))
            logger.addHandler(handler)
    else:
        logger.setLevel(logging.WARNING)
