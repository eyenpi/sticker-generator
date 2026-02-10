# Sticker Generator

Generate stickers with transparent backgrounds using Google's Gemini AI.

## Examples

| Kawaii | 3D | Pixel Art | Watercolor | Minimal |
|:------:|:--:|:---------:|:----------:|:-------:|
| ![Kawaii Cat](https://raw.githubusercontent.com/eyenpi/sticker-generator/main/examples/cat_kawaii.png) | ![3D Rocket](https://raw.githubusercontent.com/eyenpi/sticker-generator/main/examples/rocket_3d.png) | ![Pixel Robot](https://raw.githubusercontent.com/eyenpi/sticker-generator/main/examples/robot_pixel.png) | ![Watercolor Rose](https://raw.githubusercontent.com/eyenpi/sticker-generator/main/examples/rose_watercolor.png) | ![Minimal Coffee](https://raw.githubusercontent.com/eyenpi/sticker-generator/main/examples/coffee_minimal.png) |
| *"a cute happy cat"* | *"a sleek rocket ship"* | *"a friendly robot"* | *"a beautiful rose"* | *"a coffee cup"* |

## Installation

```bash
pip install sticker-generator
```

## Setup

Set your Gemini API key as an environment variable:

```bash
export GEMINI_API_KEY="your-api-key"
```

Or pass it directly to the functions/CLI.

## Usage

### Command Line

```bash
# Basic usage
sticker-generator "a cute happy cat with big eyes"

# Specify output file
sticker-generator "a rocket ship" -o rocket.png

# Use reference images
sticker-generator "similar style illustration" -i reference1.png -i reference2.png

# Custom aspect ratio
sticker-generator "a wide banner" --aspect-ratio 16:9

# Use a style preset
sticker-generator "a happy robot" --style kawaii
sticker-generator "a space astronaut" -s 3d -o astronaut.png

# Save raw image before processing
sticker-generator "a dog" --save-raw

# Generate multiple variations as a sheet
sticker-generator "happy cat" -n 4 --sheet -o cat_sheet.png

# Generate variations as individual files
sticker-generator "cute dog" -n 6 -o dog.png
# Creates: dog_1.png, dog_2.png, ..., dog_6.png

# Sheet with custom grid (3 columns)
sticker-generator "star" -n 9 --sheet --columns 3 -o stars.png

# Sheet + individual files
sticker-generator "robot" -n 4 --sheet --save-individuals -o robots.png

# Resize output to specific dimensions
sticker-generator "cute cat" --resize 512          # 512x512 square
sticker-generator "cute cat" --resize 512x256      # Fit within 512x256, maintain aspect ratio
sticker-generator "cute cat" --resize 512x256 --resize-exact  # Force exact dimensions (may distort)

# Output formats (PNG default, WebP supported)
sticker-generator "cute cat" -o cat.webp                    # Auto-detect from extension
sticker-generator "cute cat" -o cat.webp --lossy -q 85      # Lossy WebP with quality
sticker-generator "cute cat" -f webp-lossy -q 90            # Explicit format preset
sticker-generator "cute cat" -n 4 --sheet -o sheet.webp     # Sheet in WebP format

# Process an existing green-screen image (no API key needed)
sticker-generator --process photo_with_green_bg.png -o transparent.png
sticker-generator --process input.png -o out.webp --resize 512

# Strict mode: exit with error if quality validation fails
sticker-generator "a cat" --strict

# Tune green removal for tricky images
sticker-generator "a cat" --hue-center 120 --hue-range 40 --min-saturation 30

# Retry options for unreliable connections
sticker-generator "a cat" --max-retries 5 --retry-delay 2.0
sticker-generator "a cat" --max-retries 0  # Disable retries

# Verbose mode (shows processing details on stderr)
sticker-generator "a cat" -o cat.png --verbose

# Debug mode (verbose + auto-saves intermediate images)
sticker-generator "a cat" -o cat.png --debug
ls cat_intermediates/  # 01_raw_from_api.png, 02_after_hsv_removal.png, ...

# Quiet mode (only warnings and errors)
sticker-generator "a cat" -o cat.png --quiet

# Save intermediate images to a custom directory
sticker-generator "a cat" -o cat.png --save-intermediates /tmp/debug/

# Save intermediates with auto-generated directory name
sticker-generator "a cat" -o cat.png --save-intermediates

# Batch generate from a prompts file (one prompt per line, # for comments)
sticker-generator --batch-prompts prompts.txt --output-dir ./stickers/

# Batch generate with style and format options
sticker-generator --batch-prompts prompts.txt --output-dir ./stickers/ -s kawaii -f webp

# Batch process all images in a directory (remove green backgrounds)
sticker-generator --batch-dir ./green-screen-photos/ --output-dir ./processed/

# Batch with strict mode (stop on first failure)
sticker-generator --batch-prompts prompts.txt --output-dir ./stickers/ --strict

# Control delay between API requests in batch mode
sticker-generator --batch-prompts prompts.txt --output-dir ./stickers/ --delay 2.0

# Concurrent batch generation (4 workers)
sticker-generator --batch-prompts prompts.txt --output-dir ./stickers/ --max-workers 4

# Concurrent sheet generation
sticker-generator "happy cat" -n 8 --sheet -o cats.png --max-workers 4
```

#### Available Styles

| Style | Description |
|-------|-------------|
| `kawaii` | Cute Japanese style with big eyes and pastel colors |
| `minimal` | Clean minimalist style with flat colors |
| `3d` | 3D rendered look with depth and lighting |
| `pixel-art` | Retro pixel art style |
| `retro` | Vintage retro style with muted colors |
| `watercolor` | Soft watercolor painting style |

#### Output Formats

| Format | Description |
|--------|-------------|
| `png` | Lossless PNG (default) |
| `webp` | Lossless WebP (smaller files) |
| `webp-lossy` | Lossy WebP with quality setting (smallest files) |

Format options:
- `-f, --format FORMAT` - Explicit format preset (auto-detects from extension if omitted)
- `-q, --quality 1-100` - Quality for lossy formats (higher is better)
- `--lossless` - Force lossless compression
- `--lossy` - Force lossy compression

#### Concurrent Execution

Speed up batch and sheet generation by processing multiple stickers in parallel:

| Flag | Default | Description |
|------|---------|-------------|
| `--max-workers` | 1 | Max concurrent workers (1 = sequential) |

When `max_workers > 1`, `--delay` is ignored (concurrency controls rate limiting instead). Strict mode (`--strict`) forces sequential execution for deterministic error handling.

#### Progress Bars

Batch and sheet operations show tqdm progress bars by default:

| Flag | Description |
|------|-------------|
| `--no-progress` | Disable progress bars |
| `--quiet` | Also disables progress bars (along with non-warning log output) |

Progress bars work with concurrent mode (`--max-workers`).

#### Green Removal Tuning

If green removal produces bad results (incomplete removal or subject removal), tune these parameters:

| Flag | Default | Description |
|------|---------|-------------|
| `--hue-center` | 115 | Center hue for green detection (degrees) |
| `--hue-range` | 35 | Tolerance around hue center (degrees) |
| `--min-saturation` | 25 | Minimum saturation % to consider green |
| `--min-value` | 40 | Minimum brightness % to consider green |
| `--green-threshold` | 1.1 | Aggressive green ratio threshold (higher = more conservative) |

#### Retry Options

Failed API calls are automatically retried with exponential backoff. This handles transient HTTP errors (429 rate limits, 500/502/503/504 server errors) and cases where the API returns no image.

| Flag | Default | Description |
|------|---------|-------------|
| `--max-retries` | 3 | Maximum number of retries for failed API calls |
| `--retry-delay` | 1.0 | Initial delay between retries in seconds (doubles each retry) |

#### Quality Validation

After processing, the tool automatically checks the transparency ratio and warns about potential issues:
- **>95% transparent**: The subject may have been removed along with the background
- **<5% transparent**: Green background removal may have failed

Use `--strict` to make these warnings exit with a non-zero status code (useful in scripts/CI).

#### Verbosity & Debug Mode

| Flag | Level | What you see |
|------|-------|-------------|
| *(default)* | INFO | Progress messages, completion, quality warnings |
| `-v, --verbose` | DEBUG | Above + processing params, pixel stats, API details |
| `--debug` | DEBUG | Same as verbose, plus auto-saves intermediate images |
| `--quiet` | WARNING | Only warnings and errors |

#### Troubleshooting

If green removal produces unexpected results, use `--debug` to inspect each processing stage:

```bash
sticker-generator "a tree frog" -o frog.png --debug
ls frog_intermediates/
# 01_raw_from_api.png        - Raw image from Gemini
# 02_after_hsv_removal.png   - After HSV-based green removal
# 03_after_aggressive_removal.png - After aggressive green pass
# 04_after_edge_cleanup.png  - After edge cleanup
```

You can also save intermediates without debug verbosity:
```bash
sticker-generator "a frog" -o frog.png --save-intermediates /tmp/debug/
```

### Python API

```python
from sticker_generator import create_sticker, get_available_styles, get_available_formats

# Basic usage
sticker = create_sticker(
    prompt="a cute happy cat with big eyes",
    output="cat.png"
)

# With a style preset
sticker = create_sticker(
    prompt="a happy robot",
    output="robot.png",
    style="kawaii"
)

# List available styles
print(get_available_styles())
# ['3d', 'kawaii', 'minimal', 'pixel-art', 'retro', 'watercolor']

# List available formats
print(get_available_formats())
# ['png', 'webp', 'webp-lossy']

# Save as WebP (auto-detected from extension)
sticker = create_sticker(
    prompt="a rocket ship",
    output="rocket.webp"
)

# Lossy WebP with custom quality
sticker = create_sticker(
    prompt="a star",
    output="star.webp",
    output_format="webp-lossy",
    quality=85
)

# With reference images
sticker = create_sticker(
    prompt="similar style illustration",
    output="custom.png",
    input_images=["reference1.png", "reference2.png"]
)

# Just get the image without saving
sticker = create_sticker(
    prompt="a rocket ship",
    output=None  # Returns PIL Image
)

# Resize output
sticker = create_sticker(
    prompt="a cute cat",
    output="cat_small.png",
    resize=(256, 256)  # Fit within 256x256, maintain aspect ratio
)

# Force exact dimensions (may distort)
sticker = create_sticker(
    prompt="a cute cat",
    output="cat_exact.png",
    resize=(512, 256),
    resize_exact=True
)

# Custom green removal parameters for tricky images
sticker = create_sticker(
    prompt="a tree frog",
    output="frog.png",
    hue_center=120,
    hue_range=40,
    min_saturation=30,
    min_value=50,
    green_threshold=1.3
)

# Custom retry settings
sticker = create_sticker(
    prompt="a cute cat",
    output="cat.png",
    max_retries=5,     # More retries for unreliable connections
    retry_delay=2.0    # Start with 2s delay, doubles each retry
)

# Save intermediate images for debugging
sticker = create_sticker(
    prompt="a tree frog",
    output="frog.png",
    save_intermediates="frog_debug/"  # Saves each pipeline stage as PNG
)
```

### Batch Processing

Generate multiple stickers from a prompts file or process a directory of images:

```python
from sticker_generator import batch_generate, batch_process_images, parse_prompt_file

# Generate stickers from a list of prompts
result = batch_generate(
    prompts=["a cute cat", "a happy dog", "a friendly robot"],
    output_dir="./stickers/",
    style="kawaii",
    max_workers=4,  # Generate 4 stickers concurrently
)
print(f"Generated {len(result.successful)}/{result.total} stickers")
for item in result.failed:
    print(f"  Failed: {item.source} - {item.error}")

# Read prompts from a file
prompts = parse_prompt_file("prompts.txt")
result = batch_generate(prompts=prompts, output_dir="./stickers/")

# Process all images in a directory (remove green backgrounds)
result = batch_process_images(
    input_dir="./green-screen-photos/",
    output_dir="./processed/",
    output_format="webp",
)
print(f"Processed {len(result.successful)}/{result.total} images")

# Strict mode: stop on first failure
result = batch_generate(
    prompts=["a cat", "a dog"],
    output_dir="./stickers/",
    strict=True,
)
```

### Process Existing Images

Remove green backgrounds from existing images without using the Gemini API:

```python
from sticker_generator import process_image

# Basic usage - remove green background from an existing image
result = process_image("green_screen_photo.png", output="transparent.png")

# With resize and format options
result = process_image(
    "input.png",
    output="output.webp",
    resize=(512, 512),
    output_format="webp-lossy",
    quality=90
)

# Just get the PIL Image without saving
image = process_image("input.png")
```

CLI equivalent:
```bash
sticker-generator --process green_screen_photo.png -o transparent.png
sticker-generator --process input.png -o output.webp --resize 512 -f webp-lossy -q 90
```

### Quality Validation

Check the quality of processed images programmatically:

```python
from sticker_generator import validate_transparency, create_sticker

sticker = create_sticker("a cute cat", output="cat.png")

# Inspect transparency metrics
metrics = validate_transparency(sticker)
print(f"Transparent: {metrics.transparent_ratio:.0%}")
print(f"Opaque: {metrics.opaque_ratio:.0%}")
print(f"Semi-transparent: {metrics.semi_transparent_pixels} pixels")

if metrics.has_quality_warning:
    print(f"Warning: {metrics.warning_message}")
```

### Sticker Sheets

Generate multiple variations and combine into a grid:

```python
from sticker_generator import generate_sticker_sheet

# Generate 4 variations as a sheet
result = generate_sticker_sheet(
    prompt="happy cat",
    variations=4,
    output="cat_sheet.png",
    max_workers=4,  # Generate 4 variations concurrently
)

# Access individual stickers
for i, sticker in enumerate(result.stickers):
    sticker.save(f"cat_{i}.png")

# Check for failures
if result.failed_indices:
    print(f"Failed variations: {result.failed_indices}")

# Custom grid layout
result = generate_sticker_sheet(
    prompt="star",
    variations=6,
    output="stars.png",
    columns=3,      # 3x2 grid
    padding=20      # 20px between stickers
)

# Sheet in WebP format with lossy compression
result = generate_sticker_sheet(
    prompt="robot",
    variations=4,
    output="robots.webp",
    output_format="webp-lossy",
    quality=90,
    save_individuals=True  # Individual files also saved as .webp
)
```

### Image Processing Only

If you have your own green-screen images and want fine-grained control:

```python
from PIL import Image
from sticker_generator import remove_green_screen_hsv, cleanup_edges, resize_image, save_transparent_image

# Load your image
img = Image.open("green_background.png")

# Remove green background
transparent = remove_green_screen_hsv(img)

# Clean up edges
clean = cleanup_edges(transparent, threshold=64)

# Optional: resize the result
resized = resize_image(clean, (256, 256))  # Fit within bounds, maintain aspect ratio
resized = resize_image(clean, (256, 256), maintain_aspect=False)  # Force exact size

# Save as PNG
resized.save("transparent.png")

# Save as WebP with format options
save_transparent_image(resized, "transparent.webp")  # Lossless WebP
save_transparent_image(resized, "transparent.webp", "webp-lossy")  # Lossy WebP
```

## How It Works

1. **Style Application**: Optional style presets modify your prompt to achieve specific visual styles
2. **Generation**: Uses Gemini AI to generate an image with a chromakey green (#00FF00) background
3. **Green Removal**: Converts to HSV color space and removes pixels matching green hue (configurable thresholds)
4. **Aggressive Green Pass**: Catches darker greens and tinted shadows using green channel dominance ratio
5. **Edge Cleanup**: Removes semi-transparent edge artifacts for clean results
6. **Resize** (optional): Resizes output to specified dimensions using LANCZOS resampling
7. **Quality Validation**: Checks transparency ratio and warns about potential issues

## License

MIT
