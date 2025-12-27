"""
Clay atlas generation - V3 native implementation.

This module provides a simple entry point for generating clay atlases
using the v3-native UV atlas generator.
"""

from typing import Dict, Any

from .uv_atlas import generate_clay_atlas


def build_clay_atlas_with_compiler(v3_json: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a clay texture atlas for v3 model.
    
    Uses the v3-native UV atlas generator to create proper box UV unwraps
    with consistent texel density across all faces.
    
    Args:
        v3_json: V3 model definition with entities
    
    Returns:
        Updated v3_json with embedded atlas and proper face UVs
    """
    # Use v3-native atlas generator
    return generate_clay_atlas(v3_json, clay_color=(255, 255, 255, 255))
