# rolling_shutter

Create a synthetic rolling-shutter photograph from a sequence of still images.
The result combines horizontal strips from successive frames into one RGB image.
This is an image-sequence tool; it does not read or write video directly.

![Example rolling-shutter animation](example.gif)

## Install

Use Python 3.10 or newer and [Pillow](https://pillow.readthedocs.io/en/stable/)
(the maintained PIL successor). From a terminal:

```sh
git clone https://github.com/jjisnow/rolling_shutter.git
cd rolling_shutter
python -m venv .venv
```

Activate the environment:

```sh
# Windows PowerShell
.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate
```

Then install the dependency:

```sh
python -m pip install -r requirements.txt
```

On systems where Python is named `python3`, use that for the initial commands.
If PowerShell blocks activation, you can run `.venv\Scripts\python.exe` directly
in place of `python` in the remaining commands; no policy change is required.

## Run

Put frames of the same dimensions into a folder, then run:

```sh
python rollingshutter.py "path/to/frames" -o result.png
python rollingshutter.py "path/to/jpeg frames" -t jpg -o result.jpg
```

| Argument | Meaning | Default |
| --- | --- | --- |
| `folder` | Folder containing frames; only immediate child files are used | Required |
| `-o`, `--output` | Destination image; its parent folder must already exist | `out.png` in the current directory |
| `-t`, `--type` | One input extension, with or without a leading dot; case-insensitive | `png` |
| `--sort` | `natural` or `lexicographic` filename ordering | `natural` |
| `-q`, `--quiet` | Suppress progress and success messages; errors remain visible | Off |

Natural ordering reads `frame1.png`, `frame2.png`, `frame10.png` in that order.
Use `--sort lexicographic` to reproduce the old filename ordering. Zero-padded
names such as `frame000001.png` work with either ordering. `-t jpg` matches
`.jpg` and `.JPG`, but not `.jpeg`; use `-t jpeg` for those files.

The destination is overwritten after a successful encode. Prefer a destination
outside your input folder and never name it after a source frame. If it is inside
the input folder, that path is excluded from the inputs, allowing repeated runs
without incorporating the previous output. All other matching files must be
valid images of the same dimensions. Errors exit with status 1 and leave an
existing destination unchanged. Invalid command-line arguments exit with status 2.
Progress is shown on stderr only when it is a terminal.

### How the effect works

For `N` input frames and an image height of `H`, frame `i` (starting at zero)
provides rows from `floor(i × H / N)` up to, but not including,
`floor((i + 1) × H / N)`. Strips use their original row coordinates. Integer
boundaries cover the full height without gaps or overlaps.

If there are more frames than rows, some frames contribute no rows; they are
still checked for readable content and matching dimensions. This discretisation
uses one source frame per strip, with no interpolation or exposure integration.

Output is always RGB. Palette and grayscale inputs are converted to RGB; alpha
is discarded without compositing against a background. EXIF orientation is not
applied, and metadata/colour profiles are not copied. Multi-frame image formats
use only their first frame. For predictable results, prepare consistently
oriented frames in the same colour space first. Memory use grows with frame size,
rather than the number of frames, apart from the list of filenames.

### Extract frames from a video (optional)

If [FFmpeg](https://ffmpeg.org/ffmpeg.html) is already installed, create an empty
`frames` folder and extract a numbered image sequence:

```sh
ffmpeg -i input.mp4 frames/frame%08d.png
python rollingshutter.py frames -o result.png
```

The output is a single photograph assembled across the extracted sequence. It
is not an animated version of the source video. Extraction can use substantial
disk space; choose a short clip or extract a selected time range when appropriate.

## Use from Python

Importing the module does not parse arguments or write files:

```python
from pathlib import Path
from rollingshutter import compose_frames, discover_frames, save_image

output = Path("result.png")
frames = discover_frames(Path("frames"), output=output)
with compose_frames(frames) as image:
    save_image(image, output)
```

`compose_frames` returns an image owned by the caller, so use a context manager
or close it explicitly. `save_image` infers the encoder from the destination
extension and replaces the destination after encoding a temporary file beside it.

## Verify changes

The tests use Python's standard library and generate their own tiny input images:

```sh
python -m unittest discover -s tests -v
python -m compileall -q rollingshutter.py tests
```

No video assets, extra test dependencies, or CI minutes are needed.

## Upstream and audit

This fork originates from
[standupmaths/rolling_shutter](https://github.com/standupmaths/rolling_shutter).
The [audit notes](docs/AUDIT.md) record the exact compared commits, upstream merge
decisions, fixes, and remaining limitations. The original example GIF and project
history are retained. Neither repository declares a project licence, so this
change does not invent one or change the ownership of existing material.
