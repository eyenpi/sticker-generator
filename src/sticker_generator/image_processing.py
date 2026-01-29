"""Image processing utilities for green screen removal and edge cleanup."""

from __future__ import annotations

import warnings

import numpy as np
from PIL import Image

from sticker_generator.formats import OutputFormat, format_from_extension, get_format


def rgb_to_hsv_array(rgb_array: np.ndarray) -> np.ndarray:
    """Convert RGB array to HSV array efficiently.

    Args:
        rgb_array: NumPy array of RGB values (H, W, 3).

    Returns:
        NumPy array of HSV values (H, W, 3) with H in [0, 360], S and V in [0, 100].
    """
    rgb_normalized = rgb_array.astype(np.float32) / 255.0
    r, g, b = rgb_normalized[:, :, 0], rgb_normalized[:, :, 1], rgb_normalized[:, :, 2]

    max_c = np.maximum(np.maximum(r, g), b)
    min_c = np.minimum(np.minimum(r, g), b)
    delta = max_c - min_c

    h = np.zeros_like(max_c)
    mask_r = (max_c == r) & (delta != 0)
    h[mask_r] = (60 * ((g[mask_r] - b[mask_r]) / delta[mask_r]) + 360) % 360

    mask_g = (max_c == g) & (delta != 0)
    h[mask_g] = 60 * ((b[mask_g] - r[mask_g]) / delta[mask_g]) + 120

    mask_b = (max_c == b) & (delta != 0)
    h[mask_b] = 60 * ((r[mask_b] - g[mask_b]) / delta[mask_b]) + 240

    s = np.zeros_like(max_c)
    s[max_c != 0] = delta[max_c != 0] / max_c[max_c != 0]

    v = max_c
    return np.stack([h, s * 100, v * 100], axis=-1)


def remove_green_screen_hsv(
    image: Image.Image,
    hue_center: float = 120,
    hue_range: float = 25,
    min_saturation: float = 75,
    min_value: float = 70,
    dilation_iterations: int = 2,
    erosion_iterations: int = 0,
) -> Image.Image:
    """Remove green screen using HSV color space detection.

    Args:
        image: PIL Image to process.
        hue_center: Center hue value for green (default 120 degrees).
        hue_range: Tolerance around hue center in degrees.
        min_saturation: Minimum saturation percentage to consider as green.
        min_value: Minimum value/brightness percentage to consider as green.
        dilation_iterations: Number of dilation passes to catch anti-aliased edges.
        erosion_iterations: Number of erosion passes.

    Returns:
        PIL Image with green background removed (RGBA with transparency).
    """
    if image.mode != "RGBA":
        image = image.convert("RGBA")

    data = np.array(image)
    rgb = data[:, :, :3]
    hsv = rgb_to_hsv_array(rgb)
    h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]

    hue_diff = np.abs(h - hue_center)
    hue_diff = np.minimum(hue_diff, 360 - hue_diff)

    green_mask = (hue_diff < hue_range) & (s > min_saturation) & (v > min_value)

    if dilation_iterations > 0 or erosion_iterations > 0:
        from scipy import ndimage

        if dilation_iterations > 0:
            green_mask = ndimage.binary_dilation(
                green_mask, iterations=dilation_iterations
            )
        if erosion_iterations > 0:
            green_mask = ndimage.binary_erosion(
                green_mask, iterations=erosion_iterations
            )

    alpha = data[:, :, 3].copy()
    alpha[green_mask] = 0
    data[:, :, 3] = alpha

    return Image.fromarray(data)


def remove_green_screen_aggressive(
    image: Image.Image,
    green_threshold: float = 1.2,
    edge_pixels: int = 0,
) -> Image.Image:
    """Aggressive green removal detecting dominant green pixels.

    This method catches darker greens and tinted shadows that HSV might miss.

    Args:
        image: PIL Image to process.
        green_threshold: Ratio threshold for green channel dominance.
        edge_pixels: Number of dilation iterations for edge expansion.

    Returns:
        PIL Image with green background removed (RGBA with transparency).
    """
    if image.mode != "RGBA":
        image = image.convert("RGBA")

    data = np.array(image)
    r = data[:, :, 0].astype(float)
    g = data[:, :, 1].astype(float)
    b = data[:, :, 2].astype(float)

    rb_max = np.maximum(r, b) + 1
    green_ratio = g / rb_max
    green_dominant = (g > r) & (g > b)
    green_mask = (green_ratio > green_threshold) & green_dominant

    if edge_pixels > 0:
        from scipy import ndimage

        green_mask = ndimage.binary_dilation(green_mask, iterations=edge_pixels)

    alpha = data[:, :, 3].copy()
    alpha[green_mask] = 0
    data[:, :, 3] = alpha

    return Image.fromarray(data)


def cleanup_edges(image: Image.Image, threshold: int = 128) -> Image.Image:
    """Clean up semi-transparent edge pixels by thresholding alpha.

    Args:
        image: PIL Image to process.
        threshold: Alpha values below this become fully transparent,
                   values at or above become fully opaque.

    Returns:
        PIL Image with cleaned edges.
    """
    if image.mode != "RGBA":
        return image

    data = np.array(image)
    alpha = data[:, :, 3]
    alpha[alpha < threshold] = 0
    alpha[alpha >= threshold] = 255

    data[:, :, 3] = alpha
    return Image.fromarray(data)


def resize_image(
    image: Image.Image,
    size: tuple[int, int],
    maintain_aspect: bool = True,
    resampling: Image.Resampling = Image.Resampling.LANCZOS,
) -> Image.Image:
    """Resize an image to the specified dimensions.

    Args:
        image: PIL Image to resize.
        size: Target size as (width, height).
        maintain_aspect: If True, fit within bounds while preserving aspect ratio.
                        If False, force exact dimensions (may distort).
        resampling: Resampling filter to use (default LANCZOS for best quality).

    Returns:
        Resized PIL Image.

    Raises:
        ValueError: If width or height is not positive.
    """
    width, height = size
    if width <= 0 or height <= 0:
        raise ValueError("Width and height must be positive integers")

    if maintain_aspect:
        # Calculate size that fits within bounds while preserving aspect ratio
        original_width, original_height = image.size
        ratio = min(width / original_width, height / original_height)
        new_width = int(original_width * ratio)
        new_height = int(original_height * ratio)
        # Ensure at least 1 pixel
        new_width = max(1, new_width)
        new_height = max(1, new_height)
        return image.resize((new_width, new_height), resampling)
    else:
        return image.resize((width, height), resampling)


def _resolve_format(
    output_format: OutputFormat | str | None,
    filename: str,
) -> OutputFormat:
    """Resolve format from various input types.

    Args:
        output_format: OutputFormat instance, preset name, or None.
        filename: Filename to detect format from if output_format is None.

    Returns:
        Resolved OutputFormat.
    """
    if output_format is None:
        return format_from_extension(filename)
    if isinstance(output_format, str):
        return get_format(output_format)
    return output_format


def save_transparent_image(
    image: Image.Image,
    filename: str,
    output_format: OutputFormat | str | None = None,
) -> None:
    """Save image with transparency in specified format.

    Auto-detects format from extension if output_format is None.

    Args:
        image: PIL Image to save.
        filename: Output filename.
        output_format: OutputFormat instance, preset name (e.g., "png", "webp"),
            or None to auto-detect from filename extension.
    """
    if image.mode != "RGBA":
        image = image.convert("RGBA")

    fmt = _resolve_format(output_format, filename)
    save_params = fmt.get_save_params()
    image.save(filename, fmt.pil_format, **save_params)


def save_transparent_png(image: Image.Image, filename: str) -> None:
    """Save image as PNG with transparency preserved.

    .. deprecated::
        Use :func:`save_transparent_image` instead.

    Args:
        image: PIL Image to save.
        filename: Output filename.
    """
    warnings.warn(
        "save_transparent_png is deprecated, use save_transparent_image instead",
        DeprecationWarning,
        stacklevel=2,
    )
    if image.mode != "RGBA":
        image = image.convert("RGBA")
    image.save(filename, "PNG")
