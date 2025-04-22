bl_info = {
    "name": "FlashBlack CJ/ET Blender Import",
    "author": "IAmMaddieFilms",
    "version": (1, 8, 1),  # Increment version
    "blender": (3, 0, 0),
    "location": "File > Import",
    "description": "Imports camera animation and tracking data from FlashBlack CJ/ET JSON files, sets end frame, converts Minecraft coordinates and rotations.",
    "category": "Import-Export",
}

import bpy
import json
import os
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty, FloatProperty, EnumProperty
import math


class FlashBlackImport(bpy.types.Operator, ImportHelper):
    """Import camera animation from a FlashBlack JSON file"""

    bl_idname = "import_anim.flashblack_json"
    bl_label = "Import FlashBlack CJ/ET"

    filename_ext = ".json"

    filter_glob: StringProperty(
        default="*.json",
        options={"HIDDEN"},
        maxlen=255,
    )

    import_type: EnumProperty(
        name="Import",
        description="Choose what to import from the FlashBlack JSON file.",
        items=(
            ('CJ', "CJ Camera", "Import camera animation data."),
            ('TJ', "TJ Animation", "Import entity animation data."),
            ('BOTH', "Both", "Import both camera and entity animation data."),
        ),
        default='BOTH',
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
        max=5000      # Avoid zero or very small values that might cause issues
    )

    render_height: FloatProperty(
        name="Render Height",
        description="Height of Video",
        default=1080,
        min=1,
        max=5000# Avoid zero or very small values that might cause issues
    )

    def execute(self, context):
        cj_data = None
        tj_data = None
        success = True
        directory = os.path.dirname(self.filepath)
        base_name, ext = os.path.splitext(os.path.basename(self.filepath))

        modified_base_name = base_name[:-2] if len(base_name) >= 2 else base_name

        cj_filepath = os.path.join(directory, modified_base_name + "CJ" + ext)
        tj_filepath = os.path.join(directory, modified_base_name + "ET" + ext)

        if self.import_type == 'CJ' or self.import_type == 'BOTH':
            try:
                with open(cj_filepath, "r") as f:
                    cj_data = json.load(f)
            except FileNotFoundError:
                self.report({"ERROR"}, f"CJ JSON File not found: {cj_filepath}")
                success = False
            except json.JSONDecodeError:
                self.report({"ERROR"}, f"Invalid CJ JSON file: {cj_filepath}")
                success = False

        if self.import_type == 'TJ' or self.import_type == 'BOTH':
            try:
                with open(tj_filepath, "r") as f:
                    tj_data = json.load(f)
            except FileNotFoundError:
                self.report({"ERROR"}, f"ET JSON File not found: {tj_filepath}")
                success = False
            except json.JSONDecodeError:
                self.report({"ERROR"}, f"Invalid ET JSON file: {tj_filepath}")
                success = False

        if not success:
            return {"CANCELLED"}

        if self.import_type == 'CJ' and cj_data:
            self.import_flashblack_animation(context, cj_data, self.block_size_multiplier, self.render_height, self.render_width)
        elif self.import_type == 'TJ' and tj_data:
            self.import_tracking_animation(context, tj_data, self.block_size_multiplier)
        elif self.import_type == 'BOTH' and cj_data and tj_data:
            self.import_flashblack_animation(context, cj_data, self.block_size_multiplier, self.render_height, self.render_width)
            self.import_tracking_animation(context, tj_data, self.block_size_multiplier)
        elif self.import_type == 'BOTH' and (not cj_data or not tj_data):
            self.report({"ERROR"}, "Both CJ and ET JSON files are required for 'Both' import.")
            return {"CANCELLED"}

        return {"FINISHED"}

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "import_type")
        layout.prop(self, "block_size_multiplier")

        if self.import_type == 'CJ' or self.import_type == 'BOTH':
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
            
            
    def import_tracking_animation(self, context, data, block_size_multiplier):
        """Imports entity tracking animation data from the parsed JSON."""
        if 'Entities' not in data:
            self.report({"ERROR"}, "TJ JSON file does not contain 'Entities' data.")
            return

        max_frame = 0

        for frame_data in data['Entities']:
            for entity_name, entity_parts in frame_data.items():
                if entity_name == 'tick':
                    continue  # Skip the tick entry here, process later

                tick = frame_data.get('tick', -1)
                if tick == -1:
                    self.report({"WARNING"}, f"Frame missing 'tick' information: {frame_data}")
                    continue

                frame_number = int(tick) + 1

                parent_empty_name = f"{entity_name}_Animation"
                parent_empty = bpy.data.objects.get(parent_empty_name)
                if not parent_empty or parent_empty.type != 'EMPTY':
                    parent_empty = bpy.data.objects.new(parent_empty_name, None)
                    bpy.context.collection.objects.link(parent_empty)

                for part_name_json, transform_data in entity_parts.items():
                    if part_name_json.lower() == "eyes":
                        eye_position = transform_data.get("eyePosition")
                        if eye_position:
                            eye_empty_name = f"{parent_empty_name}_eyePosition"
                            eye_empty = bpy.data.objects.get(eye_empty_name)
                            if not eye_empty or eye_empty.type != 'EMPTY':
                                eye_empty = bpy.data.objects.new(eye_empty_name, None)
                                bpy.context.collection.objects.link(eye_empty)
                                

                            ex, ey, ez = eye_position
                            
                            blender_x = ex * block_size_multiplier

                            blender_y = -ez * block_size_multiplier

                            blender_z = ey * block_size_multiplier

                

                            eye_empty.location = (-blender_x, -blender_y, blender_z)
                            eye_empty.keyframe_insert(data_path="location", frame=frame_number)
                            
                            eye_angle_data = transform_data.get("eyeangle")
                            if eye_angle_data and len(eye_angle_data) == 3:
                                blender_pitch = math.radians(-eye_angle_data[0]) # Source X -> Blender -X
                                blender_yaw = math.radians(-eye_angle_data[1])   # Source Y -> Blender -Z
                                blender_roll = math.radians(eye_angle_data[2])  # Source Z -> Blender +Y
                                eye_empty.rotation_mode = 'XYZ' # Start with XYZ, adjust if needed

                                # Apply the converted rotations
                                eye_empty.rotation_euler = (blender_pitch, blender_roll, blender_yaw)
                                eye_empty.keyframe_insert(data_path="rotation_euler", frame=frame_number)


                    elif part_name_json.lower() == "blockposition":
                        block_position = transform_data.get("blockPosition")
                        if block_position:
                            bp_x, bp_y, bp_z = block_position
                            
                            blender_x = bp_x * block_size_multiplier

                            blender_y = -bp_z * block_size_multiplier

                            blender_z = bp_y * block_size_multiplier
                            parent_empty.location = (-blender_x, -blender_y, blender_z)
                            parent_empty.keyframe_insert(data_path="location", frame=frame_number)
                            
                    

                    else:  # Handle other parts with rotation and position
                        rotation = transform_data.get("rotation")
                        position = transform_data.get("position")

                        empty_object_name = f"{parent_empty_name}_{part_name_json}"
                        empty_object = bpy.data.objects.get(empty_object_name)
                        if not empty_object or empty_object.type != 'EMPTY':
                            empty_object = bpy.data.objects.new(empty_object_name, None)
                            bpy.context.collection.objects.link(empty_object)
                            empty_object.parent = parent_empty

                        if position:
                            px, py, pz = position
                            empty_object.location = (px * block_size_multiplier, py * block_size_multiplier, pz * block_size_multiplier)
                            empty_object.keyframe_insert(data_path="location", frame=frame_number)

                        if rotation:
                            rotation_rad = [r for r in rotation]
                            
                            
                            
                            # Convert degrees to radians
                            yaw_rad = rotation_rad[2]
                            pitch_rad = rotation_rad[0]
                            roll_rad = rotation_rad[1]

                            # Blender uses Euler ZYX by default when assigning a tuple
                            # We need to set the rotation_mode explicitly if we want a different order
                            empty_object.rotation_mode = 'XYZ' # Set a default mode

                            blender_pitch = -pitch_rad # Negate pitch
                            blender_yaw = -yaw_rad   # Keep yaw negation
                            blender_roll = roll_rad

                            empty_object.rotation_euler = (blender_pitch, blender_yaw, -blender_roll)
                            empty_object.keyframe_insert(data_path="rotation_euler", frame=frame_number)

                max_frame = max(max_frame, frame_number)

        bpy.context.scene.frame_end = max(bpy.context.scene.frame_end, max_frame)



def menu_func_import(self, context):
    self.layout.operator(FlashBlackImport.bl_idname, text="FlashBlack Camera/Tracking (.json)")


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
