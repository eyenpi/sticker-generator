"""Core sticker generation functionality using Gemini AI."""

from __future__ import annotations

import base64
import io
import logging
import mimetypes
import time
from pathlib import Path
from typing import TYPE_CHECKING

from google import genai
from PIL import Image

from sticker_generator.formats import OutputFormat, get_format
from sticker_generator.image_processing import (
    cleanup_edges,
    remove_green_screen_aggressive,
    remove_green_screen_hsv,
    resize_image,
    save_transparent_image,
    validate_transparency,
)
from sticker_generator.styles import format_prompt_with_style

if TYPE_CHECKING:
    from os import PathLike

logger = logging.getLogger(__name__)

MODEL_ID = "gemini-2.5-flash-image"

# fmt: off
# ruff: noqa: E501
CHROMAKEY_PROMPT_TEMPLATE = """Create a sticker illustration of: {prompt}

CRITICAL CHROMAKEY REQUIREMENTS:
1. BACKGROUND: Solid, flat, uniform chromakey green color. Use EXACTLY hex color #00FF00 (RGB 0, 255, 0).
   The entire background must be this single pure green color with NO variation, NO gradients, NO shadows, NO lighting effects.

2. WHITE OUTLINE: The subject MUST have a clean white outline/border (2-3 pixels wide) separating it from the green background.
   This white border prevents color bleeding between the subject and background.

3. NO GREEN ON SUBJECT: The subject itself should NOT contain any green colors to avoid confusion with the chromakey.
   If the subject needs green (like leaves), use a distinctly different shade like dark forest green or teal.

4. SHARP EDGES: The subject should have crisp, sharp, well-defined edges - no soft or blurry boundaries.

5. CENTERED: Subject should be centered with padding around all sides.

6. STYLE: Vibrant, clean, cartoon/illustration sticker style with bold colors.

This is for chromakey extraction - the green background will be removed programmatically."""
# fmt: on


def decode_image(data: str | bytes) -> Image.Image:
    """Decode image data to PIL Image.

    Args:
        data: Base64-encoded string or raw bytes.

    Returns:
        PIL Image object.
    """
    if isinstance(data, str):
        image_bytes = base64.b64decode(data)
    else:
        image_bytes = data
    return Image.open(io.BytesIO(image_bytes))


def load_image_as_content(image_path: str | PathLike) -> genai.types.Part:
    """Load an image file and return as API content block.

    Args:
        image_path: Path to the image file.

    Returns:
        Part formatted for Gemini API content.
    """
    path = Path(image_path)
    mime_type, _ = mimetypes.guess_type(str(path))
    if mime_type is None:
        mime_type = "image/jpeg"

    with open(path, "rb") as f:
        image_data = f.read()

    return genai.types.Part.from_bytes(data=image_data, mime_type=mime_type)


def generate_sticker(
    prompt: str,
    aspect_ratio: str = "1:1",
    input_images: list[str | PathLike] | None = None,
    api_key: str | None = None,
    style: str | None = None,
    max_retries: int = 3,
    retry_delay: float = 1.0,
) -> Image.Image:
    """Generate a sticker image with chromakey green background.

    Uses two layers of retry protection:
    1. HTTP-level retries via google-genai's built-in HttpRetryOptions for
       transient errors (429 rate limits, 500/502/503/504 server errors).
    2. Application-level retries for when the API returns a successful response
       but contains no image (only text).

    Args:
        prompt: Description of the sticker to generate.
        aspect_ratio: Image aspect ratio (default "1:1").
        input_images: Optional list of reference image paths.
        api_key: Optional Gemini API key (uses GEMINI_API_KEY env var if not provided).
        style: Optional style preset name (e.g., "kawaii", "minimal", "3d").
        max_retries: Maximum number of retries for failed generations (default 3).
            Applies to both HTTP errors and empty responses.
        retry_delay: Initial delay in seconds between retries (default 1.0).
            Doubles with each retry (exponential backoff).

    Returns:
        PIL Image with green background (before processing).

    Raises:
        ValueError: If no image was generated after all retries.
    """
    retry_options = genai.types.HttpRetryOptions(
        attempts=max_retries + 1,
        initial_delay=retry_delay,
        max_delay=retry_delay * (2**max_retries),
        exp_base=2,
        jitter=retry_delay,
    )
    http_options = genai.types.HttpOptions(retry_options=retry_options)

    if api_key:
        client = genai.Client(api_key=api_key, http_options=http_options)
    else:
        client = genai.Client(http_options=http_options)

    styled_prompt = format_prompt_with_style(prompt, style)
    enhanced_prompt = CHROMAKEY_PROMPT_TEMPLATE.format(prompt=styled_prompt)

    input_content: str | list = enhanced_prompt
    if input_images:
        content_list: list = []
        for img_path in input_images:
            content_list.append(load_image_as_content(img_path))
        content_list.append(enhanced_prompt)
        input_content = content_list

    for attempt in range(max_retries + 1):
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=input_content,
            config=genai.types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"],
            ),
        )

        if response.candidates:
            for part in response.candidates[0].content.parts:  # type: ignore[union-attr]
                if part.inline_data is not None:
                    logger.debug(
                        "Found image: mime_type=%s", part.inline_data.mime_type
                    )
                    return decode_image(part.inline_data.data)  # type: ignore[arg-type]
                elif part.text:
                    logger.debug("Text response: %s...", part.text[:200])

        if attempt < max_retries:
            delay = retry_delay * (2**attempt)
            logger.warning(
                "No image in response, retrying (%d/%d)... waiting %.1fs",
                attempt + 1,
                max_retries,
                delay,
            )
            time.sleep(delay)

    raise ValueError(f"No image was generated after {max_retries + 1} attempt(s)")


def process_image(
    input_path: str | PathLike,
    output: str | PathLike | None = None,
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
    save_intermediates: str | PathLike | None = None,
) -> Image.Image:
    """Process an existing image by removing its green background.

    Runs the same pipeline as create_sticker() but on an existing image
    instead of generating one via Gemini. Useful for processing images from
    other sources or re-processing raw outputs.

    Args:
        input_path: Path to the input image file.
        output: Optional output filename. Format auto-detected from extension.
        edge_threshold: Alpha threshold for edge cleanup (0-255).
        output_format: Output format preset name ("png", "webp", "webp-lossy").
            Auto-detected from filename extension if None.
        quality: Quality for lossy formats (1-100). Overrides preset default.
        lossless: Whether to use lossless compression. Overrides preset default.
        resize: Optional target size as (width, height) to resize the output.
        resize_exact: If True, force exact dimensions (may distort).
            Default maintains aspect ratio.
        hue_center: Center hue for green detection in degrees (default 115).
        hue_range: Tolerance around hue center in degrees (default 35).
        min_saturation: Minimum saturation % to consider green (default 25).
        min_value: Minimum brightness % to consider green (default 40).
        green_threshold: Ratio threshold for aggressive green removal
            (default 1.1). Higher values are more conservative.

    Returns:
        PIL Image with transparent background.
    """
    logger.debug("Processing image: %s", input_path)

    raw_image = Image.open(input_path)

    if save_intermediates:
        intermediates_dir = Path(save_intermediates)
        intermediates_dir.mkdir(parents=True, exist_ok=True)
        raw_image.save(intermediates_dir / "01_input_loaded.png")
        logger.debug("Saved intermediate: 01_input_loaded.png")

    # HSV-based green removal
    transparent_image = remove_green_screen_hsv(
        raw_image,
        hue_center=hue_center,
        hue_range=hue_range,
        min_saturation=min_saturation,
        min_value=min_value,
        dilation_iterations=2,
        erosion_iterations=0,
    )

    if save_intermediates:
        transparent_image.save(intermediates_dir / "02_after_hsv_removal.png")
        logger.debug("Saved intermediate: 02_after_hsv_removal.png")

    # Second pass: aggressive removal for remaining greens
    transparent_image = remove_green_screen_aggressive(
        transparent_image,
        green_threshold=green_threshold,
        edge_pixels=1,
    )

    if save_intermediates:
        transparent_image.save(intermediates_dir / "03_after_aggressive_removal.png")
        logger.debug("Saved intermediate: 03_after_aggressive_removal.png")

    # Edge cleanup
    transparent_image = cleanup_edges(transparent_image, threshold=edge_threshold)

    if save_intermediates:
        transparent_image.save(intermediates_dir / "04_after_edge_cleanup.png")
        logger.debug("Saved intermediate: 04_after_edge_cleanup.png")

    # Optional resize
    if resize is not None:
        transparent_image = resize_image(
            transparent_image, resize, maintain_aspect=not resize_exact
        )
        if save_intermediates:
            transparent_image.save(intermediates_dir / "05_after_resize.png")
            logger.debug("Saved intermediate: 05_after_resize.png")

    if output:
        fmt = _build_output_format(output_format, str(output), quality, lossless)
        save_transparent_image(transparent_image, str(output), fmt)

    return transparent_image


def create_sticker(
    prompt: str,
    output: str | PathLike | None = None,
    aspect_ratio: str = "1:1",
    save_raw: bool = False,
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
    save_intermediates: str | PathLike | None = None,
) -> Image.Image:
    """Generate a sticker with transparent background.

    Complete workflow: generates image with green background, removes green,
    cleans edges, optionally resizes, and optionally saves to file.

    Args:
        prompt: Description of the sticker to generate.
        output: Optional output filename. Format auto-detected from extension.
        aspect_ratio: Image aspect ratio (default "1:1").
        save_raw: If True, save the raw image before processing.
        input_images: Optional list of reference image paths.
        api_key: Optional Gemini API key (uses GEMINI_API_KEY env var if not provided).
        edge_threshold: Alpha threshold for edge cleanup (0-255).
        style: Optional style preset name (e.g., "kawaii", "minimal", "3d").
        output_format: Output format preset name ("png", "webp", "webp-lossy").
            Auto-detected from filename extension if None.
        quality: Quality for lossy formats (1-100). Overrides preset default.
        lossless: Whether to use lossless compression. Overrides preset default.
        resize: Optional target size as (width, height) to resize the output.
        resize_exact: If True, force exact dimensions (may distort).
            Default maintains aspect ratio.
        hue_center: Center hue for green detection in degrees (default 115).
        hue_range: Tolerance around hue center in degrees (default 35).
        min_saturation: Minimum saturation % to consider green (default 25).
        min_value: Minimum brightness % to consider green (default 40).
        green_threshold: Ratio threshold for aggressive green removal
            (default 1.1). Higher values are more conservative.
        max_retries: Maximum number of retries for failed generations (default 3).
            Applies to both HTTP errors and empty responses.
        retry_delay: Initial delay in seconds between retries (default 1.0).
            Doubles with each retry (exponential backoff).

    Returns:
        PIL Image with transparent background.
    """
    logger.debug("Creating sticker: prompt=%r, style=%s", prompt, style)

    raw_image = generate_sticker(
        prompt=prompt,
        aspect_ratio=aspect_ratio,
        input_images=input_images,
        api_key=api_key,
        style=style,
        max_retries=max_retries,
        retry_delay=retry_delay,
    )

    if save_raw and output:
        output_path = Path(output)
        raw_filename = output_path.with_stem(output_path.stem + "_raw")
        raw_image.save(raw_filename)

    if save_intermediates:
        intermediates_dir = Path(save_intermediates)
        intermediates_dir.mkdir(parents=True, exist_ok=True)
        raw_image.save(intermediates_dir / "01_raw_from_api.png")
        logger.debug("Saved intermediate: 01_raw_from_api.png")

    # HSV-based green removal
    transparent_image = remove_green_screen_hsv(
        raw_image,
        hue_center=hue_center,
        hue_range=hue_range,
        min_saturation=min_saturation,
        min_value=min_value,
        dilation_iterations=2,
        erosion_iterations=0,
    )

    if save_intermediates:
        transparent_image.save(intermediates_dir / "02_after_hsv_removal.png")
        logger.debug("Saved intermediate: 02_after_hsv_removal.png")

    # Second pass: aggressive removal for remaining greens
    transparent_image = remove_green_screen_aggressive(
        transparent_image,
        green_threshold=green_threshold,
        edge_pixels=1,
    )

    if save_intermediates:
        transparent_image.save(intermediates_dir / "03_after_aggressive_removal.png")
        logger.debug("Saved intermediate: 03_after_aggressive_removal.png")

    # Edge cleanup
    transparent_image = cleanup_edges(transparent_image, threshold=edge_threshold)

    if save_intermediates:
        transparent_image.save(intermediates_dir / "04_after_edge_cleanup.png")
        logger.debug("Saved intermediate: 04_after_edge_cleanup.png")

    # Optional resize
    if resize is not None:
        transparent_image = resize_image(
            transparent_image, resize, maintain_aspect=not resize_exact
        )
        if save_intermediates:
            transparent_image.save(intermediates_dir / "05_after_resize.png")
            logger.debug("Saved intermediate: 05_after_resize.png")

    # Quality validation
    metrics = validate_transparency(transparent_image)
    if metrics.has_quality_warning:
        logger.warning("Warning: %s", metrics.warning_message)

    if output:
        # Build format configuration
        fmt = _build_output_format(output_format, str(output), quality, lossless)
        save_transparent_image(transparent_image, str(output), fmt)

    return transparent_image


def _build_output_format(
    output_format: str | None,
    filename: str,
    quality: int | None,
    lossless: bool | None,
) -> OutputFormat:
    """Build OutputFormat from parameters, applying overrides.

    Args:
        output_format: Format preset name or None to auto-detect.
        filename: Filename to detect format from if output_format is None.
        quality: Quality override or None.
        lossless: Lossless override or None.

    Returns:
        Configured OutputFormat.
    """
    from sticker_generator.formats import format_from_extension

    # Get base format
    if output_format is not None:
        base_fmt = get_format(output_format)
    else:
        base_fmt = format_from_extension(filename)

    # Return base if no overrides
    if quality is None and lossless is None:
        return base_fmt

    # Apply overrides by creating new OutputFormat
    new_quality = quality if quality is not None else base_fmt.quality
    new_lossless = lossless if lossless is not None else base_fmt.lossless

    return OutputFormat(
        format_type=base_fmt.format_type,
        quality=new_quality,
        lossless=new_lossless,
        extra_params=base_fmt.extra_params,
    )
