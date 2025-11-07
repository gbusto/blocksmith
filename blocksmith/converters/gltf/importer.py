#!/usr/bin/env python3
"""
GLTF → v3 Schema Importer (Blender-based)

Converts GLTF/GLB files to v3 schema format using Blender's GLTF importer.
This approach leverages Blender's robust GLTF handling while implementing
v3's scale baking strategy.

Scale Strategy:
- Bakes all transforms into geometry coordinates
- Sets scale to [1,1,1] for all entities
- Preserves visual appearance while simplifying hierarchy
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
    """
    Entry point to be executed inside Blender's Python (where bpy/mathutils exist).
    Parses CLI args and writes the v3 JSON to the requested output path.
    """
    import bpy  # type: ignore
    from mathutils import Vector  # type: ignore

    # Add the project root to Python path for Blender
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, '..', '..', '..', '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    # Now import the modules after path is set up (avoid models.py which needs pydantic)
    try:
        from engines.core.v3.gltf.geometry_filter import is_non_visual_geometry
    except ImportError:
        # Fallback: simple non-visual geometry detection
        def is_non_visual_geometry(name, entity_data=None):
            keywords = ['collision', 'hitbox', 'trigger', 'physics', '_col', '_hit']
            return any(keyword in name.lower() for keyword in keywords)
    
    try:
        from engines.core.v3.coordinate_utils import (
            transform_position_blender_to_v3,
            transform_quaternion_blender_to_v3,
            normalize_quaternion,
        )
    except ImportError:
        # Fallback: simple coordinate transformations
        def transform_position_blender_to_v3(pos):
            return [pos[0], pos[2], -pos[1]]  # Blender Z-up to Y-up
        
        def transform_quaternion_blender_to_v3(quat):
            qw, qx, qy, qz = quat
            return [qw, qx, qz, -qy]  # Blender to v3 coordinate system
        
        def normalize_quaternion(quat):
            import math
            qw, qx, qy, qz = quat
            norm = math.sqrt(qw*qw + qx*qx + qy*qy + qz*qz)
            if norm == 0:
                return [1, 0, 0, 0]
            return [qw/norm, qx/norm, qy/norm, qz/norm]

    # Clear scene
    bpy.ops.wm.read_factory_settings(use_empty=True)

    # Parse args (after Blender's --)
    try:
        idx = sys.argv.index('--')
        args = sys.argv[idx + 1:]
    except ValueError:
        args = []

    input_gltf = None
    output_json = 'output_v3.json'
    skip_non_visual = True  # Default to skipping non-visual geometry

    i = 0
    while i < len(args):
        if args[i] == '--input':
            if i + 1 < len(args):
                input_gltf = args[i + 1]
                i += 2
            else:
                raise ValueError("Missing value for --input")
        elif args[i] == '--output':
            if i + 1 < len(args):
                output_json = args[i + 1]
                i += 2
            else:
                raise ValueError("Missing value for --output")
        elif args[i] == '--include-non-visual':
            skip_non_visual = False
            i += 1
        else:
            i += 1

    if input_gltf is None:
        raise ValueError("Provide --input <gltf_path>")

    input_gltf = os.path.abspath(input_gltf)
    output_json = os.path.abspath(output_json)

    if not os.path.exists(input_gltf):
        raise ValueError(f"GLTF file not found: {input_gltf}")

    # Import GLTF
    print(f"Attempting to import GLTF: {input_gltf}")
    bpy.ops.import_scene.gltf(filepath=input_gltf)

    # Collect all objects (hierarchy preserved)
    objects = bpy.data.objects

    # Extract atlases (assume one material/image for simplicity; extend for multi)
    atlases = {}
    material = None
    image = None
    for obj in objects:
        if obj.type == 'MESH' and obj.active_material:
            material = obj.active_material
            texture_node = material.node_tree.nodes.get('Image Texture')
            image = texture_node.image if texture_node else None
            break

    if image:
        """The fix for the texture becoming more "muted" on import is due to Blender... here is an explanation from Grok:

        The core issue causing the PNG texture to be altered (becoming duller/more muted) is in the importer script (gltf/importer.py), specifically at the line image.save_render(temp_path). This method doesn't save the raw, original pixel data from the imported texture—it processes the image through Blender's full render color management pipeline (including the scene's view transform, exposure, gamma correction, and display device settings). By default, Blender uses a 'Filmic' view transform, which is designed for photorealistic rendering but often results in washed-out or desaturated colors when saving or exporting, especially for GLTF textures that expect simple sRGB without additional tone mapping.

        May also need to add this to the exporter:
        # Before bpy.ops.export_scene.gltf(...)
        scene = bpy.context.scene
        scene.display_settings.display_device = 'sRGB'
        scene.view_settings.view_transform = 'Standard'  # Matches GLTF viewer expectations
        scene.view_settings.exposure = 0.0
        scene.view_settings.gamma = 1.0
        """
        temp_path = "/tmp/temp_atlas.png"

        # Temporarily set filepath for save() and disable color transforms
        original_filepath = image.filepath
        image.filepath = temp_path

        scene = bpy.context.scene
        original_view_transform = scene.view_settings.view_transform
        scene.view_settings.view_transform = 'Raw'  # No tone mapping or dulling

        image.save()  # Saves raw pixels without render processing

        with open(temp_path, "rb") as f:
            atlas_b64 = base64.b64encode(f.read()).decode('utf-8')
        os.remove(temp_path)

        # Restore originals
        image.filepath = original_filepath
        scene.view_settings.view_transform = original_view_transform

        atlases["main"] = {
            "data": atlas_b64,
            "mime": "image/png",
            "resolution": [image.size[0], image.size[1]]
        }

    # Build entities (cuboids/groups)
    entities = []
    face_map = {
        (0, 0, 1): "front",
        (0, 0, -1): "back",
        (-1, 0, 0): "right",  # After X flip, Blender's right (+X) becomes -X
        (1, 0, 0): "left",    # After X flip, Blender's left (-X) becomes +X
        (0, 1, 0): "top",
        (0, -1, 0): "bottom"
    }

    for obj in objects:
        parent_id = obj.parent.name if obj.parent else None

        # IMPORTANT: According to v3 README, we need to bake scale into geometry
        # and store scale as [1,1,1] for GLTF imports

        if obj.type == 'MESH':
            mesh = obj.data
            uv_layer = mesh.uv_layers.active.data if mesh.uv_layers.active else None

            # Get vertices in LOCAL space (mesh coordinates)
            local_verts = [v.co.copy() for v in mesh.vertices]

            # Transform local vertices to v3 coordinate system
            # Note: These are mesh-local vertices, but we use the same coordinate transformation
            transformed_verts = [Vector(transform_position_blender_to_v3([v.x, v.y, v.z])) for v in local_verts]

            # Calculate bounds in v3 space (still local to object)
            from_ = [min(v[i] for v in transformed_verts) for i in range(3)]
            to = [max(v[i] for v in transformed_verts) for i in range(3)]

            # Apply object scale to the bounds
            from_ = [from_[i] * obj.scale[i] for i in range(3)]
            to = [to[i] * obj.scale[i] for i in range(3)]

            # Transform pivot from Blender to v3 coordinate system using centralized utilities
            pivot = transform_position_blender_to_v3([obj.location.x, obj.location.y, obj.location.z])

            # Extract rotation from the object and transform to v3 coordinate system
            blender_quat = list(obj.rotation_quaternion)  # Convert to list
            rotation = transform_quaternion_blender_to_v3(blender_quat)
            rotation = normalize_quaternion(rotation)  # Ensure unit quaternion

            # Scale is always [1,1,1] for GLTF imports (scale is baked into from/to)
            scale = [1.0, 1.0, 1.0]

            # Process faces - start with all 6 faces defined
            faces = {
                "front": {"atlas_id": "main", "uv": [0.0, 0.0, 1.0, 1.0]},
                "back": {"atlas_id": "main", "uv": [0.0, 0.0, 1.0, 1.0]},
                "left": {"atlas_id": "main", "uv": [0.0, 0.0, 1.0, 1.0]},
                "right": {"atlas_id": "main", "uv": [0.0, 0.0, 1.0, 1.0]},
                "top": {"atlas_id": "main", "uv": [0.0, 0.0, 1.0, 1.0]},
                "bottom": {"atlas_id": "main", "uv": [0.0, 0.0, 1.0, 1.0]}
            }

            # Update faces with actual UV data from mesh
            detected_faces = set()
            for poly in mesh.polygons:
                n = poly.normal
                # Transform normal from local space to v3 space (don't apply object rotation)
                # This keeps normals relative to the local mesh
                transformed_n = Vector((-n.x, n.z, n.y))
                normal_rounded = tuple(round(c) for c in transformed_n)
                face_key = face_map.get(normal_rounded)
                if face_key:
                    detected_faces.add(face_key)
                    if uv_layer:
                        uvs = [uv_layer[li].uv for li in poly.loop_indices]
                        u_min, v_min = min(uv.x for uv in uvs), min(uv.y for uv in uvs)
                        u_max, v_max = max(uv.x for uv in uvs), max(uv.y for uv in uvs)
                        faces[face_key] = {
                            "atlas_id": "main",
                            "uv": [u_min, v_min, u_max, v_max]
                        }

            # Check mesh type and log accordingly
            face_count = len(detected_faces)
            size = [to[i] - from_[i] for i in range(3)]
            min_dimension = min(size)

            if face_count == 1:
                print(f"\n⚠️  SINGLE-FACE MESH DETECTED: {obj.name}")
                print(f"   Face count: 1 (only {list(detected_faces)[0]} face)")
                print(f"   Size: {[round(s, 4) for s in size]}")
                print(f"   → This is highly unusual - REQUIRES VISUAL INSPECTION!")
                print(f"   → Converting to cuboid with default textures on 5 missing faces")
            elif face_count == 2:
                # Check if it's a proper plane (opposite faces)
                if detected_faces in [{'top', 'bottom'}, {'front', 'back'}, {'left', 'right'}]:
                    if min_dimension > 0.01:  # Not super thin
                        print(f"\n📋 PLANE MESH: {obj.name}")
                        print(f"   Faces: {sorted(detected_faces)}")
                        print(f"   Thickness: {min_dimension:.4f}")
                else:
                    print(f"\n⚠️  ODD 2-FACE MESH: {obj.name}")
                    print(f"   Faces: {sorted(detected_faces)} (not opposite faces!)")
                    print(f"   → REQUIRES VISUAL INSPECTION!")
            elif face_count not in [2, 6]:
                print(f"\n⚠️  NON-STANDARD MESH DETECTED: {obj.name}")
                print(f"   Face count: {face_count} (expected 2 for plane or 6 for cube)")
                print(f"   Detected faces: {sorted(detected_faces)}")
                print(f"   Size: {[round(s, 4) for s in size]}")
                print(f"   → REQUIRES VISUAL INSPECTION - unusual geometry!")
                print(f"   → Converting to cuboid with default textures on missing faces")

            # Store metadata about original transform for potential recovery
            metadata = {
                "blender_type": "MESH",
                "original_transform": {
                    "location": list(obj.location),
                    "rotation_euler": list(obj.rotation_euler),
                    "rotation_quaternion": list(obj.rotation_quaternion),
                    "scale": list(obj.scale)
                }
            }

            entity = {
                "type": "cuboid",
                "id": obj.name,
                "label": obj.name,
                "parent": parent_id,
                "pivot": pivot,
                "rotation": rotation,
                "scale": scale,  # Always [1,1,1] for GLTF
                "from": from_,
                "to": to,
                "faces": faces,
                "inflate": 0.0,
                "metadata": metadata
            }

            # Check if this might be non-visual geometry
            if is_non_visual_geometry(obj.name, entity_data=entity):
                print("\n" + "="*60)
                print("⚠️  WARNING: POTENTIALLY NON-VISUAL GEOMETRY DETECTED! ⚠️")
                print("="*60)
                print(f"Entity: {obj.name}")
                print(f"Reason: Name contains collision/hitbox keywords or unusually large")
                size = [to[i] - from_[i] for i in range(3)]
                volume = size[0] * size[1] * size[2]
                print(f"Size: {[f'{s:.2f}' for s in size]}")
                print(f"Volume: {volume:.3f}")
                print("\nThis entity might be:")
                print("- A collision box/hitbox")
                print("- A trigger volume")
                print("- Physics geometry")

                if skip_non_visual:
                    print("\n🚫 SKIPPING: Non-visual geometry filtering is enabled")
                    print("   To include this geometry, use --include-non-visual flag")
                else:
                    print("\n✅ INCLUDING: Non-visual geometry (--include-non-visual flag set)")
                print("="*60 + "\n")

                # Skip this entity if filtering is enabled
                if skip_non_visual:
                    continue

            entities.append(entity)

        elif obj.type == 'EMPTY':  # Group
            # For groups, use the same transformation as meshes
            # Blender's GLTF import: GLTF (Y-up) X,Y,Z -> Blender (Z-up) X,-Z,Y
            # Reverse: Blender X,Y,Z -> v3 (Y-up) X,Z,-Y
            pivot = [obj.location.x, obj.location.z, -obj.location.y]

            # Groups can maintain their scale since they don't have geometry
            scale = [1.0, 1.0, 1.0]  # But we'll use identity for consistency

            metadata = {
                "blender_type": "EMPTY",
                "original_transform": {
                    "location": list(obj.location),
                    "rotation_euler": list(obj.rotation_euler),
                    "rotation_quaternion": list(obj.rotation_quaternion),
                    "scale": list(obj.scale)
                }
            }

            # Get rotation for groups (same as meshes)
            blender_quat = obj.rotation_quaternion
            qw, qx, qy, qz = blender_quat
            rotation = [qw, qx, qz, -qy]  # Same transform as meshes

            entity = {
                "type": "group",
                "id": obj.name,
                "label": obj.name,
                "parent": parent_id,
                "pivot": pivot,
                "rotation": rotation,
                "scale": scale,
                "metadata": metadata
            }

            # Check groups too - they might be parents of non-visual geometry
            if is_non_visual_geometry(obj.name):
                print("\n" + "="*60)
                print("⚠️  WARNING: POTENTIALLY NON-VISUAL GROUP DETECTED! ⚠️")
                print("="*60)
                print(f"Group: {obj.name}")
                print("This group might contain collision/physics geometry.")

                if skip_non_visual:
                    print("\n🚫 SKIPPING: Non-visual geometry filtering is enabled")
                    print("   To include this group, use --include-non-visual flag")
                else:
                    print("\n✅ INCLUDING: Non-visual geometry (--include-non-visual flag set)")
                print("="*60 + "\n")

                # Skip this group if filtering is enabled
                if skip_non_visual:
                    continue

            entities.append(entity)

    # Full V3 model
    v3_model = {
        "meta": {
            "schema_version": "3.0",
            "texel_density": 16,
            "atlases": atlases,
            "import_source": "gltf"
        },
        "entities": entities,
        "animations": None
    }

    # Ensure UVs present (compute simple strip layout if missing)
    # TODO: Re-enable ensure_uvs function when available
    # try:
    #     v3_model = ensure_uvs(v3_model, texel_density=16, mode="strip")
    # except Exception:
    #     print("Warning: failed to ensure UVs in GLTF importer; continuing with current faces")

    # Export to JSON
    with open(output_json, "w") as f:
        json.dump(v3_model, f, indent=2)

    print(f"V3 JSON exported to {output_json}")


def _find_blender_executable() -> str:
    """Locate Blender executable using env var or common paths."""
    # 1) Environment variable override
    env_path = os.environ.get("BLENDER_PATH")
    if env_path and shutil.which(env_path):
        return env_path

    # 2) Common macOS installation path
    mac_path = "/Applications/Blender.app/Contents/MacOS/Blender"
    if os.path.exists(mac_path):
        return mac_path

    # 3) Fall back to system PATH
    which_path = shutil.which("blender")
    if which_path:
        return which_path

    raise FileNotFoundError(
        "Blender executable not found. Set BLENDER_PATH or install Blender."
    )


def import_gltf(payload: object, include_non_visual: bool = False) -> dict:
    """
    Import a GLTF/GLB into v3 schema by invoking Blender headless.

    payload can be:
    - bytes/bytearray: GLB or GLTF content
    - str path to .gltf/.glb file
    - JSON string (GLTF) or dict (GLTF JSON)
    """
    try:
        blender = _find_blender_executable()
    except Exception as e:
        logger.exception("Unable to locate Blender executable")
        raise

    tmp_dir = tempfile.mkdtemp(prefix="gltf_v3_")
    input_path = None
    output_path = os.path.join(tmp_dir, "output_v3.json")

    # Normalize payload to an input file path
    try:
        if isinstance(payload, (bytes, bytearray)):
            raw = bytes(payload)
            # Heuristic: GLB starts with b'glTF' magic; JSON starts with '{'
            if raw[:4] == b'glTF':
                ext = ".glb"
            elif raw.strip().startswith(b"{"):
                ext = ".gltf"
            else:
                ext = ".glb"
            input_path = os.path.join(tmp_dir, f"input{ext}")
            with open(input_path, "wb") as f:
                f.write(raw)
        elif isinstance(payload, str):
            # Treat as path if exists
            if os.path.exists(payload):
                input_path = os.path.abspath(payload)
            else:
                # Treat as JSON string
                input_path = os.path.join(tmp_dir, "input.gltf")
                with open(input_path, "w") as f:
                    f.write(payload)
        elif isinstance(payload, dict):
            input_path = os.path.join(tmp_dir, "input.gltf")
            with open(input_path, "w") as f:
                json.dump(payload, f)
        else:
            raise ValueError(f"Unsupported GLTF payload type: {type(payload)}")

        script_path = os.path.abspath(__file__)
        cmd = [
            blender,
            "--background",
            "--python", script_path,
            "--",
            "--input", input_path,
            "--output", output_path,
        ]
        if include_non_visual:
            cmd.append("--include-non-visual")

        # Run Blender
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            text=True,
        )

        if result.returncode != 0:
            logger.error("Blender importer failed: %s", result.stderr)
            raise RuntimeError("Blender GLTF import failed")

        if not os.path.exists(output_path):
            raise RuntimeError("Blender importer did not produce output JSON")

        with open(output_path, "r") as f:
            return json.load(f)
    finally:
        # Leave tmp dir for debugging if desired by setting env var
        if os.environ.get("KEEP_GLTF_TMP") != "1":
            try:
                import shutil as _shutil
                _shutil.rmtree(tmp_dir, ignore_errors=True)
            except Exception:
                pass


if __name__ == "__main__":
    blender_entrypoint()