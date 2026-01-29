"""Sticker sheet generation - create multiple variations and combine into grid."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image

from sticker_generator.core import _build_output_format, create_sticker
from sticker_generator.image_processing import save_transparent_image

if TYPE_CHECKING:
    from os import PathLike


@dataclass
class SheetResult:
    """Result from sticker sheet generation."""

    stickers: list[Image.Image] = field(default_factory=list)
    sheet: Image.Image | None = None
    failed_indices: list[int] = field(default_factory=list)


def calculate_grid_layout(count: int) -> tuple[int, int]:
    """Calculate optimal grid dimensions for a given count.

    Returns (columns, rows) tuple optimized for roughly square layout,
    preferring wider than taller.

    Args:
        count: Number of items to arrange in grid.

    Returns:
        Tuple of (columns, rows).

    Raises:
        ValueError: If count is not positive.
    """
    if count <= 0:
        raise ValueError("Count must be positive")

    cols = math.ceil(math.sqrt(count))
    rows = math.ceil(count / cols)

    return (cols, rows)


def create_sheet_image(
    stickers: list[Image.Image],
    columns: int | None = None,
    padding: int = 10,
    background_color: tuple[int, int, int, int] = (0, 0, 0, 0),
) -> Image.Image:
    """Combine sticker images into a single sheet grid.

    Args:
        stickers: List of PIL Images to combine.
        columns: Number of columns (auto-calculated if None).
        padding: Padding between stickers in pixels.
        background_color: RGBA background color for the sheet.

    Returns:
        Combined sheet as PIL Image.

    Raises:
        ValueError: If stickers list is empty.
    """
    if not stickers:
        raise ValueError("No stickers to combine")

    if columns is None:
        columns, rows = calculate_grid_layout(len(stickers))
    else:
        rows = math.ceil(len(stickers) / columns)

    max_width = max(s.width for s in stickers)
    max_height = max(s.height for s in stickers)

    sheet_width = columns * max_width + (columns + 1) * padding
    sheet_height = rows * max_height + (rows + 1) * padding

    sheet = Image.new("RGBA", (sheet_width, sheet_height), background_color)

    for i, sticker in enumerate(stickers):
        col = i % columns
        row = i // columns

        x = padding + col * (max_width + padding) + (max_width - sticker.width) // 2
        y = padding + row * (max_height + padding) + (max_height - sticker.height) // 2

        if sticker.mode == "RGBA":
            sheet.paste(sticker, (x, y), sticker)
        else:
            sheet.paste(sticker, (x, y))

    return sheet


def generate_sticker_sheet(
    prompt: str,
    variations: int = 4,
    output: str | PathLike | None = None,
    save_individuals: bool = False,
    individual_prefix: str | None = None,
    aspect_ratio: str = "1:1",
    input_images: list[str | PathLike] | None = None,
    api_key: str | None = None,
    edge_threshold: int = 64,
    columns: int | None = None,
    padding: int = 10,
    delay_between_requests: float = 0.5,
    max_retries: int = 2,
    style: str | None = None,
    output_format: str | None = None,
    quality: int | None = None,
    lossless: bool | None = None,
    resize: tuple[int, int] | None = None,
    resize_exact: bool = False,
) -> SheetResult:
    """Generate multiple sticker variations and combine into a sheet.

    Args:
        prompt: Description of the sticker to generate.
        variations: Number of variations to generate.
        output: Output filename for the sheet. Format auto-detected from extension.
        save_individuals: If True, save each sticker separately.
        individual_prefix: Prefix for individual sticker filenames.
        aspect_ratio: Image aspect ratio (default "1:1").
        input_images: Optional list of reference image paths.
        api_key: Optional Gemini API key.
        edge_threshold: Alpha threshold for edge cleanup.
        columns: Number of columns in grid (auto if None).
        padding: Padding between stickers in pixels.
        delay_between_requests: Seconds to wait between API calls.
        max_retries: Number of retries for failed generations.
        style: Optional style for the stickers.
        output_format: Output format preset name ("png", "webp", "webp-lossy").
            Auto-detected from filename extension if None.
        quality: Quality for lossy formats (1-100). Overrides preset default.
        lossless: Whether to use lossless compression. Overrides preset default.
        resize: Optional target size as (width, height) to resize each sticker.
        resize_exact: If True, force exact dimensions (may distort).

    Returns:
        SheetResult with stickers, sheet image, and failed indices.
    """
    stickers: list[Image.Image] = []
    failed_indices: list[int] = []

    for i in range(variations):
        retries = 0
        success = False

        while retries <= max_retries and not success:
            try:
                sticker = create_sticker(
                    prompt=prompt,
                    output=None,
                    aspect_ratio=aspect_ratio,
                    input_images=input_images,
                    api_key=api_key,
                    edge_threshold=edge_threshold,
                    style=style,
                    resize=resize,
                    resize_exact=resize_exact,
                )
                stickers.append(sticker)
                print(f"Generated variation {i + 1}/{variations}")
                success = True
            except Exception as e:
                retries += 1
                if retries > max_retries:
                    attempts = max_retries + 1
                    print(f"Failed variation {i + 1} after {attempts} attempts: {e}")
                    failed_indices.append(i)
                else:
                    print(f"Retry {retries}/{max_retries} for variation {i + 1}: {e}")
                    time.sleep(delay_between_requests * 2)

        if i < variations - 1 and success:
            time.sleep(delay_between_requests)

    sheet = None
    if stickers:
        sheet = create_sheet_image(stickers, columns=columns, padding=padding)

        if output:
            fmt = _build_output_format(output_format, str(output), quality, lossless)
            save_transparent_image(sheet, str(output), fmt)

    if save_individuals and stickers:
        if individual_prefix is None:
            if output:
                individual_prefix = Path(output).stem
            else:
                individual_prefix = "sticker"

        # Use same format for individuals as for sheet
        if output:
            fmt = _build_output_format(output_format, str(output), quality, lossless)
        else:
            # Default to PNG if no output specified
            from sticker_generator.formats import get_format

            fmt = get_format(output_format)
            if quality is not None or lossless is not None:
                from sticker_generator.formats import OutputFormat

                fmt = OutputFormat(
                    format_type=fmt.format_type,
                    quality=quality if quality is not None else fmt.quality,
                    lossless=lossless if lossless is not None else fmt.lossless,
                    extra_params=fmt.extra_params,
                )

        for i, sticker in enumerate(stickers):
            individual_filename = f"{individual_prefix}_{i + 1}{fmt.extension}"
            save_transparent_image(sticker, individual_filename, fmt)

    return SheetResult(stickers=stickers, sheet=sheet, failed_indices=failed_indices)
