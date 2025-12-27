#!/usr/bin/env python3
"""
v3 Schema → GLTF/GLB Exporter (Blender-based)

Converts v3 schema format to GLTF/GLB files using Blender's GLTF exporter.
This approach creates proper box geometry with correct UV mapping and 
handles v3's pre-baked scale strategy.

Scale Strategy:
- Uses from/to coordinates directly (scale already baked)
- Maintains scale as [1,1,1] for clean GLTF output
- Geometry is positioned at world coordinates

Texture Handling:
- Uses tempfile for reliable texture loading in Blender
- Supports base64-encoded atlases from v3 schema
- Applies nearest-neighbor filtering for pixel art
"""

import os
import sys
import json
import base64
import tempfile
import subprocess
import shutil
import logging

logger = logging.getLogger(__name__)


def blender_entrypoint() -> None:
    import bpy  # type: ignore
    from mathutils import Quaternion  # type: ignore

    # Import centralized coordinate transformation utilities
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, parent_dir)
    from coordinate_utils import (  # type: ignore
        transform_position_v3_to_blender,
        transform_quaternion_v3_to_blender,
        normalize_quaternion
    )
    from uv_mapper import to_gltf as get_gltf_uv_coords # type: ignore

    # Clear scene
    bpy.ops.wm.read_factory_settings(use_empty=True)

    # Parse args after Blender's --
    try:
        idx = sys.argv.index('--')
        args = sys.argv[idx + 1:]
    except ValueError:
        args = []

    input_json = None
    output_path = 'roundtrip_test.glb'
    export_format = 'GLB'  # 'GLB' | 'GLTF_EMBEDDED' | 'GLTF_SEPARATE'

    i = 0
    while i < len(args):
        if args[i] == '--input':
            if i + 1 < len(args):
                input_json = args[i + 1]
                i += 2
            else:
                raise ValueError("Missing value for --input")
        elif args[i] == '--output':
            if i + 1 < len(args):
                output_path = args[i + 1]
                i += 2
            else:
                raise ValueError("Missing value for --output")
        elif args[i] == '--format':
            if i + 1 < len(args):
                fmt = args[i + 1].lower()
                if fmt == 'glb':
                    export_format = 'GLB'
                elif fmt in ('gltf', 'gltf_embedded', 'embedded'):
                    export_format = 'GLTF_EMBEDDED'
                elif fmt in ('gltf_separate', 'separate'):
                    export_format = 'GLTF_SEPARATE'
                else:
                    raise ValueError(f"Unsupported format: {fmt}")
                i += 2
            else:
                raise ValueError("Missing value for --format")
        else:
            i += 1

    if input_json is None:
        raise ValueError("Provide --input <json_path>")

    # Resolve absolute paths
    input_json = os.path.abspath(input_json)
    output_path = os.path.abspath(output_path)

    if not os.path.exists(input_json):
        raise ValueError(f"JSON file not found: {input_json}")

    # Load V3-like JSON (be tolerant: handle missing meta/atlases)
    print(f"Loading V3 JSON: {input_json}")
    with open(input_json, "r") as f:
        v3 = json.load(f)

    meta = v3.get("meta") or {}
    atlases = meta.get("atlases") or {}
    atlas = atlases.get("main")
    image = None
    if atlas:
        # Use tempfile for reliable texture loading
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
            temp_file.write(base64.b64decode(atlas["data"]))
            temp_path = temp_file.name
        
        image = bpy.data.images.load(temp_path)
        image.colorspace_settings.name = 'sRGB'
        image.pack()  # Pack for embedding
        os.remove(temp_path)
        print(f"Loaded and packed image: {image.name}")

    # Create shared material with texture
    mat = bpy.data.materials.new(name="V3_Mat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    tex_node = mat.node_tree.nodes.new('ShaderNodeTexImage')
    tex_node.image = image
    tex_node.interpolation = 'Closest'  # NEAREST filtering
    mat.node_tree.links.new(bsdf.inputs['Base Color'], tex_node.outputs['Color'])

    # Build Blender objects from entities
    obj_map = {}  # ID to Blender object
    for entity in v3.get("entities", []):
        parent_id = entity.get("parent")
        pivot = entity.get("pivot", [0,0,0])
        rotation = entity.get("rotation", [1,0,0,0])
        scale = entity.get("scale", [1,1,1])

        if entity["type"] == "cuboid":
            # The from/to are in LOCAL space (relative to pivot) when rotation is present
            from_v3 = entity["from"]
            to_v3 = entity["to"]
            
            # Transform v3 coordinates to Blender coordinates using centralized utilities
            from_b = transform_position_v3_to_blender(from_v3)
            to_b = transform_position_v3_to_blender(to_v3)
            
            # Calculate bounds and size
            bounds_min_b = [min(from_b[i], to_b[i]) for i in range(3)]
            bounds_max_b = [max(from_b[i], to_b[i]) for i in range(3)]
            
            # Create cube mesh
            mesh = bpy.data.meshes.new(name=f"{entity['id']}_mesh")
            obj = bpy.data.objects.new(entity["id"], mesh)
            bpy.context.collection.objects.link(obj)
            
            # Create vertices directly at the correct positions
            verts = [
                (bounds_min_b[0], bounds_min_b[1], bounds_min_b[2]),
                (bounds_max_b[0], bounds_min_b[1], bounds_min_b[2]),
                (bounds_max_b[0], bounds_max_b[1], bounds_min_b[2]),
                (bounds_min_b[0], bounds_max_b[1], bounds_min_b[2]),
                (bounds_min_b[0], bounds_min_b[1], bounds_max_b[2]),
                (bounds_max_b[0], bounds_min_b[1], bounds_max_b[2]),
                (bounds_max_b[0], bounds_max_b[1], bounds_max_b[2]),
                (bounds_min_b[0], bounds_max_b[1], bounds_max_b[2]),
            ]
            
            # Define faces (quads) - standard winding order (BL -> BR -> TR -> TL)
            # This ensures the first edge is Horizontal (matching U) and second is Vertical (matching V)
            # Preventing the 90-degree rotation/squash effect.
            faces = [
                (0, 3, 2, 1),  # Bottom (Fixed winding: 0,3,2,1 to point -Z)
                (4, 5, 6, 7),  # Top
                (0, 1, 5, 4),  # Front
                (2, 3, 7, 6),  # Back
                (0, 4, 7, 3),  # Left   (Fixed winding: 0,4,7,3 to point -X)
                (1, 2, 6, 5),  # Right
            ]
            
            # Create mesh
            mesh.from_pydata(verts, [], faces)
            mesh.update()
            
            # Apply material
            if mat:
                mesh.materials.append(mat)
            
            # Set up UV coordinates
            uv_layer = mesh.uv_layers.new(name="UVMap")
            
            # Map v3 face names to Blender's default cube face indices
            # Note: Front/Back swapped to align with Importer expectation (+Y is Front for Importer? No +Y is Back)
            # Importer expects Back=(0,0,-1) after transform?
            # Let's trust the Swap Loop analysis: Front->3 (Back Face Geom), Back->2 (Front Face Geom)
            face_map = {
                'bottom': 0, 'top':    1, 'front':  3,
                'back':   2, 'left':   4, 'right':  5
            }

            # Set UVs per face using the centralized uv_mapper
            for v3_face_name, face_idx in face_map.items():
                face_data = entity.get("faces", {}).get(v3_face_name)
                if not face_data or not face_data.get("uv"):
                    continue

                # Get the four corner UVs, correctly flipped for GLTF
                uv_coords = get_gltf_uv_coords(face_data["uv"])

                poly = mesh.polygons[face_idx]
                for i, loop_idx in enumerate(poly.loop_indices):
                    uv_layer.data[loop_idx].uv = uv_coords[i]

            
            # Check if we have original transform metadata for better roundtrip fidelity
            metadata = entity.get("metadata") or {}
            original_transform = metadata.get("original_transform", {})
            
            if original_transform and "blender_type" in metadata and metadata["blender_type"] == "MESH":
                # Use original transform data for perfect roundtrip
                print(f"Entity {entity['id']}: Using original transform from metadata for perfect roundtrip")
                
                # Use original location if available
                if "location" in original_transform:
                    obj.location = original_transform["location"]
                    print(f"  Original location: {original_transform['location']}")
                else:
                    # Fallback to transformed pivot
                    pivot_b = transform_position_v3_to_blender(pivot)
                    obj.location = pivot_b
                
                # Use original rotation if available
                if "rotation_quaternion" in original_transform:
                    obj.rotation_mode = 'QUATERNION'
                    obj.rotation_quaternion = original_transform["rotation_quaternion"]
                    print(f"  Original quaternion: {original_transform['rotation_quaternion']}")
                else:
                    # Fallback to transformed rotation using centralized utilities
                    rotation_normalized = normalize_quaternion(rotation)
                    quat_list = transform_quaternion_v3_to_blender(rotation_normalized)
                    quat_b = Quaternion(quat_list)
                    obj.rotation_mode = 'QUATERNION'
                    obj.rotation_quaternion = quat_b
                
                # Use original scale if available (though v3 normalizes to [1,1,1])
                if "scale" in original_transform:
                    obj.scale = original_transform["scale"]
                    print(f"  Original scale: {original_transform['scale']}")
                else:
                    obj.scale = scale
            else:
                # No metadata - use standard transformation with centralized utilities
                pivot_b = transform_position_v3_to_blender(pivot)
                
                # Transform quaternion from v3 to Blender coordinates
                rotation_normalized = normalize_quaternion(rotation)
                quat_list = transform_quaternion_v3_to_blender(rotation_normalized)
                quat_b = Quaternion(quat_list)
                
                # Debug print
                if rotation != [1, 0, 0, 0]:
                    print(f"Entity {entity['id']}: v3 rotation {rotation} -> Blender {list(quat_b)}")
                
                # Set object transform
                obj.location = pivot_b  # Use the pivot as location
                obj.rotation_mode = 'QUATERNION'  # CRITICAL: Must set this for rotations to be preserved!
                obj.rotation_quaternion = quat_b
                obj.scale = scale  # Should be [1,1,1] for GLTF exports
            
            obj_map[entity["id"]] = obj
            
        elif entity["type"] == "group":
            bpy.ops.object.empty_add(type='PLAIN_AXES')
            obj = bpy.context.object
            obj.name = entity["id"]
            
            # Check if we have original transform metadata for better roundtrip fidelity
            metadata = entity.get("metadata") or {}
            original_transform = metadata.get("original_transform", {})
            
            if original_transform and "blender_type" in metadata and metadata["blender_type"] == "EMPTY":
                # Use original transform data for perfect roundtrip
                print(f"Group {entity['id']}: Using original transform from metadata for perfect roundtrip")
                
                # Use original location if available
                if "location" in original_transform:
                    obj.location = original_transform["location"]
                    print(f"  Original location: {original_transform['location']}")
                else:
                    # Fallback to transformed pivot
                    pivot_b = transform_position_v3_to_blender(pivot)
                    obj.location = pivot_b
                
                # Use original rotation if available
                if "rotation_quaternion" in original_transform:
                    obj.rotation_mode = 'QUATERNION'
                    obj.rotation_quaternion = original_transform["rotation_quaternion"]
                    print(f"  Original quaternion: {original_transform['rotation_quaternion']}")
                else:
                    # Fallback to transformed rotation using centralized utilities
                    rotation_normalized = normalize_quaternion(rotation)
                    quat_list = transform_quaternion_v3_to_blender(rotation_normalized)
                    quat_b = Quaternion(quat_list)
                    obj.rotation_mode = 'QUATERNION'
                    obj.rotation_quaternion = quat_b
                
                # Use original scale if available
                if "scale" in original_transform:
                    obj.scale = original_transform["scale"]
                    print(f"  Original scale: {original_transform['scale']}")
                else:
                    obj.scale = scale
            else:
                # No metadata - use standard transformation with centralized utilities
                pivot_b = transform_position_v3_to_blender(pivot)
                
                # Transform quaternion from v3 to Blender coordinates
                rotation_normalized = normalize_quaternion(rotation)
                quat_list = transform_quaternion_v3_to_blender(rotation_normalized)
                quat_b = Quaternion(quat_list)
                
                obj.location = pivot_b
                obj.rotation_mode = 'QUATERNION'  # CRITICAL: Must set this for rotations to be preserved!
                obj.rotation_quaternion = quat_b
                obj.scale = scale
            
            obj_map[entity["id"]] = obj

    # Set parents
    for entity in v3.get("entities", []):
        parent_id = entity.get("parent")
        if parent_id:
            obj_map[entity["id"]].parent = obj_map[parent_id]

    # Debug: Print object transforms before export
    print("\nObject transforms before export:")
    for obj_name, obj in obj_map.items():
        if obj.type == 'MESH' or obj.type == 'EMPTY':
            print(f"{obj.name}: location={list(obj.location)}, rotation_quaternion={list(obj.rotation_quaternion)}, scale={list(obj.scale)}")

    # Export GLTF/GLB
    print(f"\nExporting to: {output_path} ({export_format})")

    # ============================================================================
    # CRITICAL: Enable GLTF_EMBEDDED experimental feature (Blender 4.4.0+)
    # ============================================================================
    # In Blender 4.4.0+, GLTF_EMBEDDED became an experimental feature that must
    # be explicitly enabled via preferences. The UI checkbox does NOT affect this
    # when running Blender via --background mode, so we MUST enable it
    # programmatically here.
    #
    # DO NOT REMOVE THIS CODE! Without it, GLTF_EMBEDDED exports will fail with:
    #   TypeError: enum "GLTF_EMBEDDED" not found in ('GLB', 'GLTF_SEPARATE')
    #
    # Note: Older Blender versions (< 4.4.0) may not have the 'allow_embedded_format'
    # preference. The hasattr() check ensures backward compatibility.
    # ============================================================================
    if export_format == 'GLTF_EMBEDDED':
        try:
            addon = bpy.context.preferences.addons.get('io_scene_gltf2')
            if addon and hasattr(addon.preferences, 'allow_embedded_format'):
                addon.preferences.allow_embedded_format = True
                print("Enabled GLTF_EMBEDDED experimental feature (allow_embedded_format)")
        except Exception as e:
            print(f"Warning: Could not enable GLTF_EMBEDDED: {e}")

    bpy.ops.export_scene.gltf(
        filepath=output_path,
        export_format=export_format,
        export_image_format='AUTO',
        export_texcoords=True,
        export_materials='EXPORT',
        export_apply=False,  # Don't apply modifiers
        export_attributes=True,
        use_visible=True,
        export_yup=True,  # Ensure Y-up coordinate system (matches v3 and GLTF)
        export_animations=False,  # Disable animations to simplify
        use_mesh_edges=False,
        use_mesh_vertices=True,
        export_cameras=False,
        export_lights=False
    )

    print(f"Export complete: {output_path}")


def _find_blender_executable() -> str:
    env_path = os.environ.get("BLENDER_PATH")
    if env_path and shutil.which(env_path):
        return env_path
    mac_path = "/Applications/Blender.app/Contents/MacOS/Blender"
    if os.path.exists(mac_path):
        return mac_path
    which_path = shutil.which("blender")
    if which_path:
        return which_path
    raise FileNotFoundError("Blender executable not found. Set BLENDER_PATH or install Blender.")


def _run_blender_export(v3_json_path: str, output_path: str, fmt_arg: str) -> None:
    blender = _find_blender_executable()
    script_path = os.path.abspath(__file__)
    cmd = [
        blender,
        "--background",
        "--python", script_path,
        "--",
        "--input", v3_json_path,
        "--output", output_path,
        "--format", fmt_arg,
    ]
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        logger.error("Blender exporter failed: rc=%s\nSTDOUT:\n%s\nSTDERR:\n%s", result.returncode, result.stdout, result.stderr)
        raise RuntimeError("Blender V3 export failed")

    # Some Blender versions may alter the output name; if expected path is missing,
    # attempt to find a reasonable fallback in the same directory.
    if not os.path.exists(output_path):
        out_dir = os.path.dirname(output_path)
        expected_ext = os.path.splitext(output_path)[1].lower() or ('.glb' if fmt_arg == 'glb' else '.gltf')
        candidates = [p for p in os.listdir(out_dir) if p.lower().endswith(expected_ext)]
        if candidates:
            # Use the most recently modified candidate
            candidates_full = [os.path.join(out_dir, p) for p in candidates]
            newest = max(candidates_full, key=lambda p: os.path.getmtime(p))
            return newest
        else:
            logger.error("Blender exporter produced no %s file in %s. STDOUT:\n%s\nSTDERR:\n%s", expected_ext, out_dir, result.stdout, result.stderr)
            raise RuntimeError("Blender V3 export produced no output file")


def export_glb(model_json: object) -> bytes:
    """
    Export a v3 model (dict or JSON string) to GLB bytes by invoking Blender.
    """
    tmp_dir = tempfile.mkdtemp(prefix="v3_export_")
    input_path = os.path.join(tmp_dir, "model_v3.json")
    # Create a unique temp file path for Blender to write into
    fd, output_path = tempfile.mkstemp(suffix=".glb", dir=tmp_dir)
    os.close(fd)
    try:
        os.remove(output_path)  # Ensure Blender can create it fresh
    except FileNotFoundError:
        pass
    try:
        if isinstance(model_json, dict):
            with open(input_path, "w") as f:
                json.dump(model_json, f)
        elif isinstance(model_json, str):
            with open(input_path, "w") as f:
                f.write(model_json)
        else:
            raise ValueError(f"Unsupported model_json type: {type(model_json)}")

        written_path = _run_blender_export(input_path, output_path, "glb") or output_path

        with open(written_path, "rb") as f:
            data = f.read()
        return data
    finally:
        if os.environ.get("KEEP_V3_GLTF_TMP") != "1":
            try:
                shutil.rmtree(tmp_dir, ignore_errors=True)
            except Exception:
                pass


def export_gltf(model_json: object) -> str:
    """
    Export a v3 model (dict or JSON string) to GLTF (embedded) text by invoking Blender.
    """
    tmp_dir = tempfile.mkdtemp(prefix="v3_export_")
    input_path = os.path.join(tmp_dir, "model_v3.json")
    fd, output_path = tempfile.mkstemp(suffix=".gltf", dir=tmp_dir)
    os.close(fd)
    try:
        os.remove(output_path)
    except FileNotFoundError:
        pass
    try:
        if isinstance(model_json, dict):
            with open(input_path, "w") as f:
                json.dump(model_json, f)
        elif isinstance(model_json, str):
            with open(input_path, "w") as f:
                f.write(model_json)
        else:
            raise ValueError(f"Unsupported model_json type: {type(model_json)}")

        written_path = _run_blender_export(input_path, output_path, "gltf_embedded") or output_path

        with open(written_path, "r") as f:
            text = f.read()
        return text
    finally:
        if os.environ.get("KEEP_V3_GLTF_TMP") != "1":
            try:
                shutil.rmtree(tmp_dir, ignore_errors=True)
            except Exception:
                pass


if __name__ == "__main__":
    blender_entrypoint()