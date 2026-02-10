"""Tests for progress callback support in batch, sheet, and CLI."""

import sys
from unittest.mock import MagicMock, patch

import numpy as np
from PIL import Image

from sticker_generator.batch import (
    BatchItem,
    BatchResult,
    batch_generate,
    batch_process_images,
)
from sticker_generator.cli import main
from sticker_generator.sheet import generate_sticker_sheet


def _make_green_image(size=(100, 100)):
    """Create a test image with green background and red subject."""
    data = np.zeros((size[1], size[0], 4), dtype=np.uint8)
    data[:, :] = [0, 255, 0, 255]
    h, w = size[1], size[0]
    data[h // 4 : 3 * h // 4, w // 4 : 3 * w // 4] = [255, 0, 0, 255]
    return Image.fromarray(data, "RGBA")


class TestBatchGenerateProgressCallback:
    """Tests for progress_callback in batch_generate."""

    @patch("sticker_generator.batch.create_sticker")
    def test_callback_called_for_each_item(self, mock_create, tmp_path):
        mock_create.return_value = _make_green_image()
        callback = MagicMock()

        batch_generate(
            ["a cat", "a dog", "a bird"],
            output_dir=tmp_path / "out",
            delay_between_requests=0,
            progress_callback=callback,
        )

        assert callback.call_count == 3

    @patch("sticker_generator.batch.create_sticker")
    def test_callback_called_on_failure(self, mock_create, tmp_path):
        mock_create.side_effect = [
            _make_green_image(),
            Exception("API error"),
            _make_green_image(),
        ]
        callback = MagicMock()

        batch_generate(
            ["a cat", "a dog", "a bird"],
            output_dir=tmp_path / "out",
            delay_between_requests=0,
            progress_callback=callback,
        )

        assert callback.call_count == 3

    @patch("sticker_generator.batch.create_sticker")
    def test_callback_called_on_strict_failure(self, mock_create, tmp_path):
        mock_create.side_effect = Exception("API error")
        callback = MagicMock()

        batch_generate(
            ["a cat", "a dog"],
            output_dir=tmp_path / "out",
            strict=True,
            delay_between_requests=0,
            progress_callback=callback,
        )

        # Only the failed item is counted before break
        assert callback.call_count == 1

    @patch("sticker_generator.batch.create_sticker")
    def test_works_without_callback(self, mock_create, tmp_path):
        mock_create.return_value = _make_green_image()

        result = batch_generate(
            ["a cat", "a dog"],
            output_dir=tmp_path / "out",
            delay_between_requests=0,
        )

        assert len(result.successful) == 2

    @patch("sticker_generator.batch.create_sticker")
    def test_callback_concurrent(self, mock_create, tmp_path):
        mock_create.return_value = _make_green_image()
        callback = MagicMock()

        batch_generate(
            ["a cat", "a dog", "a bird"],
            output_dir=tmp_path / "out",
            max_workers=2,
            progress_callback=callback,
        )

        assert callback.call_count == 3


class TestBatchProcessImagesProgressCallback:
    """Tests for progress_callback in batch_process_images."""

    def test_callback_sequential(self, tmp_path):
        in_dir = tmp_path / "input"
        in_dir.mkdir()
        for name in ["a.png", "b.png"]:
            _make_green_image().save(in_dir / name)

        callback = MagicMock()
        batch_process_images(in_dir, tmp_path / "output", progress_callback=callback)

        assert callback.call_count == 2

    def test_callback_concurrent(self, tmp_path):
        in_dir = tmp_path / "input"
        in_dir.mkdir()
        for name in ["a.png", "b.png", "c.png"]:
            _make_green_image().save(in_dir / name)

        callback = MagicMock()
        batch_process_images(
            in_dir, tmp_path / "output", max_workers=2, progress_callback=callback
        )

        assert callback.call_count == 3


class TestSheetProgressCallback:
    """Tests for progress_callback in generate_sticker_sheet."""

    @patch("sticker_generator.sheet.create_sticker")
    def test_callback_sequential(self, mock_create):
        mock_create.return_value = Image.new("RGBA", (100, 100), (255, 0, 0, 255))
        callback = MagicMock()

        generate_sticker_sheet(
            "test prompt",
            variations=3,
            delay_between_requests=0,
            progress_callback=callback,
        )

        assert callback.call_count == 3

    @patch("sticker_generator.sheet.create_sticker")
    def test_callback_on_partial_failure(self, mock_create):
        call_count = {"n": 0}

        def side_effect(**kwargs):
            call_count["n"] += 1
            if call_count["n"] == 2:
                raise Exception("API error")
            return Image.new("RGBA", (100, 100))

        mock_create.side_effect = side_effect
        callback = MagicMock()

        generate_sticker_sheet(
            "test",
            variations=3,
            max_retries=0,
            delay_between_requests=0,
            progress_callback=callback,
        )

        assert callback.call_count == 3

    @patch("sticker_generator.sheet.create_sticker")
    def test_callback_concurrent(self, mock_create):
        mock_create.return_value = Image.new("RGBA", (100, 100), (255, 0, 0, 255))
        callback = MagicMock()

        generate_sticker_sheet(
            "test prompt",
            variations=4,
            max_workers=2,
            delay_between_requests=0,
            progress_callback=callback,
        )

        assert callback.call_count == 4


class TestCLIProgressBars:
    """Tests for tqdm integration in CLI."""

    @patch("sticker_generator.cli.batch_generate")
    @patch("sticker_generator.cli.parse_prompt_file")
    def test_batch_prompts_passes_progress_callback(
        self, mock_parse, mock_batch, tmp_path
    ):
        prompts_file = tmp_path / "prompts.txt"
        prompts_file.write_text("a cat\n")

        mock_parse.return_value = ["a cat"]
        mock_batch.return_value = BatchResult(
            successful=[BatchItem(0, "a cat")], failed=[], total=1
        )

        with patch.object(
            sys,
            "argv",
            [
                "prog",
                "--batch-prompts",
                str(prompts_file),
                "--output-dir",
                str(tmp_path / "out"),
            ],
        ):
            result = main()

        assert result == 0
        call_kwargs = mock_batch.call_args[1]
        assert "progress_callback" in call_kwargs
        assert call_kwargs["progress_callback"] is not None

    @patch("sticker_generator.cli.batch_process_images")
    def test_batch_dir_passes_progress_callback(self, mock_batch, tmp_path):
        in_dir = tmp_path / "input"
        in_dir.mkdir()
        _make_green_image().save(in_dir / "a.png")

        mock_batch.return_value = BatchResult(
            successful=[BatchItem(0, "a.png")], failed=[], total=1
        )

        with patch.object(
            sys,
            "argv",
            [
                "prog",
                "--batch-dir",
                str(in_dir),
                "--output-dir",
                str(tmp_path / "out"),
            ],
        ):
            result = main()

        assert result == 0
        call_kwargs = mock_batch.call_args[1]
        assert "progress_callback" in call_kwargs
        assert call_kwargs["progress_callback"] is not None

    @patch("sticker_generator.cli.generate_sticker_sheet")
    def test_sheet_passes_progress_callback(self, mock_sheet):
        mock_sheet.return_value = MagicMock(
            stickers=[Image.new("RGBA", (100, 100))],
            sheet=Image.new("RGBA", (100, 100)),
            failed_indices=[],
        )

        with patch.object(
            sys,
            "argv",
            ["prog", "test prompt", "-n", "2", "--sheet"],
        ):
            result = main()

        assert result == 0
        call_kwargs = mock_sheet.call_args[1]
        assert "progress_callback" in call_kwargs
        assert call_kwargs["progress_callback"] is not None

    def test_no_progress_flag_parsed(self):
        """--no-progress flag should be parsed correctly."""
        with patch.object(
            sys,
            "argv",
            ["prog", "test prompt", "--no-progress"],
        ):
            with patch("sticker_generator.cli.create_sticker") as mock_create:
                mock_create.return_value = Image.new("RGBA", (100, 100))
                result = main()

        assert result == 0

    @patch("sticker_generator.cli.batch_generate")
    @patch("sticker_generator.cli.parse_prompt_file")
    def test_quiet_disables_progress(self, mock_parse, mock_batch, tmp_path):
        """--quiet should disable progress bars."""
        prompts_file = tmp_path / "prompts.txt"
        prompts_file.write_text("a cat\n")

        mock_parse.return_value = ["a cat"]
        mock_batch.return_value = BatchResult(
            successful=[BatchItem(0, "a cat")], failed=[], total=1
        )

        with patch.object(
            sys,
            "argv",
            [
                "prog",
                "--batch-prompts",
                str(prompts_file),
                "--output-dir",
                str(tmp_path / "out"),
                "--quiet",
            ],
        ):
            result = main()

        assert result == 0
        # Callback is still passed (tqdm is just disabled internally)
        call_kwargs = mock_batch.call_args[1]
        assert "progress_callback" in call_kwargs

    @patch("sticker_generator.cli.batch_generate")
    @patch("sticker_generator.cli.parse_prompt_file")
    def test_verbose_with_no_progress(self, mock_parse, mock_batch, tmp_path):
        """--verbose and --no-progress can be combined."""
        prompts_file = tmp_path / "prompts.txt"
        prompts_file.write_text("a cat\n")

        mock_parse.return_value = ["a cat"]
        mock_batch.return_value = BatchResult(
            successful=[BatchItem(0, "a cat")], failed=[], total=1
        )

        with patch.object(
            sys,
            "argv",
            [
                "prog",
                "--batch-prompts",
                str(prompts_file),
                "--output-dir",
                str(tmp_path / "out"),
                "--verbose",
                "--no-progress",
            ],
        ):
            result = main()

        assert result == 0
