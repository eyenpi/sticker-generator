# Priority Features for Sticker Generator

Analysis of the current codebase (v0.5.2) to identify the highest-impact features
for future development, ordered by priority.

---

## P0 — Critical / High Impact

### 1. Background Removal for Existing Images (standalone processing)

**Problem:** The image processing pipeline (green removal, edge cleanup, resize) is
tightly coupled to the Gemini generation step. Users with existing images — or images
from other generators — cannot use the processing tools from the CLI.

**Proposed scope:**
- Add a `process` subcommand (or `--input` flag) that accepts an existing image file
- Run the same green-screen removal → edge cleanup → resize → save pipeline
- Expose `process_image()` as a public library function
- Enables use as a general-purpose green-screen removal tool

**Why P0:** Doubles the utility of the package with minimal new code. The processing
functions already exist and are well-tested — this is primarily a wiring task.

---

### 2. Configurable Green Removal Parameters

**Problem:** HSV thresholds for green detection are hardcoded in `core.py`
(`hue_center=120, hue_range=35, sat_min=0.25, val_min=0.40`). When Gemini produces
slightly off-green backgrounds, removal fails silently, producing artifacts or
mostly-transparent output.

**Proposed scope:**
- Accept optional HSV tuning parameters in `create_sticker()` and the CLI
  (`--hue-center`, `--hue-range`, `--sat-min`, `--val-min`)
- Keep current values as sensible defaults
- Document the parameters with guidance on when to adjust them

**Why P0:** Directly addresses the most common failure mode (incomplete green removal)
and gives advanced users a recovery path without code changes.

---

### 3. Generation Quality Validation

**Problem:** There is no feedback when generation or green removal produces a bad
result. A fully-transparent image (green removal ate the subject) or an image with
no transparency (green removal failed entirely) is silently saved.

**Proposed scope:**
- After processing, compute basic quality metrics:
  - Percentage of transparent vs opaque pixels
  - Warn if >95% transparent (subject was likely removed)
  - Warn if <5% transparent (green removal likely failed)
- Return metrics in a `GenerationResult` dataclass alongside the image
- CLI prints warnings; library callers inspect the result object
- Optional `--strict` flag that exits non-zero on quality warnings

**Why P0:** Prevents users from unknowingly getting bad output. Zero cost when things
work correctly, high value when they don't.

---

## P1 — High Impact

### 4. Retry with Exponential Backoff for API Calls

**Problem:** `generate_sticker()` in `core.py` makes a single attempt. Gemini API
returns 429 (rate limit) and 503 (overloaded) transiently. The sheet generator has
basic retry but uses a fixed delay, not backoff.

**Proposed scope:**
- Add configurable retry logic to `generate_sticker()` with exponential backoff
  (default: 3 retries, 2/4/8s delays)
- Respect `Retry-After` header if present
- Apply to both single generation and sheet generation paths
- CLI flag `--retries` to override max attempts

**Why P1:** Significantly improves reliability for batch generation and during peak
API usage without user intervention.

---

### 5. Async / Concurrent Sticker Sheet Generation

**Problem:** `generate_sticker_sheet()` generates variations sequentially with a
`time.sleep()` between each. For N=9 variations at ~5s each + 0.5s delay, that's
~50 seconds of wall-clock time.

**Proposed scope:**
- Add `generate_sticker_sheet_async()` using `asyncio` + `aiohttp` (or the async
  Gemini client if available)
- Support configurable concurrency limit (e.g., `max_concurrent=3`) to respect
  API rate limits
- Keep the synchronous version as-is for backward compatibility
- CLI uses async version by default when generating sheets

**Why P1:** Sheet generation is the primary batch use case. 3x–5x speedup for the
most time-consuming operation.

---

### 6. Custom Style Definitions

**Problem:** Only 6 hardcoded styles are available. Users cannot define their own
reusable style presets without modifying library code.

**Proposed scope:**
- Support loading custom styles from a YAML/JSON/TOML config file
  (e.g., `~/.sticker-generator/styles.yaml` or project-local)
- CLI flag `--style-file` to specify a custom styles file
- Library function `register_style(name, description, prompt_modifier)` for
  runtime registration
- Document the style format with examples

**Why P1:** Style presets are the primary UX differentiator. Letting users create
and share styles extends the tool's value significantly.

---

### 7. Multiple AI Provider Support

**Problem:** The project is locked to Google Gemini (`gemini-2.5-flash-image`). If
the API changes, goes down, or a user prefers another provider, they're stuck.

**Proposed scope:**
- Abstract the generation backend behind a `Provider` protocol/ABC
- Implement `GeminiProvider` (current behavior) and at least one alternative
  (e.g., `OpenAIProvider` using DALL-E 3, or `StabilityProvider`)
- CLI flag `--provider` / env var `STICKER_PROVIDER`
- Each provider handles its own prompt engineering for green backgrounds
- Model selection flag `--model` to override the default per provider

**Why P1:** Reduces single-vendor lock-in and broadens the user base. The
abstraction also makes the codebase more testable.

---

## P2 — Medium Impact

### 8. SVG / Vector Output Support

**Problem:** All output is raster (PNG/WebP). Stickers for platforms like Telegram
benefit from vector formats, and designers often need scalable assets.

**Proposed scope:**
- Add bitmap-to-vector tracing using `potrace` or `vtracer` (via Python bindings)
- New output format `svg` in `formats.py`
- CLI auto-detects `.svg` extension
- Configurable tracing parameters (color count, smoothness)

**Why P2:** Valuable for a subset of users but adds a non-trivial dependency. Could
be an optional extra (`pip install sticker-generator[svg]`).

---

### 9. Prompt Templates and Prompt Library

**Problem:** Users must write full prompts each time. Common sticker types
(emoji-style reactions, character stickers, icon sets) follow predictable patterns.

**Proposed scope:**
- Built-in prompt templates: `"emoji:{emotion}"`, `"character:{description}"`,
  `"icon:{concept}"`
- Templates expand into optimized prompts with best-practice instructions
- CLI shorthand: `sticker-generator --template emoji "happy cat"`
- User-defined templates in config file (same as custom styles)

**Why P2:** Improves UX for common cases and encodes prompt engineering knowledge
that users would otherwise need to discover themselves.

---

### 10. Generation Metadata and Provenance

**Problem:** After generation, there's no record of what prompt, style, parameters,
or model produced a given image. Users generating many stickers lose track.

**Proposed scope:**
- Embed metadata in PNG `tEXt`/`iTXt` chunks and WebP EXIF:
  - Prompt, style, model, timestamp, version, HSV parameters
- `sticker-generator info <file>` subcommand to read metadata back
- Optional `--no-metadata` flag to produce clean files
- Library returns metadata dict in generation result

**Why P2:** Low implementation effort (Pillow already supports PNG text chunks).
Useful for asset management and reproducibility.

---

### 11. Animated Sticker Support (GIF / APNG / Animated WebP)

**Problem:** Many messaging platforms (Telegram, Signal, WhatsApp) support animated
stickers. Currently only static images are generated.

**Proposed scope:**
- Generate multiple frames with related prompts (e.g., "waving hand frame 1/4")
- Assemble into animated GIF, APNG, or animated WebP
- Configurable frame count, duration, and loop count
- CLI: `--animated --frames 4 --duration 100`

**Why P2:** High user appeal but technically challenging — requires Gemini to produce
coherent frame sequences, which is not guaranteed with current models.

---

## P3 — Nice to Have

### 12. Progress Reporting and Verbose Mode

- Add `--verbose` / `-v` flag for detailed processing output
- Progress bar for sheet generation (e.g., `tqdm`)
- Log HSV statistics, pixel counts, and timing per step

### 13. Sticker Pack Export

- Export a set of stickers in platform-specific formats:
  - Telegram sticker pack (WebP, 512x512)
  - WhatsApp sticker pack (WebP, 512x512, tray icon)
  - iMessage sticker pack (PNG, various sizes)
- Validate against platform requirements (size, format, count)

### 14. Web UI / API Server

- Simple Flask/FastAPI server wrapping `create_sticker()`
- Upload reference images, preview results, download stickers
- Useful for non-technical users or integration into design tools

### 15. Caching Layer

- Cache generated images by prompt+style+parameters hash
- Skip API call if identical request was made before
- Configurable cache directory and TTL
- `--no-cache` flag to force regeneration

---

## Implementation Order Recommendation

For maximum impact with minimum effort, the suggested implementation order is:

1. **Background removal for existing images** (P0) — wiring only, no new algorithms
2. **Configurable green removal parameters** (P0) — parameter threading
3. **Generation quality validation** (P0) — small addition with outsized UX impact
4. **Retry with backoff** (P1) — reliability improvement
5. **Custom style definitions** (P1) — config file + registration API
6. **Async sheet generation** (P1) — performance improvement
7. **Multiple providers** (P1) — architectural, best done before more features land
8. **Metadata embedding** (P2) — low-effort, high-utility

Features 8–15 can be tackled in any order based on user demand.
