"""Combine sequential images into one synthetic rolling-shutter photograph."""

import argparse
import os
import re
import sys
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path

from PIL import Image


def discover_frames(
    folder: Path,
    file_type: str = "png",
    sort: str = "natural",
    output: Path | None = None,
) -> list[Path]:
    """Find immediate child files, excluding the output on repeated runs."""
    extension = file_type.removeprefix(".").lower()
    if not extension or not extension.isalnum():
        raise ValueError("file type must be an extension such as png or jpg")
    if sort not in {"natural", "lexicographic"}:
        raise ValueError("sort must be natural or lexicographic")
    if not folder.is_dir():
        raise ValueError(f"input folder does not exist or is not a directory: {folder}")
    excluded = output.resolve() if output is not None else None
    frames = [
        path
        for path in folder.iterdir()
        if path.is_file()
        and path.suffix.lower() == f".{extension}"
        and path.resolve() != excluded
    ]
    if sort == "natural":
        # Tagged parts remain comparable even when filenames start differently.
        def key(path: Path) -> tuple:
            parts = tuple(
                (1, int(part)) if part.isdigit() else (0, part.casefold())
                for part in re.split(r"([0-9]+)", path.name)
            )
            return parts, path.name

        frames.sort(key=key)
    else:
        frames.sort(key=lambda path: path.name)
    if not frames:
        raise ValueError(f"no .{extension} input frames found in {folder}")
    return frames


def compose_frames(
    frames: Sequence[Path],
    progress: Callable[[int, int], None] | None = None,
) -> Image.Image:
    """Return an RGB image; the caller owns it and should close it when done.

    Every source must have identical dimensions. Only one input image is open
    at a time. Frames receiving zero rows are still decoded and validated.
    """
    if not frames:
        raise ValueError("at least one input frame is required")
    output = None
    try:
        for index, path in enumerate(frames):
            try:
                with Image.open(path) as frame:
                    frame.load()
                    if output is None:
                        output = Image.new("RGB", frame.size)
                    if frame.size != output.size:
                        raise ValueError(
                            f"frame {path} has size {frame.size}; "
                            f"expected {output.size}"
                        )
                    width, height = output.size
                    # Integer boundaries cover every row exactly once, avoiding
                    # accumulated floating-point rounding at the bottom edge.
                    top = index * height // len(frames)
                    bottom = (index + 1) * height // len(frames)
                    if bottom > top:
                        with frame.crop((0, top, width, bottom)) as strip:
                            # Palette indices must be converted to actual colours.
                            with strip.convert("RGB") as rgb:
                                output.paste(rgb, (0, top))
            except (OSError, Image.DecompressionBombError) as error:
                raise ValueError(f"cannot read frame {path}: {error}") from error
            if progress is not None:
                progress(index + 1, len(frames))
        return output
    except BaseException:
        if output is not None:
            output.close()
        raise


def save_image(image: Image.Image, output: Path) -> None:
    """Encode beside the destination, then replace it after a successful save."""
    Image.init()
    image_format = Image.registered_extensions().get(output.suffix.lower())
    if image_format not in Image.SAVE:
        raise ValueError(f"unsupported output extension: {output.suffix or '(none)'}")
    # Close the temporary file before Pillow opens it, including on Windows.
    with tempfile.NamedTemporaryFile(
        dir=output.parent, prefix=".rolling-shutter-", suffix=".tmp", delete=False
    ) as temporary:
        temporary_path = Path(temporary.name)
    try:
        image.save(temporary_path, format=image_format)
        os.replace(temporary_path, output)
    finally:
        temporary_path.unlink(missing_ok=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fake a rolling shutter effect")
    parser.add_argument("folder", type=Path, help="folder containing sequential images")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("out.png"),
        help="output filename (default: out.png)",
    )
    parser.add_argument(
        "-t", "--type", default="png", help="input extension (default: png)"
    )
    parser.add_argument(
        "--sort",
        choices=("natural", "lexicographic"),
        default="natural",
        help="filename ordering (default: natural; "
        "lexicographic matches older versions)",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="suppress progress and success messages",
    )
    args = parser.parse_args(argv)

    def report(completed: int, total: int) -> None:
        if sys.stderr.isatty() and not args.quiet:
            print(
                f"\r{completed * 100 // total:3d}%", end="", file=sys.stderr, flush=True
            )

    try:
        frames = discover_frames(args.folder, args.type, args.sort, args.output)
        with compose_frames(frames, report) as image:
            save_image(image, args.output)
    except (OSError, ValueError, Image.DecompressionBombError) as error:
        if sys.stderr.isatty() and not args.quiet:
            print(file=sys.stderr)
        parser.exit(1, f"{parser.prog}: error: {error}\n")
    if sys.stderr.isatty() and not args.quiet:
        print(file=sys.stderr)
    if not args.quiet:
        print(f"Saved output to '{args.output}'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
