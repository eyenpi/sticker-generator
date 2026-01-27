"""Sticker Generator - Create stickers with transparent backgrounds using Gemini AI."""

from sticker_generator.core import create_sticker, generate_sticker
from sticker_generator.image_processing import (
    cleanup_edges,
    remove_green_screen_aggressive,
    remove_green_screen_hsv,
)

__version__ = "0.1.0"
__all__ = [
    "create_sticker",
    "generate_sticker",
    "remove_green_screen_hsv",
    "remove_green_screen_aggressive",
    "cleanup_edges",
]
