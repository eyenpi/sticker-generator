"""Shared test fixtures."""

import logging

import pytest


@pytest.fixture(autouse=True)
def _cleanup_logging():
    """Clean up logging handlers after each test to prevent accumulation."""
    yield
    root_logger = logging.getLogger("sticker_generator")
    root_logger.handlers.clear()
    root_logger.setLevel(logging.WARNING)
