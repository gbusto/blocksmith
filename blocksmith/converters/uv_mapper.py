"""
UV Mapper - The definitive translator for v3 schema UVs.

The v3 schema's core convention is Blockbench-style:
- UVs are normalized floats [u1, v1, u2, v2].
- The coordinate origin (0,0) is in the TOP-LEFT corner.

This module provides simple, reliable translators to convert this canonical
format into the specific formats required by exporters.
"""
from typing import Dict, Tuple, List, Any

# ===================================================================
# Mappings and Constants
# ===================================================================

V3_FACE_ORDER = ["front", "back", "left", "right", "top", "bottom"]

# Flips needed to match Blockbench's internal face orientation vs. v3's
# User reported textures are Upright but Mirrored.
# This implies FLIP_V was correct (fixed upside down), but FLIP_H caused mirroring.
BBMODEL_FLIP_H = {"left"} # West/-X
BBMODEL_FLIP_V = {"front", "back", "left", "right", "top", "bottom"}

# ===================================================================
# Main Conversion Functions
# ===================================================================

def get_face_uvs(entity: dict) -> Dict[str, List[float]]:
    """Safely extracts the normalized, top-left-origin UVs for an entity."""
    return entity.get("faces", {})

def to_bbmodel(
    normalized_uvs: List[float], 
    v3_face_name: str, 
    atlas_w: int, 
    atlas_h: int
) -> List[int]:
    """Converts a single v3 UV rect to a BBModel pixel rect with flips."""
    u1, v1, u2, v2 = normalized_uvs
    
    # 1. Denormalize to pixels
    x1 = int(round(u1 * atlas_w))
    y1 = int(round(v1 * atlas_h))
    x2 = int(round(u2 * atlas_w))
    y2 = int(round(v2 * atlas_h))
    
    # 2. Apply Blockbench orientation flips
    if v3_face_name in BBMODEL_FLIP_H:
        x1, x2 = x2, x1
    if v3_face_name in BBMODEL_FLIP_V:
        y1, y2 = y2, y1
        
    return [x1, y1, x2, y2]

def to_gltf(normalized_uvs: List[float]) -> List[Tuple[float, float]]:
    """
    Converts a single v3 UV rect to the four GLTF corner coordinates
    with the required V-flip.
    """
    u1, v1, u2, v2 = normalized_uvs
    
    # 1. Flip V-axis for GLTF (top-left -> bottom-left origin)
    v1_flipped = 1.0 - v1
    v2_flipped = 1.0 - v2
    
    # 2. Return the four corner points in Blender's expected winding order
    # (bottom-left, bottom-right, top-right, top-left)
    return [
        (u1, v1_flipped),
        (u2, v1_flipped),
        (u2, v2_flipped),
        (u1, v2_flipped),
    ]
