"""
Texturing utilities for v3 models.

Includes automated atlas generation (clay/UV packing) and texture processing.
"""
from .atlas_packer import pack_textures_into_atlas, apply_atlas_to_v3_model
from .clay_atlas import build_clay_atlas_with_compiler
from .uv_atlas import generate_clay_atlas

__all__ = [
    'pack_textures_into_atlas',
    'apply_atlas_to_v3_model',
    'build_clay_atlas_with_compiler',
    'generate_clay_atlas',
]
