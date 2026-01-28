# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build and Development Commands

```bash
# Install dependencies (uses uv)
uv sync

# Run tests
uv run pytest

# Run single test
uv run pytest tests/test_image_processing.py::TestRemoveGreenScreenHsv::test_removes_green_background

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
2. **Green Removal** (`image_processing.py`): HSV-based detection removes green pixels, with optional aggressive pass for stubborn greens
3. **Edge Cleanup** (`image_processing.py`): Thresholds alpha channel to remove semi-transparent halos
4. **Resize** (`image_processing.py`): Optional resizing with LANCZOS resampling, aspect ratio preservation

Key modules:
- `core.py`: Gemini API interaction, prompt engineering, main `create_sticker()` function
- `image_processing.py`: Pure image processing (no API calls), HSV conversion, green removal, edge cleanup, resize
- `styles.py`: Style presets that modify prompts (kawaii, minimal, 3d, pixel-art, retro, watercolor)
- `sheet.py`: Sticker sheet generation - multiple variations combined into a grid
- `cli.py`: Command-line interface wrapping `create_sticker()` and `generate_sticker_sheet()`

## CI/CD

- **CI** (`.github/workflows/ci.yml`): Runs on PRs/pushes - lint, test (Python 3.10-3.13), build
- **Publish** (`.github/workflows/publish.yml`): Triggered by GitHub releases - publishes to TestPyPI then PyPI using trusted publishing

## Environment

Requires `GEMINI_API_KEY` environment variable or pass `api_key` parameter to functions.
