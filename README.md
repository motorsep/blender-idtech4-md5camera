# blender-idtech4-md5camera

MD5 Camera exporter for Blender 4.2+ / 5.x. Writes `MD5Version 10`
`.md5camera` files for idTech 4 (`idCameraAnim`).

Add-on: `io_export_md5camera/` (legacy `__init__.py` + `bl_info` layout).
Install by copying the folder into Blender's `scripts/addons/`.
`MD5Camera.py` is the original Blender 3.x single-file version, kept for
reference; it is superseded.

## What it exports

- The active camera on every frame of the scene range (or the preview
  range, optional), read through the evaluated depsgraph, so Follow Path,
  Track To and parenting are honoured. Nothing in the scene is modified.
- Position (scaled by the Scale option), orientation as an idTech 4
  compressed quaternion, and horizontal FOV in degrees.
- Cuts from timeline markers. A marker bound to a camera switches the
  exported camera the way Blender's own camera binding does; a marker
  without a camera is a plain cut (single camera that teleports). The
  extra frame the engine consumes at each cut is written automatically.
  A marker on the first frame is ignored (the engine rejects cut 0).
- Frame rate defaults to the scene frame rate.

Conventions (camera basis, quaternion handedness, cut frame layout) are
documented at the top of `io_export_md5camera/__init__.py`, each derived
from the engine source.

## Verifying

```
blender.exe -b --factory-startup --python test_headless.py -- <repo_dir> <blend> <out_dir>
```

Exports `md5camera_scene521.blend` plus two synthetic scenes and re-reads
the files with an independent parser that applies the engine's loader
checks and rebuilds the view axis with `idQuat::ToMat3` transcribed.
Prints `RESULT: PASS` or `RESULT: FAIL`.
