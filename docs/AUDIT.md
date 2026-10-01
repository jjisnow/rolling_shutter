# Upstream comparison and code audit

Reviewed on 2026-10-02 (Australia/Sydney).

## Comparison baseline

- Fork: `jjisnow/rolling_shutter`, `master` at
  `19d5be0906858d13255ed97c74cadc873ed5ee91`.
- Upstream: `standupmaths/rolling_shutter`, `master` at `9dd36f3`
  ([source](https://github.com/standupmaths/rolling_shutter/commit/9dd36f3)).
- Common ancestor: `b960e21f9487b0b4ebd8ab655567ba9e6a46c823`.
- At the baseline, the fork had 16 unique commits and upstream had 3.

Upstream's three commits are `1fd42fc` (PEP 8 cleanup), `cb5f0e3`
(portable path joining), and merge commit `9dd36f3`. The merge in this branch
records upstream as a parent so future comparisons recognise its ancestry.

| Area | Upstream | Existing fork | Decision |
| --- | --- | --- | --- |
| Paths | `os.path.join`, but hard-coded author-specific base directories | CLI folder/output, manual slash concatenation | Keep CLI; use `pathlib` for literal, portable paths |
| Execution | Function and main guard | Parses arguments and processes files on import | Restore separation into importable functions and a main guard |
| Frame selection | Unsorted glob | Lexicographically sorted glob | Natural ordering by default; retain explicit legacy order |
| Dimensions | Fixed 1920 × 1080 | Auto-detected from first image | Retain auto-detection; validate every image |
| Row allocation | Fixed rows per frame | Auto-allocation with floating-point accumulation | Retain auto-allocation; use exact integer boundaries |
| User feedback | Returns `DONE` | Progress bar and saved-output message | Retain feedback; terminal-only progress and quiet mode |
| Example | No GIF | GIF and richer README | Retain example; replace README with installation and usage guide |

Upstream's open contributions include video output and synthetic rotor generation.
These are unmerged feature proposals, not upstream fixes, and would substantially
expand this small tool's scope. They were reviewed at the title/description level
and were not incorporated. Existing CLI functionality already covers the intent
of upstream's open CLI proposal.

## Findings and fixes

| Finding | Impact | Fix |
| --- | --- | --- |
| All input images opened together without explicit closure | File-descriptor exhaustion and memory growth on large sequences | Open, decode, and close one input at a time |
| Float accumulation truncated to integers | Final row can remain black; e.g. height 1 with 6 frames | Exact integer strip boundaries covering the full height |
| Missing/empty folders index `frames[0]` | Unhelpful exception | Validate folder, extension, and non-empty input |
| Different frame sizes accepted | Crops can pad or silently produce wrong output | Reject mismatches with the offending filename and expected size |
| Corrupt image errors lack input context | Difficult diagnosis; unexpected tracebacks | Report filename and a concise CLI error |
| Palette indices pasted into RGB output | Incorrect colours | Explicitly convert cropped strips to RGB |
| Glob treats folder metacharacters as patterns | Literal folders containing brackets may fail | Enumerate immediate directory children with `pathlib` |
| Non-padded filenames sorted as 1, 10, 2 | Incorrect temporal order | Deterministic natural sorting, with legacy order option |
| Existing output discovered among input frames | Repeated runs change the composition | Exclude the resolved destination from discovery |
| Save writes directly to destination | Encoding/write failure can destroy an existing result | Encode a temporary sibling, then replace; clean up on failure |
| Import runs the CLI | Prevents reuse and unit testing | Main guard and small discovery/composition/save functions |
| No dependency declaration or practical setup guide | Installation relies on guesswork | Declare maintained Pillow dependency and document Windows/macOS/Linux setup |

## Validation

The regression suite checks actual pixel values for uneven strip sizes, the
bottom-row rounding bug, more frames than rows, original crop coordinates,
palette/grayscale/RGBA conversion, natural and legacy ordering, case-insensitive
extensions, literal bracketed folder names, empty and invalid inputs, corruption,
size mismatches, repeated runs, file closure, progress counts, failed-save
preservation and cleanup, and real CLI subprocess behaviour/import safety.

Validation was performed locally on Linux using Python 3.12.14 and Pillow 12.3.0.
All 13 regression tests passed. A separate 1,000-frame smoke test passed with the
process limited to 32 file descriptors, including PNG/JPEG/TIFF output checks.
Ruff lint/format checks, compilation, and whitespace validation also passed.
Windows and macOS execution was not tested; paths and temporary-file closure are
designed to be portable. No automated GitHub Actions workflow was added.

## Remaining limits

- No direct video decoding/output, interpolation, scan-direction controls,
  EXIF orientation correction, or metadata preservation. These are documented
  scope limits rather than incomplete code paths.
- One full decoded source image plus the output and strip intermediates are
  needed in memory. Large individual images can still be expensive; Pillow's
  default decompression-bomb protections remain enabled.
- Atomic replacement protects against failed encoding and ordinary save errors;
  it does not provide a power-loss durability guarantee or coordinate concurrent
  writers. The destination parent must exist.
- Output is RGB; alpha is discarded, not composited. Use prepared RGB frames
  when transparency or consistent colour management matters.
- An explicitly selected destination is overwritten. Keep it outside the source
  folder to avoid accidentally designating a source image as the destination.
- No project licence is declared in either baseline; no licence was added on
  behalf of upstream contributors.
