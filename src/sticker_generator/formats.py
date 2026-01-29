"""Output format configuration for sticker images."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class OutputFormatType(Enum):
    """Supported output image formats."""

    PNG = "png"
    WEBP = "webp"


@dataclass(frozen=True)
class OutputFormat:
    """Configuration for output image format.

    Attributes:
        format_type: The image format (PNG or WebP).
        quality: Quality level for lossy compression (1-100). None = lossless.
        lossless: Whether to use lossless compression. Default True for transparency.
        extra_params: Additional format-specific parameters passed to PIL save().
    """

    format_type: OutputFormatType
    quality: int | None = None
    lossless: bool = True
    extra_params: dict[str, Any] = field(default_factory=dict)

    @property
    def extension(self) -> str:
        """Get the file extension including the dot."""
        return f".{self.format_type.value}"

    @property
    def pil_format(self) -> str:
        """Get the PIL format string for saving."""
        return self.format_type.value.upper()

    def get_save_params(self) -> dict[str, Any]:
        """Get parameters to pass to PIL Image.save().

        Returns:
            Dictionary of save parameters appropriate for the format.
        """
        params: dict[str, Any] = {}

        if self.format_type == OutputFormatType.PNG:
            # PNG uses compress_level (0-9, default 6)
            if "compress_level" in self.extra_params:
                params["compress_level"] = self.extra_params["compress_level"]

        elif self.format_type == OutputFormatType.WEBP:
            # WebP has lossless and quality options
            params["lossless"] = self.lossless
            params["exact"] = True  # Preserve transparent RGB values

            if not self.lossless and self.quality is not None:
                params["quality"] = self.quality

            # Method controls quality/speed tradeoff (0-6, default 4)
            if "method" in self.extra_params:
                params["method"] = self.extra_params["method"]

        # Add any extra params
        for key, value in self.extra_params.items():
            if key not in params:
                params[key] = value

        return params


# Preset format configurations
FORMAT_PRESETS: dict[str, OutputFormat] = {
    "png": OutputFormat(
        format_type=OutputFormatType.PNG,
        lossless=True,
    ),
    "webp": OutputFormat(
        format_type=OutputFormatType.WEBP,
        lossless=True,
    ),
    "webp-lossy": OutputFormat(
        format_type=OutputFormatType.WEBP,
        lossless=False,
        quality=90,
    ),
}


def get_format(name: str | None) -> OutputFormat:
    """Get format preset by name.

    Args:
        name: Format name or None for default (PNG).

    Returns:
        OutputFormat configuration.

    Raises:
        ValueError: If name is not a valid format.
    """
    if name is None:
        return FORMAT_PRESETS["png"]
    if name not in FORMAT_PRESETS:
        available = ", ".join(sorted(FORMAT_PRESETS.keys()))
        raise ValueError(f"Unknown format '{name}'. Available formats: {available}")
    return FORMAT_PRESETS[name]


def get_available_formats() -> list[str]:
    """Get sorted list of available format preset names."""
    return sorted(FORMAT_PRESETS.keys())


def format_from_extension(filename: str) -> OutputFormat:
    """Determine format from filename extension.

    Args:
        filename: Filename or path to check.

    Returns:
        OutputFormat based on extension. Defaults to PNG for unknown extensions.
    """
    lower_filename = filename.lower()
    if lower_filename.endswith(".webp"):
        return FORMAT_PRESETS["webp"]
    # Default to PNG for .png or any unknown extension
    return FORMAT_PRESETS["png"]
