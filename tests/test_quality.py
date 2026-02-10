"""Tests for generation quality validation."""

import sys
from unittest.mock import patch

import pytest
from PIL import Image

from sticker_generator.image_processing import (
    TransparencyMetrics,
    validate_transparency,
)


class TestTransparencyMetrics:
    """Tests for TransparencyMetrics dataclass."""

    def test_is_frozen(self):
        metrics = TransparencyMetrics(
            total_pixels=100,
            transparent_pixels=50,
            opaque_pixels=50,
            semi_transparent_pixels=0,
            transparent_ratio=0.5,
            opaque_ratio=0.5,
        )
        with pytest.raises(AttributeError):
            metrics.total_pixels = 200  # type: ignore[misc]

    def test_is_mostly_transparent(self):
        metrics = TransparencyMetrics(
            total_pixels=100,
            transparent_pixels=96,
            opaque_pixels=4,
            semi_transparent_pixels=0,
            transparent_ratio=0.96,
            opaque_ratio=0.04,
        )
        assert metrics.is_mostly_transparent is True
        assert metrics.is_mostly_opaque is False

    def test_is_mostly_opaque(self):
        metrics = TransparencyMetrics(
            total_pixels=100,
            transparent_pixels=3,
            opaque_pixels=97,
            semi_transparent_pixels=0,
            transparent_ratio=0.03,
            opaque_ratio=0.97,
        )
        assert metrics.is_mostly_opaque is True
        assert metrics.is_mostly_transparent is False

    def test_normal_image_no_warning(self):
        metrics = TransparencyMetrics(
            total_pixels=100,
            transparent_pixels=40,
            opaque_pixels=60,
            semi_transparent_pixels=0,
            transparent_ratio=0.40,
            opaque_ratio=0.60,
        )
        assert metrics.is_mostly_transparent is False
        assert metrics.is_mostly_opaque is False
        assert metrics.has_quality_warning is False
        assert metrics.warning_message is None

    def test_has_quality_warning_transparent(self):
        metrics = TransparencyMetrics(
            total_pixels=100,
            transparent_pixels=96,
            opaque_pixels=4,
            semi_transparent_pixels=0,
            transparent_ratio=0.96,
            opaque_ratio=0.04,
        )
        assert metrics.has_quality_warning is True
        assert "subject may have been removed" in metrics.warning_message

    def test_has_quality_warning_opaque(self):
        metrics = TransparencyMetrics(
            total_pixels=100,
            transparent_pixels=2,
            opaque_pixels=98,
            semi_transparent_pixels=0,
            transparent_ratio=0.02,
            opaque_ratio=0.98,
        )
        assert metrics.has_quality_warning is True
        assert "green background removal may have failed" in metrics.warning_message

    def test_boundary_transparent_95(self):
        """Exactly 95% transparent should NOT trigger warning."""
        metrics = TransparencyMetrics(
            total_pixels=100,
            transparent_pixels=95,
            opaque_pixels=5,
            semi_transparent_pixels=0,
            transparent_ratio=0.95,
            opaque_ratio=0.05,
        )
        assert metrics.is_mostly_transparent is False

    def test_boundary_opaque_5(self):
        """Exactly 5% transparent should NOT trigger warning."""
        metrics = TransparencyMetrics(
            total_pixels=100,
            transparent_pixels=5,
            opaque_pixels=95,
            semi_transparent_pixels=0,
            transparent_ratio=0.05,
            opaque_ratio=0.95,
        )
        assert metrics.is_mostly_opaque is False


class TestValidateTransparency:
    """Tests for validate_transparency function."""

    def test_fully_transparent_image(self):
        img = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
        metrics = validate_transparency(img)

        assert metrics.total_pixels == 100
        assert metrics.transparent_pixels == 100
        assert metrics.opaque_pixels == 0
        assert metrics.transparent_ratio == 1.0
        assert metrics.is_mostly_transparent is True

    def test_fully_opaque_image(self):
        img = Image.new("RGBA", (10, 10), (255, 0, 0, 255))
        metrics = validate_transparency(img)

        assert metrics.total_pixels == 100
        assert metrics.transparent_pixels == 0
        assert metrics.opaque_pixels == 100
        assert metrics.opaque_ratio == 1.0
        assert metrics.is_mostly_opaque is True

    def test_half_transparent_image(self):
        img = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
        # Make top half opaque
        for x in range(10):
            for y in range(5):
                img.putpixel((x, y), (255, 0, 0, 255))

        metrics = validate_transparency(img)

        assert metrics.total_pixels == 100
        assert metrics.transparent_pixels == 50
        assert metrics.opaque_pixels == 50
        assert metrics.transparent_ratio == pytest.approx(0.5)
        assert metrics.has_quality_warning is False

    def test_rgb_image_treated_as_opaque(self):
        img = Image.new("RGB", (10, 10), (255, 0, 0))
        metrics = validate_transparency(img)

        assert metrics.total_pixels == 100
        assert metrics.transparent_pixels == 0
        assert metrics.opaque_pixels == 100
        assert metrics.opaque_ratio == 1.0

    def test_semi_transparent_pixels_counted(self):
        img = Image.new("RGBA", (10, 10), (255, 0, 0, 128))
        metrics = validate_transparency(img)

        assert metrics.semi_transparent_pixels == 100
        assert metrics.transparent_pixels == 0
        assert metrics.opaque_pixels == 0

    def test_mixed_transparency(self):
        """Image with transparent bg and opaque subject."""
        img = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
        for x in range(30, 70):
            for y in range(30, 70):
                img.putpixel((x, y), (255, 0, 0, 255))

        metrics = validate_transparency(img)

        # 40x40 = 1600 opaque, 10000-1600=8400 transparent
        assert metrics.opaque_pixels == 1600
        assert metrics.transparent_pixels == 8400
        assert metrics.transparent_ratio == pytest.approx(0.84)
        assert metrics.has_quality_warning is False


class TestCreateStickerValidation:
    """Test that create_sticker logs quality warnings."""

    @patch("sticker_generator.core.generate_sticker")
    def test_warns_on_mostly_transparent(self, mock_gen, caplog):
        from sticker_generator.core import create_sticker

        # Create an image that will be mostly transparent after processing
        # All green -> all removed -> mostly transparent
        img = Image.new("RGBA", (100, 100), (0, 255, 0, 255))
        mock_gen.return_value = img

        with caplog.at_level("WARNING", logger="sticker_generator.core"):
            create_sticker("test prompt")

        assert any("subject may have been removed" in r.message for r in caplog.records)

    @patch("sticker_generator.core.generate_sticker")
    def test_warns_on_mostly_opaque(self, mock_gen, caplog):
        from sticker_generator.core import create_sticker

        # Create image with no green at all -> nothing removed -> mostly opaque
        img = Image.new("RGBA", (100, 100), (255, 0, 0, 255))
        mock_gen.return_value = img

        with caplog.at_level("WARNING", logger="sticker_generator.core"):
            create_sticker("test prompt")

        assert any(
            "green background removal may have failed" in r.message
            for r in caplog.records
        )

    @patch("sticker_generator.core.generate_sticker")
    def test_no_warning_on_good_result(self, mock_gen, caplog):
        from sticker_generator.core import create_sticker

        # Green background with red subject -> good result
        img = Image.new("RGBA", (100, 100), (0, 255, 0, 255))
        for x in range(20, 80):
            for y in range(20, 80):
                img.putpixel((x, y), (255, 0, 0, 255))
        mock_gen.return_value = img

        with caplog.at_level("WARNING", logger="sticker_generator.core"):
            create_sticker("test prompt")

        assert not any(
            "subject may have been removed" in r.message for r in caplog.records
        )
        assert not any(
            "green background removal may have failed" in r.message
            for r in caplog.records
        )


class TestCLIStrictFlag:
    """Tests for --strict CLI flag."""

    @patch("sticker_generator.cli.create_sticker")
    def test_strict_fails_on_mostly_transparent(self, mock_create, caplog):
        from sticker_generator.cli import main

        # Return a fully transparent image
        mock_create.return_value = Image.new("RGBA", (100, 100), (0, 0, 0, 0))

        with caplog.at_level("ERROR", logger="sticker_generator"):
            with patch.object(sys, "argv", ["prog", "test prompt", "--strict"]):
                result = main()

        assert result == 1
        assert any("--strict" in r.message for r in caplog.records)

    @patch("sticker_generator.cli.create_sticker")
    def test_strict_fails_on_mostly_opaque(self, mock_create, caplog):
        from sticker_generator.cli import main

        # Return a fully opaque image
        mock_create.return_value = Image.new("RGBA", (100, 100), (255, 0, 0, 255))

        with caplog.at_level("ERROR", logger="sticker_generator"):
            with patch.object(sys, "argv", ["prog", "test prompt", "--strict"]):
                result = main()

        assert result == 1
        assert any("--strict" in r.message for r in caplog.records)

    @patch("sticker_generator.cli.create_sticker")
    def test_strict_passes_on_good_result(self, mock_create):
        from sticker_generator.cli import main

        # Return an image with ~50% transparency (good result)
        img = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
        for x in range(50):
            for y in range(100):
                img.putpixel((x, y), (255, 0, 0, 255))
        mock_create.return_value = img

        with patch.object(sys, "argv", ["prog", "test prompt", "--strict"]):
            result = main()

        assert result == 0

    @patch("sticker_generator.cli.create_sticker")
    def test_no_strict_doesnt_fail(self, mock_create):
        from sticker_generator.cli import main

        # Return a fully transparent image but without --strict
        mock_create.return_value = Image.new("RGBA", (100, 100), (0, 0, 0, 0))

        with patch.object(sys, "argv", ["prog", "test prompt"]):
            result = main()

        # Should succeed (no --strict)
        assert result == 0
