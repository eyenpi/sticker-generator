"""Tests for concurrent execution in sheet and batch workflows."""

import sys
import threading
import time
from unittest.mock import patch

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


class TestSheetConcurrent:
    """Tests for concurrent sheet generation."""

    @patch("sticker_generator.sheet.create_sticker")
    def test_concurrent_produces_correct_count(self, mock_create):
        mock_create.return_value = Image.new("RGBA", (100, 100), (255, 0, 0, 255))

        result = generate_sticker_sheet(
            "test prompt", variations=4, max_workers=2, delay_between_requests=0
        )

        assert mock_create.call_count == 4
        assert len(result.stickers) == 4
        assert len(result.failed_indices) == 0
        assert result.sheet is not None

    @patch("sticker_generator.sheet.create_sticker")
    def test_concurrent_preserves_result_ordering(self, mock_create):
        """Results should be in submission order regardless of completion order."""
        colors = {
            "variation_1": (255, 0, 0, 255),
            "variation_2": (0, 255, 0, 255),
            "variation_3": (0, 0, 255, 255),
            "variation_4": (255, 255, 0, 255),
        }

        def side_effect(**kwargs):
            intermediates = str(kwargs.get("save_intermediates", ""))
            for key, color in colors.items():
                if key in intermediates:
                    return Image.new("RGBA", (100, 100), color)
            return Image.new("RGBA", (100, 100))

        mock_create.side_effect = side_effect

        result = generate_sticker_sheet(
            "test",
            variations=4,
            max_workers=4,
            delay_between_requests=0,
            save_intermediates="/tmp/test_ordering",
        )

        assert len(result.stickers) == 4
        expected = list(colors.values())
        for i, color in enumerate(expected):
            pixel = result.stickers[i].getpixel((50, 50))
            assert pixel == color, f"Sticker {i} has wrong color"

    @patch("sticker_generator.sheet.create_sticker")
    def test_concurrent_handles_partial_failure(self, mock_create):
        def side_effect(**kwargs):
            intermediates = str(kwargs.get("save_intermediates", ""))
            if "variation_2" in intermediates:
                raise Exception("API error")
            return Image.new("RGBA", (100, 100))

        mock_create.side_effect = side_effect

        result = generate_sticker_sheet(
            "test",
            variations=3,
            max_retries=0,
            max_workers=2,
            delay_between_requests=0,
            save_intermediates="/tmp/test_failure",
        )

        assert len(result.stickers) == 2
        assert 1 in result.failed_indices
        assert result.sheet is not None

    @patch("sticker_generator.sheet.create_sticker")
    def test_concurrent_retry_works_within_threads(self, mock_create):
        """Retry logic should still function within each thread."""
        call_count = {"n": 0}
        lock = threading.Lock()

        def side_effect(**kwargs):
            with lock:
                call_count["n"] += 1
                n = call_count["n"]
            # First call for variation 1 fails, retry succeeds
            if n == 1:
                raise Exception("transient error")
            return Image.new("RGBA", (100, 100))

        mock_create.side_effect = side_effect

        result = generate_sticker_sheet(
            "test",
            variations=2,
            max_retries=1,
            max_workers=2,
            delay_between_requests=0,
        )

        # At least one retry happened
        assert mock_create.call_count >= 2
        # All should eventually succeed or at most 1 fails
        assert len(result.stickers) >= 1

    @patch("sticker_generator.sheet.create_sticker")
    def test_concurrent_delay_ignored_with_log(self, mock_create, caplog):
        mock_create.return_value = Image.new("RGBA", (100, 100))

        with caplog.at_level("DEBUG", logger="sticker_generator"):
            generate_sticker_sheet(
                "test",
                variations=2,
                max_workers=2,
                delay_between_requests=5.0,
            )

        assert any(
            "Ignoring delay_between_requests" in r.message for r in caplog.records
        )

    @patch("sticker_generator.sheet.create_sticker")
    def test_sequential_still_works_with_max_workers_1(self, mock_create):
        mock_create.return_value = Image.new("RGBA", (100, 100), (255, 0, 0, 255))

        result = generate_sticker_sheet(
            "test prompt", variations=3, max_workers=1, delay_between_requests=0
        )

        assert mock_create.call_count == 3
        assert len(result.stickers) == 3
        assert len(result.failed_indices) == 0

    @patch("sticker_generator.sheet.create_sticker")
    def test_concurrent_uses_multiple_threads(self, mock_create):
        """Verify that concurrent mode actually uses multiple threads."""
        thread_ids = []
        lock = threading.Lock()

        def side_effect(**kwargs):
            with lock:
                thread_ids.append(threading.current_thread().ident)
            # Small delay to ensure threads overlap
            time.sleep(0.05)
            return Image.new("RGBA", (100, 100))

        mock_create.side_effect = side_effect

        generate_sticker_sheet(
            "test", variations=4, max_workers=4, delay_between_requests=0
        )

        # With 4 workers and overlapping tasks, we should see multiple threads
        unique_threads = set(thread_ids)
        assert len(unique_threads) > 1, (
            f"Expected multiple threads but got {len(unique_threads)}"
        )


class TestBatchGenerateConcurrent:
    """Tests for concurrent batch generation."""

    @patch("sticker_generator.batch.create_sticker")
    def test_concurrent_all_succeed(self, mock_create, tmp_path):
        mock_create.return_value = _make_green_image()
        result = batch_generate(
            ["a cat", "a dog", "a bird"],
            output_dir=tmp_path / "out",
            max_workers=2,
            delay_between_requests=0,
        )
        assert len(result.successful) == 3
        assert len(result.failed) == 0
        assert result.total == 3

    @patch("sticker_generator.batch.create_sticker")
    def test_concurrent_partial_failure(self, mock_create, tmp_path):
        mock_create.side_effect = [
            _make_green_image(),
            Exception("API error"),
            _make_green_image(),
        ]
        result = batch_generate(
            ["a cat", "a dog", "a bird"],
            output_dir=tmp_path / "out",
            max_workers=3,
            delay_between_requests=0,
        )
        assert len(result.successful) == 2
        assert len(result.failed) == 1
        assert result.failed[0].error == "API error"
        assert result.failed[0].index == 1

    @patch("sticker_generator.batch.create_sticker")
    def test_strict_forces_sequential_with_warning(self, mock_create, tmp_path, caplog):
        mock_create.side_effect = [
            Exception("API error"),
            _make_green_image(),
        ]

        with caplog.at_level("WARNING", logger="sticker_generator"):
            result = batch_generate(
                ["a cat", "a dog"],
                output_dir=tmp_path / "out",
                strict=True,
                max_workers=4,
                delay_between_requests=0,
            )

        # Should warn about fallback
        assert any("falling back to sequential" in r.message for r in caplog.records)
        # Strict mode stops on first failure
        assert len(result.successful) == 0
        assert len(result.failed) == 1
        assert mock_create.call_count == 1

    @patch("sticker_generator.batch.create_sticker")
    def test_concurrent_output_naming(self, mock_create, tmp_path):
        mock_create.return_value = _make_green_image()
        result = batch_generate(
            ["a cat", "a dog"],
            output_dir=tmp_path / "out",
            max_workers=2,
            delay_between_requests=0,
        )
        paths = {item.output_path.name for item in result.successful}
        assert "sticker_001.png" in paths
        assert "sticker_002.png" in paths

    @patch("sticker_generator.batch.create_sticker")
    def test_concurrent_delay_ignored_with_log(self, mock_create, tmp_path, caplog):
        mock_create.return_value = _make_green_image()

        with caplog.at_level("DEBUG", logger="sticker_generator"):
            batch_generate(
                ["a cat", "a dog"],
                output_dir=tmp_path / "out",
                max_workers=2,
                delay_between_requests=5.0,
            )

        assert any(
            "Ignoring delay_between_requests" in r.message for r in caplog.records
        )


class TestBatchProcessImagesConcurrent:
    """Tests for concurrent batch image processing."""

    def test_concurrent_processing(self, tmp_path):
        in_dir = tmp_path / "input"
        in_dir.mkdir()
        out_dir = tmp_path / "output"

        for name in ["a.png", "b.png", "c.png"]:
            _make_green_image().save(in_dir / name)

        result = batch_process_images(in_dir, out_dir, max_workers=2)
        assert len(result.successful) == 3
        assert len(result.failed) == 0
        assert result.total == 3
        assert (out_dir / "a.png").exists()
        assert (out_dir / "b.png").exists()
        assert (out_dir / "c.png").exists()

    def test_concurrent_collision_avoidance(self, tmp_path):
        in_dir = tmp_path / "input"
        in_dir.mkdir()
        out_dir = tmp_path / "output"

        _make_green_image().convert("RGB").save(in_dir / "photo.jpg")
        _make_green_image().save(in_dir / "photo.png")

        result = batch_process_images(in_dir, out_dir, max_workers=2)
        paths = {item.output_path.name for item in result.successful}
        assert len(paths) == 2
        assert "photo.png" in paths
        assert "photo_2.png" in paths

    def test_strict_forces_sequential(self, tmp_path, caplog):
        in_dir = tmp_path / "input"
        in_dir.mkdir()
        out_dir = tmp_path / "output"

        _make_green_image().save(in_dir / "a_good.png")
        (in_dir / "b_bad.png").write_bytes(b"not an image")
        _make_green_image().save(in_dir / "c_good.png")

        with caplog.at_level("WARNING", logger="sticker_generator"):
            result = batch_process_images(in_dir, out_dir, strict=True, max_workers=4)

        assert any("falling back to sequential" in r.message for r in caplog.records)
        # Strict stops on first failure
        assert len(result.successful) == 1
        assert len(result.failed) == 1

    def test_concurrent_continue_on_error(self, tmp_path):
        in_dir = tmp_path / "input"
        in_dir.mkdir()
        out_dir = tmp_path / "output"

        _make_green_image().save(in_dir / "a_good.png")
        (in_dir / "b_bad.png").write_bytes(b"not an image")
        _make_green_image().save(in_dir / "c_good.png")

        result = batch_process_images(in_dir, out_dir, max_workers=2)
        assert len(result.successful) == 2
        assert len(result.failed) == 1


class TestCLIMaxWorkers:
    """Tests for --max-workers CLI argument."""

    @patch("sticker_generator.cli.batch_generate")
    @patch("sticker_generator.cli.parse_prompt_file")
    def test_max_workers_forwarded_to_batch_generate(
        self, mock_parse, mock_batch, tmp_path
    ):
        prompts_file = tmp_path / "prompts.txt"
        prompts_file.write_text("a cat\n")
        out_dir = tmp_path / "out"

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
                str(out_dir),
                "--max-workers",
                "4",
            ],
        ):
            result = main()

        assert result == 0
        call_kwargs = mock_batch.call_args[1]
        assert call_kwargs["max_workers"] == 4

    @patch("sticker_generator.cli.batch_process_images")
    def test_max_workers_forwarded_to_batch_process(self, mock_batch, tmp_path):
        in_dir = tmp_path / "input"
        in_dir.mkdir()
        out_dir = tmp_path / "out"

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
                str(out_dir),
                "--max-workers",
                "3",
            ],
        ):
            result = main()

        assert result == 0
        call_kwargs = mock_batch.call_args[1]
        assert call_kwargs["max_workers"] == 3

    @patch("sticker_generator.cli.generate_sticker_sheet")
    def test_max_workers_forwarded_to_sheet(self, mock_sheet, tmp_path):
        mock_sheet.return_value = type(
            "SheetResult",
            (),
            {"stickers": [Image.new("RGBA", (10, 10))], "failed_indices": []},
        )()

        with patch.object(
            sys,
            "argv",
            [
                "prog",
                "cute cat",
                "-n",
                "4",
                "--sheet",
                "-o",
                str(tmp_path / "sheet.png"),
                "--max-workers",
                "2",
            ],
        ):
            result = main()

        assert result == 0
        call_kwargs = mock_sheet.call_args[1]
        assert call_kwargs["max_workers"] == 2

    def test_default_max_workers_is_1(self, tmp_path, caplog):
        """Default max_workers should be 1 (sequential)."""
        prompts_file = tmp_path / "prompts.txt"
        prompts_file.write_text("a cat\n")
        out_dir = tmp_path / "out"

        with (
            patch("sticker_generator.cli.batch_generate") as mock_batch,
            patch("sticker_generator.cli.parse_prompt_file") as mock_parse,
        ):
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
                    str(out_dir),
                ],
            ):
                main()

            call_kwargs = mock_batch.call_args[1]
            assert call_kwargs["max_workers"] == 1

    def test_max_workers_zero_rejected(self, caplog):
        with caplog.at_level("ERROR", logger="sticker_generator"):
            with patch.object(
                sys,
                "argv",
                ["prog", "a cat", "--max-workers", "0"],
            ):
                result = main()

        assert result == 1
        assert any(
            "--max-workers must be at least 1" in r.message for r in caplog.records
        )

    def test_max_workers_negative_rejected(self, caplog):
        with caplog.at_level("ERROR", logger="sticker_generator"):
            with patch.object(
                sys,
                "argv",
                ["prog", "a cat", "--max-workers", "-1"],
            ):
                result = main()

        assert result == 1
        assert any(
            "--max-workers must be at least 1" in r.message for r in caplog.records
        )
