"""Tests for batch processing."""

import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from PIL import Image

from sticker_generator.batch import (
    BatchItem,
    BatchResult,
    batch_generate,
    batch_process_images,
    parse_prompt_file,
)
from sticker_generator.cli import main


def _make_green_image(size=(100, 100)):
    """Create a test image with green background and red subject."""
    data = np.zeros((size[1], size[0], 4), dtype=np.uint8)
    # Green background
    data[:, :] = [0, 255, 0, 255]
    # Red square in center
    h, w = size[1], size[0]
    data[h // 4 : 3 * h // 4, w // 4 : 3 * w // 4] = [255, 0, 0, 255]
    return Image.fromarray(data, "RGBA")


class TestBatchItem:
    """Tests for BatchItem dataclass."""

    def test_defaults(self):
        item = BatchItem(index=0, source="test")
        assert item.index == 0
        assert item.source == "test"
        assert item.output_path is None
        assert item.error is None

    def test_with_values(self):
        item = BatchItem(
            index=5,
            source="a cat",
            output_path=Path("/tmp/out.png"),
            error="failed",
        )
        assert item.index == 5
        assert item.source == "a cat"
        assert item.output_path == Path("/tmp/out.png")
        assert item.error == "failed"


class TestBatchResult:
    """Tests for BatchResult dataclass."""

    def test_defaults(self):
        result = BatchResult()
        assert result.successful == []
        assert result.failed == []
        assert result.total == 0

    def test_with_values(self):
        item = BatchItem(index=0, source="test")
        result = BatchResult(successful=[item], failed=[], total=1)
        assert len(result.successful) == 1
        assert result.total == 1


class TestParsePromptFile:
    """Tests for parse_prompt_file function."""

    def test_reads_prompts(self, tmp_path):
        f = tmp_path / "prompts.txt"
        f.write_text("a cat\na dog\na bird\n")
        result = parse_prompt_file(f)
        assert result == ["a cat", "a dog", "a bird"]

    def test_skips_blank_lines(self, tmp_path):
        f = tmp_path / "prompts.txt"
        f.write_text("a cat\n\n\na dog\n")
        result = parse_prompt_file(f)
        assert result == ["a cat", "a dog"]

    def test_skips_comment_lines(self, tmp_path):
        f = tmp_path / "prompts.txt"
        f.write_text("# This is a comment\na cat\n# Another comment\na dog\n")
        result = parse_prompt_file(f)
        assert result == ["a cat", "a dog"]

    def test_strips_whitespace(self, tmp_path):
        f = tmp_path / "prompts.txt"
        f.write_text("  a cat  \n  a dog  \n")
        result = parse_prompt_file(f)
        assert result == ["a cat", "a dog"]

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError, match="Prompt file not found"):
            parse_prompt_file("/nonexistent/prompts.txt")

    def test_empty_file_raises(self, tmp_path):
        f = tmp_path / "prompts.txt"
        f.write_text("")
        with pytest.raises(ValueError, match="No valid prompts found"):
            parse_prompt_file(f)

    def test_only_comments_raises(self, tmp_path):
        f = tmp_path / "prompts.txt"
        f.write_text("# comment 1\n# comment 2\n\n")
        with pytest.raises(ValueError, match="No valid prompts found"):
            parse_prompt_file(f)


class TestBatchGenerate:
    """Tests for batch_generate function."""

    @patch("sticker_generator.batch.create_sticker")
    def test_all_succeed(self, mock_create, tmp_path):
        mock_create.return_value = _make_green_image()
        result = batch_generate(
            ["a cat", "a dog"],
            output_dir=tmp_path / "out",
            delay_between_requests=0,
        )
        assert len(result.successful) == 2
        assert len(result.failed) == 0
        assert result.total == 2
        assert mock_create.call_count == 2

    @patch("sticker_generator.batch.create_sticker")
    def test_continue_on_error(self, mock_create, tmp_path):
        mock_create.side_effect = [
            _make_green_image(),
            Exception("API error"),
            _make_green_image(),
        ]
        result = batch_generate(
            ["a cat", "a dog", "a bird"],
            output_dir=tmp_path / "out",
            delay_between_requests=0,
        )
        assert len(result.successful) == 2
        assert len(result.failed) == 1
        assert result.failed[0].error == "API error"
        assert result.failed[0].index == 1

    @patch("sticker_generator.batch.create_sticker")
    def test_strict_mode_stops_on_failure(self, mock_create, tmp_path):
        mock_create.side_effect = [
            Exception("API error"),
            _make_green_image(),
        ]
        result = batch_generate(
            ["a cat", "a dog"],
            output_dir=tmp_path / "out",
            strict=True,
            delay_between_requests=0,
        )
        assert len(result.successful) == 0
        assert len(result.failed) == 1
        # Second item never attempted
        assert mock_create.call_count == 1

    @patch("sticker_generator.batch.create_sticker")
    def test_output_naming(self, mock_create, tmp_path):
        mock_create.return_value = _make_green_image()
        result = batch_generate(
            ["a cat", "a dog"],
            output_dir=tmp_path / "out",
            delay_between_requests=0,
        )
        assert result.successful[0].output_path == tmp_path / "out" / "sticker_001.png"
        assert result.successful[1].output_path == tmp_path / "out" / "sticker_002.png"

    @patch("sticker_generator.batch.create_sticker")
    def test_output_naming_webp(self, mock_create, tmp_path):
        mock_create.return_value = _make_green_image()
        result = batch_generate(
            ["a cat"],
            output_dir=tmp_path / "out",
            output_format="webp",
            delay_between_requests=0,
        )
        assert result.successful[0].output_path == tmp_path / "out" / "sticker_001.webp"

    @patch("sticker_generator.batch.create_sticker")
    @patch("sticker_generator.batch.time.sleep")
    def test_delay_between_requests(self, mock_sleep, mock_create, tmp_path):
        mock_create.return_value = _make_green_image()
        batch_generate(
            ["a cat", "a dog", "a bird"],
            output_dir=tmp_path / "out",
            delay_between_requests=2.0,
        )
        # Sleep called between items (not after last)
        assert mock_sleep.call_count == 2
        mock_sleep.assert_called_with(2.0)

    @patch("sticker_generator.batch.create_sticker")
    def test_parameter_forwarding(self, mock_create, tmp_path):
        mock_create.return_value = _make_green_image()
        batch_generate(
            ["a cat"],
            output_dir=tmp_path / "out",
            style="kawaii",
            aspect_ratio="16:9",
            api_key="test-key",
            edge_threshold=128,
            hue_center=120,
            hue_range=40,
            min_saturation=30,
            min_value=50,
            green_threshold=1.3,
            max_retries=5,
            retry_delay=2.0,
            delay_between_requests=0,
        )
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["style"] == "kawaii"
        assert call_kwargs["aspect_ratio"] == "16:9"
        assert call_kwargs["api_key"] == "test-key"
        assert call_kwargs["edge_threshold"] == 128
        assert call_kwargs["hue_center"] == 120
        assert call_kwargs["hue_range"] == 40
        assert call_kwargs["min_saturation"] == 30
        assert call_kwargs["min_value"] == 50
        assert call_kwargs["green_threshold"] == 1.3
        assert call_kwargs["max_retries"] == 5
        assert call_kwargs["retry_delay"] == 2.0

    @patch("sticker_generator.batch.create_sticker")
    def test_creates_output_dir(self, mock_create, tmp_path):
        mock_create.return_value = _make_green_image()
        out = tmp_path / "nested" / "output"
        assert not out.exists()
        batch_generate(["a cat"], output_dir=out, delay_between_requests=0)
        assert out.exists()

    @patch("sticker_generator.batch.create_sticker")
    def test_progress_logging(self, mock_create, tmp_path, caplog):
        mock_create.return_value = _make_green_image()
        with caplog.at_level("INFO", logger="sticker_generator"):
            batch_generate(
                ["a cat", "a dog"],
                output_dir=tmp_path / "out",
                delay_between_requests=0,
            )
        assert any("Batch generate: 1/2" in r.message for r in caplog.records)
        assert any("Batch generate: 2/2" in r.message for r in caplog.records)
        assert any("2/2 successful" in r.message for r in caplog.records)

    @patch("sticker_generator.batch.create_sticker")
    def test_save_intermediates(self, mock_create, tmp_path):
        mock_create.return_value = _make_green_image()
        batch_generate(
            ["a cat", "a dog"],
            output_dir=tmp_path / "out",
            save_intermediates=str(tmp_path / "intermediates"),
            delay_between_requests=0,
        )
        # Verify intermediates path passed to create_sticker
        calls = mock_create.call_args_list
        assert calls[0][1]["save_intermediates"] == str(
            tmp_path / "intermediates" / "batch_001"
        )
        assert calls[1][1]["save_intermediates"] == str(
            tmp_path / "intermediates" / "batch_002"
        )


class TestBatchProcessImages:
    """Tests for batch_process_images function."""

    def test_processes_all_images(self, tmp_path):
        in_dir = tmp_path / "input"
        in_dir.mkdir()
        out_dir = tmp_path / "output"

        # Create test images
        for name in ["a.png", "b.png"]:
            _make_green_image().save(in_dir / name)

        result = batch_process_images(in_dir, out_dir)
        assert len(result.successful) == 2
        assert len(result.failed) == 0
        assert result.total == 2
        assert (out_dir / "a.png").exists()
        assert (out_dir / "b.png").exists()

    def test_preserves_filenames(self, tmp_path):
        in_dir = tmp_path / "input"
        in_dir.mkdir()
        out_dir = tmp_path / "output"

        _make_green_image().save(in_dir / "photo.png")
        result = batch_process_images(in_dir, out_dir)
        assert result.successful[0].output_path == out_dir / "photo.png"

    def test_handles_mixed_extensions(self, tmp_path):
        in_dir = tmp_path / "input"
        in_dir.mkdir()
        out_dir = tmp_path / "output"

        _make_green_image().save(in_dir / "a.png")
        _make_green_image().convert("RGB").save(in_dir / "b.jpg")

        result = batch_process_images(in_dir, out_dir)
        assert result.total == 2
        assert len(result.successful) == 2

    def test_skips_non_image_files(self, tmp_path):
        in_dir = tmp_path / "input"
        in_dir.mkdir()
        out_dir = tmp_path / "output"

        _make_green_image().save(in_dir / "image.png")
        (in_dir / "readme.txt").write_text("not an image")

        result = batch_process_images(in_dir, out_dir)
        assert result.total == 1

    def test_sorted_alphabetically(self, tmp_path):
        in_dir = tmp_path / "input"
        in_dir.mkdir()
        out_dir = tmp_path / "output"

        for name in ["c.png", "a.png", "b.png"]:
            _make_green_image().save(in_dir / name)

        result = batch_process_images(in_dir, out_dir)
        sources = [item.source for item in result.successful]
        assert sources == [
            str(in_dir / "a.png"),
            str(in_dir / "b.png"),
            str(in_dir / "c.png"),
        ]

    def test_collision_avoidance(self, tmp_path):
        """Two different extension files with same stem get unique output names."""
        in_dir = tmp_path / "input"
        in_dir.mkdir()
        out_dir = tmp_path / "output"

        _make_green_image().convert("RGB").save(in_dir / "photo.jpg")
        _make_green_image().save(in_dir / "photo.png")

        result = batch_process_images(in_dir, out_dir)
        paths = {item.output_path.name for item in result.successful}
        assert len(paths) == 2
        assert "photo.png" in paths
        assert "photo_2.png" in paths

    def test_input_dir_not_found(self):
        with pytest.raises(FileNotFoundError, match="Input directory not found"):
            batch_process_images("/nonexistent/dir", "/tmp/out")

    def test_empty_dir_raises(self, tmp_path):
        in_dir = tmp_path / "input"
        in_dir.mkdir()
        with pytest.raises(ValueError, match="No image files found"):
            batch_process_images(in_dir, tmp_path / "out")

    def test_strict_mode_stops_on_failure(self, tmp_path):
        in_dir = tmp_path / "input"
        in_dir.mkdir()
        out_dir = tmp_path / "output"

        # Create a valid image and a corrupt "image"
        _make_green_image().save(in_dir / "a_good.png")
        (in_dir / "b_bad.png").write_bytes(b"not an image")
        _make_green_image().save(in_dir / "c_good.png")

        result = batch_process_images(in_dir, out_dir, strict=True)
        # First succeeds, second fails, third never attempted
        assert len(result.successful) == 1
        assert len(result.failed) == 1

    def test_continue_on_error(self, tmp_path):
        in_dir = tmp_path / "input"
        in_dir.mkdir()
        out_dir = tmp_path / "output"

        _make_green_image().save(in_dir / "a_good.png")
        (in_dir / "b_bad.png").write_bytes(b"not an image")
        _make_green_image().save(in_dir / "c_good.png")

        result = batch_process_images(in_dir, out_dir)
        assert len(result.successful) == 2
        assert len(result.failed) == 1

    def test_creates_output_dir(self, tmp_path):
        in_dir = tmp_path / "input"
        in_dir.mkdir()
        out_dir = tmp_path / "nested" / "output"

        _make_green_image().save(in_dir / "a.png")
        assert not out_dir.exists()
        batch_process_images(in_dir, out_dir)
        assert out_dir.exists()

    def test_output_format_changes_extension(self, tmp_path):
        in_dir = tmp_path / "input"
        in_dir.mkdir()
        out_dir = tmp_path / "output"

        _make_green_image().save(in_dir / "photo.png")
        result = batch_process_images(in_dir, out_dir, output_format="webp")
        assert result.successful[0].output_path == out_dir / "photo.webp"


class TestBatchCLI:
    """Tests for batch CLI flags."""

    @patch("sticker_generator.cli.batch_generate")
    @patch("sticker_generator.cli.parse_prompt_file")
    def test_batch_prompts_routing(self, mock_parse, mock_batch, tmp_path):
        prompts_file = tmp_path / "prompts.txt"
        prompts_file.write_text("a cat\na dog\n")
        out_dir = tmp_path / "out"

        mock_parse.return_value = ["a cat", "a dog"]
        mock_batch.return_value = BatchResult(
            successful=[BatchItem(0, "a cat"), BatchItem(1, "a dog")],
            failed=[],
            total=2,
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
            result = main()

        assert result == 0
        mock_parse.assert_called_once_with(str(prompts_file))
        mock_batch.assert_called_once()

    @patch("sticker_generator.cli.batch_process_images")
    def test_batch_dir_routing(self, mock_batch, tmp_path):
        in_dir = tmp_path / "input"
        in_dir.mkdir()
        out_dir = tmp_path / "out"

        mock_batch.return_value = BatchResult(
            successful=[BatchItem(0, "a.png")], failed=[], total=1
        )

        with patch.object(
            sys,
            "argv",
            ["prog", "--batch-dir", str(in_dir), "--output-dir", str(out_dir)],
        ):
            result = main()

        assert result == 0
        mock_batch.assert_called_once()

    @patch("sticker_generator.cli.batch_generate")
    @patch("sticker_generator.cli.parse_prompt_file")
    def test_batch_prompts_forwards_params(self, mock_parse, mock_batch, tmp_path):
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
                "-s",
                "kawaii",
                "-f",
                "webp",
                "--resize",
                "512",
            ],
        ):
            result = main()

        assert result == 0
        call_kwargs = mock_batch.call_args[1]
        assert call_kwargs["style"] == "kawaii"
        assert call_kwargs["output_format"] == "webp"
        assert call_kwargs["resize"] == (512, 512)

    @patch("sticker_generator.cli.batch_generate")
    @patch("sticker_generator.cli.parse_prompt_file")
    def test_batch_strict_returns_1_on_failure(self, mock_parse, mock_batch, tmp_path):
        prompts_file = tmp_path / "prompts.txt"
        prompts_file.write_text("a cat\n")
        out_dir = tmp_path / "out"

        mock_parse.return_value = ["a cat"]
        mock_batch.return_value = BatchResult(
            successful=[],
            failed=[BatchItem(0, "a cat", error="fail")],
            total=1,
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
                "--strict",
            ],
        ):
            result = main()

        assert result == 1

    def test_missing_output_dir(self, tmp_path, caplog):
        prompts_file = tmp_path / "prompts.txt"
        prompts_file.write_text("a cat\n")

        with caplog.at_level("ERROR", logger="sticker_generator"):
            with patch.object(
                sys,
                "argv",
                ["prog", "--batch-prompts", str(prompts_file)],
            ):
                result = main()

        assert result == 1
        assert any("--output-dir is required" in r.message for r in caplog.records)

    def test_mutual_exclusivity_prompts_and_dir(self, tmp_path, caplog):
        prompts_file = tmp_path / "prompts.txt"
        prompts_file.write_text("a cat\n")
        in_dir = tmp_path / "input"
        in_dir.mkdir()

        with caplog.at_level("ERROR", logger="sticker_generator"):
            with patch.object(
                sys,
                "argv",
                [
                    "prog",
                    "--batch-prompts",
                    str(prompts_file),
                    "--batch-dir",
                    str(in_dir),
                    "--output-dir",
                    str(tmp_path / "out"),
                ],
            ):
                result = main()

        assert result == 1
        assert any(
            "Cannot use both --batch-prompts and --batch-dir" in r.message
            for r in caplog.records
        )

    def test_mutual_exclusivity_dir_and_process(self, tmp_path, caplog):
        in_dir = tmp_path / "input"
        in_dir.mkdir()
        img = tmp_path / "img.png"
        _make_green_image().save(img)

        with caplog.at_level("ERROR", logger="sticker_generator"):
            with patch.object(
                sys,
                "argv",
                [
                    "prog",
                    "--batch-dir",
                    str(in_dir),
                    "--process",
                    str(img),
                    "--output-dir",
                    str(tmp_path / "out"),
                ],
            ):
                result = main()

        assert result == 1
        assert any(
            "Cannot use both --batch-dir and --process" in r.message
            for r in caplog.records
        )

    def test_batch_prompts_with_positional_prompt(self, tmp_path, caplog):
        prompts_file = tmp_path / "prompts.txt"
        prompts_file.write_text("a cat\n")

        with caplog.at_level("ERROR", logger="sticker_generator"):
            with patch.object(
                sys,
                "argv",
                [
                    "prog",
                    "a dog",
                    "--batch-prompts",
                    str(prompts_file),
                    "--output-dir",
                    str(tmp_path / "out"),
                ],
            ):
                result = main()

        assert result == 1
        assert any(
            "Cannot use both --batch-prompts and a positional prompt" in r.message
            for r in caplog.records
        )

    def test_batch_with_variations_rejected(self, tmp_path, caplog):
        prompts_file = tmp_path / "prompts.txt"
        prompts_file.write_text("a cat\n")

        with caplog.at_level("ERROR", logger="sticker_generator"):
            with patch.object(
                sys,
                "argv",
                [
                    "prog",
                    "--batch-prompts",
                    str(prompts_file),
                    "--output-dir",
                    str(tmp_path / "out"),
                    "-n",
                    "4",
                ],
            ):
                result = main()

        assert result == 1
        assert any(
            "not compatible with batch modes" in r.message for r in caplog.records
        )

    def test_batch_prompts_file_not_found(self, caplog):
        with caplog.at_level("ERROR", logger="sticker_generator"):
            with patch.object(
                sys,
                "argv",
                [
                    "prog",
                    "--batch-prompts",
                    "/nonexistent/prompts.txt",
                    "--output-dir",
                    "/tmp/out",
                ],
            ):
                result = main()

        assert result == 1
        assert any("Prompt file not found" in r.message for r in caplog.records)

    def test_batch_dir_not_found(self, caplog):
        with caplog.at_level("ERROR", logger="sticker_generator"):
            with patch.object(
                sys,
                "argv",
                [
                    "prog",
                    "--batch-dir",
                    "/nonexistent/dir",
                    "--output-dir",
                    "/tmp/out",
                ],
            ):
                result = main()

        assert result == 1
        assert any("Input directory not found" in r.message for r in caplog.records)

    @patch("sticker_generator.cli.batch_generate")
    @patch("sticker_generator.cli.parse_prompt_file")
    def test_delay_forwarded(self, mock_parse, mock_batch, tmp_path):
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
                "--delay",
                "2.5",
            ],
        ):
            main()

        call_kwargs = mock_batch.call_args[1]
        assert call_kwargs["delay_between_requests"] == 2.5
