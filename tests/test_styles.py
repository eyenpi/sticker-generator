"""Tests for style presets."""

import pytest

from sticker_generator.styles import (
    STYLE_PRESETS,
    StylePreset,
    format_prompt_with_style,
    get_available_styles,
    get_style,
)


class TestStylePreset:
    """Tests for StylePreset dataclass."""

    def test_is_frozen(self):
        """StylePreset should be immutable."""
        preset = StylePreset(
            name="test",
            description="Test style",
            prompt_modifier="test modifier",
        )
        with pytest.raises(AttributeError):
            preset.name = "changed"  # type: ignore[misc]

    def test_all_presets_have_required_fields(self):
        """All presets should have non-empty required fields."""
        for name, preset in STYLE_PRESETS.items():
            assert preset.name == name, f"Preset name mismatch for {name}"
            assert preset.description, f"Missing description for {name}"
            assert preset.prompt_modifier, f"Missing prompt_modifier for {name}"


class TestGetStyle:
    """Tests for get_style function."""

    def test_returns_none_for_none_input(self):
        """get_style(None) should return None."""
        assert get_style(None) is None

    def test_returns_preset_for_valid_name(self):
        """get_style should return the correct preset for valid names."""
        for name in STYLE_PRESETS:
            result = get_style(name)
            assert result is not None
            assert result.name == name
            assert result == STYLE_PRESETS[name]

    def test_raises_for_invalid_name(self):
        """get_style should raise ValueError for invalid names."""
        with pytest.raises(ValueError) as exc_info:
            get_style("nonexistent")
        assert "Unknown style 'nonexistent'" in str(exc_info.value)
        assert "Available styles:" in str(exc_info.value)


class TestGetAvailableStyles:
    """Tests for get_available_styles function."""

    def test_returns_sorted_list(self):
        """get_available_styles should return a sorted list."""
        styles = get_available_styles()
        assert styles == sorted(styles)

    def test_contains_all_presets(self):
        """get_available_styles should contain all preset names."""
        styles = get_available_styles()
        assert set(styles) == set(STYLE_PRESETS.keys())

    def test_expected_styles_present(self):
        """Known styles should be present."""
        styles = get_available_styles()
        expected = ["3d", "kawaii", "minimal", "pixel-art", "retro", "watercolor"]
        for style in expected:
            assert style in styles


class TestFormatPromptWithStyle:
    """Tests for format_prompt_with_style function."""

    def test_returns_original_when_no_style(self):
        """Should return original prompt when style is None."""
        prompt = "a cute cat"
        result = format_prompt_with_style(prompt, None)
        assert result == prompt

    def test_appends_modifier_when_style_provided(self):
        """Should append style modifier to prompt."""
        prompt = "a cute cat"
        result = format_prompt_with_style(prompt, "kawaii")
        assert result.startswith(prompt)
        assert "kawaii" in result
        assert STYLE_PRESETS["kawaii"].prompt_modifier in result

    def test_raises_for_invalid_style(self):
        """Should raise ValueError for invalid style names."""
        with pytest.raises(ValueError):
            format_prompt_with_style("test prompt", "invalid_style")
