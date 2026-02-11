# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build and Development Commands

```bash
# Install dependencies (uses uv)
uv sync

# Install with dev dependencies
uv sync --extra dev

# Run tests (must use python -m to pick up the correct venv)
uv run python -m pytest

# Run single test
uv run python -m pytest tests/test_image_processing.py::TestRemoveGreenScreenHsv::test_removes_green_background

# Lint and format
uv run ruff check src tests
uv run ruff format src tests

# Type check
uv run mypy src

# Build package
uv build
```

## Architecture

This package generates stickers with transparent backgrounds using Google's Gemini AI. The workflow:

1. **Generation** (`core.py`): Sends prompt to Gemini with instructions to use chromakey green (#00FF00) background
2. **Green Removal** (`image_processing.py`): HSV-based detection removes green pixels, with optional aggressive pass for stubborn greens. Parameters (hue_center, hue_range, min_saturation, min_value, green_threshold) are configurable.
3. **Edge Cleanup** (`image_processing.py`): Thresholds alpha channel to remove semi-transparent halos
4. **Resize** (`image_processing.py`): Optional resizing with LANCZOS resampling, aspect ratio preservation
5. **Quality Validation** (`image_processing.py`): `validate_transparency()` computes `TransparencyMetrics` to detect bad results (>95% transparent = subject removed, <5% transparent = green removal failed)

Key modules:
- `core.py`: Gemini API interaction, prompt engineering, `create_sticker()` and `process_image()` functions. Retry logic uses google-genai's built-in `HttpRetryOptions` for HTTP errors plus application-level retry loop for empty responses
- `image_processing.py`: Pure image processing (no API calls), HSV conversion, green removal, edge cleanup, resize, `validate_transparency()`, `TransparencyMetrics` dataclass, `save_transparent_image()`
- `formats.py`: Output format configuration (`OutputFormat` dataclass, presets for png/webp/webp-lossy)
- `styles.py`: Style presets that modify prompts (kawaii, minimal, 3d, pixel-art, retro, watercolor)
- `batch.py`: Batch processing - generate from prompt files or process image directories. `BatchItem`/`BatchResult` dataclasses, `parse_prompt_file()`, `batch_generate()`, `batch_process_images()`. Supports concurrent execution via `max_workers` parameter using `ThreadPoolExecutor`. `progress_callback` parameter for progress reporting
- `sheet.py`: Sticker sheet generation - multiple variations combined into a grid. Supports concurrent execution via `max_workers` parameter using `ThreadPoolExecutor`. `progress_callback` parameter for progress reporting
- `config.py`: TOML configuration file support. `StickerConfig` dataclass, `load_config()` discovers and merges config files (priority: CLI > CWD `.sticker-generator.toml` > `~/.config/sticker-generator/config.toml` > hardcoded defaults). `ConfigError` exception, `generate_config_template()`, validation, display formatting
- `cli.py`: Command-line interface wrapping `create_sticker()`, `process_image()`, `generate_sticker_sheet()`, and batch functions. Configures the `sticker_generator` root logger with `StreamHandler(sys.stderr)` based on verbosity flags. `config` subcommand (`init`, `show`, `path`) for managing config files. `--no-config` flag to skip config file loading

Logging hierarchy: Each module uses `logging.getLogger(__name__)`. `__init__.py` adds `NullHandler` (silent as library). CLI's `_setup_logging()` configures the `sticker_generator` root logger with a `StreamHandler(sys.stderr)`.

## Key Features

- **Process existing images**: `process_image()` / `--process` CLI flag removes green backgrounds from existing images without Gemini generation
- **Configurable green removal**: HSV thresholds and aggressive green detection ratio are tunable via `create_sticker()` parameters and CLI flags (`--hue-center`, `--hue-range`, `--min-saturation`, `--min-value`, `--green-threshold`)
- **Quality validation**: Automatic transparency analysis after processing; warns on bad results. `--strict` CLI flag exits non-zero on quality warnings
- **Retry with exponential backoff**: Two-layer retry protection for API calls. HTTP-level retries via google-genai's `HttpRetryOptions` handle transient errors (429, 500, 502, 503, 504). Application-level retries handle cases where the API returns no image. Configurable via `max_retries`/`retry_delay` params or `--max-retries`/`--retry-delay` CLI flags
- **Structured logging**: All output via Python's `logging` module. CLI verbosity flags: `-v/--verbose` (DEBUG), `--debug` (DEBUG + save intermediates), `--quiet` (WARNING only). All log output goes to stderr
- **Batch processing**: `batch_generate()` processes a list of prompts, `batch_process_images()` processes all images in a directory. CLI flags: `--batch-prompts FILE`, `--batch-dir DIR`, `--output-dir DIR`. Continue-on-error by default, `--strict` stops on first failure. Rate limiting via `--delay`
- **Concurrent execution**: `max_workers` parameter on `batch_generate()`, `batch_process_images()`, and `generate_sticker_sheet()` enables parallel processing via `ThreadPoolExecutor`. Default `max_workers=1` preserves sequential behavior. CLI flag: `--max-workers`. Strict mode forces sequential execution when `max_workers > 1`
- **Progress bars**: tqdm progress bars for batch and sheet operations. CLI shows them by default; `--no-progress` or `--quiet` disables. Library API uses callback-based `progress_callback` parameter (tqdm-agnostic). `logging_redirect_tqdm()` prevents log/progress bar conflicts
- **Save intermediates**: `--save-intermediates [DIR]` or `save_intermediates` parameter saves PNGs after each pipeline stage for debugging. `--debug` auto-enables this
- **TOML configuration**: `StickerConfig` loaded from `~/.config/sticker-generator/config.toml` (global) and `.sticker-generator.toml` (CWD). CLI flags override config values. `config init [--global]` creates template, `config show` displays resolved values, `config path` shows lookup paths. `--no-config` skips loading. Requires `tomli` on Python < 3.11

## Output Formats

Supported formats (via `formats.py`):
- `png` - Lossless PNG (default)
- `webp` - Lossless WebP
- `webp-lossy` - Lossy WebP (quality=90 default)

Format is auto-detected from file extension, or can be explicitly specified via `output_format` parameter or `-f` CLI flag. The `save_transparent_image()` function handles all format-specific save parameters.

## CI/CD

- **CI** (`.github/workflows/ci.yml`): Runs on PRs/pushes - lint, test (Python 3.10-3.13), build
- **Publish** (`.github/workflows/publish.yml`): Triggered by GitHub releases - publishes to TestPyPI then PyPI using trusted publishing

## Environment

Requires `GEMINI_API_KEY` environment variable or pass `api_key` parameter to functions.
