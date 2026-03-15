from __future__ import annotations

import logging

from meeting_summarizer.logging_config import configure_logging


def test_configure_logging_sets_warning_by_default() -> None:
    configure_logging(0)
    assert logging.getLogger().level == logging.WARNING


def test_configure_logging_sets_info_for_single_verbose() -> None:
    configure_logging(1)
    assert logging.getLogger().level == logging.INFO


def test_configure_logging_sets_debug_for_double_verbose() -> None:
    configure_logging(2)
    assert logging.getLogger().level == logging.DEBUG
