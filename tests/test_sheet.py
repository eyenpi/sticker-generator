"""Tests for sticker sheet generation."""

from unittest.mock import patch

import pytest
from PIL import Image

from sticker_generator.sheet import (
    SheetResult,
    calculate_grid_layout,
    create_sheet_image,
    generate_sticker_sheet,
)


class TestCalculateGridLayout:
    """Tests for calculate_grid_layout function."""

    def test_single_sticker(self):
        assert calculate_grid_layout(1) == (1, 1)

    def test_two_stickers(self):
        assert calculate_grid_layout(2) == (2, 1)

    def test_three_stickers(self):
        cols, rows = calculate_grid_layout(3)
        assert cols * rows >= 3
        assert cols == 2 and rows == 2

    def test_perfect_square_4(self):
        assert calculate_grid_layout(4) == (2, 2)

    def test_five_stickers(self):
        cols, rows = calculate_grid_layout(5)
        assert cols * rows >= 5
        assert cols == 3 and rows == 2

    def test_six_stickers(self):
        cols, rows = calculate_grid_layout(6)
        assert cols * rows >= 6
        assert cols == 3 and rows == 2

    def test_perfect_square_9(self):
        assert calculate_grid_layout(9) == (3, 3)

    def test_ten_stickers(self):
        cols, rows = calculate_grid_layout(10)
        assert cols * rows >= 10

    def test_zero_raises_error(self):
        with pytest.raises(ValueError, match="Count must be positive"):
            calculate_grid_layout(0)

    def test_negative_raises_error(self):
        with pytest.raises(ValueError, match="Count must be positive"):
            calculate_grid_layout(-1)


class TestCreateSheetImage:
    """Tests for create_sheet_image function."""

    def create_test_sticker(
        self, color: tuple = (255, 0, 0, 255), size: tuple = (100, 100)
    ) -> Image.Image:
        return Image.new("RGBA", size, color)

    def test_single_sticker_sheet_no_padding(self):
        stickers = [self.create_test_sticker()]
        sheet = create_sheet_image(stickers, padding=0)
        assert sheet.size == (100, 100)

    def test_single_sticker_sheet_with_padding(self):
        stickers = [self.create_test_sticker()]
        sheet = create_sheet_image(stickers, padding=10)
        # 1 col * 100px + 2 * 10px padding = 120
        assert sheet.size == (120, 120)

    def test_two_stickers_horizontal(self):
        stickers = [self.create_test_sticker() for _ in range(2)]
        sheet = create_sheet_image(stickers, columns=2, padding=0)
        assert sheet.size == (200, 100)

    def test_four_stickers_grid_no_padding(self):
        stickers = [self.create_test_sticker() for _ in range(4)]
        sheet = create_sheet_image(stickers, columns=2, padding=0)
        assert sheet.size == (200, 200)

    def test_four_stickers_grid_with_padding(self):
        stickers = [self.create_test_sticker() for _ in range(4)]
        sheet = create_sheet_image(stickers, columns=2, padding=10)
        # 2 cols * 100px + 3 * 10px padding = 230
        # 2 rows * 100px + 3 * 10px padding = 230
        assert sheet.size == (230, 230)

    def test_auto_columns(self):
        stickers = [self.create_test_sticker() for _ in range(4)]
        sheet = create_sheet_image(stickers, padding=0)
        # Should auto-calculate to 2x2
        assert sheet.size == (200, 200)

    def test_varying_sizes_uses_max(self):
        stickers = [
            Image.new("RGBA", (50, 50), (255, 0, 0, 255)),
            Image.new("RGBA", (100, 100), (0, 255, 0, 255)),
        ]
        sheet = create_sheet_image(stickers, columns=2, padding=0)
        # Uses max width/height for cell size
        assert sheet.size == (200, 100)

    def test_empty_list_raises_error(self):
        with pytest.raises(ValueError, match="No stickers to combine"):
            create_sheet_image([])

    def test_transparent_background(self):
        stickers = [self.create_test_sticker()]
        sheet = create_sheet_image(stickers, padding=10)
        # Check corner pixel is transparent
        pixel = sheet.getpixel((0, 0))
        assert isinstance(pixel, tuple) and pixel[3] == 0

    def test_custom_background_color(self):
        stickers = [self.create_test_sticker()]
        sheet = create_sheet_image(
            stickers, padding=10, background_color=(255, 255, 255, 255)
        )
        # Check corner pixel is white
        pixel = sheet.getpixel((0, 0))
        assert pixel == (255, 255, 255, 255)

    def test_rgb_sticker_converted(self):
        sticker = Image.new("RGB", (100, 100), (255, 0, 0))
        stickers = [sticker]
        sheet = create_sheet_image(stickers, padding=0)
        assert sheet.mode == "RGBA"


class TestSheetResult:
    """Tests for SheetResult dataclass."""

    def test_default_values(self):
        result = SheetResult()
        assert result.stickers == []
        assert result.sheet is None
        assert result.failed_indices == []

    def test_with_values(self):
        stickers = [Image.new("RGBA", (10, 10))]
        sheet = Image.new("RGBA", (20, 20))
        result = SheetResult(stickers=stickers, sheet=sheet, failed_indices=[2])

        assert len(result.stickers) == 1
        assert result.sheet is not None
        assert result.failed_indices == [2]


class TestGenerateStickerSheet:
    """Tests for generate_sticker_sheet function."""

    @patch("sticker_generator.sheet.create_sticker")
    def test_generates_requested_variations(self, mock_create):
        mock_create.return_value = Image.new("RGBA", (100, 100), (255, 0, 0, 255))

        result = generate_sticker_sheet(
            "test prompt", variations=3, delay_between_requests=0
        )

        assert mock_create.call_count == 3
        assert len(result.stickers) == 3
        assert len(result.failed_indices) == 0
        assert result.sheet is not None

    @patch("sticker_generator.sheet.create_sticker")
    def test_handles_complete_failure(self, mock_create):
        mock_create.side_effect = Exception("API error")

        result = generate_sticker_sheet(
            "test", variations=2, max_retries=0, delay_between_requests=0
        )

        assert len(result.stickers) == 0
        assert len(result.failed_indices) == 2
        assert result.sheet is None

    @patch("sticker_generator.sheet.create_sticker")
    def test_handles_partial_failure(self, mock_create):
        mock_create.side_effect = [
            Image.new("RGBA", (100, 100)),
            Exception("API error"),
            Image.new("RGBA", (100, 100)),
        ]

        result = generate_sticker_sheet(
            "test", variations=3, max_retries=0, delay_between_requests=0
        )

        assert len(result.stickers) == 2
        assert 1 in result.failed_indices
        assert result.sheet is not None

    @patch("sticker_generator.sheet.create_sticker")
    @patch("sticker_generator.sheet.save_transparent_png")
    def test_saves_sheet_when_output_specified(self, mock_save, mock_create, tmp_path):
        mock_create.return_value = Image.new("RGBA", (100, 100))
        output_path = tmp_path / "sheet.png"

        result = generate_sticker_sheet(
            "test", variations=2, output=output_path, delay_between_requests=0
        )

        assert result.sheet is not None
        mock_save.assert_called()

    @patch("sticker_generator.sheet.create_sticker")
    @patch("sticker_generator.sheet.save_transparent_png")
    def test_saves_individuals_when_requested(self, mock_save, mock_create, tmp_path):
        mock_create.return_value = Image.new("RGBA", (100, 100))
        output_path = tmp_path / "sheet.png"

        generate_sticker_sheet(
            "test",
            variations=2,
            output=output_path,
            save_individuals=True,
            delay_between_requests=0,
        )

        # Should save sheet + 2 individuals = 3 calls
        assert mock_save.call_count == 3

    @patch("sticker_generator.sheet.create_sticker")
    def test_passes_parameters_to_create_sticker(self, mock_create):
        mock_create.return_value = Image.new("RGBA", (100, 100))

        generate_sticker_sheet(
            "test prompt",
            variations=1,
            aspect_ratio="16:9",
            api_key="test-key",
            edge_threshold=128,
            delay_between_requests=0,
        )

        mock_create.assert_called_once_with(
            prompt="test prompt",
            output=None,
            aspect_ratio="16:9",
            input_images=None,
            api_key="test-key",
            edge_threshold=128,
            style=None,
            resize=None,
            resize_exact=False,
        )

    @patch("sticker_generator.sheet.create_sticker")
    def test_custom_columns(self, mock_create):
        mock_create.return_value = Image.new("RGBA", (100, 100))

        result = generate_sticker_sheet(
            "test", variations=4, columns=4, padding=0, delay_between_requests=0
        )

        # 4 columns = all in one row
        assert result.sheet is not None
        assert result.sheet.size == (400, 100)

    @patch("sticker_generator.sheet.create_sticker")
    def test_custom_padding(self, mock_create):
        mock_create.return_value = Image.new("RGBA", (100, 100))

        result = generate_sticker_sheet(
            "test", variations=1, padding=20, delay_between_requests=0
        )

        assert result.sheet is not None
        # 1 sticker with 20px padding on all sides
        assert result.sheet.size == (140, 140)

    @patch("sticker_generator.sheet.create_sticker")
    def test_resize_passed_to_create_sticker(self, mock_create):
        mock_create.return_value = Image.new("RGBA", (50, 50))

        generate_sticker_sheet(
            "test prompt",
            variations=1,
            resize=(256, 256),
            resize_exact=True,
            delay_between_requests=0,
        )

        mock_create.assert_called_once_with(
            prompt="test prompt",
            output=None,
            aspect_ratio="1:1",
            input_images=None,
            api_key=None,
            edge_threshold=64,
            style=None,
            resize=(256, 256),
            resize_exact=True,
        )
