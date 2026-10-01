"""Pixel-level and command-line regressions using generated images."""

import io
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from rollingshutter import compose_frames, discover_frames, main, save_image


class RollingShutterTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name) / "frames [test]"
        self.folder.mkdir()

    def frame(self, name, colour, size=(2, 7), mode="RGB"):
        path = self.folder / name
        with Image.new(mode, size, colour) as image:
            image.save(path)
        return path

    def test_non_divisible_height_and_bottom_row(self):
        frames = [self.frame(f"{i}.png", (i * 60, 10, 20)) for i in range(3)]
        with compose_frames(frames) as image:
            self.assertEqual(image.size, (2, 7))
            self.assertEqual(
                [image.getpixel((0, row))[0] for row in range(7)],
                [0, 0, 60, 60, 120, 120, 120],
            )

    def test_float_rounding_regression(self):
        frames = [self.frame(f"{i}.png", "red", (1, 1)) for i in range(6)]
        with compose_frames(frames) as image:
            self.assertEqual(image.getpixel((0, 0)), (255, 0, 0))

    def test_crop_uses_original_row_coordinates(self):
        path = self.folder / "gradient.png"
        with Image.new("RGB", (1, 5)) as frame:
            for row in range(5):
                frame.putpixel((0, row), (row * 40, 10, 20))
            frame.save(path)
        with compose_frames([path, path]) as image:
            self.assertEqual(
                [image.getpixel((0, row))[0] for row in range(5)], [0, 40, 80, 120, 160]
            )

    def test_more_frames_than_rows(self):
        frames = [self.frame(f"{i}.png", (i * 40, 0, 0), (1, 2)) for i in range(5)]
        with compose_frames(frames) as image:
            self.assertEqual(
                [image.getpixel((0, row))[0] for row in range(2)], [80, 160]
            )

    def test_natural_order_case_insensitive_extension_and_literal_path(self):
        for name in ("frame10.png", "frame2.PNG", "frame1.png"):
            self.frame(name, "red")
        (self.folder / "directory.png").mkdir()
        self.assertEqual(
            [path.name for path in discover_frames(self.folder, ".PNG")],
            ["frame1.png", "frame2.PNG", "frame10.png"],
        )
        self.assertEqual(
            [path.name for path in discover_frames(self.folder, sort="lexicographic")],
            ["frame1.png", "frame10.png", "frame2.PNG"],
        )

    def test_output_excluded_on_repeated_runs(self):
        source = self.frame("frame1.png", "red")
        output = self.folder / "out.png"
        with redirect_stderr(io.StringIO()):
            for _ in range(2):
                self.assertEqual(main([str(self.folder), "-o", str(output), "-q"]), 0)
        self.assertEqual(discover_frames(self.folder, output=output), [source])
        with Image.open(output) as image:
            self.assertEqual(image.getpixel((0, 6)), (255, 0, 0))

    def test_invalid_folder_empty_input_and_extension(self):
        with self.assertRaisesRegex(ValueError, "no .png"):
            discover_frames(self.folder)
        with self.assertRaisesRegex(ValueError, "not a directory"):
            discover_frames(self.folder / "missing")
        with self.assertRaisesRegex(ValueError, "extension"):
            discover_frames(self.folder, "../png")
        with self.assertRaisesRegex(ValueError, "at least one"):
            compose_frames([])

    def test_dimension_mismatch_and_corrupt_frame(self):
        first = self.frame("first.png", "red")
        second = self.frame("second.png", "blue", (3, 7))
        with self.assertRaisesRegex(ValueError, "second.png.*expected"):
            compose_frames([first, second])
        second.write_bytes(b"not an image")
        with self.assertRaisesRegex(ValueError, "cannot read frame.*second.png"):
            compose_frames([first, second])

    def test_zero_row_frame_is_still_validated(self):
        bad = self.folder / "bad.png"
        bad.write_bytes(b"not an image")
        good = self.frame("good.png", "red", (1, 1))
        with self.assertRaisesRegex(ValueError, "bad.png"):
            compose_frames([bad, good])

    def test_palette_grayscale_and_rgba_colours(self):
        palette = self.folder / "palette.png"
        with Image.new("P", (2, 7), 1) as image:
            image.putpalette([0, 0, 0, 12, 34, 56] + [0] * 762)
            image.save(palette)
        cases = [
            (palette, (12, 34, 56)),
            (self.frame("gray.png", 123, mode="L"), (123, 123, 123)),
            (self.frame("alpha.png", (12, 34, 56, 0), mode="RGBA"), (12, 34, 56)),
        ]
        for path, expected in cases:
            with self.subTest(path=path), compose_frames([path]) as image:
                self.assertEqual(image.mode, "RGB")
                self.assertEqual(image.getpixel((0, 6)), expected)

    def test_source_files_closed_and_progress(self):
        frames = [self.frame(f"{i}.png", "red") for i in range(4)]
        real_open = Image.open
        opened = []

        def tracked_open(path):
            self.assertTrue(all(image.fp is None for image in opened))
            image = real_open(path)
            opened.append(image)
            return image

        progress = []
        with patch("rollingshutter.Image.open", side_effect=tracked_open):
            with compose_frames(
                frames, lambda done, total: progress.append((done, total))
            ):
                pass
        self.assertTrue(all(image.fp is None for image in opened))
        self.assertEqual(progress, [(1, 4), (2, 4), (3, 4), (4, 4)])

    def test_failed_save_preserves_destination_and_cleans_temp(self):
        output = self.folder.parent / "existing.png"
        output.write_bytes(b"original output")

        def fail_save(path, **kwargs):
            path.write_bytes(b"partial output")
            raise OSError("disk full")

        with Image.new("RGB", (1, 1)) as image:
            with patch.object(image, "save", side_effect=fail_save):
                with self.assertRaisesRegex(OSError, "disk full"):
                    save_image(image, output)
            with self.assertRaisesRegex(ValueError, "unsupported"):
                save_image(image, output.with_suffix(".unknown"))
        self.assertEqual(output.read_bytes(), b"original output")
        self.assertEqual(list(output.parent.glob(".rolling-shutter-*")), [])

    def test_real_cli_and_import_without_side_effects(self):
        self.frame("frame1.png", "red")
        script = Path(__file__).resolve().parents[1] / "rollingshutter.py"
        output = self.folder.parent / "result.png"
        command = [
            sys.executable,
            str(script),
            str(self.folder),
            "-o",
            str(output),
            "-q",
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout + result.stderr, "")
        with Image.open(output) as image:
            self.assertEqual(image.getpixel((0, 6)), (255, 0, 0))
        command[-1:] = ["-t", "jpg"]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 1)
        self.assertIn("no .jpg", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        result = subprocess.run(
            [sys.executable, "-c", "import rollingshutter"],
            cwd=script.parent,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout + result.stderr, "")


if __name__ == "__main__":
    unittest.main()
