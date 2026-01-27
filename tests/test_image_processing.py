"""Tests for image processing utilities."""

import numpy as np
import pytest
from PIL import Image

from sticker_generator.image_processing import (
    cleanup_edges,
    remove_green_screen_aggressive,
    remove_green_screen_hsv,
    rgb_to_hsv_array,
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
