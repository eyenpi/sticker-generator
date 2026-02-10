"""Batch processing for sticker generation and image processing."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from sticker_generator.core import _build_output_format, create_sticker, process_image
from sticker_generator.image_processing import validate_transparency

if TYPE_CHECKING:
    from os import PathLike

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"})


@dataclass
class BatchItem:
    """A single item in a batch operation."""

    index: int
    source: str
    output_path: Path | None = None
    error: str | None = None


@dataclass
class BatchResult:
    """Result from batch processing."""

    successful: list[BatchItem] = field(default_factory=list)
    failed: list[BatchItem] = field(default_factory=list)
    total: int = 0


def parse_prompt_file(file_path: str | PathLike) -> list[str]:
    """Read prompts from a text file, one per line.

    Blank lines and lines starting with # are skipped.

    Args:
        file_path: Path to the prompts file.

    Returns:
        List of prompt strings.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If no valid prompts are found.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {file_path}")

    prompts: list[str] = []
    with open(path) as f:
        for line in f:
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                prompts.append(stripped)

    if not prompts:
        raise ValueError(f"No valid prompts found in: {file_path}")

    return prompts


def batch_generate(
    prompts: list[str],
    output_dir: str | PathLike,
    aspect_ratio: str = "1:1",
    input_images: list[str | PathLike] | None = None,
    api_key: str | None = None,
    edge_threshold: int = 64,
    style: str | None = None,
    output_format: str | None = None,
    quality: int | None = None,
    lossless: bool | None = None,
    resize: tuple[int, int] | None = None,
    resize_exact: bool = False,
    hue_center: float = 115,
    hue_range: float = 35,
    min_saturation: float = 25,
    min_value: float = 40,
    green_threshold: float = 1.1,
    max_retries: int = 3,
    retry_delay: float = 1.0,
    delay_between_requests: float = 1.0,
    strict: bool = False,
    save_intermediates: str | PathLike | None = None,
) -> BatchResult:
    """Generate stickers from a list of prompts.

    Args:
        prompts: List of prompt strings.
        output_dir: Directory to save generated stickers.
        aspect_ratio: Image aspect ratio (default "1:1").
        input_images: Optional list of reference image paths.
        api_key: Optional Gemini API key.
        edge_threshold: Alpha threshold for edge cleanup (0-255).
        style: Optional style preset name.
        output_format: Output format preset name.
        quality: Quality for lossy formats (1-100).
        lossless: Whether to use lossless compression.
        resize: Optional target size as (width, height).
        resize_exact: If True, force exact dimensions.
        hue_center: Center hue for green detection in degrees.
        hue_range: Tolerance around hue center in degrees.
        min_saturation: Minimum saturation % to consider green.
        min_value: Minimum brightness % to consider green.
        green_threshold: Ratio threshold for aggressive green removal.
        max_retries: Maximum number of retries for failed generations.
        retry_delay: Initial delay in seconds between retries.
        delay_between_requests: Seconds to wait between API calls.
        strict: If True, stop on first failure.
        save_intermediates: Directory to save intermediate images.

    Returns:
        BatchResult with successful and failed items.
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    fmt = _build_output_format(output_format, "output.png", quality, lossless)
    ext = fmt.extension

    result = BatchResult(total=len(prompts))

    for i, prompt in enumerate(prompts):
        item = BatchItem(index=i, source=prompt)
        filename = f"sticker_{i + 1:03d}{ext}"
        output_path = out_dir / filename
        item.output_path = output_path

        logger.info("Batch generate: %d/%d - %s", i + 1, len(prompts), prompt)

        try:
            item_intermediates = None
            if save_intermediates:
                item_intermediates = str(
                    Path(save_intermediates) / f"batch_{i + 1:03d}"
                )

            image = create_sticker(
                prompt=prompt,
                output=str(output_path),
                aspect_ratio=aspect_ratio,
                input_images=input_images,
                api_key=api_key,
                edge_threshold=edge_threshold,
                style=style,
                output_format=output_format,
                quality=quality,
                lossless=lossless,
                resize=resize,
                resize_exact=resize_exact,
                hue_center=hue_center,
                hue_range=hue_range,
                min_saturation=min_saturation,
                min_value=min_value,
                green_threshold=green_threshold,
                max_retries=max_retries,
                retry_delay=retry_delay,
                save_intermediates=item_intermediates,
            )

            metrics = validate_transparency(image)
            if metrics.has_quality_warning:
                logger.warning(
                    "Quality warning for item %d: %s", i + 1, metrics.warning_message
                )

            result.successful.append(item)
        except Exception as e:
            item.error = str(e)
            result.failed.append(item)
            logger.error("Failed item %d: %s", i + 1, e)

            if strict:
                logger.error("Stopping batch (--strict mode)")
                break

        if i < len(prompts) - 1:
            time.sleep(delay_between_requests)

    logger.info(
        "Batch generate complete: %d/%d successful",
        len(result.successful),
        result.total,
    )
    return result


def batch_process_images(
    input_dir: str | PathLike,
    output_dir: str | PathLike,
    edge_threshold: int = 64,
    output_format: str | None = None,
    quality: int | None = None,
    lossless: bool | None = None,
    resize: tuple[int, int] | None = None,
    resize_exact: bool = False,
    hue_center: float = 115,
    hue_range: float = 35,
    min_saturation: float = 25,
    min_value: float = 40,
    green_threshold: float = 1.1,
    strict: bool = False,
    save_intermediates: str | PathLike | None = None,
) -> BatchResult:
    """Process all images in a directory by removing green backgrounds.

    Args:
        input_dir: Directory containing input images.
        output_dir: Directory to save processed images.
        edge_threshold: Alpha threshold for edge cleanup (0-255).
        output_format: Output format preset name.
        quality: Quality for lossy formats (1-100).
        lossless: Whether to use lossless compression.
        resize: Optional target size as (width, height).
        resize_exact: If True, force exact dimensions.
        hue_center: Center hue for green detection in degrees.
        hue_range: Tolerance around hue center in degrees.
        min_saturation: Minimum saturation % to consider green.
        min_value: Minimum brightness % to consider green.
        green_threshold: Ratio threshold for aggressive green removal.
        strict: If True, stop on first failure.
        save_intermediates: Directory to save intermediate images.

    Returns:
        BatchResult with successful and failed items.

    Raises:
        FileNotFoundError: If input_dir does not exist.
        ValueError: If no image files are found.
    """
    in_dir = Path(input_dir)
    if not in_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    image_files = sorted(
        f for f in in_dir.iterdir() if f.suffix.lower() in IMAGE_EXTENSIONS
    )

    if not image_files:
        raise ValueError(f"No image files found in: {input_dir}")

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    fmt = _build_output_format(output_format, "output.png", quality, lossless)
    ext = fmt.extension

    # Track used stems for collision avoidance
    used_stems: dict[str, int] = {}

    result = BatchResult(total=len(image_files))

    for i, image_file in enumerate(image_files):
        item = BatchItem(index=i, source=str(image_file))

        # Collision avoidance for output filenames
        stem = image_file.stem
        if stem in used_stems:
            used_stems[stem] += 1
            output_filename = f"{stem}_{used_stems[stem]}{ext}"
        else:
            used_stems[stem] = 1
            output_filename = f"{stem}{ext}"

        output_path = out_dir / output_filename
        item.output_path = output_path

        logger.info(
            "Batch process: %d/%d - %s", i + 1, len(image_files), image_file.name
        )

        try:
            item_intermediates = None
            if save_intermediates:
                item_intermediates = str(
                    Path(save_intermediates) / f"batch_{i + 1:03d}"
                )

            image = process_image(
                input_path=str(image_file),
                output=str(output_path),
                edge_threshold=edge_threshold,
                output_format=output_format,
                quality=quality,
                lossless=lossless,
                resize=resize,
                resize_exact=resize_exact,
                hue_center=hue_center,
                hue_range=hue_range,
                min_saturation=min_saturation,
                min_value=min_value,
                green_threshold=green_threshold,
                save_intermediates=item_intermediates,
            )

            metrics = validate_transparency(image)
            if metrics.has_quality_warning:
                logger.warning(
                    "Quality warning for %s: %s",
                    image_file.name,
                    metrics.warning_message,
                )

            result.successful.append(item)
        except Exception as e:
            item.error = str(e)
            result.failed.append(item)
            logger.error("Failed %s: %s", image_file.name, e)

            if strict:
                logger.error("Stopping batch (--strict mode)")
                break

    logger.info(
        "Batch process complete: %d/%d successful",
        len(result.successful),
        result.total,
    )
    return result
