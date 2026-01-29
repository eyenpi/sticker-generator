"""Tests for output format configuration."""

import pytest

from sticker_generator.formats import (
    FORMAT_PRESETS,
    OutputFormat,
    OutputFormatType,
    format_from_extension,
    get_available_formats,
    get_format,
)


class TestOutputFormat:
    """Tests for OutputFormat dataclass."""

    def test_is_frozen(self):
        fmt = OutputFormat(format_type=OutputFormatType.PNG)
        with pytest.raises(AttributeError):
            fmt.format_type = OutputFormatType.WEBP  # type: ignore[misc]

    def test_extension_property_png(self):
        fmt = OutputFormat(format_type=OutputFormatType.PNG)
        assert fmt.extension == ".png"

    def test_extension_property_webp(self):
        fmt = OutputFormat(format_type=OutputFormatType.WEBP)
        assert fmt.extension == ".webp"

    def test_pil_format_property_png(self):
        fmt = OutputFormat(format_type=OutputFormatType.PNG)
        assert fmt.pil_format == "PNG"

    def test_pil_format_property_webp(self):
        fmt = OutputFormat(format_type=OutputFormatType.WEBP)
        assert fmt.pil_format == "WEBP"

    def test_png_save_params_default(self):
        fmt = OutputFormat(format_type=OutputFormatType.PNG)
        params = fmt.get_save_params()
        # PNG default has no special params
        assert "compress_level" not in params

    def test_png_save_params_with_compress_level(self):
        fmt = OutputFormat(
            format_type=OutputFormatType.PNG,
            extra_params={"compress_level": 9},
        )
        params = fmt.get_save_params()
        assert params["compress_level"] == 9

    def test_webp_lossless_save_params(self):
        fmt = OutputFormat(format_type=OutputFormatType.WEBP, lossless=True)
        params = fmt.get_save_params()
        assert params["lossless"] is True
        assert params["exact"] is True
        assert "quality" not in params

    def test_webp_lossy_save_params(self):
        fmt = OutputFormat(
            format_type=OutputFormatType.WEBP,
            lossless=False,
            quality=85,
        )
        params = fmt.get_save_params()
        assert params["lossless"] is False
        assert params["exact"] is True
        assert params["quality"] == 85

    def test_webp_lossy_without_quality(self):
        fmt = OutputFormat(format_type=OutputFormatType.WEBP, lossless=False)
        params = fmt.get_save_params()
        assert params["lossless"] is False
        assert "quality" not in params

    def test_webp_with_method(self):
        fmt = OutputFormat(
            format_type=OutputFormatType.WEBP,
            extra_params={"method": 6},
        )
        params = fmt.get_save_params()
        assert params["method"] == 6

    def test_extra_params_passed_through(self):
        fmt = OutputFormat(
            format_type=OutputFormatType.PNG,
            extra_params={"custom_param": "value"},
        )
        params = fmt.get_save_params()
        assert params["custom_param"] == "value"


class TestGetFormat:
    """Tests for get_format function."""

    def test_none_returns_png(self):
        fmt = get_format(None)
        assert fmt.format_type == OutputFormatType.PNG

    def test_png_format(self):
        fmt = get_format("png")
        assert fmt.format_type == OutputFormatType.PNG
        assert fmt.lossless is True

    def test_webp_format(self):
        fmt = get_format("webp")
        assert fmt.format_type == OutputFormatType.WEBP
        assert fmt.lossless is True

    def test_webp_lossy_format(self):
        fmt = get_format("webp-lossy")
        assert fmt.format_type == OutputFormatType.WEBP
        assert fmt.lossless is False
        assert fmt.quality == 90

    def test_invalid_format_raises(self):
        with pytest.raises(ValueError, match="Unknown format 'invalid'"):
            get_format("invalid")

    def test_error_message_lists_available(self):
        with pytest.raises(ValueError, match="Available formats:"):
            get_format("bad")


class TestFormatFromExtension:
    """Tests for format_from_extension function."""

    def test_png_extension(self):
        fmt = format_from_extension("image.png")
        assert fmt.format_type == OutputFormatType.PNG

    def test_webp_extension(self):
        fmt = format_from_extension("image.webp")
        assert fmt.format_type == OutputFormatType.WEBP

    def test_case_insensitive_png(self):
        fmt = format_from_extension("IMAGE.PNG")
        assert fmt.format_type == OutputFormatType.PNG

    def test_case_insensitive_webp(self):
        fmt = format_from_extension("IMAGE.WEBP")
        assert fmt.format_type == OutputFormatType.WEBP

    def test_mixed_case(self):
        fmt = format_from_extension("image.WebP")
        assert fmt.format_type == OutputFormatType.WEBP

    def test_unknown_extension_defaults_to_png(self):
        fmt = format_from_extension("image.xyz")
        assert fmt.format_type == OutputFormatType.PNG

    def test_no_extension_defaults_to_png(self):
        fmt = format_from_extension("image")
        assert fmt.format_type == OutputFormatType.PNG

    def test_path_with_directories(self):
        fmt = format_from_extension("/path/to/file.webp")
        assert fmt.format_type == OutputFormatType.WEBP


class TestGetAvailableFormats:
    """Tests for get_available_formats function."""

    def test_returns_sorted_list(self):
        formats = get_available_formats()
        assert formats == sorted(formats)

    def test_contains_expected_formats(self):
        formats = get_available_formats()
        assert "png" in formats
        assert "webp" in formats
        assert "webp-lossy" in formats

    def test_matches_presets_keys(self):
        formats = get_available_formats()
        assert set(formats) == set(FORMAT_PRESETS.keys())


class TestFormatPresets:
    """Tests for FORMAT_PRESETS dictionary."""

    def test_png_preset_exists(self):
        assert "png" in FORMAT_PRESETS
        assert FORMAT_PRESETS["png"].format_type == OutputFormatType.PNG

    def test_webp_preset_exists(self):
        assert "webp" in FORMAT_PRESETS
        assert FORMAT_PRESETS["webp"].format_type == OutputFormatType.WEBP

    def test_webp_lossy_preset_exists(self):
        assert "webp-lossy" in FORMAT_PRESETS
        assert FORMAT_PRESETS["webp-lossy"].format_type == OutputFormatType.WEBP
        assert FORMAT_PRESETS["webp-lossy"].lossless is False
