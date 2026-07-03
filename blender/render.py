"""blender/render.py — Code-gen helpers for Blender rendering (bpy strings)."""


class RenderBuilder:
    def set_engine(self, engine="CYCLES", blender_major=5):
        if engine == "EEVEE" and blender_major >= 5:
            engine = "BLENDER_EEVEE_NEXT"
        elif engine == "EEVEE":
            engine = "BLENDER_EEVEE"
        elif engine == "WORKBENCH":
            engine = "BLENDER_WORKBENCH"
        return (
            "import bpy\n"
            f"bpy.context.scene.render.engine = '{engine}'\n"
            f"print('Render engine: {engine}')\n"
        )

    def set_resolution(self, width=1920, height=1080, pct=100):
        return (
            "import bpy\n"
            f"bpy.context.scene.render.resolution_x          = {width}\n"
            f"bpy.context.scene.render.resolution_y          = {height}\n"
            f"bpy.context.scene.render.resolution_percentage = {pct}\n"
        )

    def set_output(self, filepath, fmt="PNG"):
        return (
            "import bpy\n"
            f"bpy.context.scene.render.filepath       = r'{filepath}'\n"
            f"bpy.context.scene.render.image_settings.file_format = '{fmt}'\n"
        )

    def set_samples(self, samples=128):
        return (
            "import bpy\n"
            "scene = bpy.context.scene\n"
            "eng   = scene.render.engine\n"
            "if eng == 'CYCLES':\n"
            f"    scene.cycles.samples = {samples}\n"
            "else:\n"
            f"    scene.eevee.taa_render_samples = {samples}\n"
        )

    def render_still(self, output_path=""):
        write_line = (
            f"bpy.context.scene.render.filepath = r'{output_path}'\n"
            if output_path else ""
        )
        return (
            "import bpy\n"
            + write_line +
            "bpy.ops.render.render(write_still=True)\n"
            "print('Render complete')\n"
        )

    def render_animation(self, start=None, end=None):
        lines = ["import bpy"]
        if start is not None:
            lines.append(f"bpy.context.scene.frame_start = {start}")
        if end is not None:
            lines.append(f"bpy.context.scene.frame_end = {end}")
        lines.append("bpy.ops.render.render(animation=True)")
        lines.append("print('Animation render complete')")
        return "\n".join(lines) + "\n"
