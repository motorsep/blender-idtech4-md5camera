## ***** BEGIN GPL LICENSE BLOCK ***** 
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
    "author": "MCampagnini",
    "version": ( 1, 0, 1 ),
    "blender": ( 2, 6, 4 ),
    "api": 36079,
    "location": "File > Export > My Addon",
    "description": "Converts a Blender scene into an md5camera format",
    "warning": "",
    "wiki_url": "",
    "tracker_url": "",
    "category": "Import-Export"
}

"""
--  Notes
"""

import os
import bpy
import mathutils
from mathutils import *
from math import *
import time
from decimal import *

# settings
optionCommandLine = ''
optionFPS = 24
optionRotation = 'QUATERNION'
optionScale = 1.0
optionUnit = 'RADIANS'
optionKeyframeAll = False
optionInvertX = False
optionInvertY = False
optionInvertZ = False
optionUsePath = False

framerange = range( 0 )

#== Error ==================================================================
class Error( Exception ):

    def __init__( self, message ):
        self.message = message
        print( '\n\n' + message + '\n\n' )

#== Header =================================================================
class cHeader:
    def __init__( self ):
        print( '\tBuilding Header' )
        global optionCommandLine

        self.versionNum = 10
        self.version = "MD5Version {0}".format( str( self.versionNum ) )
        self.commandLine = "commandline \"{0}\"".format( optionCommandLine )

    def __repr__( self ):
        return "{0}\n{1}\n\n".format( self.version, self.commandLine )

#== Parameters =================================================================
class cParameters:
    def __init__( self ):
        print( '\tBuilding Parameters' )
        global optionFPS
        scene = bpy.context.scene
        self.numFrames = bpy.context.scene.frame_end - bpy.context.scene.frame_start
        self.frameRate = optionFPS
        self.numCuts = len( scene.timeline_markers )

    def __repr__( self ):
        return "numFrames {0}\nframeRate {1}\nnumCuts {2}\n\n".format( self.numFrames, self.frameRate, str( self.numCuts ) )

#== Cuts =================================================================
class cCuts:
    def __init__( self ):
        print( '\tBuilding Cuts' )
        scene = bpy.context.scene
        self.cuts = ''

        for cut in scene.timeline_markers:
            self.cuts += '{0}\n'.format( str(int(cut.frame)-1) )

    def __repr__( self ):
        return "cuts {{\n{0}}}\n\n".format( self.cuts )

#== Camera =================================================================
class cCamera:
    def __init__( self ):
        global optionScale
        print( '\tBuilding Camera Data (Scale: {0})'.format( optionScale ) )
        global framerange
        global optionKeyframeAll
        self.dump = ''

        #( [X Pos] [Y Pos] [Z Pos] ) ( [Orientation] ) [FOV]

        # Get camera
        camera = get_camera()
        scene = bpy.context.scene

        for obj in scene.objects:
            if obj.type == 'CAMERA':
                camera = obj
                break

        # If no camera exists
        if camera == None:
            raise Error( 'Error:  Scene does not have a camera!' )

        # Get camera data for every frame in the scene
        for frame in framerange:
            scene.frame_set( frame )
            if optionKeyframeAll:
                bpy.ops.anim.keyframe_insert( type = 'LocRotScale' )
            self.dump += self.getData( camera )

    def getData( self, camera ):
        pos = self.getPos( camera )
        ori = self.getOri( camera )
        fov = self.getFov( camera )

        return "\t( {0} ) ( {1} ) {2}\n".format( pos, ori, fov )

    # Get X, Y, and Z
    def getPos( self, camera ):
        global optionScale
        global optionUsePath

        if optionUsePath:
            posx = camera.matrix_world.to_translation().x * optionScale
            posy = camera.matrix_world.to_translation().y * optionScale
            posz = camera.matrix_world.to_translation().z * optionScale
        else:
            posx = camera.location[0] * optionScale
            posy = camera.location[1] * optionScale
            posz = camera.location[2] * optionScale

        return "{0:.10f} {1:.10f} {2:.10f}".format( posx, posy, posz )

    def getOri( self, camera ):
        global optionRotation
        global optionUnit
        global optionFlipX
        global optionFlipY
        global optionFlipZ
        global optionInvertX
        global optionInvertY
        global optionInvertZ
        global optionUsePath

        # UPDATE CAMERA ROTATION
        camera.rotation_mode = 'QUATERNION'
        camera.rotation_mode = 'AXIS_ANGLE'
        camera.rotation_mode = 'XYZ'
        camera.rotation_mode = optionRotation

        toDegrees = Decimal( 180 / pi )
        #toRadians = Decimal( pi / 180 )

        # IF EULER
        if optionRotation == 'EULER':
            if optionUnit == 'DEGREES':
                if optionUsePath:
                    rotx = camera.matrix_world.to_euler().x * toDegrees
                    roty = camera.matrix_world.to_euler().y * toDegrees
                    rotz = camera.matrix_world.to_euler().z * toDegrees
                else:
                    rotx = camera.rotation_euler[0] * toDegrees
                    roty = camera.rotation_euler[1] * toDegrees
                    rotz = camera.rotation_euler[2] * toDegrees
            else:
                if optionUsePath:
                    rotx = camera.matrix_world.to_euler().x
                    roty = camera.matrix_world.to_euler().y
                    rotz = camera.matrix_world.to_euler().z
                else:
                    rotx = camera.rotation_euler[0]
                    roty = camera.rotation_euler[1]
                    rotz = camera.rotation_euler[2]
        # IF QUATERNION, ignore [0] (W)
        else:
            if optionUnit == 'DEGREES':
                if optionUsePath:
                    rotx = camera.matrix_world.to_quaternion().x * toDegrees
                    roty = camera.matrix_world.to_quaternion().y * toDegrees
                    rotz = camera.matrix_world.to_quaternion().z * toDegrees
                else:
                    rotx = camera.rotation_quaternion[1] * toDegrees
                    roty = camera.rotation_quaternion[2] * toDegrees
                    rotz = camera.rotation_quaternion[3] * toDegrees
            else:
                if optionUsePath:
                    rotx = camera.matrix_world.to_quaternion().x
                    roty = camera.matrix_world.to_quaternion().y
                    rotz = camera.matrix_world.to_quaternion().z
                else:
                    rotx = camera.rotation_quaternion[1]
                    roty = camera.rotation_quaternion[2]
                    rotz = camera.rotation_quaternion[3]

        if optionInvertX:
            rotx *= -1
        if optionInvertY:
            roty *= -1
        if optionInvertZ:
            rotz *= -1

        return "{0:.10} {1:.10} {2:.10}".format( rotx, roty, rotz )

    def getFov( self, camera ):
        fov = camera.data.angle * 180 / pi

        return"{0:.2f}".format( fov )

    def __repr__( self ):
        return "camera {{\n{0}}}\n".format( self.dump )

#== Core ===================================================================
from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty, BoolProperty, FloatProperty, IntProperty, EnumProperty

class Export( bpy.types.Operator, ExportHelper ):
    bl_idname = "export.md5camera"
    bl_label = "Export"
    __doc__ = "MD5 Camera Exporter (.md5camera)"
    filename_ext = ".md5camera"
    filter_glob = StringProperty( default = "*.md5camera", options = {'HIDDEN'} )

    # Scene FPS Value
    #fps = bpy.context.scene.render.fps    
    #fps = bpy.context.scene.fps    
    fps = 30

    filepath = StringProperty(
        name = "File Path",
        description = "Export path",
        maxlen = 1024,
        default = "" )

    option_scale = FloatProperty(
        name = "Scale",
        description = "Scale camera position",
        default = 1,
        min = 0.1,
        max = 1000 )

    option_keyframeall = BoolProperty(
        name = "Keyframe All",
        description = "Keyframe every frame",
        default = False )

    option_invertx = BoolProperty(
        name = "Invert X",
        description = "Invert X",
        default = True )

    option_inverty = BoolProperty(
        name = "Invert Y",
        description = "Invert Y",
        default = True )

    option_invertz = BoolProperty(
        name = "Invert Z",
        description = "Invert Z",
        default = True )

    option_usepath = BoolProperty(
        name = "Use Path Constraint",
        description = "Using path as a constraint",
        default = False )

    option_fps = IntProperty(
        name = "FPS",
        description = "Frames per second",
        min = 1,
        max = 100,
        soft_min = 1,
        soft_max = 100,
        default = fps )

    option_commandline = StringProperty(
        name = "",
        description = "Parameters passed to the exportmodels console command",
        maxlen = 1024,
        default = "" )

    option_rotation = EnumProperty(
        items = [( 'QUATERNION', 'QUATERNION', 'QUATERNION' ),
                 ( 'EULER', 'EULER', 'EULER' )],
        name = "" )

    option_unit = EnumProperty(
        items = [( 'RADIANS', 'RADIANS', 'RADIANS' ),
                 ( 'DEGREES', 'DEGREES', 'DEGREES' )],
        name = "Unit" )

    def draw( self, context ):
        layout = self.layout
        box = layout.box()
        box.label( 'General:' )
        box.prop( self, 'option_fps' )
        box.prop( self, 'option_scale' )
        box.prop( self, 'option_unit' )
        box.prop( self, 'option_keyframeall' )
        box.prop( self, 'option_usepath' )
        box.label( 'Command Line:' )
        box.prop( self, 'option_commandline' )
        box.label( 'Rotation:' )
        box.prop( self, 'option_rotation' )
        box.prop( self, 'option_invertx' )
        box.prop( self, 'option_inverty' )
        box.prop( self, 'option_invertz' )
        #box.prop( self, 'option_selectedframes' )

    @classmethod
    def poll( cls, context ):
        active = context.active_object
        selected = context.selected_objects
        camera = context.scene.camera
        ok = selected or camera
        return ok

    def write( self, filename, data ):
        print( '\nWriting', filename )
        try:
            file = open( filename, 'w' )
        except IOError:
            print( 'Error: The file could not be written to. Aborting.' )
        else:
            file.write( data )
            file.close()

    def execute( self, context ):
        print( 'MCampagnini MD5Camera Exporter\n' )
        start = time.clock()
        # Declare globals
        global optionCommandLine
        global optionFPS
        global optionInvertX
        global optionInvertY
        global optionInvertZ
        global optionRotation
        global optionScale
        global optionUnit
        global optionKeyframeAll
        global optionUsePath
        global framerange

        # Initialize globals
        optionCommandLine = self.option_commandline
        optionFPS = self.option_fps
        optionRotation = self.option_rotation
        optionScale = self.option_scale
        optionUnit = self.option_unit
        optionKeyframeAll = self.option_keyframeall
        optionInvertX = self.option_invertx
        optionInvertY = self.option_inverty
        optionInvertZ = self.option_invertz
        optionUsePath = self.option_usepath

        # Frame range
        framestart = bpy.context.scene.frame_start
        frameend = bpy.context.scene.frame_end
        framerange = range( framestart, frameend )

        # Get data
        header = str( cHeader() )
        parameters = str( cParameters() )
        cuts = str( cCuts() )
        camera = str( cCamera() )

        # Save
        model = header
        model += parameters
        model += cuts
        model += camera

        self.write( self.filepath, model )

        lapse = ( time.clock() - start )
        print( 'Completed in ' + str( lapse ) + ' seconds' )

        return {'FINISHED'}

def get_camera():
    scene = bpy.context.scene
    camera = None

    # Get camera
    for obj in scene.objects:
        if obj.type == 'CAMERA':
            camera = obj
            break

    # If no camera exists
    if camera == None:
        raise Error( 'Error:  Scene does not have a camera!' )
    else:
        return camera

def menu_func( self, context ):
    self.layout.operator( Export.bl_idname, text = "idTech 4 MD5Camera Export", icon='BLENDER' )

def register():
    bpy.utils.register_class( Export )
    bpy.types.INFO_MT_file_export.append( menu_func )

def unregister():
    bpy.utils.unregister_class( Export )
    bpy.types.INFO_MT_file_export.remove( menu_func )

if __name__ == "__main__":
    register()
