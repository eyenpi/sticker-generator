"""Style presets for sticker generation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StylePreset:
    """A style preset that modifies the prompt for sticker generation."""

    name: str
    description: str
    prompt_modifier: str


# fmt: off
# ruff: noqa: E501
STYLE_PRESETS: dict[str, StylePreset] = {
    "kawaii": StylePreset(
        name="kawaii",
        description="Cute Japanese style with big eyes and pastel colors",
        prompt_modifier="in kawaii style with big sparkling eyes, rounded soft shapes, chibi proportions, pastel colors, and an adorable cute expression",
    ),
    "minimal": StylePreset(
        name="minimal",
        description="Clean minimalist style with flat colors",
        prompt_modifier="in minimalist flat design style with simple geometric shapes, limited color palette, clean lines, no gradients, bold solid colors",
    ),
    "3d": StylePreset(
        name="3d",
        description="3D rendered look with depth and lighting",
        prompt_modifier="as a 3D rendered illustration with smooth shading, soft shadows, depth and dimension, glossy highlights, professional 3D cartoon style",
    ),
    "pixel-art": StylePreset(
        name="pixel-art",
        description="Retro pixel art style",
        prompt_modifier="in pixel art style with visible square pixels, limited color palette, retro 16-bit video game aesthetic, crisp pixelated edges",
    ),
    "retro": StylePreset(
        name="retro",
        description="Vintage retro style with muted colors",
        prompt_modifier="in retro vintage style with muted warm colors, slightly worn look, 1970s-80s aesthetic, nostalgic cartoon style",
    ),
    "watercolor": StylePreset(
        name="watercolor",
        description="Soft watercolor painting style",
        prompt_modifier="in watercolor painting style with soft edges, color bleeds, artistic brush strokes, delicate and painterly aesthetic",
    ),
}
# fmt: on


def get_style(name: str | None) -> StylePreset | None:
    """Get style preset by name.

    Args:
        name: Style name or None.

    Returns:
        StylePreset if found, None if name is None.

    Raises:
        ValueError: If name is not a valid style.
    """
    if name is None:
        return None
    if name not in STYLE_PRESETS:
        available = ", ".join(sorted(STYLE_PRESETS.keys()))
        raise ValueError(f"Unknown style '{name}'. Available styles: {available}")
    return STYLE_PRESETS[name]


def get_available_styles() -> list[str]:
    """Get sorted list of available style names."""
    return sorted(STYLE_PRESETS.keys())


def format_prompt_with_style(prompt: str, style: str | None) -> str:
    """Apply style modifier to prompt.

    Args:
        prompt: The base prompt.
        style: Style name or None.

    Returns:
        Modified prompt with style, or original if no style.
    """
    style_preset = get_style(style)
    if style_preset is None:
        return prompt
    return f"{prompt} {style_preset.prompt_modifier}"
