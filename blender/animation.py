"""blender/animation.py — Code-gen helpers for Blender animation (bpy strings)."""


class AnimationBuilder:
    def set_keyframe(self, obj_name, frame, location=None, rotation=None, scale=None):
        lines = [
            "import bpy",
            f"obj = bpy.data.objects['{obj_name}']",
            f"bpy.context.scene.frame_set({frame})",
        ]
        if location:
            x, y, z = location
            lines.append(f"obj.location = ({x}, {y}, {z})")
            lines.append("obj.keyframe_insert(data_path='location')")
        if rotation:
            x, y, z = rotation
            lines.append(f"obj.rotation_euler = ({x}, {y}, {z})")
            lines.append("obj.keyframe_insert(data_path='rotation_euler')")
        if scale:
            x, y, z = scale
            lines.append(f"obj.scale = ({x}, {y}, {z})")
            lines.append("obj.keyframe_insert(data_path='scale')")
        lines.append(f"print('Keyframe set at frame {frame}')")
        return "\n".join(lines) + "\n"

    def set_frame_range(self, start=1, end=250, fps=24):
        return (
            "import bpy\n"
            f"bpy.context.scene.frame_start = {start}\n"
            f"bpy.context.scene.frame_end   = {end}\n"
            f"bpy.context.scene.render.fps  = {fps}\n"
            f"print('Frame range {start}-{end} @ {fps}fps')\n"
        )

    def add_driver(self, obj_name, data_path, index, expr):
        return (
            "import bpy\n"
            f"obj = bpy.data.objects['{obj_name}']\n"
            f"drv = obj.driver_add('{data_path}', {index}).driver\n"
            "drv.type = 'SCRIPTED'\n"
            f"drv.expression = '{expr}'\n"
            "print('Driver added')\n"
        )

    def add_constraint(self, obj_name, constraint_type, target_name=""):
        target_line = (
            f"c.target = bpy.data.objects['{target_name}']\n"
            if target_name else ""
        )
        return (
            "import bpy\n"
            f"obj = bpy.data.objects['{obj_name}']\n"
            f"c   = obj.constraints.new(type='{constraint_type}')\n"
            + target_line +
            "print('Constraint added')\n"
        )
