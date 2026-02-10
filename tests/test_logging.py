"""Tests for structured logging and debug mode."""

import logging
import sys
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image


class TestLoggerHierarchy:
    """Test that each module has the correct logger and root has NullHandler."""

    def test_root_logger_has_null_handler(self):
        # Re-add NullHandler as __init__.py does at import time
        # (conftest autouse fixture clears handlers between tests)
        import importlib

        import sticker_generator

        importlib.reload(sticker_generator)

        root = logging.getLogger("sticker_generator")
        handler_types = [type(h) for h in root.handlers]
        assert logging.NullHandler in handler_types

    def test_core_logger_name(self):
        from sticker_generator import core

        assert core.logger.name == "sticker_generator.core"

    def test_image_processing_logger_name(self):
        from sticker_generator import image_processing

        assert image_processing.logger.name == "sticker_generator.image_processing"

    def test_sheet_logger_name(self):
        from sticker_generator import sheet

        assert sheet.logger.name == "sticker_generator.sheet"

    def test_cli_logger_name(self):
        from sticker_generator import cli

        assert cli.logger.name == "sticker_generator.cli"


class TestSetupLogging:
    """Test the _setup_logging function."""

    def test_setup_logging_info_level(self):
        from sticker_generator.cli import _setup_logging

        _setup_logging(logging.INFO)
        root = logging.getLogger("sticker_generator")
        assert root.level == logging.INFO
        assert len(root.handlers) == 1
        assert isinstance(root.handlers[0], logging.StreamHandler)

    def test_setup_logging_debug_format(self):
        from sticker_generator.cli import _setup_logging

        _setup_logging(logging.DEBUG)
        root = logging.getLogger("sticker_generator")
        assert root.level == logging.DEBUG
        fmt = root.handlers[0].formatter
        assert fmt is not None
        assert "levelname" in fmt._fmt

    def test_setup_logging_info_format(self):
        from sticker_generator.cli import _setup_logging

        _setup_logging(logging.INFO)
        root = logging.getLogger("sticker_generator")
        fmt = root.handlers[0].formatter
        assert fmt is not None
        assert fmt._fmt == "%(message)s"

    def test_setup_logging_idempotent(self):
        from sticker_generator.cli import _setup_logging

        _setup_logging(logging.INFO)
        _setup_logging(logging.DEBUG)
        root = logging.getLogger("sticker_generator")
        # Should only have 1 handler (not accumulated)
        assert len(root.handlers) == 1

    def test_setup_logging_outputs_to_stderr(self):
        from sticker_generator.cli import _setup_logging

        _setup_logging(logging.INFO)
        root = logging.getLogger("sticker_generator")
        handler = root.handlers[0]
        assert handler.stream is sys.stderr


class TestCLIVerbosityFlags:
    """Test CLI verbosity flags."""

    @patch("sticker_generator.cli.create_sticker")
    def test_default_info_messages_appear(self, mock_create, caplog):
        mock_create.return_value = Image.new("RGBA", (100, 100))

        with caplog.at_level("INFO", logger="sticker_generator"):
            with patch.object(sys, "argv", ["prog", "test prompt"]):
                from sticker_generator.cli import main

                main()

        assert any("Generating sticker" in r.message for r in caplog.records)

    @patch("sticker_generator.cli.create_sticker")
    def test_verbose_shows_debug(self, mock_create, caplog):
        mock_create.return_value = Image.new("RGBA", (100, 100))

        with caplog.at_level("DEBUG", logger="sticker_generator"):
            with patch.object(sys, "argv", ["prog", "test prompt", "--verbose"]):
                from sticker_generator.cli import main

                main()

                # Check level inside the test, before conftest cleanup
                root = logging.getLogger("sticker_generator")
                assert root.level == logging.DEBUG

    @patch("sticker_generator.cli.create_sticker")
    def test_quiet_hides_info(self, mock_create, caplog):
        mock_create.return_value = Image.new("RGBA", (100, 100))

        with caplog.at_level("WARNING", logger="sticker_generator"):
            with patch.object(sys, "argv", ["prog", "test prompt", "--quiet"]):
                from sticker_generator.cli import main

                main()

        # No INFO-level messages should appear
        assert not any(r.levelno < logging.WARNING for r in caplog.records)

    def test_quiet_and_verbose_mutually_exclusive(self):
        with pytest.raises(SystemExit):
            with patch.object(
                sys, "argv", ["prog", "test prompt", "--quiet", "--verbose"]
            ):
                from sticker_generator.cli import main

                main()

    @patch("sticker_generator.cli.create_sticker")
    def test_debug_sets_debug_level(self, mock_create):
        mock_create.return_value = Image.new("RGBA", (100, 100))

        with patch.object(sys, "argv", ["prog", "test prompt", "--debug"]):
            from sticker_generator.cli import main

            main()

            # Check level before conftest cleanup
            root = logging.getLogger("sticker_generator")
            assert root.level == logging.DEBUG


class TestSaveIntermediates:
    """Test --save-intermediates flag and save_intermediates parameter."""

    @patch("sticker_generator.cli.create_sticker")
    def test_save_intermediates_auto_dir(self, mock_create):
        mock_create.return_value = Image.new("RGBA", (100, 100))

        with patch.object(
            sys,
            "argv",
            ["prog", "test prompt", "-o", "my_sticker.png", "--save-intermediates"],
        ):
            from sticker_generator.cli import main

            main()

        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["save_intermediates"] == "my_sticker_intermediates"

    @patch("sticker_generator.cli.create_sticker")
    def test_save_intermediates_custom_dir(self, mock_create):
        mock_create.return_value = Image.new("RGBA", (100, 100))

        with patch.object(
            sys,
            "argv",
            [
                "prog",
                "test prompt",
                "--save-intermediates",
                "/tmp/my_debug",
            ],
        ):
            from sticker_generator.cli import main

            main()

        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["save_intermediates"] == "/tmp/my_debug"

    @patch("sticker_generator.cli.create_sticker")
    def test_no_intermediates_by_default(self, mock_create):
        mock_create.return_value = Image.new("RGBA", (100, 100))

        with patch.object(sys, "argv", ["prog", "test prompt"]):
            from sticker_generator.cli import main

            main()

        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["save_intermediates"] is None

    @patch("sticker_generator.cli.create_sticker")
    def test_debug_implies_save_intermediates(self, mock_create):
        mock_create.return_value = Image.new("RGBA", (100, 100))

        with patch.object(
            sys, "argv", ["prog", "test prompt", "-o", "out.png", "--debug"]
        ):
            from sticker_generator.cli import main

            main()

        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["save_intermediates"] == "out_intermediates"

    @patch("sticker_generator.core.generate_sticker")
    def test_create_sticker_saves_intermediates(self, mock_gen, tmp_path):
        from sticker_generator.core import create_sticker

        img = Image.new("RGBA", (100, 100), (0, 255, 0, 255))
        mock_gen.return_value = img

        intermediates_dir = tmp_path / "intermediates"

        create_sticker("test prompt", save_intermediates=str(intermediates_dir))

        assert intermediates_dir.exists()
        assert (intermediates_dir / "01_raw_from_api.png").exists()
        assert (intermediates_dir / "02_after_hsv_removal.png").exists()
        assert (intermediates_dir / "03_after_aggressive_removal.png").exists()
        assert (intermediates_dir / "04_after_edge_cleanup.png").exists()

    def test_process_image_saves_intermediates(self, tmp_path):
        from sticker_generator.core import process_image

        # Create a green-screen test image
        img = Image.new("RGBA", (50, 50), (0, 255, 0, 255))
        input_file = tmp_path / "input.png"
        img.save(str(input_file))

        intermediates_dir = tmp_path / "intermediates"

        process_image(str(input_file), save_intermediates=str(intermediates_dir))

        assert intermediates_dir.exists()
        assert (intermediates_dir / "01_input_loaded.png").exists()
        assert (intermediates_dir / "02_after_hsv_removal.png").exists()
        assert (intermediates_dir / "03_after_aggressive_removal.png").exists()
        assert (intermediates_dir / "04_after_edge_cleanup.png").exists()

    @patch("sticker_generator.cli.generate_sticker_sheet")
    def test_save_intermediates_passed_to_sheet(self, mock_sheet):
        mock_sheet.return_value = MagicMock(
            stickers=[Image.new("RGBA", (100, 100))],
            sheet=Image.new("RGBA", (100, 100)),
            failed_indices=[],
        )

        with patch.object(
            sys,
            "argv",
            [
                "prog",
                "test prompt",
                "-n",
                "2",
                "--sheet",
                "--save-intermediates",
                "/tmp/dbg",
            ],
        ):
            from sticker_generator.cli import main

            main()

        call_kwargs = mock_sheet.call_args[1]
        assert call_kwargs["save_intermediates"] == "/tmp/dbg"


class TestBackwardCompatibility:
    """Test that library functions produce no output without logging config."""

    @patch("sticker_generator.core.generate_sticker")
    def test_no_output_without_logging_config(self, mock_gen, capsys):
        from sticker_generator.core import create_sticker

        # Reset to library defaults (NullHandler only)
        root = logging.getLogger("sticker_generator")
        root.handlers.clear()
        root.addHandler(logging.NullHandler())
        root.setLevel(logging.WARNING)

        img = Image.new("RGBA", (100, 100), (0, 255, 0, 255))
        mock_gen.return_value = img

        create_sticker("test prompt")

        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""
