"""Batch processing for sticker generation and image processing."""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sticker_generator.core import _build_output_format, create_sticker, process_image
from sticker_generator.image_processing import validate_transparency

if TYPE_CHECKING:
    from collections.abc import Callable
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


def _generate_single_batch_item(item: BatchItem, **kwargs: Any) -> BatchItem:
    """Generate a single sticker for a batch item.

    Catches exceptions internally and stores them in item.error.

    Args:
        item: BatchItem with index, source (prompt), and output_path set.
        **kwargs: Forwarded to create_sticker().

    Returns:
        The same BatchItem, with error set on failure.
    """
    try:
        logger.info("Batch generate: %d - %s", item.index + 1, item.source)
        image = create_sticker(prompt=item.source, **kwargs)

        metrics = validate_transparency(image)
        if metrics.has_quality_warning:
            logger.warning(
                "Quality warning for item %d: %s",
                item.index + 1,
                metrics.warning_message,
            )
    except Exception as e:
        item.error = str(e)
        logger.error("Failed item %d: %s", item.index + 1, e)

    return item


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
    max_workers: int = 1,
    progress_callback: Callable[[], object] | None = None,
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
        max_workers: Maximum number of concurrent workers (default 1 for
            sequential execution).
        progress_callback: Optional callable invoked after each item completes
            (success or failure). Called with no arguments.

    Returns:
        BatchResult with successful and failed items.
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    fmt = _build_output_format(output_format, "output.png", quality, lossless)
    ext = fmt.extension

    result = BatchResult(total=len(prompts))

    # Pre-compute items with output paths
    items: list[BatchItem] = []
    for i, prompt in enumerate(prompts):
        item = BatchItem(index=i, source=prompt)
        filename = f"sticker_{i + 1:03d}{ext}"
        item.output_path = out_dir / filename
        items.append(item)

    effective_workers = max_workers
    if strict and max_workers > 1:
        logger.warning(
            "Strict mode enabled: falling back to sequential execution "
            "(max_workers=1 instead of %d)",
            max_workers,
        )
        effective_workers = 1

    if effective_workers > 1:
        logger.debug(
            "Ignoring delay_between_requests=%.1f in concurrent mode "
            "(max_workers=%d controls rate limiting)",
            delay_between_requests,
            effective_workers,
        )

        futures = []
        with ThreadPoolExecutor(max_workers=effective_workers) as executor:
            for item in items:
                item_intermediates = None
                if save_intermediates:
                    item_intermediates = str(
                        Path(save_intermediates) / f"batch_{item.index + 1:03d}"
                    )

                future = executor.submit(
                    _generate_single_batch_item,
                    item=item,
                    output=str(item.output_path),
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
                futures.append(future)

        # Collect results in submission order
        for future in futures:
            item = future.result()
            if item.error is None:
                result.successful.append(item)
            else:
                result.failed.append(item)
            if progress_callback is not None:
                progress_callback()
    else:
        for item in items:
            item_intermediates = None
            if save_intermediates:
                item_intermediates = str(
                    Path(save_intermediates) / f"batch_{item.index + 1:03d}"
                )

            logger.info(
                "Batch generate: %d/%d - %s",
                item.index + 1,
                len(prompts),
                item.source,
            )

            try:
                image = create_sticker(
                    prompt=item.source,
                    output=str(item.output_path),
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
                        "Quality warning for item %d: %s",
                        item.index + 1,
                        metrics.warning_message,
                    )

                result.successful.append(item)
            except Exception as e:
                item.error = str(e)
                result.failed.append(item)
                logger.error("Failed item %d: %s", item.index + 1, e)

                if strict:
                    logger.error("Stopping batch (--strict mode)")
                    if progress_callback is not None:
                        progress_callback()
                    break

            if progress_callback is not None:
                progress_callback()

            if item.index < len(prompts) - 1:
                time.sleep(delay_between_requests)

    logger.info(
        "Batch generate complete: %d/%d successful",
        len(result.successful),
        result.total,
    )
    return result


def _process_single_image(item: BatchItem, **kwargs: Any) -> BatchItem:
    """Process a single image for batch processing.

    Catches exceptions internally and stores them in item.error.

    Args:
        item: BatchItem with index, source (input path), and output_path set.
        **kwargs: Forwarded to process_image().

    Returns:
        The same BatchItem, with error set on failure.
    """
    try:
        logger.info("Batch process: %d - %s", item.index + 1, Path(item.source).name)
        image = process_image(input_path=item.source, **kwargs)

        metrics = validate_transparency(image)
        if metrics.has_quality_warning:
            logger.warning(
                "Quality warning for %s: %s",
                Path(item.source).name,
                metrics.warning_message,
            )
    except Exception as e:
        item.error = str(e)
        logger.error("Failed %s: %s", Path(item.source).name, e)

    return item


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
    max_workers: int = 1,
    progress_callback: Callable[[], object] | None = None,
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
        max_workers: Maximum number of concurrent workers (default 1 for
            sequential execution).
        progress_callback: Optional callable invoked after each item completes
            (success or failure). Called with no arguments.

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

    # Pre-compute items with output paths (collision avoidance)
    used_stems: dict[str, int] = {}
    items: list[BatchItem] = []
    for i, image_file in enumerate(image_files):
        item = BatchItem(index=i, source=str(image_file))

        stem = image_file.stem
        if stem in used_stems:
            used_stems[stem] += 1
            output_filename = f"{stem}_{used_stems[stem]}{ext}"
        else:
            used_stems[stem] = 1
            output_filename = f"{stem}{ext}"

        item.output_path = out_dir / output_filename
        items.append(item)

    result = BatchResult(total=len(image_files))

    effective_workers = max_workers
    if strict and max_workers > 1:
        logger.warning(
            "Strict mode enabled: falling back to sequential execution "
            "(max_workers=1 instead of %d)",
            max_workers,
        )
        effective_workers = 1

    if effective_workers > 1:
        futures = []
        with ThreadPoolExecutor(max_workers=effective_workers) as executor:
            for item in items:
                item_intermediates = None
                if save_intermediates:
                    item_intermediates = str(
                        Path(save_intermediates) / f"batch_{item.index + 1:03d}"
                    )

                future = executor.submit(
                    _process_single_image,
                    item=item,
                    output=str(item.output_path),
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
                futures.append(future)

        # Collect results in submission order
        for future in futures:
            item = future.result()
            if item.error is None:
                result.successful.append(item)
            else:
                result.failed.append(item)
            if progress_callback is not None:
                progress_callback()
    else:
        for item in items:
            item_intermediates = None
            if save_intermediates:
                item_intermediates = str(
                    Path(save_intermediates) / f"batch_{item.index + 1:03d}"
                )

            logger.info(
                "Batch process: %d/%d - %s",
                item.index + 1,
                len(image_files),
                Path(item.source).name,
            )

            try:
                image = process_image(
                    input_path=item.source,
                    output=str(item.output_path),
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
                        Path(item.source).name,
                        metrics.warning_message,
                    )

                result.successful.append(item)
            except Exception as e:
                item.error = str(e)
                result.failed.append(item)
                logger.error("Failed %s: %s", Path(item.source).name, e)

                if strict:
                    logger.error("Stopping batch (--strict mode)")
                    if progress_callback is not None:
                        progress_callback()
                    break

            if progress_callback is not None:
                progress_callback()

    logger.info(
        "Batch process complete: %d/%d successful",
        len(result.successful),
        result.total,
    )
    return result
