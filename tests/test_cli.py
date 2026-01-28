"""Tests for CLI argument parsing."""

import argparse

import pytest

from sticker_generator.cli import parse_resize_arg


class TestParseResizeArg:
    def test_square_format(self):
        assert parse_resize_arg("512") == (512, 512)

    def test_width_x_height_format(self):
        assert parse_resize_arg("512x256") == (512, 256)

    def test_case_insensitive_x(self):
        assert parse_resize_arg("512X256") == (512, 256)

    def test_whitespace_trimmed(self):
        assert parse_resize_arg("  512  ") == (512, 512)
        assert parse_resize_arg(" 512 x 256 ") == (512, 256)

    def test_invalid_format_raises(self):
        with pytest.raises(argparse.ArgumentTypeError, match="Invalid resize format"):
            parse_resize_arg("512x256x128")

    def test_zero_raises(self):
        with pytest.raises(argparse.ArgumentTypeError, match="must be positive"):
            parse_resize_arg("0")

    def test_zero_height_raises(self):
        with pytest.raises(argparse.ArgumentTypeError, match="must be positive"):
            parse_resize_arg("512x0")

    def test_negative_raises(self):
        with pytest.raises(argparse.ArgumentTypeError, match="must be positive"):
            parse_resize_arg("-100")

    def test_non_numeric_raises(self):
        with pytest.raises(argparse.ArgumentTypeError, match="Invalid resize format"):
            parse_resize_arg("abc")

    def test_non_numeric_height_raises(self):
        with pytest.raises(argparse.ArgumentTypeError, match="must be integers"):
            parse_resize_arg("512xabc")
