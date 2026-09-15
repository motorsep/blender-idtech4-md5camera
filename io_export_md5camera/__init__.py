# ***** BEGIN GPL LICENSE BLOCK *****
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
# ***** END GPL LICENCE BLOCK *****

bl_info = {
    "name": "idTech 4 MD5Camera Exporter",
    "author": "MCampagnini, motorsep/Claude",
    "version": (2, 0, 0),
    "blender": (4, 2, 0),
    "location": "File > Export > idTech 4 MD5 Camera (.md5camera)",
    "description": "Export the scene camera animation to idTech 4 .md5camera",
    "warning": "",
    "wiki_url": "",
    "tracker_url": "",
    "category": "Import-Export",
}

"""
idTech 4 MD5Camera Exporter

Samples the active camera on every frame of the scene (or preview) range
and writes an MD5Version 10 .md5camera file as read by idCameraAnim::LoadAnim.

Non-destructive: the scene is stepped through its frames with frame_set()
and read back through the evaluated depsgraph; nothing is keyed, no rotation
modes are touched, and the original current frame is restored afterwards.
Constraints (Follow Path, Track To, parenting) are therefore honoured for
free because the evaluated world matrix already contains them.

Conventions, all derived from the engine source:

* Camera basis. A Blender camera looks down its local -Z with +Y up and
  +X to the right. An idTech 4 view axis is rows [forward, left, up] =
  [+X, +Y, +Z]. So forward = -Z, left = -X, up = +Y of the camera's world
  rotation.

* Quaternion. idQuat::ToMat3 uses the same element formula as a standard
  column-major rotation matrix, but the engine reads the RESULT'S ROWS as
  the axes. The engine quaternion for axes (f, l, u) is therefore the
  standard quaternion of the matrix whose rows are (f, l, u), which is the
  conjugate of the quaternion Blender would report for the same frame.
  The file stores an idCQuat: x y z only, with w >= 0 implied, so a
  quaternion with negative w is negated first.

* Cuts. The engine consumes one file frame per cut: playback lasts
  (numFrames - numCuts) frames and at cut index k it lerps file frame k-1
  towards k, then jumps to k+1. So every cut needs an extra frame written
  at the cut index. This exporter emits, for a cut at scene frame F, the
  previous shot's pose at F (the outgoing camera evaluated at F when the
  camera object changes, otherwise a hold of frame F-1) followed by the
  new shot's pose at F. Cut index = (F - frame_start) + number of earlier
  cuts. A marker on the first frame is not a cut (the engine rejects cut 0).

* Cameras. The camera on a given frame follows Blender's own marker
  binding rule: the latest camera-bound marker at or before the frame,
  else the earliest camera-bound marker, else scene.camera. Every marker
  inside the range is a cut, bound to a camera or not, so a single camera
  that teleports can be cut with a plain marker.

* FOV. The engine's fov_x is the horizontal field of view in degrees;
  Blender's camera.angle_x is that value for a perspective camera.
"""

import time
from math import degrees, sqrt

import bpy
from bpy.props import BoolProperty, FloatProperty, IntProperty, StringProperty
from bpy_extras.io_utils import ExportHelper
from mathutils import Matrix, Vector


MD5_VERSION = 10


# =============================================================================
# Math
# =============================================================================

def engine_orientation(matrix_world):
    """Return the idCQuat (x, y, z) for a camera object's world matrix."""
    rot = matrix_world.to_3x3()
    rot.normalize()  # strip any scale, columns become unit axis directions

    forward = -rot.col[2]
    left = -rot.col[0]
    up = rot.col[1]

    # Matrix((...)) takes rows. A matrix whose rows are the engine axes is
    # the transpose of Blender's columns-are-axes form, and its standard
    # quaternion is exactly what idQuat::ToMat3 reproduces (see module doc).
    q = Matrix((forward, left, up)).to_quaternion()
    if q.w < 0.0:
        q.negate()
    return (q.x, q.y, q.z)


def camera_at_frame(scene, frame):
    """Blender's marker camera-binding rule, evaluated explicitly."""
    bound = [m for m in scene.timeline_markers if m.camera is not None]
    if not bound:
        return scene.camera
    before = [m for m in bound if m.frame <= frame]
    if before:
        return max(before, key=lambda m: m.frame).camera
    return min(bound, key=lambda m: m.frame).camera


# =============================================================================
# Builder
# =============================================================================

class MD5CameraBuilder:
    """Samples the scene into (position, cquat, fov) frames plus cut indices."""

    def __init__(self, context, options):
        self.context = context
        self.scene = context.scene
        self.options = options
        self.frames = []
        self.cuts = []

    def sample(self, cam_obj, depsgraph):
        cam_eval = cam_obj.evaluated_get(depsgraph)
        mw = cam_eval.matrix_world
        pos = mw.to_translation() * self.options['scale']
        quat = engine_orientation(mw)
        if cam_eval.data.type != 'PERSP':
            print(f"MD5Camera: camera '{cam_obj.name}' is not perspective, "
                  f"fov will be meaningless")
        fov = degrees(cam_eval.data.angle_x)
        return (Vector(pos), quat, fov)

    def frame_range(self):
        scene = self.scene
        if self.options['preview_range'] and scene.use_preview_range:
            return scene.frame_preview_start, scene.frame_preview_end
        return scene.frame_start, scene.frame_end

    def build(self):
        scene = self.scene
        frame_start, frame_end = self.frame_range()
        if frame_end < frame_start:
            raise RuntimeError('Frame range is empty')

        cut_frames = set()
        if self.options['cuts']:
            cut_frames = {m.frame for m in scene.timeline_markers
                          if frame_start < m.frame <= frame_end}

        original_frame = scene.frame_current
        prev_cam = None
        try:
            for frame in range(frame_start, frame_end + 1):
                scene.frame_set(frame)
                depsgraph = self.context.evaluated_depsgraph_get()

                cam = camera_at_frame(scene, frame)
                if cam is None:
                    raise RuntimeError('Scene has no active camera')

                if frame in cut_frames:
                    # Extra frame the engine consumes at the cut: the
                    # outgoing shot continued to this frame.
                    if prev_cam is not None and prev_cam != cam:
                        self.frames.append(self.sample(prev_cam, depsgraph))
                    else:
                        self.frames.append(self.frames[-1])
                    self.cuts.append(len(self.frames) - 1)

                self.frames.append(self.sample(cam, depsgraph))
                prev_cam = cam
        finally:
            scene.frame_set(original_frame)

        return self.format()

    def format(self):
        opt = self.options
        out = []
        out.append(f'MD5Version {MD5_VERSION}\n')
        out.append(f'commandline "{opt["command_line"]}"\n\n')
        out.append(f'numFrames {len(self.frames)}\n')
        out.append(f'frameRate {opt["frame_rate"]}\n')
        out.append(f'numCuts {len(self.cuts)}\n\n')

        out.append('cuts {\n')
        for cut in self.cuts:
            out.append(f'\t{cut}\n')
        out.append('}\n\n')

        out.append('camera {\n')
        for pos, quat, fov in self.frames:
            out.append(
                f'\t( {pos.x:.10f} {pos.y:.10f} {pos.z:.10f} ) '
                f'( {quat[0]:.10f} {quat[1]:.10f} {quat[2]:.10f} ) '
                f'{fov:.2f}\n')
        out.append('}\n')
        return ''.join(out)


# =============================================================================
# Operator
# =============================================================================

class ExportMD5Camera(bpy.types.Operator, ExportHelper):
    """Export the scene camera animation to idTech 4 .md5camera"""
    bl_idname = "export_scene.md5camera"
    bl_label = "Export MD5 Camera"
    bl_options = {'PRESET'}
    filename_ext = ".md5camera"
    filter_glob: StringProperty(default="*.md5camera", options={'HIDDEN'})

    filepath: StringProperty(
        name="File Path",
        description="Output file path",
        maxlen=1024,
        default="",
    )

    option_frame_rate: IntProperty(
        name="Frame Rate",
        description=(
            "Playback rate written to the file. Defaults to the scene "
            "frame rate; the engine plays one file frame per 1/rate second"
        ),
        min=1,
        max=240,
        default=24,
    )

    option_scale: FloatProperty(
        name="Scale",
        description=(
            "Multiply camera positions by this factor. "
            "idTech 4 uses roughly 1 unit = 1 inch. "
            "Default 1.0 exports at Blender's native scale"
        ),
        min=0.001,
        max=10000.0,
        soft_min=0.01,
        soft_max=1000.0,
        default=1.0,
    )

    option_cuts: BoolProperty(
        name="Cuts from Markers",
        description=(
            "Every timeline marker inside the exported range becomes a "
            "camera cut. Markers bound to a camera also switch the exported "
            "camera, like Blender's own camera binding"
        ),
        default=True,
    )

    option_preview_range: BoolProperty(
        name="Use Preview Range",
        description=(
            "Export the timeline preview range instead of the scene range "
            "when a preview range is active"
        ),
        default=False,
    )

    option_command_line: StringProperty(
        name="Command Line",
        description="Text written to the commandline field; the engine ignores it",
        maxlen=1024,
        default="",
    )

    def draw(self, context):
        layout = self.layout

        box = layout.box()
        box.label(text='Timing:')
        box.prop(self, 'option_frame_rate')
        box.prop(self, 'option_cuts')
        box.prop(self, 'option_preview_range')

        box = layout.box()
        box.label(text='Transform:')
        box.prop(self, 'option_scale')

        box = layout.box()
        box.label(text='Header:')
        box.prop(self, 'option_command_line')

    @classmethod
    def poll(cls, context):
        scene = context.scene
        if scene.camera is not None:
            return True
        return any(m.camera is not None for m in scene.timeline_markers)

    def invoke(self, context, event):
        if not self.properties.is_property_set('option_frame_rate'):
            render = context.scene.render
            self.option_frame_rate = max(1, round(render.fps / render.fps_base))
        return ExportHelper.invoke(self, context, event)

    def execute(self, context):
        start = time.perf_counter()

        options = {
            'frame_rate': self.option_frame_rate,
            'scale': self.option_scale,
            'cuts': self.option_cuts,
            'preview_range': self.option_preview_range,
            'command_line': self.option_command_line,
        }

        try:
            builder = MD5CameraBuilder(context, options)
            data = builder.build()
            self._write_file(self.filepath, data)
        except RuntimeError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}

        elapsed = time.perf_counter() - start
        msg = (f'MD5Camera export: {len(builder.frames)} frames, '
               f'{len(builder.cuts)} cuts in {elapsed:.3f}s')
        print(msg)
        self.report({'INFO'}, msg)
        return {'FINISHED'}

    def _write_file(self, filepath, data):
        print(f'Writing: {filepath}')
        try:
            with open(filepath, 'w', newline='\n') as f:
                f.write(data)
        except IOError as e:
            raise RuntimeError(f'Could not write file: {filepath}\n{e}')


# =============================================================================
# Registration
# =============================================================================

def menu_func_export(self, context):
    self.layout.operator(ExportMD5Camera.bl_idname,
                         text="idTech 4 MD5 Camera (.md5camera)")


def register():
    bpy.utils.register_class(ExportMD5Camera)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
    bpy.utils.unregister_class(ExportMD5Camera)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)


if __name__ == "__main__":
    register()
