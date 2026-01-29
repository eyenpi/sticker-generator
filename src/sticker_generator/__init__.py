"""Sticker Generator - Create stickers with transparent backgrounds using Gemini AI."""

from sticker_generator.core import create_sticker, generate_sticker
from sticker_generator.formats import (
    FORMAT_PRESETS,
    OutputFormat,
    OutputFormatType,
    get_available_formats,
    get_format,
)
from sticker_generator.image_processing import (
    cleanup_edges,
    remove_green_screen_aggressive,
    remove_green_screen_hsv,
    resize_image,
    save_transparent_image,
)
from sticker_generator.sheet import (
    SheetResult,
    calculate_grid_layout,
    create_sheet_image,
    generate_sticker_sheet,
)
from sticker_generator.styles import (
    STYLE_PRESETS,
    StylePreset,
    get_available_styles,
    get_style,
)

__all__ = [
    "create_sticker",
    "generate_sticker",
    "remove_green_screen_hsv",
    "remove_green_screen_aggressive",
    "cleanup_edges",
    "resize_image",
    "save_transparent_image",
    "STYLE_PRESETS",
    "StylePreset",
    "get_available_styles",
    "get_style",
    "FORMAT_PRESETS",
    "OutputFormat",
    "OutputFormatType",
    "get_available_formats",
    "get_format",
    "generate_sticker_sheet",
    "create_sheet_image",
    "calculate_grid_layout",
    "SheetResult",
]
