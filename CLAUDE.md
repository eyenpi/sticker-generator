# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build and Development Commands

```bash
# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Run single test
pytest tests/test_image_processing.py::TestRemoveGreenScreenHsv::test_removes_green_background

# Lint and format
ruff check src tests
ruff format src tests

# Type check
mypy src

# Build package
python -m build
```

## Architecture

This package generates stickers with transparent backgrounds using Google's Gemini AI. The workflow:

1. **Generation** (`core.py`): Sends prompt to Gemini with instructions to use chromakey green (#00FF00) background
2. **Green Removal** (`image_processing.py`): HSV-based detection removes green pixels, with optional aggressive pass for stubborn greens
3. **Edge Cleanup** (`image_processing.py`): Thresholds alpha channel to remove semi-transparent halos

Key modules:
- `core.py`: Gemini API interaction, prompt engineering, main `create_sticker()` function
- `image_processing.py`: Pure image processing (no API calls), HSV conversion, green removal, edge cleanup
- `styles.py`: Style presets that modify prompts (kawaii, minimal, 3d, pixel-art, retro, watercolor)
- `cli.py`: Command-line interface wrapping `create_sticker()`

## CI/CD

- **CI** (`.github/workflows/ci.yml`): Runs on PRs/pushes - lint, test (Python 3.10-3.13), build
- **Publish** (`.github/workflows/publish.yml`): Triggered by GitHub releases - publishes to TestPyPI then PyPI using trusted publishing

## Environment

Requires `GEMINI_API_KEY` environment variable or pass `api_key` parameter to functions.
