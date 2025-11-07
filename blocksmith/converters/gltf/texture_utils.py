"""
Texture utilities for GLTF processing

Includes debug color generation and texture processing helpers.
"""

import base64
import hashlib
import colorsys
from io import BytesIO
from typing import List, Tuple, Dict, Any
from PIL import Image, ImageDraw

from engines.core.v3.models import CuboidEntity
from engines.core.v3.smart_uv_packer import pack_rectangles


def generate_debug_atlas(entities: List[Any], texture_size: int = 512) -> Dict[str, Any]:
    """
    Generate debug texture with unique pastel color per cuboid
    
    Args:
        entities: List of v3 entities (CuboidEntity objects)
        texture_size: Target texture size (will be adjusted by packer)
    
    Returns:
        Dict with 'data' (base64 PNG), 'mime', 'resolution', and 'uv_mappings'
    """
    
    # Step 1: Collect all faces that need UV mapping
    faces_to_pack = []
    face_colors = {}
    
    for entity in entities:
        if not isinstance(entity, CuboidEntity):
            continue
            
        # Calculate cuboid dimensions for face sizing
        size = [entity.to[i] - entity.from_[i] for i in range(3)]
        width, height, depth = size
        
        # Generate unique color for this entity
        entity_color = generate_pastel_color(entity.id)
        
        # Add faces (using approximate pixel dimensions)
        face_specs = [
            ('front', int(width * 16), int(height * 16)),   # X-Y plane
            ('back', int(width * 16), int(height * 16)),    # X-Y plane  
            ('left', int(depth * 16), int(height * 16)),    # Z-Y plane
            ('right', int(depth * 16), int(height * 16)),   # Z-Y plane
            ('top', int(width * 16), int(depth * 16)),      # X-Z plane
            ('bottom', int(width * 16), int(depth * 16)),   # X-Z plane
        ]
        
        for face_name, face_width, face_height in face_specs:
            # Ensure minimum size
            face_width = max(face_width, 1)
            face_height = max(face_height, 1)
            
            face_id = f"{entity.id}_{face_name}"
            faces_to_pack.append((face_width, face_height, face_id))
            face_colors[face_id] = entity_color
    
    if not faces_to_pack:
        # No faces to pack, return minimal atlas
        return _create_minimal_atlas()
    
    # Step 2: Pack faces using smart UV packer
    try:
        packed_faces, atlas_width, atlas_height = pack_rectangles(faces_to_pack)
    except Exception as e:
        # Fallback to simple layout
        return _create_fallback_atlas(face_colors, texture_size)
    
    # Step 3: Generate texture image
    image = Image.new('RGBA', (atlas_width, atlas_height), (220, 220, 220, 255))  # Light gray background
    draw = ImageDraw.Draw(image)
    
    # Step 4: Draw each face with its color and UV mapping
    uv_mappings = {}
    
    for face_info in packed_faces:
        face_id = face_info['id']
        x, y = face_info['x'], face_info['y']
        width, height = face_info['width'], face_info['height']
        
        # Draw colored rectangle
        color = face_colors.get(face_id, (200, 200, 200))
        draw.rectangle([x, y, x + width - 1, y + height - 1], fill=color)
        
        # Add subtle border for visibility
        border_color = tuple(max(0, c - 30) for c in color)  # Darker border
        draw.rectangle([x, y, x + width - 1, y + height - 1], outline=border_color)
        
        # Calculate normalized UV coordinates
        u_min = x / atlas_width
        v_min = y / atlas_height
        u_max = (x + width) / atlas_width
        v_max = (y + height) / atlas_height
        
        uv_mappings[face_id] = [u_min, v_min, u_max, v_max]
    
    # Step 5: Convert to base64
    buffer = BytesIO()
    image.save(buffer, format='PNG')
    base64_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    return {
        'data': base64_data,
        'mime': 'image/png',
        'resolution': [atlas_width, atlas_height],
        'uv_mappings': uv_mappings
    }


def generate_pastel_color(seed: str) -> Tuple[int, int, int]:
    """
    Generate pleasant pastel color from seed string
    
    Args:
        seed: String to generate deterministic color from
        
    Returns:
        RGB tuple (r, g, b) with values 0-255
    """
    # Use hash of seed for deterministic colors
    hash_val = int(hashlib.md5(seed.encode()).hexdigest()[:8], 16)
    
    # HSL values for pleasant pastel colors
    hue = (hash_val % 360) / 360.0  # 0-1, full hue range
    saturation = 0.4 + (hash_val % 20) / 100.0  # 0.4-0.6, moderate saturation
    lightness = 0.7 + (hash_val % 15) / 100.0  # 0.7-0.85, light colors
    
    # Convert HSL to RGB
    r, g, b = colorsys.hls_to_rgb(hue, lightness, saturation)
    
    # Convert to 0-255 range
    return (int(r * 255), int(g * 255), int(b * 255))


def _create_minimal_atlas() -> Dict[str, Any]:
    """Create minimal 1x1 atlas for edge cases"""
    # 1x1 light gray PNG
    gray_png_base64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAEklEQVR42mO8d+8eBgYGRgYGAAYTAwOKN1z6AAAAAElFTkSuQmCC"
    
    return {
        'data': gray_png_base64,
        'mime': 'image/png', 
        'resolution': [1, 1],
        'uv_mappings': {}
    }


def _create_fallback_atlas(face_colors: Dict[str, Tuple[int, int, int]], size: int) -> Dict[str, Any]:
    """Create simple fallback atlas when packing fails"""
    # Create solid color atlas
    color = (180, 180, 180)  # Light gray
    if face_colors:
        # Use average of all colors
        avg_r = sum(c[0] for c in face_colors.values()) // len(face_colors)
        avg_g = sum(c[1] for c in face_colors.values()) // len(face_colors)
        avg_b = sum(c[2] for c in face_colors.values()) // len(face_colors)
        color = (avg_r, avg_g, avg_b)
    
    image = Image.new('RGBA', (size, size), color)
    
    # Convert to base64
    buffer = BytesIO()
    image.save(buffer, format='PNG')
    base64_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    return {
        'data': base64_data,
        'mime': 'image/png',
        'resolution': [size, size],
        'uv_mappings': {}
    }