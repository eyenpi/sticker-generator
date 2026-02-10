"""Command-line interface for sticker generation."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm

from sticker_generator.batch import (
    batch_generate,
    batch_process_images,
    parse_prompt_file,
)
from sticker_generator.core import create_sticker, process_image
from sticker_generator.formats import get_available_formats
from sticker_generator.image_processing import validate_transparency
from sticker_generator.sheet import generate_sticker_sheet
from sticker_generator.styles import get_available_styles

logger = logging.getLogger(__name__)


def _setup_logging(level: int) -> None:
    """Configure logging for the sticker_generator package.

    Args:
        level: Logging level (e.g., logging.DEBUG, logging.INFO, logging.WARNING).
    """
    root_logger = logging.getLogger("sticker_generator")
    # Clear existing handlers (idempotent for tests)
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stderr)
    if level <= logging.DEBUG:
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    else:
        handler.setFormatter(logging.Formatter("%(message)s"))
    root_logger.addHandler(handler)
    root_logger.setLevel(level)


def parse_resize_arg(value: str) -> tuple[int, int]:
    """Parse resize argument string into (width, height) tuple.

    Args:
        value: Size string in format "SIZE" (square) or "WIDTHxHEIGHT".

    Returns:
        Tuple of (width, height).

    Raises:
        argparse.ArgumentTypeError: If format is invalid or values are not positive.
    """
    value = value.strip()

    # Handle WIDTHxHEIGHT format (case-insensitive x)
    if "x" in value.lower():
        parts = value.lower().split("x")
        if len(parts) != 2:
            raise argparse.ArgumentTypeError(
                f"Invalid resize format: {value}. Use SIZE or WIDTHxHEIGHT"
            )
        try:
            width = int(parts[0].strip())
            height = int(parts[1].strip())
        except ValueError:
            raise argparse.ArgumentTypeError(
                f"Invalid resize format: {value}. Width and height must be integers"
            ) from None
    else:
        # Square format
        try:
            width = height = int(value)
        except ValueError:
            raise argparse.ArgumentTypeError(
                f"Invalid resize format: {value}. Use SIZE or WIDTHxHEIGHT"
            ) from None

    if width <= 0 or height <= 0:
        raise argparse.ArgumentTypeError(
            f"Invalid resize dimensions: {value}. Width and height must be positive"
        )

    return (width, height)


def main() -> int:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        prog="sticker-generator",
        description="Generate stickers with transparent backgrounds using Gemini AI",
    )
    parser.add_argument(
        "prompt",
        nargs="?",
        default=None,
        help="Description of the sticker to generate",
    )
    parser.add_argument(
        "--process",
        metavar="IMAGE",
        help="Process an existing image (remove green background)",
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
    parser.add_argument(
        "-s",
        "--style",
        choices=get_available_styles(),
        metavar="STYLE",
        help="Style preset: " + ", ".join(get_available_styles()),
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=get_available_formats(),
        metavar="FORMAT",
        help="Output format: "
        + ", ".join(get_available_formats())
        + " (default: auto-detect from filename)",
    )
    parser.add_argument(
        "-q",
        "--quality",
        type=int,
        metavar="1-100",
        help="Quality for lossy formats (1-100, higher is better)",
    )
    parser.add_argument(
        "--lossless",
        action="store_true",
        help="Force lossless compression",
    )
    parser.add_argument(
        "--lossy",
        action="store_true",
        help="Force lossy compression",
    )
    parser.add_argument(
        "--resize",
        type=parse_resize_arg,
        metavar="SIZE",
        help="Resize output to WIDTHxHEIGHT or SIZE for square (e.g., 512 or 512x256)",
    )
    parser.add_argument(
        "--resize-exact",
        action="store_true",
        help="Force exact resize dimensions (may distort aspect ratio)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with error if quality validation fails",
    )

    # Verbosity flags (mutually exclusive)
    verbosity_group = parser.add_mutually_exclusive_group()
    verbosity_group.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed processing information (DEBUG level)",
    )
    verbosity_group.add_argument(
        "--debug",
        action="store_true",
        help="Verbose output plus auto-save intermediate images",
    )
    verbosity_group.add_argument(
        "--quiet",
        action="store_true",
        help="Only show warnings and errors",
    )

    parser.add_argument(
        "--save-intermediates",
        nargs="?",
        const="",
        default=None,
        metavar="DIR",
        help="Save intermediate processing images to DIR "
        "(auto-generated from output stem if DIR omitted)",
    )

    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable progress bars",
    )

    # Retry parameters
    retry_group = parser.add_argument_group(
        "retry options",
        "Control retry behavior for API calls",
    )
    retry_group.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Max retries for failed API calls (default: 3)",
    )
    retry_group.add_argument(
        "--retry-delay",
        type=float,
        default=1.0,
        help="Initial delay between retries in seconds (default: 1.0)",
    )

    # Batch processing options
    batch_group = parser.add_argument_group(
        "batch options",
        "Process multiple prompts or images at once",
    )
    batch_group.add_argument(
        "--batch-prompts",
        metavar="FILE",
        help="Read prompts from text file (one per line, # for comments)",
    )
    batch_group.add_argument(
        "--batch-dir",
        metavar="DIR",
        help="Process all images in directory (removes green backgrounds)",
    )
    batch_group.add_argument(
        "--output-dir",
        metavar="DIR",
        help="Output directory for batch results (required for batch modes)",
    )
    batch_group.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay between API requests in batch mode, seconds (default: 1.0)",
    )
    batch_group.add_argument(
        "--max-workers",
        type=int,
        default=1,
        help="Max concurrent workers for batch/sheet generation (default: 1)",
    )

    # Green removal tuning parameters
    green_group = parser.add_argument_group(
        "green removal tuning",
        "Advanced parameters for green screen detection and removal",
    )
    green_group.add_argument(
        "--hue-center",
        type=float,
        default=115,
        help="Center hue for green detection, degrees (default: 115)",
    )
    green_group.add_argument(
        "--hue-range",
        type=float,
        default=35,
        help="Hue tolerance in degrees (default: 35)",
    )
    green_group.add_argument(
        "--min-saturation",
        type=float,
        default=25,
        help="Min saturation %% to consider green (default: 25)",
    )
    green_group.add_argument(
        "--min-value",
        type=float,
        default=40,
        help="Min brightness %% to consider green (default: 40)",
    )
    green_group.add_argument(
        "--green-threshold",
        type=float,
        default=1.1,
        help="Aggressive green ratio threshold (default: 1.1)",
    )

    args = parser.parse_args()

    # Configure logging based on verbosity flags
    if args.debug or args.verbose:
        _setup_logging(logging.DEBUG)
    elif args.quiet:
        _setup_logging(logging.WARNING)
    else:
        _setup_logging(logging.INFO)

    # Compute save_intermediates directory
    save_intermediates: str | None = None
    if args.save_intermediates is not None:
        if args.save_intermediates == "":
            # Auto-generate from output stem
            save_intermediates = str(Path(args.output).stem + "_intermediates")
        else:
            save_intermediates = args.save_intermediates
    elif args.debug:
        # --debug implies save-intermediates
        save_intermediates = str(Path(args.output).stem + "_intermediates")

    # Validate quality range
    if args.quality is not None and not (1 <= args.quality <= 100):
        logger.error("Error: Quality must be between 1 and 100")
        return 1

    # Validate lossless/lossy flags are not both set
    if args.lossless and args.lossy:
        logger.error("Error: Cannot specify both --lossless and --lossy")
        return 1

    # Determine lossless setting
    lossless: bool | None = None
    if args.lossless:
        lossless = True
    elif args.lossy:
        lossless = False

    # Validate retry parameters
    if args.max_retries < 0:
        logger.error("Error: --max-retries must be non-negative")
        return 1

    if args.retry_delay < 0:
        logger.error("Error: --retry-delay must be non-negative")
        return 1

    if args.max_workers < 1:
        logger.error("Error: --max-workers must be at least 1")
        return 1

    disable_progress = args.quiet or args.no_progress

    # Validate batch flag combinations
    if args.batch_prompts and args.batch_dir:
        logger.error("Error: Cannot use both --batch-prompts and --batch-dir")
        return 1

    if args.batch_dir and args.process:
        logger.error("Error: Cannot use both --batch-dir and --process")
        return 1

    if args.batch_prompts and args.prompt:
        logger.error("Error: Cannot use both --batch-prompts and a positional prompt")
        return 1

    is_batch = args.batch_prompts or args.batch_dir

    if is_batch and not args.output_dir:
        logger.error("Error: --output-dir is required for batch modes")
        return 1

    if is_batch and args.variations > 1:
        logger.error("Error: -n/--variations is not compatible with batch modes")
        return 1

    if args.batch_prompts and not Path(args.batch_prompts).exists():
        logger.error("Error: Prompt file not found: %s", args.batch_prompts)
        return 1

    if args.batch_dir and not Path(args.batch_dir).exists():
        logger.error("Error: Input directory not found: %s", args.batch_dir)
        return 1

    # Validate that either prompt, --process, or batch flag is provided
    if args.process is None and args.prompt is None and not is_batch:
        logger.error(
            "Error: A prompt is required "
            "(or use --process IMAGE, --batch-prompts FILE, --batch-dir DIR)"
        )
        return 1

    # Validate --process image exists
    if args.process and not Path(args.process).exists():
        logger.error("Error: Input image not found: %s", args.process)
        return 1

    # Validate reference images exist
    if args.images:
        for img_path in args.images:
            if not Path(img_path).exists():
                logger.error("Error: Reference image not found: %s", img_path)
                return 1

    try:
        if args.batch_prompts:
            prompts = parse_prompt_file(args.batch_prompts)
            logger.info(
                "Batch generating %d stickers from: %s",
                len(prompts),
                args.batch_prompts,
            )
            with logging_redirect_tqdm():
                with tqdm(
                    total=len(prompts),
                    desc="Generating stickers",
                    disable=disable_progress,
                    file=sys.stderr,
                ) as pbar:
                    batch_result = batch_generate(
                        prompts=prompts,
                        output_dir=args.output_dir,
                        aspect_ratio=args.aspect_ratio,
                        input_images=args.images,
                        api_key=args.api_key,
                        edge_threshold=args.edge_threshold,
                        style=args.style,
                        output_format=args.format,
                        quality=args.quality,
                        lossless=lossless,
                        resize=args.resize,
                        resize_exact=args.resize_exact,
                        hue_center=args.hue_center,
                        hue_range=args.hue_range,
                        min_saturation=args.min_saturation,
                        min_value=args.min_value,
                        green_threshold=args.green_threshold,
                        max_retries=args.max_retries,
                        retry_delay=args.retry_delay,
                        delay_between_requests=args.delay,
                        strict=args.strict,
                        save_intermediates=save_intermediates,
                        max_workers=args.max_workers,
                        progress_callback=pbar.update,
                    )
            if batch_result.failed:
                logger.warning(
                    "%d/%d items failed", len(batch_result.failed), batch_result.total
                )
                if args.strict:
                    return 1
            return 0

        elif args.batch_dir:
            logger.info("Batch processing images from: %s", args.batch_dir)
            from sticker_generator.batch import IMAGE_EXTENSIONS

            image_count = sum(
                1
                for f in Path(args.batch_dir).iterdir()
                if f.suffix.lower() in IMAGE_EXTENSIONS
            )
            with logging_redirect_tqdm():
                with tqdm(
                    total=image_count,
                    desc="Processing images",
                    disable=disable_progress,
                    file=sys.stderr,
                ) as pbar:
                    batch_result = batch_process_images(
                        input_dir=args.batch_dir,
                        output_dir=args.output_dir,
                        edge_threshold=args.edge_threshold,
                        output_format=args.format,
                        quality=args.quality,
                        lossless=lossless,
                        resize=args.resize,
                        resize_exact=args.resize_exact,
                        hue_center=args.hue_center,
                        hue_range=args.hue_range,
                        min_saturation=args.min_saturation,
                        min_value=args.min_value,
                        green_threshold=args.green_threshold,
                        strict=args.strict,
                        save_intermediates=save_intermediates,
                        max_workers=args.max_workers,
                        progress_callback=pbar.update,
                    )
            if batch_result.failed:
                logger.warning(
                    "%d/%d items failed", len(batch_result.failed), batch_result.total
                )
                if args.strict:
                    return 1
            return 0

        elif args.process:
            # Process existing image mode
            logger.info("Processing image: %s", args.process)
            process_image(
                input_path=args.process,
                output=args.output,
                edge_threshold=args.edge_threshold,
                output_format=args.format,
                quality=args.quality,
                lossless=lossless,
                resize=args.resize,
                resize_exact=args.resize_exact,
                hue_center=args.hue_center,
                hue_range=args.hue_range,
                min_saturation=args.min_saturation,
                min_value=args.min_value,
                green_threshold=args.green_threshold,
                save_intermediates=save_intermediates,
            )
            logger.info("Processed image saved to: %s", args.output)
        else:
            logger.info("Generating sticker: %s", args.prompt)
            if args.images:
                logger.info("Using %d reference image(s)", len(args.images))
            if args.style:
                logger.info("Using style: %s", args.style)

            if args.variations > 1:
                logger.info("Generating %d variations...", args.variations)
                with logging_redirect_tqdm():
                    with tqdm(
                        total=args.variations,
                        desc="Generating variations",
                        disable=disable_progress,
                        file=sys.stderr,
                    ) as pbar:
                        result = generate_sticker_sheet(
                            prompt=args.prompt,
                            variations=args.variations,
                            output=args.output if args.sheet else None,
                            save_individuals=args.save_individuals or not args.sheet,
                            individual_prefix=Path(args.output).stem
                            if not args.sheet
                            else None,
                            aspect_ratio=args.aspect_ratio,
                            input_images=args.images,
                            api_key=args.api_key,
                            edge_threshold=args.edge_threshold,
                            columns=args.columns,
                            padding=args.padding,
                            style=args.style,
                            output_format=args.format,
                            quality=args.quality,
                            lossless=lossless,
                            resize=args.resize,
                            resize_exact=args.resize_exact,
                            hue_center=args.hue_center,
                            hue_range=args.hue_range,
                            min_saturation=args.min_saturation,
                            min_value=args.min_value,
                            green_threshold=args.green_threshold,
                            sticker_max_retries=args.max_retries,
                            sticker_retry_delay=args.retry_delay,
                            save_intermediates=save_intermediates,
                            max_workers=args.max_workers,
                            progress_callback=pbar.update,
                        )

                if result.failed_indices:
                    logger.warning(
                        "Warning: %d variation(s) failed",
                        len(result.failed_indices),
                    )

                if args.sheet:
                    logger.info("Sheet saved to: %s", args.output)
                    if args.save_individuals:
                        prefix = Path(args.output).stem
                        logger.info("Individual stickers saved with prefix: %s", prefix)
                else:
                    logger.info(
                        "Stickers saved with prefix: %s", Path(args.output).stem
                    )
            else:
                result_image = create_sticker(
                    prompt=args.prompt,
                    output=args.output,
                    aspect_ratio=args.aspect_ratio,
                    save_raw=args.save_raw,
                    input_images=args.images,
                    api_key=args.api_key,
                    edge_threshold=args.edge_threshold,
                    style=args.style,
                    output_format=args.format,
                    quality=args.quality,
                    lossless=lossless,
                    resize=args.resize,
                    resize_exact=args.resize_exact,
                    hue_center=args.hue_center,
                    hue_range=args.hue_range,
                    min_saturation=args.min_saturation,
                    min_value=args.min_value,
                    green_threshold=args.green_threshold,
                    max_retries=args.max_retries,
                    retry_delay=args.retry_delay,
                    save_intermediates=save_intermediates,
                )
                logger.info("Sticker saved to: %s", args.output)

                if args.strict:
                    metrics = validate_transparency(result_image)
                    if metrics.has_quality_warning:
                        logger.error("Error (--strict): %s", metrics.warning_message)
                        return 1

        return 0

    except Exception as e:
        logger.error("Error: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
