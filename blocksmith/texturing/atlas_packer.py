"""
V3-native texture atlas packer.

Handles packing textures into atlases while respecting the existing UV layout.
This ensures consistent texel density across all faces.
"""

import base64
import logging
import math
from io import BytesIO
from typing import Dict, Any, List, Tuple, Optional
from PIL import Image

logger = logging.getLogger(__name__)


def _tile_texture_to_size(source: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """
    Create a texture of target size by tiling/cropping the source.
    
    This maintains consistent pixel size (no stretching) by:
    - Tiling if target is larger than source
    - Cropping if target is smaller than source
    
    Args:
        source: Source texture (any size)
        target_w: Target width in pixels
        target_h: Target height in pixels
        
    Returns:
        New image of exactly target_w x target_h
    """
    if source.mode != 'RGBA':
        source = source.convert('RGBA')
    
    src_w, src_h = source.size
    
    # Create target image with transparent background
    result = Image.new('RGBA', (target_w, target_h), (0, 0, 0, 0))
    
    # Tile the source texture to fill target
    for y in range(0, target_h, src_h):
        for x in range(0, target_w, src_w):
            # Calculate how much of the source to use
            paste_w = min(src_w, target_w - x)
            paste_h = min(src_h, target_h - y)
            
            # Crop source if needed
            if paste_w < src_w or paste_h < src_h:
                cropped = source.crop((0, 0, paste_w, paste_h))
                result.paste(cropped, (x, y))
            else:
                result.paste(source, (x, y))
    
    return result


def pack_textures_into_atlas(
    entity_textures: Dict[str, Image.Image],
    model_data: Optional[Dict[str, Any]] = None,
    texel_density: int = 16
) -> Tuple[str, Dict[str, Dict[str, List[float]]]]:
    """
    Pack entity textures into an atlas with proper texel density.
    
    If model_data is provided, uses the existing UV layout.
    Otherwise creates a new layout based on texel_density.
    
    Args:
        entity_textures: Dict of entity_id -> PIL Image (the texture for that entity)
        model_data: Optional v3 model JSON to get UV layout from
        texel_density: Pixels per unit (default 16)
        
    Returns:
        Tuple of:
        - atlas_b64: Base64-encoded PNG atlas
        - uv_map: Dict of entity_id -> {face: [u1, v1, u2, v2]} normalized UVs
    """
    if not entity_textures:
        logger.warning("No textures to pack, returning transparent atlas")
        return _create_transparent_atlas(64), {}
    
    # If we have model data, use its existing UV layout
    if model_data:
        return _pack_using_existing_uvs(entity_textures, model_data, texel_density)
    else:
        return _pack_with_proper_sizing(entity_textures, texel_density)


def _pack_using_existing_uvs(
    entity_textures: Dict[str, Image.Image],
    model_data: Dict[str, Any],
    texel_density: int
) -> Tuple[str, Dict[str, Dict[str, List[float]]]]:
    """
    Paint textures into the existing atlas layout, respecting UV coordinates.
    """
    # Get existing atlas info
    atlas_info = model_data.get('meta', {}).get('atlases', {}).get('main', {})
    atlas_resolution = atlas_info.get('resolution', [256, 256])
    atlas_width, atlas_height = atlas_resolution
    
    # Create or load existing atlas
    if atlas_info.get('data'):
        try:
            atlas_bytes = base64.b64decode(atlas_info['data'])
            atlas = Image.open(BytesIO(atlas_bytes)).convert('RGBA')
        except:
            atlas = Image.new('RGBA', (atlas_width, atlas_height), (0, 0, 0, 0))
    else:
        atlas = Image.new('RGBA', (atlas_width, atlas_height), (0, 0, 0, 0))
    
    uv_map = {}
    
    # For each entity with a texture, paint into its UV regions
    for entity in model_data.get('entities', []):
        if entity.get('type') != 'cuboid':
            continue
            
        entity_id = entity['id']
        
        if entity_id not in entity_textures:
            # Keep existing UVs for this entity
            if 'faces' in entity:
                uv_map[entity_id] = {
                    face: data.get('uv', [0, 0, 1, 1])
                    for face, data in entity['faces'].items()
                }
            continue
        
        source_texture = entity_textures[entity_id]
        if source_texture.mode != 'RGBA':
            source_texture = source_texture.convert('RGBA')
        
        # Calculate cuboid dimensions for proper face sizing
        from_coords = entity.get('from', [0, 0, 0])
        to_coords = entity.get('to', [1, 1, 1])
        size_x = abs(to_coords[0] - from_coords[0])
        size_y = abs(to_coords[1] - from_coords[1])
        size_z = abs(to_coords[2] - from_coords[2])
        
        # Calculate pixel dimensions for each face type based on cuboid geometry
        # This is the KEY - face dimensions depend on which axes the face spans
        # Use round() to match uv_atlas.py's calculate_face_dimensions()
        w_px = max(1, int(round(size_x * texel_density)))  # X dimension
        h_px = max(1, int(round(size_y * texel_density)))  # Y dimension
        d_px = max(1, int(round(size_z * texel_density)))  # Z dimension
        
        # Map face names to their proper pixel dimensions
        # Front/Back face the Z axis, so they span X (width) and Y (height)
        # Left/Right face the X axis, so they span Z (depth) and Y (height)
        # Top/Bottom face the Y axis, so they span X (width) and Z (depth)
        face_pixel_sizes = {
            'front': (w_px, h_px),   # X × Y
            'back': (w_px, h_px),    # X × Y
            'left': (d_px, h_px),    # Z × Y
            'right': (d_px, h_px),   # Z × Y
            'top': (w_px, d_px),     # X × Z
            'bottom': (w_px, d_px),  # X × Z
        }
        
        # Paint each face with properly sized texture
        face_uvs = {}
        for face_name, face_data in entity.get('faces', {}).items():
            uv = face_data.get('uv', [0, 0, 1, 1])
            face_uvs[face_name] = uv
            
            # Calculate pixel region in atlas from UV coords
            x1 = int(uv[0] * atlas_width)
            y1 = int(uv[1] * atlas_height)
            x2 = int(uv[2] * atlas_width)
            y2 = int(uv[3] * atlas_height)
            
            # Handle flipped UVs
            paste_x = min(x1, x2)
            paste_y = min(y1, y2)
            region_w = max(1, abs(x2 - x1))
            region_h = max(1, abs(y2 - y1))
            
            # Get the proper face dimensions based on cuboid geometry
            proper_w, proper_h = face_pixel_sizes.get(face_name, (region_w, region_h))
            
            # Resize source texture to match the FACE dimensions (not UV region)
            # This ensures the texture has the correct aspect ratio for this face
            # OLD: face_texture = source_texture.resize((proper_w, proper_h), Image.NEAREST)
            # NEW: Tile/Crop the texture to fit dimensions without squashing pixels
            face_texture = _tile_texture_to_size(source_texture, proper_w, proper_h)
            
            # If UV region differs (shouldn't happen with correct atlas), resize to fit
            if proper_w != region_w or proper_h != region_h:
                logger.warning(f"UV region {region_w}x{region_h} differs from face size {proper_w}x{proper_h} for {entity_id}/{face_name}")
                # OLD: face_texture = _tile_texture_to_size(source_texture, region_w, region_h)
                # NEW: Tile to PROPER size (to keep pixel size correct), THEN upscale to region
                # This ensures we don't get "high res" pixels in a large UV region, but "big pixels"
                base_texture = _tile_texture_to_size(source_texture, proper_w, proper_h)
                face_texture = base_texture.resize((region_w, region_h), Image.NEAREST)
            
            # Paste into atlas
            atlas.paste(face_texture, (paste_x, paste_y))
        
        uv_map[entity_id] = face_uvs
    
    # Encode atlas
    buf = BytesIO()
    atlas.save(buf, format='PNG')
    atlas_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
    
    logger.info(f"Painted {len(entity_textures)} textures into {atlas_width}x{atlas_height} atlas (existing layout)")
    return atlas_b64, uv_map


def _pack_with_proper_sizing(
    entity_textures: Dict[str, Image.Image],
    texel_density: int
) -> Tuple[str, Dict[str, Dict[str, List[float]]]]:
    """
    Pack textures when no model data is available.
    Uses uniform sizing since we don't know the cuboid dimensions.
    """
    num_textures = len(entity_textures)
    
    # Calculate grid size
    grid_cols = math.ceil(math.sqrt(num_textures))
    grid_rows = math.ceil(num_textures / grid_cols)
    
    # Use 16x16 as default texture size
    tex_size = 16
    atlas_width = max(64, 2 ** math.ceil(math.log2(grid_cols * tex_size)))
    atlas_height = max(64, 2 ** math.ceil(math.log2(grid_rows * tex_size)))
    
    # Create atlas with transparent background
    atlas = Image.new('RGBA', (atlas_width, atlas_height), (0, 0, 0, 0))
    
    uv_map = {}
    for idx, (entity_id, texture) in enumerate(entity_textures.items()):
        col = idx % grid_cols
        row = idx // grid_cols
        
        x = col * tex_size
        y = row * tex_size
        
        # Resize texture to tex_size x tex_size
        if texture.mode != 'RGBA':
            texture = texture.convert('RGBA')
        texture_resized = texture.resize((tex_size, tex_size), Image.NEAREST)
        atlas.paste(texture_resized, (x, y))
        
        # Calculate UVs
        u1 = x / atlas_width
        v1 = y / atlas_height
        u2 = (x + tex_size) / atlas_width
        v2 = (y + tex_size) / atlas_height
        
        uv_map[entity_id] = {
            'front': [u1, v1, u2, v2],
            'back': [u1, v1, u2, v2],
            'left': [u1, v1, u2, v2],
            'right': [u1, v1, u2, v2],
            'top': [u1, v1, u2, v2],
            'bottom': [u1, v1, u2, v2],
        }
    
    buf = BytesIO()
    atlas.save(buf, format='PNG')
    atlas_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
    
    logger.info(f"Packed {num_textures} textures into {atlas_width}x{atlas_height} atlas (uniform layout)")
    return atlas_b64, uv_map


def _create_transparent_atlas(size: int = 64) -> str:
    """Create a simple transparent atlas as fallback."""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    buf = BytesIO()
    img.save(buf, format='PNG')
    return base64.b64encode(buf.getvalue()).decode('utf-8')


def apply_atlas_to_v3_model(
    v3_json: Dict[str, Any],
    atlas_b64: str,
    atlas_resolution: Tuple[int, int],
    uv_map: Dict[str, Dict[str, List[float]]]
) -> Dict[str, Any]:
    """
    Apply a packed atlas to a v3 model.
    
    Updates:
    - meta.atlases.main with the atlas data
    - Each cuboid's faces with the UV coordinates from uv_map
    """
    import copy
    v3_json = copy.deepcopy(v3_json)
    
    # Update atlas
    v3_json['meta']['atlases'] = {
        'main': {
            'data': atlas_b64,
            'mime': 'image/png',
            'resolution': list(atlas_resolution)
        }
    }
    
    # Update entity face UVs
    for entity in v3_json['entities']:
        if entity['type'] != 'cuboid':
            continue
            
        entity_id = entity['id']
        
        if entity_id in uv_map:
            for face_name, uv in uv_map[entity_id].items():
                if face_name in entity['faces']:
                    entity['faces'][face_name]['atlas_id'] = 'main'
                    entity['faces'][face_name]['uv'] = uv
    
    logger.info(f"Applied atlas to v3 model ({len(uv_map)} entities mapped)")
    return v3_json
