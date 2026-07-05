"""
pipeline/workflow_catalog.py
Named workflow templates with pre-filled prompts and skill hints.
Skill hints are injected into the system prompt to reduce hallucination.
"""

WORKFLOWS: dict[str, dict] = {
    "polyhaven_asset": {
        "name": "Import PolyHaven Asset",
        "prompt_template": "Download a PolyHaven HDRI or texture asset and apply it to the scene",
        "skill_hint": (
            "Use MCP tools in this order: get_polyhaven_categories → "
            "search_polyhaven_assets → download_polyhaven_asset. "
            "Apply textures via bpy.ops.image.open and material nodes."
        ),
    },
    "hyper3d_from_image": {
        "name": "Generate 3D from Image (Hyper3D Rodin)",
        "prompt_template": (
            "Generate a 3D model from the attached reference image using "
            "Hyper3D Rodin and import it into the scene"
        ),
        "skill_hint": (
            "Call generate_hyper3d_model_via_images with the image path, "
            "then poll_rodin_job_status until complete, "
            "then import_generated_asset to bring the mesh into Blender."
        ),
    },
    "godot_export": {
        "name": "Export Scene to Godot (glTF)",
        "prompt_template": (
            "Apply all transforms, verify PBR materials, and export the "
            "scene as glTF 2.0 to the output directory"
        ),
        "skill_hint": (
            "Apply Ctrl+A transforms with bpy.ops.object.transform_apply. "
            "Ensure all materials use Principled BSDF. "
            "Export with bpy.ops.export_scene.gltf(filepath=..., export_format='GLB')."
        ),
    },
    "pbr_from_image": {
        "name": "PBR Material from Reference Image",
        "prompt_template": (
            "Create a PBR Principled BSDF material that visually matches "
            "the attached reference image and apply it to the selected object"
        ),
        "skill_hint": (
            "Analyze the reference image colors and texture. "
            "Create a new material with a Principled BSDF node. "
            "Set Base Color, Roughness, and Metallic values to match the reference. "
            "Assign the material to the active object."
        ),
    },
    "hard_surface_stack": {
        "name": "Hard Surface Modifier Stack",
        "prompt_template": (
            "Add the hard surface modifier stack (Mirror + Bevel + "
            "Weighted Normal + SubSurf) to the selected object"
        ),
        "skill_hint": (
            "Add modifiers in this order: "
            "Mirror (use_axis=(True,False,False), use_clip=True), "
            "Bevel (limit_method='WEIGHT', segments=3, profile=0.7), "
            "WeightedNormal (mode='FACE_AREA', keep_sharp=True), "
            "Subdivision (levels=2, render_levels=3). "
            "Use bpy.ops.object.modifier_add(type='...')."
        ),
    },
    "low_poly_scene": {
        "name": "Low-Poly Scene",
        "prompt_template": (
            "Create a stylized low-poly scene with simple geometric shapes, "
            "flat shaded materials, and basic lighting"
        ),
        "skill_hint": (
            "Use primitive meshes (cube, sphere, cylinder, cone). "
            "Set shading to flat: mesh.use_auto_smooth=False, "
            "apply bpy.ops.object.shade_flat(). "
            "Create simple emission or diffuse materials with solid colors. "
            "Add a sun lamp and sky texture for lighting."
        ),
    },
    "animate_object": {
        "name": "Animate Object (Keyframes)",
        "prompt_template": (
            "Animate the selected object with location/rotation/scale "
            "keyframes across frames 1 to 120"
        ),
        "skill_hint": (
            "Set bpy.context.scene.frame_set(frame) before inserting keyframes. "
            "Use obj.keyframe_insert(data_path='location', frame=...) etc. "
            "Set interpolation with fcurve.keyframe_points[i].interpolation = 'BEZIER'. "
            "Set frame range: scene.frame_start=1, scene.frame_end=120."
        ),
    },
}
