"""Tests for configurable green removal parameters."""

import sys
from unittest.mock import MagicMock, patch

import numpy as np
from PIL import Image

from sticker_generator.cli import main


def create_green_bg_image():
    """Create a test image with green background and red square."""
    img = Image.new("RGBA", (100, 100), (0, 255, 0, 255))
    for x in range(30, 70):
        for y in range(30, 70):
            img.putpixel((x, y), (255, 0, 0, 255))
    return img


class TestCreateStickerGreenParams:
    """Test that create_sticker passes green params to processing functions."""

    @patch("sticker_generator.core.generate_sticker")
    @patch("sticker_generator.core.remove_green_screen_hsv")
    @patch("sticker_generator.core.remove_green_screen_aggressive")
    @patch("sticker_generator.core.cleanup_edges")
    def test_default_params(self, mock_cleanup, mock_agg, mock_hsv, mock_gen):
        from sticker_generator.core import create_sticker

        raw = create_green_bg_image()
        mock_gen.return_value = raw
        mock_hsv.return_value = raw
        mock_agg.return_value = raw
        mock_cleanup.return_value = raw

        create_sticker("test prompt")

        mock_hsv.assert_called_once()
        hsv_kwargs = mock_hsv.call_args[1]
        assert hsv_kwargs["hue_center"] == 115
        assert hsv_kwargs["hue_range"] == 35
        assert hsv_kwargs["min_saturation"] == 25
        assert hsv_kwargs["min_value"] == 40

        mock_agg.assert_called_once()
        agg_kwargs = mock_agg.call_args[1]
        assert agg_kwargs["green_threshold"] == 1.1

    @patch("sticker_generator.core.generate_sticker")
    @patch("sticker_generator.core.remove_green_screen_hsv")
    @patch("sticker_generator.core.remove_green_screen_aggressive")
    @patch("sticker_generator.core.cleanup_edges")
    def test_custom_params(self, mock_cleanup, mock_agg, mock_hsv, mock_gen):
        from sticker_generator.core import create_sticker

        raw = create_green_bg_image()
        mock_gen.return_value = raw
        mock_hsv.return_value = raw
        mock_agg.return_value = raw
        mock_cleanup.return_value = raw

        create_sticker(
            "test prompt",
            hue_center=130,
            hue_range=20,
            min_saturation=50,
            min_value=60,
            green_threshold=1.5,
        )

        hsv_kwargs = mock_hsv.call_args[1]
        assert hsv_kwargs["hue_center"] == 130
        assert hsv_kwargs["hue_range"] == 20
        assert hsv_kwargs["min_saturation"] == 50
        assert hsv_kwargs["min_value"] == 60

        agg_kwargs = mock_agg.call_args[1]
        assert agg_kwargs["green_threshold"] == 1.5

    @patch("sticker_generator.core.generate_sticker")
    def test_narrow_hue_range_preserves_greens(self, mock_gen):
        """Narrowing hue_range should leave more green pixels opaque."""
        from sticker_generator.core import create_sticker

        raw = create_green_bg_image()
        mock_gen.return_value = raw

        # Very narrow range - should miss some greens
        result_narrow = create_sticker(
            "test",
            hue_range=1,
            min_saturation=99,
            min_value=99,
            green_threshold=999,  # effectively disable aggressive pass
        )

        # Wide range - should catch all greens
        result_wide = create_sticker("test", hue_range=60)

        narrow_data = np.array(result_narrow)
        wide_data = np.array(result_wide)

        # Narrow range should have more opaque pixels than wide range
        narrow_opaque = np.sum(narrow_data[:, :, 3] > 0)
        wide_opaque = np.sum(wide_data[:, :, 3] > 0)
        assert narrow_opaque >= wide_opaque


class TestCLIGreenParams:
    """Test that CLI passes green params to create_sticker."""

    @patch("sticker_generator.cli.create_sticker")
    def test_default_green_params(self, mock_create):
        mock_create.return_value = Image.new("RGBA", (100, 100))

        with patch.object(sys, "argv", ["prog", "test prompt"]):
            result = main()

        assert result == 0
        kwargs = mock_create.call_args[1]
        assert kwargs["hue_center"] == 115
        assert kwargs["hue_range"] == 35
        assert kwargs["min_saturation"] == 25
        assert kwargs["min_value"] == 40
        assert kwargs["green_threshold"] == 1.1

    @patch("sticker_generator.cli.create_sticker")
    def test_custom_hue_center(self, mock_create):
        mock_create.return_value = Image.new("RGBA", (100, 100))

        with patch.object(sys, "argv", ["prog", "test prompt", "--hue-center", "130"]):
            result = main()

        assert result == 0
        assert mock_create.call_args[1]["hue_center"] == 130.0

    @patch("sticker_generator.cli.create_sticker")
    def test_custom_hue_range(self, mock_create):
        mock_create.return_value = Image.new("RGBA", (100, 100))

        with patch.object(sys, "argv", ["prog", "test prompt", "--hue-range", "50"]):
            result = main()

        assert result == 0
        assert mock_create.call_args[1]["hue_range"] == 50.0

    @patch("sticker_generator.cli.create_sticker")
    def test_custom_min_saturation(self, mock_create):
        mock_create.return_value = Image.new("RGBA", (100, 100))

        with patch.object(
            sys, "argv", ["prog", "test prompt", "--min-saturation", "75"]
        ):
            result = main()

        assert result == 0
        assert mock_create.call_args[1]["min_saturation"] == 75.0

    @patch("sticker_generator.cli.create_sticker")
    def test_custom_min_value(self, mock_create):
        mock_create.return_value = Image.new("RGBA", (100, 100))

        with patch.object(sys, "argv", ["prog", "test prompt", "--min-value", "60"]):
            result = main()

        assert result == 0
        assert mock_create.call_args[1]["min_value"] == 60.0

    @patch("sticker_generator.cli.create_sticker")
    def test_custom_green_threshold(self, mock_create):
        mock_create.return_value = Image.new("RGBA", (100, 100))

        with patch.object(
            sys, "argv", ["prog", "test prompt", "--green-threshold", "1.5"]
        ):
            result = main()

        assert result == 0
        assert mock_create.call_args[1]["green_threshold"] == 1.5

    @patch("sticker_generator.cli.create_sticker")
    def test_all_green_params_together(self, mock_create):
        mock_create.return_value = Image.new("RGBA", (100, 100))

        with patch.object(
            sys,
            "argv",
            [
                "prog",
                "test prompt",
                "--hue-center",
                "130",
                "--hue-range",
                "20",
                "--min-saturation",
                "50",
                "--min-value",
                "60",
                "--green-threshold",
                "1.3",
            ],
        ):
            result = main()

        assert result == 0
        kwargs = mock_create.call_args[1]
        assert kwargs["hue_center"] == 130.0
        assert kwargs["hue_range"] == 20.0
        assert kwargs["min_saturation"] == 50.0
        assert kwargs["min_value"] == 60.0
        assert kwargs["green_threshold"] == 1.3

    @patch("sticker_generator.cli.generate_sticker_sheet")
    def test_green_params_passed_to_sheet(self, mock_sheet):
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
                "--hue-center",
                "130",
                "--green-threshold",
                "1.5",
            ],
        ):
            result = main()

        assert result == 0
        kwargs = mock_sheet.call_args[1]
        assert kwargs["hue_center"] == 130.0
        assert kwargs["green_threshold"] == 1.5


class TestSheetGreenParams:
    """Test that sheet generation passes green params to create_sticker."""

    @patch("sticker_generator.sheet.create_sticker")
    def test_green_params_forwarded(self, mock_create):
        from sticker_generator.sheet import generate_sticker_sheet

        mock_create.return_value = Image.new("RGBA", (100, 100))

        generate_sticker_sheet(
            "test",
            variations=1,
            hue_center=130,
            hue_range=20,
            min_saturation=50,
            min_value=60,
            green_threshold=1.5,
            delay_between_requests=0,
        )

        kwargs = mock_create.call_args[1]
        assert kwargs["hue_center"] == 130
        assert kwargs["hue_range"] == 20
        assert kwargs["min_saturation"] == 50
        assert kwargs["min_value"] == 60
        assert kwargs["green_threshold"] == 1.5
