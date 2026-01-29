# Sticker Generator

Generate stickers with transparent backgrounds using Google's Gemini AI.

## Examples

| Kawaii | 3D | Pixel Art | Watercolor | Minimal |
|:------:|:--:|:---------:|:----------:|:-------:|
| ![Kawaii Cat](examples/cat_kawaii.png) | ![3D Rocket](examples/rocket_3d.png) | ![Pixel Robot](examples/robot_pixel.png) | ![Watercolor Rose](examples/rose_watercolor.png) | ![Minimal Coffee](examples/coffee_minimal.png) |
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
```

### Sticker Sheets

Generate multiple variations and combine into a grid:

```python
from sticker_generator import generate_sticker_sheet

# Generate 4 variations as a sheet
result = generate_sticker_sheet(
    prompt="happy cat",
    variations=4,
    output="cat_sheet.png"
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

If you have your own green-screen images:

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
3. **Green Removal**: Converts to HSV color space and removes pixels matching green hue
4. **Edge Cleanup**: Removes semi-transparent edge artifacts for clean results
5. **Resize** (optional): Resizes output to specified dimensions using LANCZOS resampling

## License

MIT
