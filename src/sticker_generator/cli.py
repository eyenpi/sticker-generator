"""Command-line interface for sticker generation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sticker_generator.core import create_sticker
from sticker_generator.sheet import generate_sticker_sheet


def main() -> int:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        prog="sticker-generator",
        description="Generate stickers with transparent backgrounds using Gemini AI",
    )
    parser.add_argument(
        "prompt",
        help="Description of the sticker to generate",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="sticker.png",
        help="Output filename (default: sticker.png)",
    )
    parser.add_argument(
        "-i",
        "--image",
        action="append",
        dest="images",
        help="Reference image path (can be specified multiple times)",
    )
    parser.add_argument(
        "--aspect-ratio",
        default="1:1",
        help="Image aspect ratio (default: 1:1)",
    )
    parser.add_argument(
        "--save-raw",
        action="store_true",
        help="Save the raw image before green screen removal",
    )
    parser.add_argument(
        "--edge-threshold",
        type=int,
        default=64,
        help="Alpha threshold for edge cleanup, 0-255 (default: 64)",
    )
    parser.add_argument(
        "--api-key",
        help="Gemini API key (or set GEMINI_API_KEY environment variable)",
    )
    parser.add_argument(
        "-n",
        "--variations",
        type=int,
        default=1,
        help="Number of sticker variations to generate (default: 1)",
    )
    parser.add_argument(
        "--sheet",
        action="store_true",
        help="Combine variations into a single sheet image",
    )
    parser.add_argument(
        "--save-individuals",
        action="store_true",
        help="Save individual stickers when generating a sheet",
    )
    parser.add_argument(
        "--columns",
        type=int,
        default=None,
        help="Number of columns in sheet grid (auto-calculated if not specified)",
    )
    parser.add_argument(
        "--padding",
        type=int,
        default=10,
        help="Padding between stickers in sheet (default: 10 pixels)",
    )

    args = parser.parse_args()

    # Validate reference images exist
    if args.images:
        for img_path in args.images:
            if not Path(img_path).exists():
                print(f"Error: Reference image not found: {img_path}", file=sys.stderr)
                return 1

    try:
        print(f"Generating sticker: {args.prompt}")
        if args.images:
            print(f"Using {len(args.images)} reference image(s)")

        if args.variations > 1:
            print(f"Generating {args.variations} variations...")
            result = generate_sticker_sheet(
                prompt=args.prompt,
                variations=args.variations,
                output=args.output if args.sheet else None,
                save_individuals=args.save_individuals or not args.sheet,
                individual_prefix=Path(args.output).stem if not args.sheet else None,
                aspect_ratio=args.aspect_ratio,
                input_images=args.images,
                api_key=args.api_key,
                edge_threshold=args.edge_threshold,
                columns=args.columns,
                padding=args.padding,
            )

            if result.failed_indices:
                print(f"Warning: {len(result.failed_indices)} variation(s) failed")

            if args.sheet:
                print(f"Sheet saved to: {args.output}")
                if args.save_individuals:
                    prefix = Path(args.output).stem
                    print(f"Individual stickers saved with prefix: {prefix}")
            else:
                print(f"Stickers saved with prefix: {Path(args.output).stem}")
        else:
            create_sticker(
                prompt=args.prompt,
                output=args.output,
                aspect_ratio=args.aspect_ratio,
                save_raw=args.save_raw,
                input_images=args.images,
                api_key=args.api_key,
                edge_threshold=args.edge_threshold,
            )
            print(f"Sticker saved to: {args.output}")

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
