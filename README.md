# Label Anything

Desktop tool (PySide6 + OpenCV) to label, annotate and analyze any kind of image. Fully configurable from the GUI: no config file to edit by hand.

## Download (no Python needed)

**[⬇️ Download the latest release](https://github.com/filippocasini98/label-anything/releases/latest)** and grab the binary for your platform — no Python or setup required, just unzip and double-click:

- **Windows**: `LabelAnything-<version>-win64.zip` → extract and run `LabelAnything.exe`
- **macOS**: `LabelAnything-<version>-macOS.zip` → extract and run `Label Anything.app`
- **Linux**: `LabelAnything-<version>-linux64.zip` → extract and run `LabelAnything`

The binaries are built automatically for every release by GitHub Actions (PyInstaller, onedir: fast startup, no temporary unpacking). The `Source code` asset is there for developers.

### macOS: first launch (Gatekeeper)

The app is not signed with an Apple Developer certificate, so Gatekeeper blocks it on first launch. To open it:

- **Way 1**: right-click (or `Ctrl`+click) `Label Anything.app` → **Open** → **Open** in the dialog. This is only needed once.
- **Way 2**: after extracting, run in Terminal:

```bash
xattr -cr "Label Anything.app"
```

### Linux: system libraries

On minimal distributions, install the graphics libraries Qt needs (they are not bundled in the zip):

```bash
sudo apt install libgl1 libegl1   # Debian/Ubuntu and derivatives
```

## Requirements (running from source)

Python 3.9 or newer (macOS, Windows or Linux). Everything else is installed automatically.

### One-command install

**macOS / Linux:**

```bash
curl -fsSL https://raw.githubusercontent.com/filippocasini98/label-anything/main/install.sh | bash
```

**Windows:** download [`install.bat`](https://github.com/filippocasini98/label-anything/raw/main/install.bat) and double-click it.

## First-time setup from source (once)

Double-click `setup.command` (macOS) or `setup.bat` (Windows): it creates the virtual environment and installs PySide6, OpenCV and numpy.

## Running (from source)

Double-click `start.command` (macOS) or `start.bat` (Windows), or:

```bash
./venv/bin/python run_labeling.py
```

The program **remembers the last opened folder** and restarts right from there: the folder picker only appears on first launch (or with `Ctrl+O` to change folder). You can also pass the folder on the command line: `python run_labeling.py /path/to/folder`.

On first launch in a folder: select the images folder, the wizard creates the project (`nome.progetto.json` inside the folder). Reopening the folder loads the project automatically.

### Double-clickable macOS app (optional)

For a terminal-free launch you can create a `Label Anything.app` bundle:

```bash
mkdir -p "Label Anything.app/Contents/MacOS"
cat > "Label Anything.app/Contents/MacOS/LabelAnything" <<'SH'
#!/bin/bash
exec "/path/to/project/venv/bin/python" "/path/to/project/run_labeling.py" "$@"
SH
chmod +x "Label Anything.app/Contents/MacOS/LabelAnything"
```

with a `Contents/Info.plist` pointing `CFBundleExecutable` to `LabelAnything` (see the standard macOS bundle structure).

## Features

- **Classification**: labels with configurable shortcut keys; single-label mode (auto-advance after assignment) or multi-label mode (toggle).
- **Geometries** ("classification + geometries" or "geometries only" workflow): bounding boxes dragged on screen, resizable with 8 handles and movable; click-to-draw polygons, closed with Enter. Per-object class is selectable. The **size of every geometry** is shown on the image, reported in `etichette.csv` and aggregated per class in `statistiche.csv`: for boxes width/height/area, for polygons bounding box and area (mean, min, max, in px or in the configured unit).
- **Measurements** (if enabled): distance between two clicks (px and configured unit via px/unit scale), polygon area, click object counting, **object dimensions** (dragged rectangle: width, height and area in px and in the configured unit — useful e.g. to measure stomata in electron microscope images). All measurements are saved and re-displayed.
- **Auto-annotation**: annotate with YOLO/Ultralytics models (`.pt`/`.onnx`, detection → boxes, segmentation → polygons) run in-app — requires the optional `pip install ultralytics` package — or import ready-made annotations in YOLO txt, COCO json, LabelMe json or Pascal VOC xml format. Source classes are mapped onto the project labels in a dialog (confidence threshold, "skip images that already have geometries" option). Every model-annotated image stays **to verify**: fix it with the normal tools (move, resize, `Delete`, change class on the selected geometry) and approve with `V`, which jumps to the next image to verify; dedicated "To verify (model)" filter.
- **Visual analysis**: brightness, contrast, grayscale, CLAHE equalization, zoom/pan.
- **Statistics**: label distribution, progress, reviews, geometry and measurement counts; exportable to CSV.
- **Filters**: by status (unlabeled, to review, reviewed, with notes, with geometries) and by label.
- **Undo/redo** on every change, atomic autosave at 350 ms and on close.
- **"Geometries only" workflow**: draw boxes and polygons without image classification; the labels section is hidden and an image counts as completed once it has geometries. Labels remain mandatory because they are the object classes.
- **Pointer selector**: 8 cursors for drawing and measurement tools (crosshair, full-screen cross, precision, annotation, target, dot, arrow, invisible), selectable on the fly from a toolbar combobox and saved as a global preference.

## Shortcuts

- `Ctrl+O` open folder, `Ctrl+S` save, `Ctrl+Z`/`Ctrl+Y` undo/redo
- `Ctrl+E` configuration, `N` next image to label
- Keys `1..9` (configurable): assign/toggle label
- `A`/`D` previous/next, `X` mark for review, `Enter` confirm review
- `G` grayscale, `H` equalize, `R` reset view, `+`/`-` zoom
- `Enter` closes polygon/area, `Esc` cancels drawing, `Delete` deletes the selected geometry/measurement (or the labels)
- Polygon/area can also be closed by clicking the first vertex or double-clicking; the label combobox changes the class of the selected box
- `V` approves the image (model annotations)

## Data and export

Data lives in a **dedicated data folder**:

- folder with multiple images → `etichettatura/` subfolder inside the images folder
- single image → next to the image, no subfolder

Inside the data folder:

- `nome.progetto.json` — the project: configuration + annotations + measurements. Atomic saving; if corrupted it is set aside as `.corrotto` and the project restarts. Projects created with earlier versions (in the root) are migrated automatically.
- `etichette.csv` — updated on every save: one row per image with name, number of labels, labels, status, notes, geometry and measurement counts.
- `statistiche.csv` — updated on every save: label distribution, statuses, progress and statistics of measured objects (count, mean/min/max width/height/area, in px or in the configured unit).

Additional exports from the "Export" menu: COCO detection/segmentation, YOLO detection/segmentation, LabelMe, indexed PNG masks (with `legend.csv`), CSV and statistics report to a folder of your choice.

## Development

```bash
./venv/bin/python -m pytest        # pure-logic tests (config, model, io, export)
```

Structure: `labeling_tool/` — `config.py` (schema and validation), `model.py` (records, project, undo/redo, calculations), `io_utils.py` (scanning and cache), `export.py` (formats, pure functions), `cursors.py` (annotation cursors), `image_view.py` (annotation viewer), `settings_dialog.py` (wizard and editor), `main_window.py` (main UI).

Every merge to `main` automatically produces a release (tag with bumped minor version) via GitHub Actions (`.github/workflows/release.yml`): `Source-code.zip` plus self-contained binaries for Windows, macOS and Linux (built with PyInstaller from `label-anything.spec`, see `docs/piano-distribuzione-self-contained.md`). Local binary build: `APP_VERSION=vX.Y.Z ./scripts/build.sh`.

The optional **"Double-clickable macOS app"** section below is superseded by the release binaries, which already ship a real `Label Anything.app` bundle.

In-app inference requires the optional package: `./venv/bin/pip install ultralytics`. Without it, annotation import (YOLO/COCO/LabelMe/VOC) and everything else remain available.

## Sharing the program

Easiest: share the **release binary** for the recipient's platform — nothing to install. Alternative from source: the program folder is self-contained, just copy or zip it (without `venv/`, `__pycache__/` and the `*.progetto.json` labeling projects). Whoever receives it runs `setup` once and then `start`. Labeling data always stays in the user's images folder, never inside the program.

## License

Distributed under the MIT license: see the `LICENSE` file.
