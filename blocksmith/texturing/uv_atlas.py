"""
V3-Native UV Atlas Generator

Creates proper box UV unwraps for cuboids (like Blockbench/Minecraft) and packs
them into power-of-2 atlases.

Box UV Strip Layout (per cuboid):
    +-----+-----+-----+-----+   ← d_px tall
    | Top | Bot |     |     |
    +-----+-----+-----+-----+   ← h_px tall  
    | L   | Bk  | R   | Fr  |
    +-----+-----+-----+-----+
      D     W     D     W

    Strip width = 2 * (w_px + d_px)
    Strip height = h_px + d_px
"""

import base64
from io import BytesIO
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass
from PIL import Image
import math
import logging

logger = logging.getLogger(__name__)


@dataclass
class CuboidStrip:
    """Represents a box UV strip for one cuboid."""
    entity_id: str
    w_px: int  # Width in pixels (X dimension)
    h_px: int  # Height in pixels (Y dimension)
    d_px: int  # Depth in pixels (Z dimension)
    strip_w: int  # Total strip width
    strip_h: int  # Total strip height
    # Packing results
    x: int = 0
    y: int = 0
    packed: bool = False


def calculate_cuboid_pixels(
    from_coords: List[float], 
    to_coords: List[float], 
    texel_density: int = 16
) -> Tuple[int, int, int]:
    """
    Calculate pixel dimensions for a cuboid.
    
    Returns:
        Tuple of (w_px, h_px, d_px) - width, height, depth in pixels
    """
    size_x = abs(to_coords[0] - from_coords[0])
    size_y = abs(to_coords[1] - from_coords[1])
    size_z = abs(to_coords[2] - from_coords[2])
    
    w_px = max(1, int(round(size_x * texel_density)))
    h_px = max(1, int(round(size_y * texel_density)))
    d_px = max(1, int(round(size_z * texel_density)))
    
    return w_px, h_px, d_px


def get_box_uv_face_rects(
    w_px: int, h_px: int, d_px: int,
    strip_x: int, strip_y: int
) -> Dict[str, Tuple[int, int, int, int]]:
    """
    Get pixel rectangles for each face within a box UV strip.
    
    Standard Minecraft/Blockbench box UV layout:
        +-----+-----+
        | +Y  | -Y  |   (row 0, height = d_px)
        +-----+-----+-----+-----+
        | -X  | +Z  | +X  | -Z  |   (row 1, height = h_px)
        +-----+-----+-----+-----+
          D     W     D     W
    
    In v3 face names:
        +-----+-----+
        | top | bot |
        +-----+-----+-----+-----+
        | L   | Fr  | R   | Bk  |
        +-----+-----+-----+-----+
    
    Returns:
        Dict mapping face name to (x1, y1, x2, y2) pixel coordinates
    """
    # Row 0: Top (+Y) and Bottom (-Y)
    top_x = strip_x + d_px
    top_y = strip_y
    
    bottom_x = strip_x + d_px + w_px
    bottom_y = strip_y
    
    # Row 1: Left (-X), Front (+Z), Right (+X), Back (-Z)
    row_y = strip_y + d_px
    
    left_x = strip_x
    front_x = strip_x + d_px
    right_x = strip_x + d_px + w_px
    back_x = strip_x + d_px + w_px + d_px
    
    return {
        'top':    (top_x, top_y, top_x + w_px, top_y + d_px),
        'bottom': (bottom_x, bottom_y, bottom_x + w_px, bottom_y + d_px),
        'left':   (left_x, row_y, left_x + d_px, row_y + h_px),
        'front':  (front_x, row_y, front_x + w_px, row_y + h_px),
        'right':  (right_x, row_y, right_x + d_px, row_y + h_px),
        'back':   (back_x, row_y, back_x + w_px, row_y + h_px),
    }


def next_power_of_2(n: int) -> int:
    """Return the next power of 2 >= n."""
    if n <= 0:
        return 1
    return 2 ** math.ceil(math.log2(n))


class StripPacker:
    """Packs box UV strips into an atlas using shelf algorithm."""
    
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.shelves: List[Dict] = []
    
    def pack(self, strip: CuboidStrip) -> bool:
        """Try to pack a strip. Returns True if successful."""
        # Try existing shelves
        for shelf in self.shelves:
            if strip.strip_w <= self.width - shelf['x'] and strip.strip_h <= shelf['height']:
                strip.x = shelf['x']
                strip.y = shelf['y']
                strip.packed = True
                shelf['x'] += strip.strip_w
                return True
        
        # New shelf
        new_y = sum(s['height'] for s in self.shelves)
        if new_y + strip.strip_h > self.height or strip.strip_w > self.width:
            return False
        
        self.shelves.append({
            'y': new_y,
            'height': strip.strip_h,
            'x': strip.strip_w
        })
        strip.x = 0
        strip.y = new_y
        strip.packed = True
        return True


def pack_strips(strips: List[CuboidStrip], min_size: int = 16, max_size: int = 2048) -> int:
    """Pack strips into smallest power-of-2 atlas. Returns atlas size."""
    if not strips:
        return min_size
    
    # Sort by height (tallest first)
    sorted_strips = sorted(strips, key=lambda s: (s.strip_h, s.strip_w), reverse=True)
    
    atlas_size = max(min_size, next_power_of_2(max(s.strip_h for s in sorted_strips)))
    
    while atlas_size <= max_size:
        packer = StripPacker(atlas_size, atlas_size)
        
        for strip in sorted_strips:
            strip.packed = False
            strip.x = 0
            strip.y = 0
        
        if all(packer.pack(strip) for strip in sorted_strips):
            return atlas_size
        
        atlas_size *= 2
    
    raise RuntimeError(f"Could not pack strips into atlas up to {max_size}x{max_size}")


def generate_clay_atlas(
    v3_json: Dict[str, Any],
    clay_color: Tuple[int, int, int, int] = (255, 255, 255, 255)
) -> Dict[str, Any]:
    """
    Generate a clay texture atlas with proper box UV layout.
    """
    texel_density = v3_json.get('meta', {}).get('texel_density', 16)
    
    # Create strips for each cuboid
    strips: List[CuboidStrip] = []
    
    for entity in v3_json['entities']:
        if entity.get('type') != 'cuboid':
            continue
        
        from_coords = entity.get('from', [0, 0, 0])
        to_coords = entity.get('to', [1, 1, 1])
        
        w_px, h_px, d_px = calculate_cuboid_pixels(from_coords, to_coords, texel_density)
        
        strip_w = 2 * (w_px + d_px)
        strip_h = h_px + d_px
        
        strips.append(CuboidStrip(
            entity_id=entity['id'],
            w_px=w_px,
            h_px=h_px,
            d_px=d_px,
            strip_w=strip_w,
            strip_h=strip_h
        ))
    
    if not strips:
        v3_json['meta']['atlases'] = {
            'main': {'data': '', 'mime': 'image/png', 'resolution': [16, 16]}
        }
        return v3_json
    
    # Pack strips
    atlas_size = pack_strips(strips)
    
    # Create atlas with TRANSPARENT background (not white!)
    atlas_img = Image.new('RGBA', (atlas_size, atlas_size), (0, 0, 0, 0))
    
    # Draw clay color into each face region
    for strip in strips:
        face_rects = get_box_uv_face_rects(
            strip.w_px, strip.h_px, strip.d_px,
            strip.x, strip.y
        )
        
        for face_name, (x1, y1, x2, y2) in face_rects.items():
            w = x2 - x1
            h = y2 - y1
            if w > 0 and h > 0:
                face_img = Image.new('RGBA', (w, h), clay_color)
                atlas_img.paste(face_img, (x1, y1))
    
    # Encode atlas
    buffer = BytesIO()
    atlas_img.save(buffer, format='PNG')
    atlas_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    v3_json['meta']['atlases'] = {
        'main': {
            'data': atlas_b64,
            'mime': 'image/png',
            'resolution': [atlas_size, atlas_size]
        }
    }
    
    # Flips for orientation (matching TextureCompiler)
    FLIP_H = {'front', 'back', 'left', 'right'}
    FLIP_V = {'top', 'bottom'}
    
    # Calculate and store UV coordinates
    for strip in strips:
        entity = next((e for e in v3_json['entities'] if e['id'] == strip.entity_id), None)
        if not entity:
            continue
        
        face_rects = get_box_uv_face_rects(
            strip.w_px, strip.h_px, strip.d_px,
            strip.x, strip.y
        )
        
        for face_name, (x1, y1, x2, y2) in face_rects.items():
            # Normalize to [0, 1]
            u1 = x1 / atlas_size
            v1 = y1 / atlas_size
            u2 = x2 / atlas_size
            v2 = y2 / atlas_size
            
            if face_name in entity.get('faces', {}):
                entity['faces'][face_name]['atlas_id'] = 'main'
                entity['faces'][face_name]['uv'] = [u1, v1, u2, v2]
    
    logger.info(f"Generated {atlas_size}x{atlas_size} box UV atlas for {len(strips)} cuboids")
    return v3_json
