"""
v3 Schema → BBModel Exporter

Converts v3 schema format back to Blockbench .bbmodel files.
Focus: Geometry-first approach (Phase 1), textures later (Phase 2).
"""

import json
import logging
import math
import uuid
import base64
from typing import Dict, List, Optional, Any, Union

# Import BlockJSON schema
from blocksmith.schema.blockjson import ModelDefinition, CuboidEntity, GroupEntity
from blocksmith.converters.uv_mapper import to_bbmodel

logger = logging.getLogger(__name__)

# Constants
PIXELS_PER_BLOCK = 16  # Minecraft standard
DEFAULT_TEXEL_DENSITY = 16
COORDINATE_PRECISION = 4  # Decimal places for pixel coordinates
ANGLE_PRECISION = 6      # Decimal places for rotation angles


def _get_atlas_resolution(model: ModelDefinition) -> tuple[int, int]:
    """Read atlas resolution from the validated v3 model; default to 256x256."""
    try:
        if model.meta and model.meta.atlases:
            main_atlas = model.meta.atlases.get("main")
            if main_atlas and main_atlas.resolution and len(main_atlas.resolution) == 2:
                return int(main_atlas.resolution[0]), int(main_atlas.resolution[1])
    except Exception:
        pass
    return 256, 256


def _calculate_world_pivot(entity: Union[CuboidEntity, GroupEntity], entities_dict: Dict[str, Union[CuboidEntity, GroupEntity]]) -> List[float]:
    """Calculate world pivot by walking up parent hierarchy."""
    world_pivot = entity.pivot.copy()
    
    current_parent_id = entity.parent
    while current_parent_id and current_parent_id in entities_dict:
        parent = entities_dict[current_parent_id]
        # Add parent's pivot to world position
        for i in range(3):
            world_pivot[i] += parent.pivot[i]
        current_parent_id = parent.parent
    
    return world_pivot


def quaternion_to_euler(quat: List[float]) -> List[float]:
    """
    Convert quaternion [w, x, y, z] to Euler angles [rx, ry, rz] in degrees.
    Uses ZYX rotation order to match Blockbench.
    """
    w, x, y, z = quat
    
    # Roll (x-axis rotation)
    sinr_cosp = 2 * (w * x + y * z)
    cosr_cosp = 1 - 2 * (x * x + y * y)
    rx = math.atan2(sinr_cosp, cosr_cosp)
    
    # Pitch (y-axis rotation)
    sinp = 2 * (w * y - z * x)
    if abs(sinp) >= 1:
        ry = math.copysign(math.pi / 2, sinp)  # Use 90 degrees if out of range
    else:
        ry = math.asin(sinp)
    
    # Yaw (z-axis rotation)
    siny_cosp = 2 * (w * z + x * y)
    cosy_cosp = 1 - 2 * (y * y + z * z)
    rz = math.atan2(siny_cosp, cosy_cosp)
    
    # Convert to degrees
    return [math.degrees(rx), math.degrees(ry), math.degrees(rz)]


def export_bbmodel(
    schema_data: Union[Dict, str],
    output_dir: Optional[str] = None,
    options: Dict[str, Any] = None
) -> str:
    """
    Export v3 schema to BBModel JSON string.
    
    Args:
        schema_data: v3 schema dict or JSON string
        output_dir: Optional output directory (for Phase 2 texture files)
        options: Export options (geometry_only=True for Phase 1)
    
    Returns:
        BBModel JSON string
    """
    if options is None:
        options = {}
    
    # Parse input if string
    if isinstance(schema_data, str):
        schema_data = json.loads(schema_data)
    
    # Strip any extra fields from meta that aren't in the v3 schema
    # This handles legacy models that may have extra fields like 'generator'
    if 'meta' in schema_data:
        allowed_meta_fields = {'schema_version', 'texel_density', 'atlases', 'import_source'}
        schema_data['meta'] = {k: v for k, v in schema_data['meta'].items() if k in allowed_meta_fields}
    
    # Validate v3 schema
    try:
        model = ModelDefinition.model_validate(schema_data)
    except Exception as e:
        raise ValueError(f"Invalid v3 schema: {e}")
    
    logger.info(f"Exporting v3 schema to BBModel (texel_density={model.meta.texel_density})")
    
    # Extract parameters
    texel_density = model.meta.texel_density
    atlas_w, atlas_h = _get_atlas_resolution(model)
    
    # Process textures
    bb_textures = []
    atlas_map = {} # v3 atlas_id -> bb texture index
    if model.meta.atlases:
        main_atlas = model.meta.atlases.get("main")
        if main_atlas and main_atlas.data:
            resolution = main_atlas.resolution or [atlas_w, atlas_h]
            texture_index = len(bb_textures)
            atlas_map["main"] = texture_index
            
            # BBModel requires a specific set of texture properties
            tex_obj = {
                "uuid": str(uuid.uuid4()),
                "name": "main",
                "id": texture_index,
                "source": f"data:image/png;base64,{main_atlas.data}",
                "width": resolution[0],
                "height": resolution[1],
                "uv_width": resolution[0],
                "uv_height": resolution[1],
                "folder": "",
                "namespace": "",
                "path": "",
                "visible": True,
                "internal": True, # Keep as internal data URI
                "render_mode": "default",
                "render_sides": "auto",
            }
            bb_textures.append(tex_obj)
            
            # Set model resolution to match the main atlas
            resolution_w, resolution_h = resolution
        else:
            resolution_w, resolution_h = 256, 256
    else:
        resolution_w, resolution_h = 256, 256


    # Create BBModel structure
    bbmodel = {
        "meta": {
            "format_version": "4.10",
            "model_format": "free",
            "box_uv": False
        },
        "name": "exported_model",
        "resolution": {
            "width": resolution_w,
            "height": resolution_h
        },
        "elements": [],
        "outliner": [],
        "textures": bb_textures
    }
    
    # Map v3 entities to BBModel structures
    id_to_uuid = {}
    elements = []
    groups = {}  # Store as dict for easy lookup
    
    # Create entity lookup dict for hierarchy walking
    entities_dict = {entity.id: entity for entity in model.entities}
    
    for entity in model.entities:
        entity_uuid = str(uuid.uuid4())
        id_to_uuid[entity.id] = entity_uuid
        
        if isinstance(entity, CuboidEntity):
            elements.append(_convert_cuboid_to_bbmodel(
                entity, 
                entity_uuid, 
                texel_density, 
                entities_dict, 
                atlas_map,
                resolution_w,
                resolution_h
            ))
        elif isinstance(entity, GroupEntity):
            groups[entity.id] = _convert_group_to_bbmodel(entity, entity_uuid, texel_density, entities_dict)
    
    # Add elements to BBModel
    bbmodel["elements"] = elements
    
    # Build outliner hierarchy
    bbmodel["outliner"] = _build_outliner(model.entities, id_to_uuid, groups)
    
    return json.dumps(bbmodel, indent=2)


def _convert_cuboid_to_bbmodel(
    cuboid: CuboidEntity, 
    entity_uuid: str, 
    texel_density: float,
    entities_dict: Dict[str, Union[CuboidEntity, GroupEntity]] = None,
    atlas_map: Dict[str, int] = None,
    atlas_w: int = 256,
    atlas_h: int = 256
) -> Dict[str, Any]:
    """Convert v3 CuboidEntity to BBModel element."""
    
    # Calculate world pivot by walking up parent hierarchy
    world_pivot = _calculate_world_pivot(cuboid, entities_dict or {})
    
    # Convert from v3 local coordinates to BBModel world coordinates
    from_local = list(cuboid.from_)  # Access aliased field properly
    to_local = list(cuboid.to)
    
    # Convert to world coordinates by adding world pivot
    from_world = [from_local[i] + world_pivot[i] for i in range(3)]
    to_world = [to_local[i] + world_pivot[i] for i in range(3)]
    
    # Ensure from < to in world coordinates
    for i in range(3):
        if from_world[i] > to_world[i]:
            from_world[i], to_world[i] = to_world[i], from_world[i]
    
    # Scale to pixels
    from_px = [coord * texel_density for coord in from_world]
    to_px = [coord * texel_density for coord in to_world]
    origin_px = [coord * texel_density for coord in world_pivot]
    
    # Convert quaternion back to Euler - no transform needed
    euler_bbmodel = quaternion_to_euler(cuboid.rotation)
    
    # Check for preserved UUID in metadata (only non-recoverable data)
    if cuboid.metadata and "bbmodel" in cuboid.metadata:
        bb_meta = cuboid.metadata["bbmodel"]
        entity_uuid = bb_meta.get("uuid", entity_uuid)
    
    # Convert inflate from blocks back to pixels
    inflate_px = cuboid.inflate * texel_density
    
    # Note: BBModel can't represent scale transforms, so we ignore cuboid.scale
    # This matches BBModel's own behavior when exporting to other formats
    
    # Round coordinates to reasonable precision to prevent floating point noise
    from_px = [round(coord, COORDINATE_PRECISION) for coord in from_px]
    to_px = [round(coord, COORDINATE_PRECISION) for coord in to_px]
    origin_px = [round(coord, COORDINATE_PRECISION) for coord in origin_px]
    euler_bbmodel = [round(angle, ANGLE_PRECISION) for angle in euler_bbmodel]
    
    # Create BBModel element
    element = {
        "name": cuboid.label,
        "type": "cube",
        "uuid": entity_uuid,
        "box_uv": False,
        "rescale": False,
        "locked": False,
        "render_order": "default",
        "allow_mirror_modeling": True,
        "from": from_px,
        "to": to_px,
        "autouv": 0,
        "color": 1,
        "origin": origin_px,
        "rotation": euler_bbmodel,
        "faces": {
            "north": {"uv": [0, 0, 16, 16], "texture": None},
            "east": {"uv": [0, 0, 16, 16], "texture": None},
            "south": {"uv": [0, 0, 16, 16], "texture": None},
            "west": {"uv": [0, 0, 16, 16], "texture": None},
            "up": {"uv": [0, 0, 16, 16], "texture": None},
            "down": {"uv": [0, 0, 16, 16], "texture": None}
        }
    }
    
    # Per-face UVs from centralized mapper (applies BB flips)
    if atlas_map and cuboid.faces:
        v3_to_bb_face_map = {
            "front": "north", "back": "south", "left": "west",
            "right": "east", "top": "up", "bottom": "down"
        }
        for v3_face_name, face_texture in cuboid.faces.items():
            bb_face_name = v3_to_bb_face_map.get(v3_face_name)
            if not bb_face_name or not face_texture.uv:
                continue
            
            pixel_uv = to_bbmodel(face_texture.uv, v3_face_name, atlas_w, atlas_h)
            
            element["faces"][bb_face_name]["uv"] = pixel_uv
            element["faces"][bb_face_name]["texture"] = atlas_map.get(face_texture.atlas_id)

            # Fix Bottom/-Y Rotation (User reported 90 deg CCW offset relative to GLTF)
            if v3_face_name == "bottom":
                element["faces"][bb_face_name]["rotation"] = 90
    
    # Add inflate if non-zero
    if inflate_px != 0:
        element["inflate"] = round(inflate_px, COORDINATE_PRECISION)
    
    return element


def _convert_group_to_bbmodel(
    group: GroupEntity, 
    entity_uuid: str, 
    texel_density: float,
    entities_dict: Dict[str, Union[CuboidEntity, GroupEntity]] = None
) -> Dict[str, Any]:
    """Convert v3 GroupEntity to BBModel group node."""
    
    # Calculate WORLD pivot by walking up parent hierarchy
    # BBModel groups need origins in world coordinates!
    world_pivot = _calculate_world_pivot(group, entities_dict or {})
    origin_px = [coord * texel_density for coord in world_pivot]
    
    # Convert quaternion back to Euler - no transform needed
    euler_bbmodel = quaternion_to_euler(group.rotation)
    
    # Check for preserved UUID in metadata (only non-recoverable data)
    if group.metadata and "bbmodel" in group.metadata:
        bb_meta = group.metadata["bbmodel"]
        entity_uuid = bb_meta.get("uuid", entity_uuid)
    
    # Create BBModel group node
    group_node = {
        "name": group.label,
        "origin": origin_px,
        "rotation": euler_bbmodel,
        "color": 0,
        "uuid": entity_uuid,
        "export": True,
        "mirror_uv": False,
        "isOpen": True,
        "locked": False,
        "visibility": True,
        "autouv": 0,
        "children": []  # Will be populated by _build_outliner
    }
    
    return group_node


def _build_outliner(
    entities: List[Union[CuboidEntity, GroupEntity]], 
    id_to_uuid: Dict[str, str],
    converted_groups: Dict[str, Dict[str, Any]]
) -> List[Union[str, Dict[str, Any]]]:
    """Build BBModel outliner structure from v3 entity hierarchy."""
    
    # Find root entities (no parent)
    root_entities = [e for e in entities if e.parent is None]
    
    def build_node(entity):
        if isinstance(entity, CuboidEntity):
            # Cuboids are just UUID references
            return id_to_uuid[entity.id]
        else:
            # Groups use pre-converted structure
            if entity.id in converted_groups:
                group_dict = converted_groups[entity.id].copy()  # Copy to avoid mutation
                
                # Add children
                children = [e for e in entities if e.parent == entity.id]
                group_dict["children"] = [build_node(child) for child in children]
                
                return group_dict
            else:
                return id_to_uuid[entity.id]  # Fallback
    
    return [build_node(entity) for entity in root_entities]