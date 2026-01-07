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
                (2, 1, 0, 3),  # Bottom (Rotated 180. Maps V->-X. Mirrored? User approved.)
                (7, 4, 5, 6),  # Top    (Rotated to 7->4 (-Y). V->+X. UN-MIRRORED. Fixes Regression.)
                (0, 1, 5, 4),  # Front
                (2, 3, 7, 6),  # Back
                (4, 7, 3, 0),  # Left   (Rotated: 4->7 is +Y/Depth. Matches Atlas U=Depth)
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

                # FIX: Left face (-X) appears vertically mirrored ("Upside Down")
                # We simply swap the top and bottom pairs in the uv_coords list.
                # Standard order from get_gltf_uv_coords: [BL, BR, TR, TL] (based on loop idx logic?)
                # Actually, get_gltf_uv_coords returns standard [u_min, v_min] etc.
                # Let's just swap the V coordinates manually for the Left face.
                if v3_face_name == 'left':
                    # Swap first two with last two? Or swap V in each coord?
                    # Since get_gltf_uv_coords does v=1-v, let's just reverse the list?
                    # No, let's be precise. We want to mirror vertically relative to the face.
                    # This means swapping the V mapping.
                    # Current: v_min -> Top of face, v_max -> Bottom of face (due to face winding?)
                    # If upside down, we want v_min -> Bottom, v_max -> Top.
                    # So we iterate and swap the UV assignments.
                    # Instead of complex logic, allow UV_MAPPER to handle flips? 
                    # No, let's keep it local.
                    # Reverse the list of UV coords effectively rotates 180 (both H and V).
                    # We only want V.
                    # Let's just reverse the order of UVs? No, that rotates the texture.
                    
                    # Let's try: Swap vertex 0 with 3, and 1 with 2 in the loop assignment?
                    # Only for Left face.
                    pass 

                poly = mesh.polygons[face_idx]
                
                # Apply V-Flip for Left Face by re-ordering assignment
                # Left: Fixes "Upside Down" vertical mirroring.
                # Bottom: Removed V-Flip to fix L/R Mirroring (matches BBModel).
                # Top: Removed V-Flip (matches BBModel).
                if v3_face_name == 'left':
                   # Flip V: Swap A/D and B/C.
                   # [D, C, B, A] basically.
                   uv_coords = [uv_coords[3], uv_coords[2], uv_coords[1], uv_coords[0]]

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
    print("\nObject transforms before export (BIND POSE CAPTURE):")
    BIND_POSE = {}
    for obj_name, obj in obj_map.items():
        if obj.type == 'MESH' or obj.type == 'EMPTY':
            BIND_POSE[obj.name] = {
                "location": obj.location.copy(),
                "rotation_quaternion": obj.rotation_quaternion.copy(),
                "scale": obj.scale.copy(),
                "rotation_mode": obj.rotation_mode
            }
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

    # ============================================================================
    # ANIMATION PROCESSING
    # ============================================================================
    
    def _map_interpolation(interp: str) -> str:
        """Map V3 interpolation to Blender interpolation mode."""
        if interp == 'step':
            return 'CONSTANT'
        elif interp == 'cubic':
            return 'BEZIER'
        return 'LINEAR'

    animations = v3.get("animations", [])
    
    # Pre-build entity map for fast lookup of bind pose data (Rest Pose)
    entity_map = {e.get("id"): e for e in v3.get("entities", [])}

    def _reset_scene_state(obj_map_local: dict, entity_map_local: dict) -> None:
        """
        Reset all objects to their V3 bind pose and clear animation state.
        This enforces a 'Clean Room' protocol between animations to prevent 'Dirty Canvas' leakage.
        """
        for eid, obj_reset in obj_map_local.items():
            # 1. Reset Transforms to V3 Bind Pose
            ent_data = entity_map_local.get(eid, {})
            
            piv = ent_data.get("pivot", [0, 0, 0])
            rot = ent_data.get("rotation", [1, 0, 0, 0])
            scl = ent_data.get("scale", [1, 1, 1])

            obj_reset.location = transform_position_v3_to_blender(piv)
            
            obj_reset.rotation_mode = 'QUATERNION'
            rot_norm = normalize_quaternion(rot)
            q_list = transform_quaternion_v3_to_blender(rot_norm)
            obj_reset.rotation_quaternion = Quaternion(q_list)
            
            obj_reset.scale = (scl[0], scl[1], scl[2])

            # 2. Clear Active Action
            if obj_reset.animation_data:
                obj_reset.animation_data.action = None
                
                # 3. Mute all NLA tracks to ensure they don't influence the next record/evaluation
                if obj_reset.animation_data.nla_tracks:
                    for t in obj_reset.animation_data.nla_tracks:
                        t.mute = True
                        t.is_solo = False
        
        # Force update
        bpy.context.view_layer.update()

    if animations:
        print(f"Processing {len(animations)} animations...")
        
        for anim in animations:
            # CRITICAL: Clean the canvas before processing this animation
            _reset_scene_state(obj_map, entity_map)
            
            anim_name = anim.get("name", "animation")
            loop_mode = anim.get("loop_mode", "repeat")
            
            # CRITICAL FIX: Prevent "Duration Leak" (Time Contamination)
            # Calculate the actual duration of THIS animation from its keys.
            # If we don't do this, Blender defaults to the longest previous animation (e.g., Explode=60),
            # causing short animations (Drive=30) to have 30 frames of dead air.
            max_anim_frame = 0.0
            for ch in anim.get("channels", []):
                frames = ch.get("frames", [])
                if frames:
                    last_time = frames[-1].get("time", 0.0)
                    if last_time > max_anim_frame:
                        max_anim_frame = last_time
            
            # Sanity check: If animation is empty, default to 1
            if max_anim_frame == 0:
                max_anim_frame = 1.0
            
            # Set the Scene Timeline limits for the Exporter
            # We extend the scene to fit the longest animation seen so far.
            # Individual animations are clamped by their NLA Strip length (see below).
            bpy.context.scene.frame_start = 0
            current_end = bpy.context.scene.frame_end
            new_end = max(current_end, int(max_anim_frame))
            bpy.context.scene.frame_end = new_end
            print(f"  Configured Timeline for '{anim_name}': End Frame = {new_end} (Local Max: {max_anim_frame})")

            # Group channels by target object
            channels_by_target = {}
            for channel in anim.get("channels", []):
                target_id = channel.get("target_id")
                if target_id not in obj_map:
                    print(f"  Warning: Animation target {target_id} not found, skipping channel")
                    continue
                if target_id not in channels_by_target:
                    channels_by_target[target_id] = []
                channels_by_target[target_id].append(channel)
            
            # Create Actions and NLA Tracks for each affected object
            for target_id, channels in channels_by_target.items():
                obj = obj_map[target_id]
                
                # Create a new Action for this object-animation pair
                # Name it carefully so debugging is invalid, but NLA track name matters more for GLTF
                action_name = f"{anim_name}_{target_id}"
                action = bpy.data.actions.new(name=action_name)
                
                # Ensure object has animation data
                if not obj.animation_data:
                    obj.animation_data_create()
                
                print(f"Creating Action '{action_name}' for object '{target_id}'")

                # Process channels
                for channel in channels:
                    prop = channel.get("property")
                    print(f"  Processing channel: property={prop}, frames={len(channel.get('frames', []))}")
                    interpolation = _map_interpolation(channel.get("interpolation", "linear"))
                    frames = channel.get("frames", [])
                    
                    data_path = ""
                    num_indices = 0
                    
                    if prop == "position":
                        data_path = "location"
                        num_indices = 3
                    elif prop == "rotation":
                        data_path = "rotation_quaternion"
                        num_indices = 4
                    elif prop == "scale":
                        data_path = "scale"
                        num_indices = 3
                    else:
                        print(f"  Warning: Unknown animation property {prop}")
                        continue
                        
                    # Create F-Curves
                    fcurves = []
                    for i in range(num_indices):
                        fc = action.fcurves.find(data_path, index=i)
                        if not fc:
                            fc = action.fcurves.new(data_path, index=i)
                        fcurves.append(fc)
                    
                    # Insert Keyframes
                    for kf in frames:
                        time = kf.get("time", 0)
                        val_v3 = kf.get("value")
                        val_b = []
                        
                        # Apply Coordinate Transformations
                        if prop == "position":
                            # V3 Pos -> Blender Pos
                            val_b = transform_position_v3_to_blender(val_v3)
                        elif prop == "rotation":
                            # V3 Quat -> Blender Quat
                            val_b = transform_quaternion_v3_to_blender(val_v3)
                        elif prop == "scale":
                            # V3 Scale [x, y, z] -> Blender Scale [x, z, -y]? 
                            # Scale is magnitude. Just swap axes. Y(up) becomes Z(up). Z(forward) becomes Y(forward).
                            # Since scale is unsigned size, we ignore the 'negative' direction of Z->-Y mapping.
                            # So [sx, sy, sz] -> [sx, sz, sy]
                            val_b = [val_v3[0], val_v3[2], val_v3[1]]
                        
                        # Insert frame data
                        for i in range(num_indices):
                            # We use 'FAST' for initial sparse creation
                            kp = fcurves[i].keyframe_points.insert(time, val_b[i], options={'FAST'})
                            kp.interpolation = interpolation

                # 1. Stash the Sparse Action directly to NLA
                # We do NOT bake. This preserves the sparse nature of the V3 data.
                # "Drive" -> Rotation keys only. "Explode" -> Position keys only.
                # This allows runtime composition (blending) in the game engine.
                
                action.name = anim_name
                
                track = obj.animation_data.nla_tracks.new()
                track.name = anim_name # Final GLTF Name
                
                start_frame = 0
                strip = track.strips.new(name=anim_name, start=start_frame, action=action)
                
                # CRITICAL: Clamp the strip to the actual animation length.
                # This ensures that short animations don't inherit the scene's global end frame.
                strip.frame_end = float(max_anim_frame)
                
                # Mute to prevent it affecting the viewport or other exports during this session loop
                # The GLTF exporter works with NLA tracks even if muted (usually), 
                # but to be safe and match standard Blender-GLTF workflows where we want distinct clips:
                # Muting essentially "stashes" it.
                track.mute = True
                
                # Clear active action so the object is clean for the next channel/animation
                obj.animation_data.action = None
                
                print(f"  > Stashed sparse action '{anim_name}' to NLA track.")


    # CRITICAL: Reset all objects to their V3 bind pose before export.
    # To prevent NLA tracks from overriding the bind pose during the "Node" export phase,
    # we temporarily disable NLA evaluation on the objects.
    # The GLTF exporter's 'NLA_TRACKS' mode should still be able to find and export the tracks
    # stored in obj.animation_data.nla_tracks, even if use_nla is False for the scene.
    
    print("\nPreparing for export: Disabling NLA evaluation and resetting bind pose (CAPTURE & RESTORE)...")
    
    # 0. RESTORE BIND POSE (Fixes 'Zero Fallacy')
    # Instead of blindly zeroing transforms (which flattens pyramids), we restore the
    # captured BIND_POSE state associated with the static model structure.
    for obj_name, data in BIND_POSE.items():
        if obj_name in bpy.data.objects:
             obj = bpy.data.objects[obj_name]
             try:
                 obj.location = data["location"]
                 obj.rotation_mode = data["rotation_mode"]
                 obj.rotation_quaternion = data["rotation_quaternion"]
                 obj.scale = data["scale"]
             except Exception as e:
                 print(f"Warning: Failed to restore bind pose for {obj_name}: {e}")
    
    # NEW STEP 7 (CRITICAL): UNMUTE ALL TRACKS FOR EXPORT
    # We unmute all tracks so the exporter sees them as active.
    # This causes blending/crosstalk, but we fix that with the _sanitize_gltf post-processor.
    for entity in v3.get("entities", []):
         entity_id = entity.get("id")
         if entity_id in obj_map:
             obj_unmute = obj_map[entity_id]
             if obj_unmute.animation_data and obj_unmute.animation_data.nla_tracks:
                 print(f"  Unmuting NLA tracks for {entity_id}...")
                 for t in obj_unmute.animation_data.nla_tracks:
                     t.mute = False
                     t.is_solo = False
    
    # DEBUG: Inspect Actions before export
    print("\n[DEBUG] Inspecting Blender Actions before Export:")
    for action in bpy.data.actions:
        print(f"  Action '{action.name}':")
        paths = set()
        for fc in action.fcurves:
            paths.add(fc.data_path)
        for p in paths:
            print(f"    - {p}")
    
    # Ensure all manual changes are propagated
    bpy.context.view_layer.update()

    bpy.ops.export_scene.gltf(
        filepath=output_path,
        export_format=export_format,
        export_image_format='AUTO',
        export_texcoords=True,
        export_materials='EXPORT',
        export_apply=False,  # Don't apply modifiers
        export_attributes=True,
        use_visible=True,
        export_yup=True,
        export_animations=True,
        
        # NOTE: We allow sampling (default) because we are exporting Muted tracks.
        # The exporter handles the evaluation.
        # export_force_sampling=False, 
        
        # NLA Merging settings
        # Force NLA_TRACKS mode to ensure merging by Track Name
        export_animation_mode='NLA_TRACKS',
        export_nla_strips=True,  # Explicitly enable NLA export
        export_def_bones=True,   # Ensure bones are exported
        export_anim_single_armature=False, # We are animating separate objects, not a single armature
        
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
    # DEBUG: Always print Blender output to see debug prints
    print(f"Blender STDOUT:\n{result.stdout}")
    if result.stderr:
        print(f"Blender STDERR:\n{result.stderr}")

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




def _sanitize_gltf(output_path: str, v3_json: object) -> None:
    """
    Post-process the GLB to remove unauthored animation channels AND trim time domains.
    Fixes "Duration Leak" where short animations inherit long timelines from Blender.
    """
    try:
        from pygltflib import GLTF2, BufferView, Accessor, Buffer
        import struct
    except ImportError:
        print("Warning: pygltflib not found, skipping sanitization.")
        return

    # Ensure v3_json is a dict
    if isinstance(v3_json, str):
        try:
            v3_json = json.loads(v3_json)
        except Exception:
            return
    if not isinstance(v3_json, dict):
        return

    try:
        gltf = GLTF2().load(output_path)
    except Exception as e:
        print(f"Warning: Failed to load GLB for sanitization: {e}")
        return

    # 1. Build Maps: AnimName -> AllowedChannels, AnimName -> Duration
    allowed_channels = {}
    anim_durations = {}
    
    for anim in (v3_json.get("animations") or []):
        anim_name = anim.get("name")
        allowed_channels[anim_name] = set()
        max_t = 0.0
        
        for ch in anim.get("channels", []):
            target_id = ch.get("target_id")
            prop = ch.get("property")
            path = "translation" if prop == "position" else "rotation" if prop == "rotation" else "scale"
            allowed_channels[anim_name].add((target_id, path))
            
            # Track duration
            frames = ch.get("frames", [])
            if frames:
                t = frames[-1].get("time", 0.0)
                if t > max_t: max_t = t
        
        if max_t == 0: max_t = 24.0 # Default 1 second (24 frames)
        anim_durations[anim_name] = max_t

    # Helper to read accessor data
    def read_accessor(acc_idx):
        acc = gltf.accessors[acc_idx]
        bv = gltf.bufferViews[acc.bufferView]
        buf = gltf.buffers[bv.buffer]
        
        # Safe blob access
        blob = gltf.binary_blob
        if callable(blob): blob = blob()
        
        data = gltf.get_data_from_buffer_uri(buf.uri) if buf.uri else (blob or b"")
        start = (bv.byteOffset or 0) + (acc.byteOffset or 0)
        
        # Determine format
        comp_count = {
            "SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16
        }.get(acc.type, 1)
        
        # Assume float for animation (5126)
        fmt = "<" + ("f" * comp_count)
        stride = struct.calcsize(fmt)
        
        values = []
        for i in range(acc.count):
            offset = start + (i * stride) # Note: tightly packed assumption (no bufferView stride)
            if bv.byteStride and bv.byteStride > 0:
                 offset = start + (i * bv.byteStride)
            values.append(struct.unpack_from(fmt, data, offset))
        return values

    # Helper to append new data
    def append_data(values, type_str):
        comp_count = {
            "SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4
        }.get(type_str, 1)
        fmt = "<" + ("f" * comp_count)
        new_bytes = b"".join([struct.pack(fmt, *v) for v in values])
        
        # Align to 4 bytes
        padding = (4 - (len(new_bytes) % 4)) % 4
        new_bytes += b"\x00" * padding
        
        # Safe blob access/setup
        blob = gltf.binary_blob
        if callable(blob): blob = blob()
        if blob is None: blob = b""
        
        offset = len(blob)
        final_blob = blob + new_bytes
        
        # Hack: pygltflib expects binary_blob to be a callable method in some versions.
        # So we overwrite it with a lambda that returns our new data.
        gltf.binary_blob = lambda: final_blob
        
        # Return (offset, length)
        return offset, len(new_bytes)

    # 2. Iterate GLTF Animations
    cleaned_count = 0
    trimmed_count = 0
    
    if gltf.animations:
        for gltf_anim in gltf.animations:
            if gltf_anim.name not in allowed_channels:
                continue
            
            allowed_set = allowed_channels[gltf_anim.name]
            target_duration_frames = anim_durations.get(gltf_anim.name, 24.0)
            target_duration_sec = target_duration_frames / 24.0
            
            new_channels = []
            
            # Filter Channels
            for ch in gltf_anim.channels:
                if ch.target.node is None: continue
                
                # Resolve Node Name
                node_name = f"node_{ch.target.node}"
                if gltf.nodes and ch.target.node < len(gltf.nodes):
                     if gltf.nodes[ch.target.node].name:
                         node_name = gltf.nodes[ch.target.node].name
                
                path = ch.target.path
                
                if (node_name, path) in allowed_set:
                    new_channels.append(ch)
                    
                    # PROCESS SAMPLER trimming
                    sampler = gltf_anim.samplers[ch.sampler]
                    
                    # Check if already processed (heuristic: if min/max on input matches target?)
                    # Or simpler: Just re-slice always. 
                    # Optimization: Only slice if max time > target + epsilon
                    
                    input_times = read_accessor(sampler.input) # List of (t,) tuples
                    times_flat = [t[0] for t in input_times]
                    if not times_flat: continue
                    
                    max_t_in = max(times_flat)
                    
                    if max_t_in > target_duration_sec + 0.01: # Epsilon
                        # Need to Trim
                        # Find cutoff index
                        cutoff_idx = 0
                        for i, t in enumerate(times_flat):
                            if t <= target_duration_sec + 0.001:
                                cutoff_idx = i
                        
                        # Inclusive slice
                        slice_len = cutoff_idx + 1
                        
                        # Read Output Values
                        output_vals = read_accessor(sampler.output)
                        
                        # Check compatibility
                        if len(output_vals) != len(input_times):
                            print("Warning: Accessor count mismatch, skipping trim.")
                            continue
                        
                        new_times = input_times[:slice_len]
                        new_outputs = output_vals[:slice_len]
                        
                        # Create New Accessors
                        # 1. Output (Keys)
                        out_vals_flat = new_outputs # List of tuples
                        # Look up type from old accessor
                        old_out_acc = gltf.accessors[sampler.output]
                        out_offset, out_len = append_data(out_vals_flat, old_out_acc.type)
                        
                        # Create BufferView
                        out_bv = BufferView(buffer=0, byteOffset=out_offset, byteLength=out_len)
                        gltf.bufferViews.append(out_bv)
                        out_bv_idx = len(gltf.bufferViews) - 1
                        
                        # Create Accessor
                        new_out_acc = Accessor(
                            bufferView=out_bv_idx,
                            componentType=5126, # FLOAT
                            count=slice_len,
                            type=old_out_acc.type
                        )
                        gltf.accessors.append(new_out_acc)
                        new_out_acc_idx = len(gltf.accessors) - 1
                        
                        # 2. Input (Times)
                        in_vals_flat = new_times
                        in_offset, in_len = append_data(in_vals_flat, "SCALAR")
                        
                        in_bv = BufferView(buffer=0, byteOffset=in_offset, byteLength=in_len)
                        gltf.bufferViews.append(in_bv)
                        in_bv_idx = len(gltf.bufferViews) - 1
                        
                        new_in_acc = Accessor(
                            bufferView=in_bv_idx,
                            componentType=5126, # FLOAT
                            count=slice_len,
                            type="SCALAR",
                            min=[new_times[0][0]],
                            max=[new_times[-1][0]]
                        )
                        gltf.accessors.append(new_in_acc)
                        new_in_acc_idx = len(gltf.accessors) - 1
                        
                        # Update Sampler
                        # CRITICAL: We must make a NEW sampler if shared?
                        # Using 'append' to sampler list? 
                        # To be safe, we perform IN-PLACE update if unique, or copy?
                        # For simplicity, we update in place. This fixes THIS channel. 
                        # If another channel uses it, it gets trimmed too (correct, if same anim).
                        # But wait, samplers are per-animation struct. They are NOT cross-animation shared usually.
                        # (Unless blender reuses them).
                        # We will assume unique sampler per anim-channel-group for now.
                        
                        sampler.input = new_in_acc_idx
                        sampler.output = new_out_acc_idx
                        trimmed_count += 1

                else:
                    cleaned_count += 1
            
            gltf_anim.channels = new_channels

    if cleaned_count > 0 or trimmed_count > 0:
        print(f"Sanitized GLTF: Removed {cleaned_count} channels, Trimmed {trimmed_count} samplers.")
        gltf.save(output_path)

def _merge_gltf_single_animation(target_bytes: bytes, source_bytes: bytes) -> bytes:
    """
    Merges the animation from source_bytes into target_bytes.
    Assumes source_bytes contains ONE animation (and geometry).
    We append the source's binary buffer to the target, remap indices, and add the animation.
    This creates file size overhead (duplicate geometry in buffer) but ensures total isolation.
    """
    try:
        from pygltflib import GLTF2
    except ImportError:
        # If pygltflib is missing, we can't merge. Just return target.
        # Ideally this should log a warning.
        return target_bytes

    target = GLTF2.load_from_bytes(target_bytes)
    source = GLTF2.load_from_bytes(source_bytes)

    if not source.animations:
        return target_bytes

    # 1. Prepare Binary Blob Concatenation
    t_blob = target.binary_blob() or b""
    s_blob = source.binary_blob() or b""
    
    # Calculate offset for source bufferViews
    blob_offset = len(t_blob)
    
    # Concatenate blobs
    target_blob_final = t_blob + s_blob
    target.set_binary_blob(target_blob_final)

    # 2. Remap and Append BufferViews
    bv_map = {}
    if not target.buffers: # Should exist for GLB
        target.buffers.append(source.buffers[0]) 
    
    base_bv_idx = len(target.bufferViews)
    base_acc_idx = len(target.accessors)
    
    for i, bv in enumerate(source.bufferViews):
        bv.byteOffset = (bv.byteOffset or 0) + blob_offset
        target.bufferViews.append(bv)
        bv_map[i] = base_bv_idx + i

    # 3. Remap and Append Accessors
    acc_map = {}
    for i, acc in enumerate(source.accessors):
        if acc.bufferView is not None:
            acc.bufferView = bv_map[acc.bufferView]
        target.accessors.append(acc)
        acc_map[i] = base_acc_idx + i

    # 4. Remap and Append Animation
    src_anim = source.animations[0]
    
    for sampler in src_anim.samplers:
        if sampler.input is not None:
            sampler.input = acc_map[sampler.input]
        if sampler.output is not None:
            sampler.output = acc_map[sampler.output]
            
    # No node remapping needed (Assumption: Identical Hierarchy)
    target.animations.append(src_anim)
    
    result = target.save_to_bytes()
    if isinstance(result, list):
        # Join list of bytes segments
        return b"".join(result)
    return result


def _export_glb_single_pass(model_json: object, output_path: str = None) -> bytes:
    """
    Internal function: Runs a single blender export pass.
    Renamed from original export_glb to support multi-pass strategy.
    """
    # Create temp dir
    tmp_dir = tempfile.mkdtemp(prefix="v3_export_")
    input_path = os.path.join(tmp_dir, "model_v3.json")
    
    # Create a unique temp file path for Blender to write into
    # If output_path is provided, we still use a temp one for blender (then move/read)
    # or just use it directly? Original logic used temp file inside tmp_dir.
    # Let's stick to original logic: write to temp, then read.
    fd, temp_output_path = tempfile.mkstemp(suffix=".glb", dir=tmp_dir)
    os.close(fd)
    
    try:
        os.remove(temp_output_path)
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

        written_path = _run_blender_export(input_path, temp_output_path, "glb") or temp_output_path

        # Post-process to remove crosstalk (still need sanitization per-pass)
        _sanitize_gltf(written_path, model_json)

        with open(written_path, "rb") as f:
            data = f.read()
            
        return data
    finally:
        if os.environ.get("KEEP_V3_GLTF_TMP") != "1":
            try:
                shutil.rmtree(tmp_dir, ignore_errors=True)
            except Exception:
                pass


def export_glb(model_json: object) -> bytes:
    """
    Orchestrates the export process.
    If multiple animations are present, it performs a "Clean Room" Multi-Pass Export
    and merges them at the GLTF level using pygltflib.
    """
    if isinstance(model_json, str):
         try:
             model_data = json.loads(model_json)
         except:
             # Fallback if valid JSON string but we need dict for logic
             return _export_glb_single_pass(model_json)
    else:
        model_data = model_json
        
    animations = model_data.get('animations') or []
    
    # Case A: 0 or 1 Animation -> Single Pass
    if len(animations) <= 1:
        return _export_glb_single_pass(model_data)
        
    print(f"[Multi-Pass Export] Detected {len(animations)} animations. Using Clean Room Merge.")
    
    # Case B: Multi-Pass
    # 1. Export Master (Geometry + Anim 0)
    master_scope = json.loads(json.dumps(model_data))
    master_scope['animations'] = [animations[0]] if animations else []
    
    print(f"[Pass 0] Exporting Master Base...")
    master_bytes = _export_glb_single_pass(master_scope)
    
    # 2. Loop & Merge
    for i in range(1, len(animations)):
        anim = animations[i]
        anim_name = anim.get('name', f'anim_{i}')
        print(f"[Pass {i}] Exporting Isolated ({anim_name})...")
        
        pass_scope = json.loads(json.dumps(model_data))
        pass_scope['animations'] = [anim]
        
        source_bytes = _export_glb_single_pass(pass_scope)
        
        print(f"  Merging {anim_name} into Master...")
        master_bytes = _merge_gltf_single_animation(master_bytes, source_bytes)
            
    return master_bytes


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