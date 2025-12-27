"""
BBModel → v3 Schema Importer

Converts Blockbench .bbmodel files to v3 schema format.
Focus: Geometry-first approach (Phase 1), textures later (Phase 2).
"""

import json
import logging
import base64
import math
from pathlib import Path
from typing import Dict, List, Optional, Any, Union

# Import BlockJSON schema
# Import BlockJSON schema
from blocksmith.schema.blockjson import (
    ModelDefinition, MetaModel, AtlasDefinition,
    CuboidEntity, GroupEntity, FaceTexture, FaceEnum
)

logger = logging.getLogger(__name__)

# Constants
PIXELS_PER_BLOCK = 16  # Minecraft standard
DEFAULT_TEXEL_DENSITY = 16
MIN_TEXEL_DENSITY = 1
MAX_TEXEL_DENSITY = 256


def euler_to_quaternion(euler_degrees: List[float]) -> List[float]:
    """
    Convert Euler angles [rx, ry, rz] in degrees to quaternion [w, x, y, z].
    Uses ZYX rotation order (yaw, pitch, roll) which matches Blockbench.
    """
    rx, ry, rz = [math.radians(angle) for angle in euler_degrees]
    
    # Half angles
    cx = math.cos(rx * 0.5)
    sx = math.sin(rx * 0.5)
    cy = math.cos(ry * 0.5)
    sy = math.sin(ry * 0.5)
    cz = math.cos(rz * 0.5)
    sz = math.sin(rz * 0.5)
    
    # Quaternion multiplication (ZYX order)
    w = cx * cy * cz + sx * sy * sz
    x = sx * cy * cz - cx * sy * sz
    y = cx * sy * cz + sx * cy * sz
    z = cx * cy * sz - sx * sy * cz
    
    return [w, x, y, z]


def import_bbmodel(
    bbmodel_data: Union[Dict, str],
    texture_files: Optional[List[str]] = None,
    texture_dir: Optional[str] = None,
    options: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Import BBModel to v3 schema.
    
    Args:
        bbmodel_data: BBModel dict or JSON string
        texture_files: Optional list of texture file paths
        texture_dir: Optional directory to scan for textures
        options: Import options (geometry_only=True for Phase 1)
    
    Returns:
        v3 schema dict
    """
    if options is None:
        options = {}
    
    # Parse input if string
    if isinstance(bbmodel_data, str):
        bbmodel_data = json.loads(bbmodel_data)
    
    # Validate BBModel
    if not bbmodel_data.get("meta") or not bbmodel_data["meta"].get("format_version"):
        raise ValueError("Invalid bbmodel: missing meta or format_version")
    
    logger.info(f"Importing BBModel '{bbmodel_data.get('name', 'unnamed')}' "
                f"(format v{bbmodel_data['meta']['format_version']})")
    
    # BBModel always uses 16 pixels per block (texture resolution is separate from texel density)
    texel_density = DEFAULT_TEXEL_DENSITY  # Always 16 pixels per block
    
    # Validate texel density
    if not isinstance(texel_density, (int, float)) or texel_density < MIN_TEXEL_DENSITY or texel_density > MAX_TEXEL_DENSITY:
        logger.warning(f"Invalid texel density {texel_density}, using default {DEFAULT_TEXEL_DENSITY}")
        texel_density = DEFAULT_TEXEL_DENSITY
    
    # Extract texture from BBModel if available
    atlas = _extract_texture_atlas(bbmodel_data)
    
    # Get texture resolution for UV normalization
    texture_resolution = bbmodel_data.get("resolution", {"width": 128, "height": 128})
    texture_width = texture_resolution.get("width", 128)
    texture_height = texture_resolution.get("height", 128)
    
    # Create meta
    meta = MetaModel(
        schema_version="3.0",
        texel_density=texel_density,
        atlases={"main": atlas},
        import_source="bbmodel"
    )
    
    # Process entities
    entities = []
    uuid_to_id = {}  # Map BBModel UUIDs to v3 IDs
    entity_parents = {}  # Track parent relationships from outliner
    
    # Build a map of group UUID → group data from the 'groups' array
    # Blockbench stores full group data (including rotation) in 'groups' array,
    # while 'outliner' only contains hierarchy info when file is saved
    groups_data_map: Dict[str, Dict] = {}
    for group_data in bbmodel_data.get("groups", []):
        if "uuid" in group_data:
            groups_data_map[group_data["uuid"]] = group_data
    
    if groups_data_map:
        logger.debug(f"Found {len(groups_data_map)} groups in 'groups' array with rotation data")
    
    # First pass: process outliner to build hierarchy and collect group info
    group_transforms = {}  # Store group transforms for later use
    if bbmodel_data.get("outliner"):
        _build_hierarchy_map(bbmodel_data["outliner"], entity_parents)
        _collect_group_transforms(bbmodel_data["outliner"], group_transforms, texel_density, groups_data_map)
    
    # Process elements (cuboids)
    for i, element in enumerate(bbmodel_data.get("elements", [])):
        if element["type"] != "cube":
            continue
            
        # Use UUID as unique ID, name as label
        entity_id = element["uuid"]
        uuid_to_id[element["uuid"]] = entity_id
        
        # Get parent info
        parent_id = entity_parents.get(element["uuid"])
        
        # CRITICAL: BBModel stores cubes in WORLD coordinates (pixels)
        # v3 schema expects LOCAL coordinates relative to parent
        
        # Get element's world coordinates (in pixels)
        element_origin_world = element.get("origin", [(element["from"][j] + element["to"][j]) / 2 for j in range(3)])
        element_from_world = element["from"]
        element_to_world = element["to"]
        
        # Convert to v3 units (divide by texel_density)
        origin_world_v3 = [coord / texel_density for coord in element_origin_world]
        from_world_v3 = [coord / texel_density for coord in element_from_world]
        to_world_v3 = [coord / texel_density for coord in element_to_world]
        
        # Calculate from/to relative to the element's own origin/pivot
        # This is ALWAYS relative to the element's pivot, not the parent
        from_local = [from_world_v3[j] - origin_world_v3[j] for j in range(3)]
        to_local = [to_world_v3[j] - origin_world_v3[j] for j in range(3)]
        
        # Convert world pivot to LOCAL pivot (relative to parent)
        # v3 schema: pivot is LOCAL translation in parent space
        if parent_id and parent_id in group_transforms:
            parent_world_pivot = group_transforms[parent_id]["pivot"]
            pivot = [origin_world_v3[j] - parent_world_pivot[j] for j in range(3)]
        else:
            # No parent - pivot is world position (root level)
            pivot = origin_world_v3
        
        # Set from/to coords (ensure from < to)
        from_coords = from_local[:]
        to_coords = to_local[:]
        
        # Ensure from < to after transform
        for i in range(3):
            if from_coords[i] > to_coords[i]:
                from_coords[i], to_coords[i] = to_coords[i], from_coords[i]
        
        # Convert rotation (Euler → Quaternion)
        rotation_euler = element.get("rotation", [0, 0, 0])
        # Direct conversion - no negation needed since coordinate systems match
        rotation_quat = euler_to_quaternion(rotation_euler)
        
        # Handle inflate (BBModel's geometry expansion property)
        # For BBModel/Bedrock formats, we store inflate separately (not baked)
        inflate = element.get("inflate", 0)
        inflate_in_units = inflate / texel_density
        scale_factors = [1.0, 1.0, 1.0]  # BBModel doesn't use scale transforms
        
        # Extract face UVs from BBModel (normalized to 0-1 range)
        faces = _extract_face_uvs(element, texture_width, texture_height)
        
        cuboid_data = {
            "id": entity_id,
            "label": element.get("name", entity_id),
            "parent": parent_id,
            "from": from_coords,  # Use alias 'from' 
            "to": to_coords,
            "pivot": pivot,
            "rotation": rotation_quat,
            "scale": scale_factors,
            "faces": faces,
            "inflate": inflate_in_units
        }
        
        if not options.get("geometry_only", True):
            cuboid_data["metadata"] = {
                "bbmodel": {
                    "uuid": element["uuid"]
                }
            }
        
        cuboid = CuboidEntity(**cuboid_data)
        
        entities.append(cuboid)
    
    # Process outliner to create groups
    if bbmodel_data.get("outliner"):
        _create_groups_from_outliner(
            bbmodel_data["outliner"], 
            entities, 
            uuid_to_id, 
            texel_density,
            options,
            groups_data_map,
            group_transforms,
            parent_id=None
        )
    
    # Create model definition
    model = ModelDefinition(
        meta=meta,
        entities=entities
    )
    
    data = model.model_dump(by_alias=True)
    try:
        # Ensure UVs/resolution for completeness
        from ..uv_utils import ensure_uvs  # type: ignore
        data = ensure_uvs(data, texel_density=texel_density, mode="strip")
    except ModuleNotFoundError:
        # uv_utils not available - skip UV processing (geometry-only import)
        logger.debug("UV processing skipped (geometry-only import)")
    except Exception as e:
        logger.debug(f"UV processing failed: {e} (continuing with geometry-only)")
    
    return data


def _create_dummy_atlas() -> AtlasDefinition:
    """Create a 1x1 white dummy atlas for geometry-only imports."""
    # 1x1 white PNG in base64
    white_png_base64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
    
    return AtlasDefinition(
        data=white_png_base64,
        mime="image/png", 
        resolution=[1, 1]
    )


def _extract_texture_atlas(bbmodel_data: Dict) -> AtlasDefinition:
    """
    Extract texture atlas from BBModel.
    
    BBModel embeds textures as base64 data URIs in the 'textures' array.
    Returns the first texture found, or a dummy atlas if none.
    """
    textures = bbmodel_data.get("textures", [])
    
    if textures:
        # Use the first texture
        tex = textures[0]
        source = tex.get("source", "")
        
        # BBModel stores as data URI: "data:image/png;base64,..."
        if source.startswith("data:"):
            # Extract mime type and base64 data
            parts = source.split(",", 1)
            if len(parts) == 2:
                header = parts[0]  # e.g., "data:image/png;base64"
                data_b64 = parts[1]
                
                # Parse mime type
                mime = "image/png"  # Default
                if "image/png" in header:
                    mime = "image/png"
                elif "image/jpeg" in header:
                    mime = "image/jpeg"
                
                # Get resolution from texture or bbmodel resolution
                width = tex.get("width") or tex.get("uv_width", 128)
                height = tex.get("height") or tex.get("uv_height", 128)
                
                logger.debug(f"Extracted texture: {width}x{height}, {len(data_b64)} bytes")
                
                return AtlasDefinition(
                    data=data_b64,
                    mime=mime,
                    resolution=[width, height]
                )
    
    # No texture found - return dummy
    logger.warning("No texture found in BBModel, using dummy atlas")
    return _create_dummy_atlas()


def _extract_face_uvs(element: Dict, texture_width: int, texture_height: int) -> Dict[FaceEnum, FaceTexture]:
    """
    Extract and normalize UV coordinates from BBModel element faces.
    
    BBModel stores UVs in pixel coordinates, we normalize to 0-1 range.
    """
    faces = {}
    
    # Mapping from BBModel face names to v3 FaceEnum
    face_mapping = {
        "north": FaceEnum.front,  # BBModel north = front (negative Z face)
        "south": FaceEnum.back,   # BBModel south = back (positive Z face)
        "east": FaceEnum.right,   # BBModel east = right (positive X face)
        "west": FaceEnum.left,    # BBModel west = left (negative X face)
        "up": FaceEnum.top,
        "down": FaceEnum.bottom
    }
    
    bbmodel_faces = element.get("faces", {})
    
    for bbmodel_name, v3_face in face_mapping.items():
        face_data = bbmodel_faces.get(bbmodel_name, {})
        uv = face_data.get("uv", [0, 0, 16, 16])  # Default to full face
        
        # Normalize UV from pixel coords to 0-1 range
        # BBModel UV: [u1, v1, u2, v2] in pixels
        u1 = uv[0] / texture_width
        v1 = uv[1] / texture_height
        u2 = uv[2] / texture_width
        v2 = uv[3] / texture_height
        
        # INVERSE FLIPS Logic
        # If exporting applied a flip, importing must un-flip.
        # FLIP_H (Swap U): V3(u1,u2) -> BB(u2,u1) => Import BB(u1,u2) is actually (u2,u1)
        # FLIP_V (Swap V): V3(v1,v2) -> BB(v2,v1) => Import BB(v1,v2) is actually (v2,v1)
        
        # West is FLIP_H + FLIP_V
        if v3_face == FaceEnum.left: # West
             u1, u2 = u2, u1
             v1, v2 = v2, v1
        # All others are FLIP_V only
        else:
             v1, v2 = v2, v1

        faces[v3_face] = FaceTexture(
            atlas_id="main",
            uv=[u1, v1, u2, v2]
        )
    
    return faces


def _build_hierarchy_map(
    nodes: List[Union[str, Dict]], 
    entity_parents: Dict[str, str],
    parent_id: Optional[str] = None
) -> None:
    """
    Build a map of entity UUID -> parent_id from BBModel outliner.
    
    Args:
        nodes: BBModel outliner nodes (strings for elements, dicts for groups)
        entity_parents: Output mapping of UUID -> parent_id
        parent_id: Current parent ID for nested elements
    """
    for node in nodes:
        if isinstance(node, str):
            # Element reference - map to parent
            entity_parents[node] = parent_id
        else:
            # Group node - process children with this group as parent
            group_id = node["uuid"]
            if "children" in node:
                _build_hierarchy_map(node["children"], entity_parents, group_id)


def _collect_group_transforms(
    nodes: List[Union[str, Dict]], 
    group_transforms: Dict[str, Dict],
    texel_density: float,
    groups_data_map: Dict[str, Dict] = None,
    parent_pivot: Optional[List[float]] = None
) -> None:
    """
    Collect group transforms (pivot points) from BBModel outliner.
    
    Args:
        nodes: BBModel outliner nodes (strings for elements, dicts for groups)
        group_transforms: Output mapping of UUID -> transform info
        texel_density: Pixels per block for coordinate conversion
        groups_data_map: Mapping of group UUID -> full group data (from 'groups' array)
        parent_pivot: Parent group's pivot in v3 coordinates (for nested groups)
    """
    if groups_data_map is None:
        groups_data_map = {}
        
    for node in nodes:
        if isinstance(node, dict):  # Group node
            group_uuid = node.get("uuid")
            
            # Look up full group data from 'groups' array (has rotation when Blockbench saves)
            full_group_data = groups_data_map.get(group_uuid, {})
            
            # Get origin - prefer 'groups' array, fall back to outliner node
            origin = full_group_data.get("origin") or node.get("origin", [0, 0, 0])
            pivot_v3 = [coord / texel_density for coord in origin]
            # Direct conversion - coordinate systems match
            
            # Get rotation - prefer 'groups' array (Blockbench saves rotation there!)
            rotation = full_group_data.get("rotation") or node.get("rotation", [0, 0, 0])
            
            # Store the world pivot for this group
            group_transforms[group_uuid] = {
                "pivot": pivot_v3,
                "rotation": rotation
            }
            
            # Process children recursively
            if "children" in node:
                _collect_group_transforms(node["children"], group_transforms, texel_density, groups_data_map, pivot_v3)


def _create_groups_from_outliner(
    nodes: List[Union[str, Dict]], 
    entities: List[Union[CuboidEntity, GroupEntity]], 
    uuid_to_id: Dict[str, str],
    texel_density: float,
    options: Dict[str, Any],
    groups_data_map: Dict[str, Dict] = None,
    group_transforms: Dict[str, Dict] = None,
    parent_id: Optional[str] = None
) -> None:
    """
    Create GroupEntity objects from BBModel outliner hierarchy.
    
    Args:
        nodes: BBModel outliner nodes (strings for elements, dicts for groups)
        entities: List to append created GroupEntity objects to
        uuid_to_id: Mapping of BBModel UUID -> v3 entity ID
        texel_density: Pixels per block for coordinate conversion
        options: Import options (geometry_only, etc.)
        groups_data_map: Mapping of group UUID -> full group data (from 'groups' array)
        group_transforms: Mapping of group UUID -> world pivot/rotation
        parent_id: Parent group ID for nested groups
    """
    if groups_data_map is None:
        groups_data_map = {}
    if group_transforms is None:
        group_transforms = {}
        
    for node in nodes:
        if isinstance(node, dict):  # Only process group nodes
            # Group node - use UUID as ID
            group_id = node.get("uuid")
            
            # Look up full group data from 'groups' array (has rotation when Blockbench saves)
            full_group_data = groups_data_map.get(group_id, {})
            
            # Get origin (world coordinates) - prefer 'groups' array, fall back to outliner node
            origin = full_group_data.get("origin") or node.get("origin", [0, 0, 0])
            world_pivot = [coord / texel_density for coord in origin]
            
            # Convert world pivot to LOCAL pivot (relative to parent)
            # v3 schema: pivot is LOCAL translation in parent space
            if parent_id and parent_id in group_transforms:
                parent_world_pivot = group_transforms[parent_id]["pivot"]
                pivot = [world_pivot[j] - parent_world_pivot[j] for j in range(3)]
            else:
                # No parent - pivot is world position (root level)
                pivot = world_pivot
            
            # Get rotation - prefer 'groups' array (Blockbench saves rotation there!)
            rotation_euler = full_group_data.get("rotation") or node.get("rotation", [0, 0, 0])
            # Direct conversion - no negation needed since coordinate systems match
            rotation_quat = euler_to_quaternion(rotation_euler)
            
            # Only store metadata that can't be recovered
            metadata = None
            if not options.get("geometry_only", True):
                # UUID is the only thing we can't derive from v3 data
                metadata = {
                    "bbmodel": {
                        "uuid": group_id
                    }
                }
            
            group = GroupEntity(
                id=group_id,
                label=full_group_data.get("name") or node.get("name", group_id),
                parent=parent_id,
                pivot=pivot,
                rotation=rotation_quat,
                metadata=metadata
            )
            
            entities.append(group)
            
            # Process children recursively
            if "children" in node:
                _create_groups_from_outliner(
                    node["children"], 
                    entities, 
                    uuid_to_id, 
                    texel_density,
                    options,
                    groups_data_map,
                    group_transforms,
                    parent_id=group_id
                )