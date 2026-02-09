"""Tests for process_image functionality."""

import sys
from unittest.mock import patch

import numpy as np
from PIL import Image

from sticker_generator.core import process_image


def create_green_bg_image(tmp_path, filename="input.png"):
    """Create a test image with green background and red square, save to disk."""
    img = Image.new("RGBA", (100, 100), (0, 255, 0, 255))  # Green background
    for x in range(30, 70):
        for y in range(30, 70):
            img.putpixel((x, y), (255, 0, 0, 255))
    path = tmp_path / filename
    img.save(str(path))
    return path


class TestProcessImage:
    """Tests for process_image function."""

    def test_removes_green_background(self, tmp_path):
        input_path = create_green_bg_image(tmp_path)
        result = process_image(input_path)

        assert result.mode == "RGBA"
        data = np.array(result)
        # Green background should be transparent
        assert data[10, 10, 3] == 0
        # Red subject should be opaque
        assert data[50, 50, 3] == 255

    def test_saves_output_file(self, tmp_path):
        input_path = create_green_bg_image(tmp_path)
        output_path = tmp_path / "output.png"

        process_image(input_path, output=output_path)

        assert output_path.exists()
        loaded = Image.open(output_path)
        assert loaded.mode == "RGBA"

    def test_saves_webp_format(self, tmp_path):
        input_path = create_green_bg_image(tmp_path)
        output_path = tmp_path / "output.webp"

        process_image(input_path, output=output_path, output_format="webp")

        assert output_path.exists()
        loaded = Image.open(output_path)
        assert loaded.format == "WEBP"

    def test_resize_applied(self, tmp_path):
        input_path = create_green_bg_image(tmp_path)

        result = process_image(input_path, resize=(50, 50))

        assert result.size == (50, 50)

    def test_resize_exact(self, tmp_path):
        # Create non-square image
        img = Image.new("RGBA", (200, 100), (0, 255, 0, 255))
        for x in range(60, 140):
            for y in range(20, 80):
                img.putpixel((x, y), (255, 0, 0, 255))
        input_path = tmp_path / "wide.png"
        img.save(str(input_path))

        result = process_image(input_path, resize=(50, 50), resize_exact=True)

        assert result.size == (50, 50)

    def test_edge_threshold(self, tmp_path):
        input_path = create_green_bg_image(tmp_path)

        # Very high threshold should make semi-transparent pixels fully transparent
        result = process_image(input_path, edge_threshold=200)

        assert result.mode == "RGBA"

    def test_returns_image_without_output(self, tmp_path):
        input_path = create_green_bg_image(tmp_path)

        result = process_image(input_path)

        assert isinstance(result, Image.Image)
        assert result.mode == "RGBA"

    def test_processes_rgb_image(self, tmp_path):
        img = Image.new("RGB", (100, 100), (0, 255, 0))
        for x in range(30, 70):
            for y in range(30, 70):
                img.putpixel((x, y), (255, 0, 0))
        input_path = tmp_path / "rgb_input.png"
        img.save(str(input_path))

        result = process_image(input_path)

        assert result.mode == "RGBA"

    def test_output_with_quality(self, tmp_path):
        input_path = create_green_bg_image(tmp_path)
        output_path = tmp_path / "output.webp"

        process_image(
            input_path,
            output=output_path,
            output_format="webp-lossy",
            quality=50,
        )

        assert output_path.exists()


class TestCLIProcessFlag:
    """Tests for CLI --process flag."""

    @patch("sticker_generator.cli.process_image")
    def test_process_flag_calls_process_image(self, mock_process, tmp_path):
        from sticker_generator.cli import main

        input_path = create_green_bg_image(tmp_path)
        mock_process.return_value = Image.new("RGBA", (100, 100))

        with patch.object(
            sys,
            "argv",
            ["prog", "--process", str(input_path), "-o", "out.png"],
        ):
            result = main()

        assert result == 0
        mock_process.assert_called_once()
        call_kwargs = mock_process.call_args[1]
        assert call_kwargs["input_path"] == str(input_path)
        assert call_kwargs["output"] == "out.png"

    @patch("sticker_generator.cli.process_image")
    def test_process_with_resize(self, mock_process, tmp_path):
        from sticker_generator.cli import main

        input_path = create_green_bg_image(tmp_path)
        mock_process.return_value = Image.new("RGBA", (50, 50))

        with patch.object(
            sys,
            "argv",
            [
                "prog",
                "--process",
                str(input_path),
                "-o",
                "out.png",
                "--resize",
                "512",
            ],
        ):
            result = main()

        assert result == 0
        call_kwargs = mock_process.call_args[1]
        assert call_kwargs["resize"] == (512, 512)

    @patch("sticker_generator.cli.process_image")
    def test_process_with_format(self, mock_process, tmp_path):
        from sticker_generator.cli import main

        input_path = create_green_bg_image(tmp_path)
        mock_process.return_value = Image.new("RGBA", (100, 100))

        with patch.object(
            sys,
            "argv",
            [
                "prog",
                "--process",
                str(input_path),
                "-o",
                "out.webp",
                "-f",
                "webp",
            ],
        ):
            result = main()

        assert result == 0
        call_kwargs = mock_process.call_args[1]
        assert call_kwargs["output_format"] == "webp"

    def test_process_missing_file_error(self, capsys):
        from sticker_generator.cli import main

        with patch.object(
            sys,
            "argv",
            ["prog", "--process", "/nonexistent/image.png"],
        ):
            result = main()

        assert result == 1
        captured = capsys.readouterr()
        assert "Input image not found" in captured.err

    def test_no_prompt_no_process_error(self, capsys):
        from sticker_generator.cli import main

        with patch.object(sys, "argv", ["prog"]):
            result = main()

        assert result == 1
        captured = capsys.readouterr()
        assert "prompt is required" in captured.err

    @patch("sticker_generator.cli.create_sticker")
    def test_prompt_still_works(self, mock_create):
        """Ensure regular prompt mode still works after adding --process."""
        from sticker_generator.cli import main

        mock_create.return_value = Image.new("RGBA", (100, 100))

        with patch.object(sys, "argv", ["prog", "a cute cat"]):
            result = main()

        assert result == 0
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["prompt"] == "a cute cat"
