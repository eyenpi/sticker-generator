"""TOML configuration file support for sticker-generator."""

from __future__ import annotations

import logging
import sys
import warnings
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """Raised for invalid configuration values."""


@dataclass
class StickerConfig:
    """Configuration loaded from TOML files.

    All fields default to None, meaning "not set". The CLI applies
    hardcoded defaults for any value that remains None after config
    file loading.
    """

    # [api]
    api_key: str | None = None

    # [style]
    style: str | None = None
    output_format: str | None = None
    quality: int | None = None
    lossless: bool | None = None

    # [green_removal]
    hue_center: float | None = None
    hue_range: float | None = None
    min_saturation: float | None = None
    min_value: float | None = None
    green_threshold: float | None = None

    # [processing]
    edge_threshold: int | None = None
    resize: tuple[int, int] | None = None
    resize_exact: bool | None = None

    # [retry]
    max_retries: int | None = None
    retry_delay: float | None = None

    # [batch]
    delay: float | None = None
    max_workers: int | None = None
    strict: bool | None = None

    # [sheet]
    variations: int | None = None
    columns: int | None = None
    padding: int | None = None

    # [output]
    aspect_ratio: str | None = None
    save_raw: bool | None = None
    save_intermediates: str | None = None


# Maps (section, toml_key) -> StickerConfig field name
_TOML_KEY_MAP: dict[tuple[str, str], str] = {
    ("api", "api_key"): "api_key",
    ("style", "preset"): "style",
    ("style", "output_format"): "output_format",
    ("style", "quality"): "quality",
    ("style", "lossless"): "lossless",
    ("green_removal", "hue_center"): "hue_center",
    ("green_removal", "hue_range"): "hue_range",
    ("green_removal", "min_saturation"): "min_saturation",
    ("green_removal", "min_value"): "min_value",
    ("green_removal", "green_threshold"): "green_threshold",
    ("processing", "edge_threshold"): "edge_threshold",
    ("processing", "resize"): "resize",
    ("processing", "resize_exact"): "resize_exact",
    ("retry", "max_retries"): "max_retries",
    ("retry", "retry_delay"): "retry_delay",
    ("batch", "delay"): "delay",
    ("batch", "max_workers"): "max_workers",
    ("batch", "strict"): "strict",
    ("sheet", "variations"): "variations",
    ("sheet", "columns"): "columns",
    ("sheet", "padding"): "padding",
    ("output", "aspect_ratio"): "aspect_ratio",
    ("output", "save_raw"): "save_raw",
    ("output", "save_intermediates"): "save_intermediates",
}

# Known TOML sections
_KNOWN_SECTIONS = {section for section, _ in _TOML_KEY_MAP}

# Known keys per section
_KNOWN_KEYS: dict[str, set[str]] = {}
for _sec, _key in _TOML_KEY_MAP:
    _KNOWN_KEYS.setdefault(_sec, set()).add(_key)

# Valid style and format names (kept in sync with styles.py / formats.py)
_VALID_STYLES = {"kawaii", "minimal", "3d", "pixel-art", "retro", "watercolor"}
_VALID_FORMATS = {"png", "webp", "webp-lossy"}


def _parse_resize_value(
    value: int | str | list[Any],
) -> tuple[int, int]:
    """Parse a resize value from TOML into (width, height).

    Accepts:
        - int: square size (e.g. 512 -> (512, 512))
        - str: "WIDTHxHEIGHT" or "SIZE" (e.g. "512x256" or "512")
        - list: [WIDTH, HEIGHT] (e.g. [512, 256])

    Raises:
        ConfigError: If the value cannot be parsed.
    """
    if isinstance(value, int):
        if value <= 0:
            raise ConfigError(f"Resize dimensions must be positive, got {value}")
        return (value, value)

    if isinstance(value, list):
        if len(value) != 2:
            raise ConfigError(
                f"Resize array must have exactly 2 elements, got {len(value)}"
            )
        try:
            w, h = int(value[0]), int(value[1])
        except (ValueError, TypeError):
            raise ConfigError(
                f"Resize array elements must be integers, got {value}"
            ) from None
        if w <= 0 or h <= 0:
            raise ConfigError(f"Resize dimensions must be positive, got [{w}, {h}]")
        return (w, h)

    if isinstance(value, str):
        value = value.strip()
        if "x" in value.lower():
            parts = value.lower().split("x")
            if len(parts) != 2:
                raise ConfigError(f"Invalid resize format: {value!r}")
            try:
                w, h = int(parts[0].strip()), int(parts[1].strip())
            except ValueError:
                raise ConfigError(f"Invalid resize format: {value!r}") from None
        else:
            try:
                w = h = int(value)
            except ValueError:
                raise ConfigError(f"Invalid resize format: {value!r}") from None
        if w <= 0 or h <= 0:
            raise ConfigError(f"Resize dimensions must be positive, got {value!r}")
        return (w, h)

    raise ConfigError(f"Invalid resize value type: {type(value).__name__}")


def _validate_config(config: StickerConfig) -> None:
    """Validate config values, raising ConfigError for invalid ones."""
    if config.quality is not None and not (1 <= config.quality <= 100):
        raise ConfigError(f"quality must be between 1 and 100, got {config.quality}")

    if config.max_retries is not None and config.max_retries < 0:
        raise ConfigError(f"max_retries must be non-negative, got {config.max_retries}")

    if config.max_workers is not None and config.max_workers < 1:
        raise ConfigError(f"max_workers must be at least 1, got {config.max_workers}")

    if config.edge_threshold is not None and not (0 <= config.edge_threshold <= 255):
        raise ConfigError(
            f"edge_threshold must be between 0 and 255, got {config.edge_threshold}"
        )

    if config.style is not None and config.style not in _VALID_STYLES:
        raise ConfigError(
            f"Unknown style {config.style!r}. "
            f"Available: {', '.join(sorted(_VALID_STYLES))}"
        )

    if config.output_format is not None and config.output_format not in _VALID_FORMATS:
        raise ConfigError(
            f"Unknown output_format {config.output_format!r}. "
            f"Available: {', '.join(sorted(_VALID_FORMATS))}"
        )


def get_config_paths() -> list[Path]:
    """Return config file lookup paths, lowest-to-highest priority.

    Returns:
        [home_config_path, cwd_config_path]
    """
    home = Path.home() / ".config" / "sticker-generator" / "config.toml"
    cwd = Path.cwd() / ".sticker-generator.toml"
    return [home, cwd]


def find_config_files() -> list[Path]:
    """Return existing config files in priority order (lowest first)."""
    return [p for p in get_config_paths() if p.exists()]


def load_config_file(path: Path) -> StickerConfig:
    """Parse a single TOML config file into a StickerConfig.

    Args:
        path: Path to the TOML file.

    Returns:
        StickerConfig with values from the file.

    Raises:
        ConfigError: If the file contains invalid TOML or invalid values.
    """
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"Invalid TOML in {path}: {e}") from e

    config = StickerConfig()

    for section_name, section_data in data.items():
        if not isinstance(section_data, dict):
            warnings.warn(
                f"Config: ignoring top-level key {section_name!r} "
                f"(expected a [section])",
                stacklevel=2,
            )
            continue

        if section_name not in _KNOWN_SECTIONS:
            warnings.warn(
                f"Config: unknown section [{section_name}] in {path}",
                stacklevel=2,
            )
            continue

        for key, value in section_data.items():
            field_name = _TOML_KEY_MAP.get((section_name, key))
            if field_name is None:
                warnings.warn(
                    f"Config: unknown key {key!r} in [{section_name}] in {path}",
                    stacklevel=2,
                )
                continue

            # Special handling for resize
            if field_name == "resize":
                value = _parse_resize_value(value)

            setattr(config, field_name, value)

    _validate_config(config)
    return config


def merge_configs(base: StickerConfig, override: StickerConfig) -> StickerConfig:
    """Merge two configs: non-None values in override win.

    Args:
        base: Lower-priority config.
        override: Higher-priority config.

    Returns:
        New StickerConfig with merged values.
    """
    merged = StickerConfig()
    for f in fields(StickerConfig):
        override_val = getattr(override, f.name)
        base_val = getattr(base, f.name)
        setattr(merged, f.name, override_val if override_val is not None else base_val)
    return merged


def load_config() -> StickerConfig:
    """Discover, load, and merge all config files.

    Priority order: CWD config overrides home config.

    Returns:
        Merged StickerConfig from all found config files.
    """
    config_files = find_config_files()
    if not config_files:
        return StickerConfig()

    result = StickerConfig()
    for path in config_files:
        file_config = load_config_file(path)
        result = merge_configs(result, file_config)

    return result


_CONFIG_TEMPLATE = """\
# sticker-generator configuration
# CLI flags override these values. CWD file overrides global.

[api]
# api_key = "your-gemini-api-key"

[style]
# preset = "kawaii"          # kawaii, minimal, 3d, pixel-art, retro, watercolor
# output_format = "png"     # png, webp, webp-lossy
# quality = 90              # 1-100, for lossy formats
# lossless = true

[green_removal]
# hue_center = 115
# hue_range = 35
# min_saturation = 25
# min_value = 40
# green_threshold = 1.1

[processing]
# edge_threshold = 64
# resize = "512x512"        # WIDTHxHEIGHT, SIZE, or [W, H]
# resize_exact = false

[retry]
# max_retries = 3
# retry_delay = 1.0

[batch]
# delay = 1.0
# max_workers = 1
# strict = false

[sheet]
# variations = 4
# columns = 2
# padding = 10

[output]
# aspect_ratio = "1:1"
# save_raw = false
"""


def generate_config_template() -> str:
    """Return the commented-out TOML config template."""
    return _CONFIG_TEMPLATE


# Section display order and field-to-section mapping for display
_DISPLAY_SECTIONS: list[tuple[str, list[tuple[str, str]]]] = [
    ("api", [("api_key", "api_key")]),
    (
        "style",
        [
            ("preset", "style"),
            ("output_format", "output_format"),
            ("quality", "quality"),
            ("lossless", "lossless"),
        ],
    ),
    (
        "green_removal",
        [
            ("hue_center", "hue_center"),
            ("hue_range", "hue_range"),
            ("min_saturation", "min_saturation"),
            ("min_value", "min_value"),
            ("green_threshold", "green_threshold"),
        ],
    ),
    (
        "processing",
        [
            ("edge_threshold", "edge_threshold"),
            ("resize", "resize"),
            ("resize_exact", "resize_exact"),
        ],
    ),
    (
        "retry",
        [
            ("max_retries", "max_retries"),
            ("retry_delay", "retry_delay"),
        ],
    ),
    (
        "batch",
        [
            ("delay", "delay"),
            ("max_workers", "max_workers"),
            ("strict", "strict"),
        ],
    ),
    (
        "sheet",
        [
            ("variations", "variations"),
            ("columns", "columns"),
            ("padding", "padding"),
        ],
    ),
    (
        "output",
        [
            ("aspect_ratio", "aspect_ratio"),
            ("save_raw", "save_raw"),
            ("save_intermediates", "save_intermediates"),
        ],
    ),
]


def format_config_for_display(config: StickerConfig) -> str:
    """Format resolved config values for display.

    Masks the api_key if present.

    Returns:
        Human-readable string showing set config values.
    """
    sections: list[str] = []

    for section_name, keys in _DISPLAY_SECTIONS:
        lines: list[str] = []
        for toml_key, field_name in keys:
            value = getattr(config, field_name)
            if value is not None:
                display_value = value
                if field_name == "api_key":
                    display_value = value[:4] + "****" if len(value) > 4 else "****"
                lines.append(f"  {toml_key} = {display_value!r}")
        if lines:
            sections.append(f"[{section_name}]\n" + "\n".join(lines))

    if not sections:
        return "No configuration values set."

    return "\n\n".join(sections)


def format_config_paths() -> str:
    """Show lookup paths with found/not-found markers.

    Returns:
        Human-readable string showing config file paths and their status.
    """
    lines: list[str] = []
    for path in get_config_paths():
        marker = "FOUND" if path.exists() else "not found"
        lines.append(f"  [{marker}] {path}")
    return "Config file paths (lowest to highest priority):\n" + "\n".join(lines)
