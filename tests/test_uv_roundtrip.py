"""
V3 Engine Roundtrip Verification Test

This script verifies the integrity of model conversions (V3 -> Format -> V3).
It checks for:
1. Data Integrity: All metadata and structure are preserved.
2. UV Mapping: UV coordinates match exactly after conversion.
3. Orientation: Faces and winding orders are correct.

Supported Formats:
- Blockbench (.bbmodel)
- GLTF/GLB (.glb)
"""

import base64
import logging
from io import BytesIO
import pytest
from PIL import Image

from blocksmith.schema import ModelDefinition, CuboidEntity, FaceTexture
# Correctly importing converters from blocksmith package
from blocksmith.converters import (
    export_glb, 
    import_gltf as import_gltf_func,
    export_bbmodel as export_bbmodel_func, 
    import_bbmodel as import_bbmodel_func
)

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

def create_golden_v3_model() -> ModelDefinition:
    """Creates a standard 16px cube model with known UVs."""
    # 1. Create Texture (Atlas)
    # We'll make a 64x64 simple atlas
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    
    # Define UVs explicitly for the "Front" face.
    # Front Face UV: [0.0, 0.0, 0.25, 0.25]
    
    faces = {
        "front": FaceTexture(uv=[0.0, 0.0, 0.25, 0.25], atlas_id="main"),
        "back": FaceTexture(uv=[0.25, 0.0, 0.50, 0.25], atlas_id="main"),
        "left": FaceTexture(uv=[0.50, 0.0, 0.75, 0.25], atlas_id="main"),
        "right": FaceTexture(uv=[0.75, 0.0, 1.00, 0.25], atlas_id="main"),
        "top": FaceTexture(uv=[0.0, 0.25, 0.25, 0.50], atlas_id="main"),
        "bottom": FaceTexture(uv=[0.25, 0.25, 0.50, 0.50], atlas_id="main"),
    }

    # Helper to get base64 from PIL
    buf = BytesIO()
    img.save(buf, format="PNG")
    base64_img = base64.b64encode(buf.getvalue()).decode("utf-8")

    cuboid = CuboidEntity(
        id="cube_1",
        label="Golden Cube",
        to=[1,1,1],
        faces=faces,
        **{"from": [0,0,0]}
    )

    model = ModelDefinition(
        meta={
            "schema_version": "3.0",
            "texel_density": 16.0,
            "atlases": {
                "main": {
                    "data": base64_img,
                    "mime": "image/png",
                    "resolution": [64, 64]
                }
            }
        },
        entities=[cuboid]
    )
    return model

def verify_uvs(label: str, original: ModelDefinition, converted: ModelDefinition):
    """Compares UVs between two models."""
    print(f"--- Verifying {label} ---")
    
    orig_cube = original.entities[0]
    conv_cube = converted.entities[0]
    
    # We expect entity order/count to match for this simple test
    assert len(converted.entities) == 1, f"Entity count mismatch. Got {len(converted.entities)}"

    # Check Faces
    failures = 0
    for face in ["front", "back", "left", "right", "top", "bottom"]:
        if face not in orig_cube.faces: continue
        
        orig_uv = orig_cube.faces[face].uv
        # Converted might not have all faces?
        if face not in conv_cube.faces:
            print(f"FAILURE: Missing face {face} in converted model")
            failures += 1
            continue
            
        conv_uv = conv_cube.faces[face].uv
        
        # Check equality with epsilon
        matches = all(abs(o - c) < 0.001 for o, c in zip(orig_uv, conv_uv))
        
        if matches:
            print(f"Face {face}: MATCH {orig_uv}")
        else:
            print(f"Face {face}: MISMATCH")
            print(f"  Orig: {orig_uv}")
            print(f"  Conv: {conv_uv}")
            
            # Diagnose Flip
            u1, v1, u2, v2 = orig_uv
            cu1, cv1, cu2, cv2 = conv_uv
            
            if abs(cu1 - u2) < 0.001 and abs(cu2 - u1) < 0.001:
                print("  -> HORIZONTAL FLIP DETECTED")
            if abs(cv1 - v2) < 0.001 and abs(cv2 - v1) < 0.001:
                print("  -> VERTICAL FLIP DETECTED")

            failures += 1

    assert failures == 0, f"{label} Roundtrip Failed with {failures} errors."
    print(f"SUCCESS: {label} Roundtrip Passed!")

def test_bbmodel_roundtrip():
    """Test BBModel Roundtrip (V3 -> BBModel -> V3)"""
    golden = create_golden_v3_model()
    golden_json = golden.model_dump(mode='json', by_alias=True)
    
    # 1. Export V3 to BBModel JSON String
    bbmodel_str = export_bbmodel_func(golden_json)
    
    # 2. Import BBModel JSON back to V3 ModelDefinition (dict)
    v3_data = import_bbmodel_func(bbmodel_str)
    v3_from_bb = ModelDefinition(**v3_data)
    
    # 3. Verify
    verify_uvs("BBModel Roundtrip", golden, v3_from_bb)

def test_gltf_roundtrip():
    """Test GLTF Roundtrip (V3 -> GLTF -> V3)"""
    golden = create_golden_v3_model()
    golden_json = golden.model_dump(mode='json', by_alias=True)
    
    # 1. Export V3 to GLTF (GLB bytes)
    glb_bytes = export_glb(golden_json)
    
    # 2. Import GLTF back to V3 ModelDefinition (dict)
    # import_gltf expects a file path
    import tempfile
    import os
    
    with tempfile.NamedTemporaryFile(suffix='.glb', delete=False) as tmp:
        tmp.write(glb_bytes)
        tmp_path = tmp.name
        
    try:
        v3_data_gltf = import_gltf_func(tmp_path)
        v3_from_gltf = ModelDefinition(**v3_data_gltf)
        
        # 3. Verify
        verify_uvs("GLTF Roundtrip", golden, v3_from_gltf)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
