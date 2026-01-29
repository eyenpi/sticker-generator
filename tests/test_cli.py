"""Tests for command-line interface."""

import argparse
import sys
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from sticker_generator.cli import main, parse_resize_arg


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


class TestCLIFormatOptions:
    """Tests for CLI format options."""

    @patch("sticker_generator.cli.create_sticker")
    def test_format_flag_passed_to_create_sticker(self, mock_create):
        mock_create.return_value = Image.new("RGBA", (100, 100))

        with patch.object(sys, "argv", ["prog", "test prompt", "-f", "webp"]):
            result = main()

        assert result == 0
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["output_format"] == "webp"

    @patch("sticker_generator.cli.create_sticker")
    def test_quality_flag_passed(self, mock_create):
        mock_create.return_value = Image.new("RGBA", (100, 100))

        with patch.object(sys, "argv", ["prog", "test prompt", "-q", "85"]):
            result = main()

        assert result == 0
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["quality"] == 85

    @patch("sticker_generator.cli.create_sticker")
    def test_lossless_flag(self, mock_create):
        mock_create.return_value = Image.new("RGBA", (100, 100))

        with patch.object(sys, "argv", ["prog", "test prompt", "--lossless"]):
            result = main()

        assert result == 0
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["lossless"] is True

    @patch("sticker_generator.cli.create_sticker")
    def test_lossy_flag(self, mock_create):
        mock_create.return_value = Image.new("RGBA", (100, 100))

        with patch.object(sys, "argv", ["prog", "test prompt", "--lossy"]):
            result = main()

        assert result == 0
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["lossless"] is False

    @patch("sticker_generator.cli.create_sticker")
    def test_no_format_flag_passes_none(self, mock_create):
        mock_create.return_value = Image.new("RGBA", (100, 100))

        with patch.object(sys, "argv", ["prog", "test prompt"]):
            result = main()

        assert result == 0
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["output_format"] is None

    def test_invalid_quality_below_range(self, capsys):
        with patch.object(sys, "argv", ["prog", "test prompt", "-q", "0"]):
            result = main()

        assert result == 1
        captured = capsys.readouterr()
        assert "Quality must be between 1 and 100" in captured.err

    def test_invalid_quality_above_range(self, capsys):
        with patch.object(sys, "argv", ["prog", "test prompt", "-q", "101"]):
            result = main()

        assert result == 1
        captured = capsys.readouterr()
        assert "Quality must be between 1 and 100" in captured.err

    def test_both_lossless_and_lossy_rejected(self, capsys):
        with patch.object(
            sys, "argv", ["prog", "test prompt", "--lossless", "--lossy"]
        ):
            result = main()

        assert result == 1
        captured = capsys.readouterr()
        assert "Cannot specify both --lossless and --lossy" in captured.err

    @patch("sticker_generator.cli.generate_sticker_sheet")
    def test_format_passed_to_sheet_generation(self, mock_sheet):
        mock_sheet.return_value = MagicMock(
            stickers=[Image.new("RGBA", (100, 100))],
            sheet=Image.new("RGBA", (100, 100)),
            failed_indices=[],
        )

        with patch.object(
            sys,
            "argv",
            ["prog", "test prompt", "-n", "2", "--sheet", "-f", "webp-lossy"],
        ):
            result = main()

        assert result == 0
        mock_sheet.assert_called_once()
        call_kwargs = mock_sheet.call_args[1]
        assert call_kwargs["output_format"] == "webp-lossy"

    @patch("sticker_generator.cli.generate_sticker_sheet")
    def test_quality_passed_to_sheet_generation(self, mock_sheet):
        mock_sheet.return_value = MagicMock(
            stickers=[Image.new("RGBA", (100, 100))],
            sheet=Image.new("RGBA", (100, 100)),
            failed_indices=[],
        )

        with patch.object(
            sys, "argv", ["prog", "test prompt", "-n", "2", "--sheet", "-q", "75"]
        ):
            result = main()

        assert result == 0
        mock_sheet.assert_called_once()
        call_kwargs = mock_sheet.call_args[1]
        assert call_kwargs["quality"] == 75

    @patch("sticker_generator.cli.generate_sticker_sheet")
    def test_lossless_passed_to_sheet_generation(self, mock_sheet):
        mock_sheet.return_value = MagicMock(
            stickers=[Image.new("RGBA", (100, 100))],
            sheet=Image.new("RGBA", (100, 100)),
            failed_indices=[],
        )

        with patch.object(
            sys, "argv", ["prog", "test prompt", "-n", "2", "--sheet", "--lossless"]
        ):
            result = main()

        assert result == 0
        mock_sheet.assert_called_once()
        call_kwargs = mock_sheet.call_args[1]
        assert call_kwargs["lossless"] is True

    @patch("sticker_generator.cli.create_sticker")
    def test_combined_format_and_quality(self, mock_create):
        mock_create.return_value = Image.new("RGBA", (100, 100))

        with patch.object(
            sys, "argv", ["prog", "test prompt", "-f", "webp", "-q", "90", "--lossy"]
        ):
            result = main()

        assert result == 0
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["output_format"] == "webp"
        assert call_kwargs["quality"] == 90
        assert call_kwargs["lossless"] is False


class TestCLIBasicFunctionality:
    """Tests for basic CLI functionality."""

    @patch("sticker_generator.cli.create_sticker")
    def test_default_output_filename(self, mock_create):
        mock_create.return_value = Image.new("RGBA", (100, 100))

        with patch.object(sys, "argv", ["prog", "test prompt"]):
            result = main()

        assert result == 0
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["output"] == "sticker.png"

    @patch("sticker_generator.cli.create_sticker")
    def test_custom_output_filename(self, mock_create):
        mock_create.return_value = Image.new("RGBA", (100, 100))

        with patch.object(sys, "argv", ["prog", "test prompt", "-o", "custom.webp"]):
            result = main()

        assert result == 0
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["output"] == "custom.webp"

    @patch("sticker_generator.cli.create_sticker")
    def test_style_flag_passed(self, mock_create):
        mock_create.return_value = Image.new("RGBA", (100, 100))

        with patch.object(sys, "argv", ["prog", "test prompt", "-s", "kawaii"]):
            result = main()

        assert result == 0
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["style"] == "kawaii"

    @patch("sticker_generator.cli.create_sticker")
    def test_resize_flag_passed(self, mock_create):
        mock_create.return_value = Image.new("RGBA", (100, 100))

        with patch.object(sys, "argv", ["prog", "test prompt", "--resize", "512"]):
            result = main()

        assert result == 0
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["resize"] == (512, 512)

    @patch("sticker_generator.cli.create_sticker")
    def test_resize_exact_flag_passed(self, mock_create):
        mock_create.return_value = Image.new("RGBA", (100, 100))

        with patch.object(
            sys,
            "argv",
            ["prog", "test prompt", "--resize", "512x256", "--resize-exact"],
        ):
            result = main()

        assert result == 0
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["resize"] == (512, 256)
        assert call_kwargs["resize_exact"] is True

    def test_error_handling(self, capsys):
        with patch("sticker_generator.cli.create_sticker") as mock_create:
            mock_create.side_effect = Exception("API error")

            with patch.object(sys, "argv", ["prog", "test prompt"]):
                result = main()

            assert result == 1
            captured = capsys.readouterr()
            assert "Error: API error" in captured.err
