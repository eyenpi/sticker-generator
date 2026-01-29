"""Tests for image processing utilities."""

import warnings

import numpy as np
import pytest
from PIL import Image

from sticker_generator.formats import OutputFormat, OutputFormatType
from sticker_generator.image_processing import (
    cleanup_edges,
    remove_green_screen_aggressive,
    remove_green_screen_hsv,
    resize_image,
    rgb_to_hsv_array,
    save_transparent_image,
    save_transparent_png,
)


def create_test_image(width: int = 100, height: int = 100) -> Image.Image:
    """Create a test image with green background and red square."""
    img = Image.new("RGBA", (width, height), (0, 255, 0, 255))  # Green background
    # Add a red square in the center
    for x in range(30, 70):
        for y in range(30, 70):
            img.putpixel((x, y), (255, 0, 0, 255))
    return img


class TestRgbToHsvArray:
    def test_pure_red(self):
        rgb = np.array([[[255, 0, 0]]], dtype=np.uint8)
        hsv = rgb_to_hsv_array(rgb)
        assert hsv[0, 0, 0] == pytest.approx(0, abs=1)  # Hue ~0 (red)
        assert hsv[0, 0, 1] == pytest.approx(100, abs=1)  # Saturation 100%
        assert hsv[0, 0, 2] == pytest.approx(100, abs=1)  # Value 100%

    def test_pure_green(self):
        rgb = np.array([[[0, 255, 0]]], dtype=np.uint8)
        hsv = rgb_to_hsv_array(rgb)
        assert hsv[0, 0, 0] == pytest.approx(120, abs=1)  # Hue 120 (green)
        assert hsv[0, 0, 1] == pytest.approx(100, abs=1)
        assert hsv[0, 0, 2] == pytest.approx(100, abs=1)

    def test_pure_blue(self):
        rgb = np.array([[[0, 0, 255]]], dtype=np.uint8)
        hsv = rgb_to_hsv_array(rgb)
        assert hsv[0, 0, 0] == pytest.approx(240, abs=1)  # Hue 240 (blue)
        assert hsv[0, 0, 1] == pytest.approx(100, abs=1)
        assert hsv[0, 0, 2] == pytest.approx(100, abs=1)

    def test_white(self):
        rgb = np.array([[[255, 255, 255]]], dtype=np.uint8)
        hsv = rgb_to_hsv_array(rgb)
        assert hsv[0, 0, 1] == pytest.approx(0, abs=1)  # Saturation 0%
        assert hsv[0, 0, 2] == pytest.approx(100, abs=1)  # Value 100%

    def test_black(self):
        rgb = np.array([[[0, 0, 0]]], dtype=np.uint8)
        hsv = rgb_to_hsv_array(rgb)
        assert hsv[0, 0, 2] == pytest.approx(0, abs=1)  # Value 0%


class TestRemoveGreenScreenHsv:
    def test_removes_green_background(self):
        img = create_test_image()
        result = remove_green_screen_hsv(img)

        assert result.mode == "RGBA"
        data = np.array(result)

        # Check that green pixels are transparent
        assert data[10, 10, 3] == 0  # Corner (green) should be transparent

        # Check that red pixels are opaque
        assert data[50, 50, 3] == 255  # Center (red) should be opaque

    def test_preserves_non_green_colors(self):
        img = create_test_image()
        result = remove_green_screen_hsv(img)
        data = np.array(result)

        # Red should be preserved
        assert data[50, 50, 0] == 255  # R
        assert data[50, 50, 1] == 0  # G
        assert data[50, 50, 2] == 0  # B

    def test_converts_rgb_to_rgba(self):
        img = Image.new("RGB", (50, 50), (0, 255, 0))
        result = remove_green_screen_hsv(img)
        assert result.mode == "RGBA"


class TestRemoveGreenScreenAggressive:
    def test_removes_dominant_green(self):
        img = create_test_image()
        result = remove_green_screen_aggressive(img)

        data = np.array(result)
        # Green background should be transparent
        assert data[10, 10, 3] == 0

    def test_preserves_non_green(self):
        img = create_test_image()
        result = remove_green_screen_aggressive(img)

        data = np.array(result)
        # Red center should be opaque
        assert data[50, 50, 3] == 255


class TestCleanupEdges:
    def test_thresholds_alpha(self):
        img = Image.new("RGBA", (10, 10), (255, 0, 0, 100))  # Semi-transparent red
        result = cleanup_edges(img, threshold=128)

        data = np.array(result)
        # Alpha below threshold should become 0
        assert data[5, 5, 3] == 0

    def test_preserves_opaque(self):
        img = Image.new("RGBA", (10, 10), (255, 0, 0, 200))
        result = cleanup_edges(img, threshold=128)

        data = np.array(result)
        # Alpha above threshold should become 255
        assert data[5, 5, 3] == 255

    def test_handles_non_rgba(self):
        img = Image.new("RGB", (10, 10), (255, 0, 0))
        result = cleanup_edges(img)
        # Should return unchanged
        assert result.mode == "RGB"


class TestResizeImage:
    def test_resize_square_image_to_smaller_square(self):
        img = Image.new("RGBA", (100, 100), (255, 0, 0, 255))
        result = resize_image(img, (50, 50))
        assert result.size == (50, 50)

    def test_resize_square_image_to_larger_square(self):
        img = Image.new("RGBA", (50, 50), (255, 0, 0, 255))
        result = resize_image(img, (100, 100))
        assert result.size == (100, 100)

    def test_maintain_aspect_landscape_to_square(self):
        # 200x100 landscape image fit into 50x50 box -> 50x25
        img = Image.new("RGBA", (200, 100), (255, 0, 0, 255))
        result = resize_image(img, (50, 50), maintain_aspect=True)
        assert result.size == (50, 25)

    def test_maintain_aspect_portrait_to_square(self):
        # 100x200 portrait image fit into 50x50 box -> 25x50
        img = Image.new("RGBA", (100, 200), (255, 0, 0, 255))
        result = resize_image(img, (50, 50), maintain_aspect=True)
        assert result.size == (25, 50)

    def test_exact_resize_distorts(self):
        # 200x100 forced to 50x50 (distorts)
        img = Image.new("RGBA", (200, 100), (255, 0, 0, 255))
        result = resize_image(img, (50, 50), maintain_aspect=False)
        assert result.size == (50, 50)

    def test_preserves_transparency(self):
        # Create image with transparent pixels
        img = Image.new("RGBA", (100, 100), (255, 0, 0, 128))
        result = resize_image(img, (50, 50))
        assert result.mode == "RGBA"
        # Check that alpha is preserved (approximately, due to resampling)
        pixel = result.getpixel((25, 25))
        assert isinstance(pixel, tuple) and len(pixel) == 4
        assert pixel[3] > 0  # Has some alpha

    def test_zero_width_raises_error(self):
        img = Image.new("RGBA", (100, 100))
        with pytest.raises(ValueError, match="must be positive"):
            resize_image(img, (0, 50))

    def test_negative_height_raises_error(self):
        img = Image.new("RGBA", (100, 100))
        with pytest.raises(ValueError, match="must be positive"):
            resize_image(img, (50, -10))

    def test_resize_to_one_pixel(self):
        img = Image.new("RGBA", (100, 100), (255, 0, 0, 255))
        result = resize_image(img, (1, 1))
        assert result.size == (1, 1)

    def test_custom_resampling_filter(self):
        img = Image.new("RGBA", (100, 100), (255, 0, 0, 255))
        # Should not raise - NEAREST is a valid filter
        result = resize_image(img, (50, 50), resampling=Image.Resampling.NEAREST)
        assert result.size == (50, 50)
        # Also test BILINEAR
        result = resize_image(img, (50, 50), resampling=Image.Resampling.BILINEAR)
        assert result.size == (50, 50)

    def test_rgb_mode_preserved(self):
        img = Image.new("RGB", (100, 100), (255, 0, 0))
        result = resize_image(img, (50, 50))
        assert result.mode == "RGB"
        assert result.size == (50, 50)


def create_transparent_test_image(width: int = 50, height: int = 50) -> Image.Image:
    """Create a test image with transparent and opaque regions."""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))  # Fully transparent
    # Add a red opaque square in the center
    for x in range(15, 35):
        for y in range(15, 35):
            img.putpixel((x, y), (255, 0, 0, 255))
    return img


class TestSaveTransparentImage:
    """Tests for save_transparent_image function."""

    def test_save_png_preserves_transparency(self, tmp_path):
        img = create_transparent_test_image()
        output_path = tmp_path / "test.png"

        save_transparent_image(img, str(output_path))

        loaded = Image.open(output_path)
        assert loaded.mode == "RGBA"
        # Check transparent corner
        assert loaded.getpixel((0, 0))[3] == 0
        # Check opaque center
        assert loaded.getpixel((25, 25))[3] == 255

    def test_save_webp_lossless_preserves_transparency(self, tmp_path):
        img = create_transparent_test_image()
        output_path = tmp_path / "test.webp"

        save_transparent_image(img, str(output_path), "webp")

        loaded = Image.open(output_path)
        assert loaded.mode == "RGBA"
        # Check transparent corner
        assert loaded.getpixel((0, 0))[3] == 0
        # Check opaque center
        assert loaded.getpixel((25, 25))[3] == 255

    def test_save_webp_lossy_preserves_transparency(self, tmp_path):
        img = create_transparent_test_image()
        output_path = tmp_path / "test_lossy.webp"

        save_transparent_image(img, str(output_path), "webp-lossy")

        loaded = Image.open(output_path)
        assert loaded.mode == "RGBA"
        # Lossy compression may have slight variations but transparency preserved
        # Check transparent corner (should still be transparent)
        assert loaded.getpixel((0, 0))[3] < 10
        # Check opaque center (should still be opaque)
        assert loaded.getpixel((25, 25))[3] > 245

    def test_auto_detect_format_from_extension_png(self, tmp_path):
        img = create_transparent_test_image()
        output_path = tmp_path / "test.png"

        save_transparent_image(img, str(output_path))

        # Verify it's actually a PNG
        loaded = Image.open(output_path)
        assert loaded.format == "PNG"

    def test_auto_detect_format_from_extension_webp(self, tmp_path):
        img = create_transparent_test_image()
        output_path = tmp_path / "test.webp"

        save_transparent_image(img, str(output_path))

        # Verify it's actually a WebP
        loaded = Image.open(output_path)
        assert loaded.format == "WEBP"

    def test_explicit_format_overrides_extension(self, tmp_path):
        img = create_transparent_test_image()
        # Extension says PNG but we specify WebP
        output_path = tmp_path / "test.png"

        save_transparent_image(img, str(output_path), "webp")

        # File should be WebP despite .png extension
        loaded = Image.open(output_path)
        assert loaded.format == "WEBP"

    def test_converts_rgb_to_rgba(self, tmp_path):
        img = Image.new("RGB", (50, 50), (255, 0, 0))
        output_path = tmp_path / "test.png"

        save_transparent_image(img, str(output_path))

        loaded = Image.open(output_path)
        assert loaded.mode == "RGBA"

    def test_invalid_format_raises_error(self, tmp_path):
        img = create_transparent_test_image()
        output_path = tmp_path / "test.png"

        with pytest.raises(ValueError, match="Unknown format"):
            save_transparent_image(img, str(output_path), "invalid")

    def test_custom_quality_applied(self, tmp_path):
        img = create_transparent_test_image()
        output_path = tmp_path / "test.webp"

        # Low quality should result in smaller file
        fmt_low = OutputFormat(
            format_type=OutputFormatType.WEBP,
            lossless=False,
            quality=10,
        )
        save_transparent_image(img, str(output_path), fmt_low)
        size_low = output_path.stat().st_size

        # High quality should result in larger file
        output_path_high = tmp_path / "test_high.webp"
        fmt_high = OutputFormat(
            format_type=OutputFormatType.WEBP,
            lossless=False,
            quality=100,
        )
        save_transparent_image(img, str(output_path_high), fmt_high)
        size_high = output_path_high.stat().st_size

        # Higher quality should generally result in larger file
        # (for lossy compression)
        assert size_high >= size_low

    def test_lossless_override(self, tmp_path):
        img = create_transparent_test_image()
        output_path = tmp_path / "test.webp"

        fmt = OutputFormat(
            format_type=OutputFormatType.WEBP,
            lossless=True,
        )
        save_transparent_image(img, str(output_path), fmt)

        loaded = Image.open(output_path)
        # Lossless should preserve exact pixel values
        data = np.array(loaded)
        assert data[0, 0, 3] == 0  # Exact transparent
        assert data[25, 25, 0] == 255  # Exact red value
        assert data[25, 25, 3] == 255  # Exact opaque

    def test_output_format_object(self, tmp_path):
        img = create_transparent_test_image()
        output_path = tmp_path / "test.png"

        fmt = OutputFormat(format_type=OutputFormatType.PNG)
        save_transparent_image(img, str(output_path), fmt)

        loaded = Image.open(output_path)
        assert loaded.format == "PNG"


class TestSaveTransparentPngDeprecation:
    """Tests for save_transparent_png deprecation."""

    def test_deprecation_warning(self, tmp_path):
        img = create_transparent_test_image()
        output_path = tmp_path / "test.png"

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            save_transparent_png(img, str(output_path))

            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "save_transparent_image" in str(w[0].message)

    def test_still_functions_correctly(self, tmp_path):
        img = create_transparent_test_image()
        output_path = tmp_path / "test.png"

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            save_transparent_png(img, str(output_path))

        loaded = Image.open(output_path)
        assert loaded.mode == "RGBA"
        assert loaded.format == "PNG"
        # Check transparency preserved
        assert loaded.getpixel((0, 0))[3] == 0
        assert loaded.getpixel((25, 25))[3] == 255
