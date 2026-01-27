# Sticker Generator

Generate stickers with transparent backgrounds using Google's Gemini AI.

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
```

### Python API

```python
from sticker_generator import create_sticker

# Basic usage
sticker = create_sticker(
    prompt="a cute happy cat with big eyes",
    output="cat.png"
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
```

### Image Processing Only

If you have your own green-screen images:

```python
from PIL import Image
from sticker_generator import remove_green_screen_hsv, cleanup_edges

# Load your image
img = Image.open("green_background.png")

# Remove green background
transparent = remove_green_screen_hsv(img)

# Clean up edges
clean = cleanup_edges(transparent, threshold=64)

# Save
clean.save("transparent.png")
```

## How It Works

1. **Generation**: Uses Gemini AI to generate an image with a chromakey green (#00FF00) background
2. **Green Removal**: Converts to HSV color space and removes pixels matching green hue
3. **Edge Cleanup**: Removes semi-transparent edge artifacts for clean results

## License

MIT
