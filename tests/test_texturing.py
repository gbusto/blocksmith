"""
Tests for new texturing modules synced from core.
"""
import pytest
from blocksmith.texturing import generate_clay_atlas

def test_imports():
    """Verify that new modules can be imported correctly."""
    from blocksmith.texturing import (
        pack_textures_into_atlas,
        apply_atlas_to_v3_model,
        build_clay_atlas_with_compiler,
        generate_clay_atlas
    )
    assert pack_textures_into_atlas is not None
    assert apply_atlas_to_v3_model is not None
    assert build_clay_atlas_with_compiler is not None
    assert generate_clay_atlas is not None

def test_clay_atlas_generation():
    """Test generating a clay atlas for a simple model."""
    v3_json = {
        "meta": {"texel_density": 16},
        "entities": [
            {
                "id": "cube",
                "type": "cuboid",
                "from": [0, 0, 0],
                "to": [1, 1, 1],
                "faces": {
                    "front": {"uv": [0, 0, 1, 1]},
                    "back": {"uv": [0, 0, 1, 1]},
                    "left": {"uv": [0, 0, 1, 1]},
                    "right": {"uv": [0, 0, 1, 1]},
                    "top": {"uv": [0, 0, 1, 1]},
                    "bottom": {"uv": [0, 0, 1, 1]}
                }
            }
        ]
    }
    
    result = generate_clay_atlas(v3_json)
    assert "atlases" in result["meta"]
    assert "main" in result["meta"]["atlases"]
    assert "data" in result["meta"]["atlases"]["main"]
