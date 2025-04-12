bl_info = {
    "name": "FlashBlack CJ Blender Import",
    "author": "IAmMaddieFilms",
    "version": (1, 8, 0),  # Increment version
    "blender": (3, 0, 0),
    "location": "File > Import",
    "description": "Imports camera animation from FlashBlack CJ JSON files, sets end frame, converts Minecraft coordinates and rotations.",
    "category": "Import-Export",
}

import bpy
import json
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty, FloatProperty
import math


class FlashBlackImport(bpy.types.Operator, ImportHelper):
    """Import camera animation from a FlashBlack JSON file"""

    bl_idname = "import_anim.flashblack_json"
    bl_label = "Import FlashBlack CJ"

    filename_ext = ".json"

    filter_glob: StringProperty(
        default="*.json",
        options={"HIDDEN"},
        maxlen=255,
    )

    block_size_multiplier: FloatProperty(
        name="Block Size Multiplier",
        description="Multiplier to scale the camera movement (e.g., 0.1 to reduce scale) // Usually it should stay at 1",
        default=1.0,
        min=0.001,  # Avoid zero or very small values that might cause issues
    )
    
    render_width: FloatProperty(
        name="Render Width",
        description="Width of Video",
        default=1920,
        min=1,
        max=5000        # Avoid zero or very small values that might cause issues
    )
    
    render_height: FloatProperty(
        name="Render Height",
        description="Height of Video",
        default=1080,
        min=1, 
        max=5000# Avoid zero or very small values that might cause issues
    )

    def execute(self, context):
        try:
            with open(self.filepath, "r") as f:
                data = json.load(f)
            self.import_flashblack_animation(context, data, self.block_size_multiplier,self.render_height,self.render_width)
            return {"FINISHED"}
        except FileNotFoundError:
            self.report({"ERROR"}, f"File not found: {self.filepath}")
            return {"CANCELLED"}
        except json.JSONDecodeError:
            self.report({"ERROR"}, f"Invalid JSON file: {self.filepath}")
            return {"CANCELLED"}
        except Exception as e:
            self.report({"ERROR"}, f"An error occurred: {e}")
            return {"CANCELLED"}

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "block_size_multiplier")
        layout.prop(self, "render_height")
        layout.prop(self, "render_width")
        
    def calculate_horizontal_fov(ignore, vertical_fov_degrees,aspect_ratio):
        
        
        vertical_fov_radians = math.radians(vertical_fov_degrees)
        horizontal_fov_radians = 2 * math.atan(aspect_ratio * math.tan(vertical_fov_radians / 2))
        horizontal_fov_degrees = math.degrees(horizontal_fov_radians)
        return horizontal_fov_degrees
    
    

    def import_flashblack_animation(self, context, data, block_size_multiplier,render_height,render_width):
        """Imports camera animation data from the parsed JSON."""
        max_frame = 0  # Initialize the maximum frame number

        # Create a new camera object
        camera_data = bpy.data.cameras.new(name="ImportedCameraData")
        new_camera = bpy.data.objects.new("CJ Camera", camera_data)
        bpy.context.collection.objects.link(new_camera)

        # Make the new camera the active camera
        bpy.context.scene.camera = new_camera

        # Ensure there is an animation data block for the camera object
        if not new_camera.animation_data:
            new_camera.animation_data_create()

        # Process keyframes and assign consecutive frame numbers
        if "keyframes" in data:
            for frame_number, keyframe_data in enumerate(data["keyframes"]):
                blender_frame = frame_number + 1  # Blender frames start at 1
                self.import_keyframe(
                    context,
                    new_camera,
                    keyframe_data,
                    block_size_multiplier,
                    blender_frame,render_width,render_height
                )
                max_frame = max(max_frame, blender_frame)

        # Set the end frame of the playback window
        bpy.context.scene.frame_end = int(max_frame)

    def import_keyframe(
        self, context, camera_object, keyframe_data, block_size_multiplier, frame,render_width,render_height
    ):
        """Imports position, rotation, and FOV data for a specific frame."""
        try:
            # Position
            if "position" in keyframe_data:
                mc_x, mc_y, mc_z = keyframe_data["position"]

                blender_x = mc_x * block_size_multiplier

                blender_y = -mc_z * block_size_multiplier

                blender_z = mc_y * block_size_multiplier

                camera_object.location = (-blender_x, -blender_y, blender_z)

                camera_object.keyframe_insert(data_path="location", frame=frame)

            # Rotation
            if (
                "yaw" in keyframe_data
                and "pitch" in keyframe_data
                and "roll" in keyframe_data
            ):
                yaw_degrees = keyframe_data["yaw"]
                pitch_degrees = keyframe_data["pitch"]
                roll_degrees = keyframe_data.get("roll", 0.0)  # Assuming roll is 0 if not present

                # Convert degrees to radians
                yaw_rad = math.radians(yaw_degrees)
                pitch_rad = math.radians(pitch_degrees)
                roll_rad = math.radians(roll_degrees)

                # Blender uses Euler ZYX by default when assigning a tuple
                # We need to set the rotation_mode explicitly if we want a different order
                camera_object.rotation_mode = 'XYZ' # Set a default mode

                blender_pitch = math.radians(-pitch_degrees) # Negate pitch
                blender_yaw = math.radians(-yaw_degrees)   # Keep yaw negation
                blender_roll = math.radians(roll_degrees)

                camera_object.rotation_euler = (blender_pitch, blender_yaw, blender_roll)
                camera_object.keyframe_insert(data_path="rotation_euler", frame=frame)

            # FOV
            if "fov" in keyframe_data:
                fov_degrees = keyframe_data["fov"]
                sensor_width_mm = (
                    36  # Assuming a 36mm full-frame equivalent sensor width
                )
                
                camera_object.data.lens_unit = "MILLIMETERS"
                camera_object.data.sensor_fit = "AUTO"
                # Avoid division by zero if FOV is very close to 0
                if fov_degrees > 0 and fov_degrees < 180:
                
                    aspect_ratio = (render_width / render_height)
                    print(fov_degrees)
                    print(aspect_ratio)
                    sensor_width_mm = camera_object.data.sensor_width
                    blender_horizontal_fov = self.calculate_horizontal_fov(int(fov_degrees), float(aspect_ratio))
                    focal_length = sensor_width_mm / (2 * math.tan(math.radians(blender_horizontal_fov) / 2))

                    # Get or create the F-curve for data.lens
                    if not camera_object.animation_data:
                        camera_object.animation_data_create()
                    action = camera_object.animation_data.action
                    if not action:
                        action = bpy.data.actions.new(
                            name=camera_object.name + "_Action"
                        )
                        camera_object.animation_data.action = action

                    fcurve = action.fcurves.find(data_path="data.lens")
                    if fcurve is None:
                        fcurve = action.fcurves.new(data_path="data.lens")

                    # Insert keyframe
                    fcurve.keyframe_points.insert(
                        frame=frame, value=focal_length
                    )

        except ValueError as e:
            self.report({"WARNING"}, f"Error processing keyframe at frame {frame}: {e}")
        except Exception as e:
            self.report({"ERROR"}, f"Error processing keyframe: {e}")


def menu_func_import(self, context):
    self.layout.operator(FlashBlackImport.bl_idname, text="FlashBlack Camera (.json)")


def register():
    bpy.utils.register_class(FlashBlackImport)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
    bpy.utils.unregister_class(FlashBlackImport)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)


if __name__ == "__main__":
    register()

    # For testing purposes, you can run this part if you want to directly execute the script
    # bpy.ops.import_anim.flashblack_json('INVOKE_DEFAULT')
