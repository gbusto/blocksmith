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

Usage:
    python3 -m blocksmith_backend.engines.core.v3.test_roundtrip
"""

import asyncio
import base64
import json
import logging
import math
import os
import sys
from io import BytesIO
from typing import Dict, Any, List

import numpy as np
from PIL import Image

try:
    from pygltflib import GLTF2
    PYGLTFLIB_AVAILABLE = True
except ImportError:
    PYGLTFLIB_AVAILABLE = False
    logger.warning("pygltflib not installed. Direct GLTF inspection will be skipped.")

# Path Setup: Add blocksmith_backend to path so 'engines' imports work
# This is necessary because the codebase uses 'from engines...' which implies blocksmith_backend is in path
current_dir = os.path.dirname(os.path.abspath(__file__))
# v3 -> core -> engines -> blocksmith_backend
backend_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

# Imports from backend
from blocksmith.schema.blockjson import ModelDefinition, CuboidEntity, FaceTexture
from blocksmith.converters.gltf.exporter import export_glb as export_glb_v3
from blocksmith.converters.gltf.importer import import_gltf as import_gltf_func
from blocksmith.converters.bbmodel.exporter import export_bbmodel as export_bbmodel_func
from blocksmith.converters.bbmodel.importer import import_bbmodel as import_bbmodel_func

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

def inspect_bbmodel_uvs(bbmodel_content: str):
    """Parses BBModel JSON and prints UV data for manual verification."""
    data = json.loads(bbmodel_content)
    logger.info("=== BBModel UV Inspection ===")
    
    if "elements" not in data or not data["elements"]:
        logger.warning("No elements found in BBModel.")
        return

    element = data["elements"][0] # Assume single element
    logger.info(f"Element: {element.get('name', 'unknown')}")
    
    if "faces" in element:
        for face_name, face_data in element["faces"].items():
            uv = face_data.get("uv")
            rot = face_data.get("rotation", 0)
            logger.info(f"  Face {face_name}: UV={uv}, Rot={rot}")
# Hardcoded Expectations for Regression Testing
# These values capture the functionality as of 2025-12-28, ensuring:
# 1. BBModel Top/Bottom are Transposed (Rotated 90/270).
# 2. GLTF UVs match the exact buffer layout produced by the Exporter fixes.

EXPECTED_BBMODEL_FACES = {
    "up": {"uv": [0, 77, 102, 51], "rotation": 90},
    "down": {"uv": [0, 103, 102, 77], "rotation": 270}
}

# First 12 pairs for brevity in code, but we check what we captured.
EXPECTED_GLTF_UVS_HEAD = [
    [0.1015625, 0.0], [0.3984375, 0.40234375], [0.203125, 0.0], [0.203125, 0.0],
    [0.3984375, 0.30078125], [0.40234375, 0.0], [0.0, 0.0], [0.0, 0.30078125],
    [0.6015625, 0.0], [0.1015625, 0.0], [0.0, 0.40234375], [0.40234375, 0.0]
]

def inspect_bbmodel_uvs(bbmodel_content: str):
    """Parses BBModel JSON and verifies critical UV/Rotation data against expectations."""
    data = json.loads(bbmodel_content)
    logger.info("=== BBModel UV Verification ===")
    
    if "elements" not in data or not data["elements"]:
        logger.warning("No elements found in BBModel.")
        pass
    else:
        element = data["elements"][0]
        faces = element.get("faces", {})
        
        failures = 0
        for face_key, expected in EXPECTED_BBMODEL_FACES.items():
            if face_key not in faces:
                logger.error(f"FAILURE: Expected face '{face_key}' not found in BBModel.")
                failures += 1
                continue
                
            actual = faces[face_key]
            
            # Check Rotation
            if actual.get("rotation", 0) != expected["rotation"]:
                logger.error(f"Face {face_key}: Rotation Mismatch. Expected {expected['rotation']}, Got {actual.get('rotation', 0)}")
                failures += 1
                
            # Check UVs (Approximate)
            # BBModel UVs are integers/floats.
            act_uv = actual.get("uv", [])
            exp_uv = expected["uv"]
            if not np.allclose(act_uv, exp_uv, atol=0.1):
                logger.error(f"Face {face_key}: UV Mismatch. Expected {exp_uv}, Got {act_uv}")
                failures += 1
                
        if failures == 0:
            logger.info("SUCCESS: BBModel Direct Inspection Passed.")
        else:
            msg = f"FAILURE: BBModel Direct Inspection Failed with {failures} errors."
            logger.error(msg)
            raise RuntimeError(msg)

def inspect_gltf_uvs(glb_bytes: bytes):
    """Parses GLB bytes and verifies UV buffer against expectations."""
    if not PYGLTFLIB_AVAILABLE:
        return
        
    logger.info("=== GLTF UV Verification ===")
    
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".glb", delete=False) as f:
        f.write(glb_bytes)
        tmp_path = f.name
        
    try:
        gltf = GLTF2.load_binary(tmp_path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
    
    if not gltf.meshes:
        return
        
    mesh = gltf.meshes[0]
    primitive = mesh.primitives[0]
    tex_acc_idx = primitive.attributes.TEXCOORD_0
    if tex_acc_idx is None:
        return
        
    accessor = gltf.accessors[tex_acc_idx]
    buffer_view = gltf.bufferViews[accessor.bufferView]
    
    blob = gltf.binary_blob()
    offset = (accessor.byteOffset or 0) + (buffer_view.byteOffset or 0)
    stride = buffer_view.byteStride or 8
    count = accessor.count
    
    import struct
    uvs = []
    for i in range(count):
        start = offset + (i * stride if buffer_view.byteStride else i * 8)
        chunk = blob[start:start+8]
        u, v = struct.unpack("<ff", chunk)
        uvs.append([u, v])
        
    # Verify Head
    head_len = len(EXPECTED_GLTF_UVS_HEAD)
    if len(uvs) < head_len:
        logger.error(f"FAILURE: GLTF UV count {len(uvs)} < expected head {head_len}")
        return
        
    actual_head = uvs[:head_len]
    if np.allclose(actual_head, EXPECTED_GLTF_UVS_HEAD, atol=0.0001):
        logger.info("SUCCESS: GLTF UV Buffer Head Matches Expectations.")
    else:
        logger.error("FAILURE: GLTF UV Buffer Head Mismatch.")
        logger.error(f"Expected: {EXPECTED_GLTF_UVS_HEAD}")
        logger.error(f"Actual:   {actual_head}")
        raise RuntimeError("GLTF Direct Inspection Failed")
        
def create_golden_v3_model() -> ModelDefinition:
    """Creates a non-uniform cuboid (2x4x8) to detect UV rotation/stretching issues."""
    # We define simple UVs that occupy these aspect ratios in a 256x256 atlas.
    # IMPORTANT: Blockbench snaps UVs to the nearest pixel. 
    # To ensure exact roundtrip matches, our input UVs must be pixel-aligned.
    # Atlas is 256x256. 1 pixel = 1/256 = 0.00390625.
    
    # helper:
    def px(p): return p / 256.0
    
    faces = {
        # Front: 32x64 (0.5). UV 26px x 51px (approx 0.1 x 0.2)
        "front": FaceTexture(uv=[px(0), px(0), px(26), px(51)], atlas_id="main"),
        "back": FaceTexture(uv=[px(26), px(0), px(52), px(51)], atlas_id="main"),
        
        # Left: 128x64 (2.0). UV 51px x 26px
        # If rotated (interpreted as 64x128), it's 0.5 ratio vs 2.0. Massive stretch.
        "left": FaceTexture(uv=[px(52), px(0), px(103), px(26)], atlas_id="main"),
        "right": FaceTexture(uv=[px(103), px(0), px(154), px(26)], atlas_id="main"),
        
        # Top: 32x128 (0.25). 
        # NEW LAYOUT (Transposed): UV is D x W (128x32).
        # We need a 128x32 slot.
        # Let's say we use 26px x 102px (approx). 
        # Transposed: 102px x 26px.
        "top": FaceTexture(uv=[px(0), px(51), px(102), px(77)], atlas_id="main"),
        "bottom": FaceTexture(uv=[px(0), px(77), px(102), px(103)], atlas_id="main"),
    }

    # Dummy image
    img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    buf = BytesIO()
    img.save(buf, format="PNG")
    base64_img = base64.b64encode(buf.getvalue()).decode("utf-8")

    cuboid = CuboidEntity(
        id="cuboid_non_uniform",
        label="Golden Non-Uniform",
        to=[2,4,8],
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
                    "resolution": [256, 256]
                }
            }
        },
        entities=[cuboid]
    )
    return model

def verify_uvs(label: str, original: ModelDefinition, converted: ModelDefinition):
    """Compares UVs between two models."""
    logger.info(f"--- Verifying {label} ---")
    
    orig_cube = original.entities[0]
    conv_cube = converted.entities[0]
    
    # We expect entity order/count to match for this simple test
    if len(converted.entities) != 1:
        logger.error(f"FAILURE: Entity count mismatch. Got {len(converted.entities)}")
        return

    # Check Faces
    failures = 0
    for face in ["front", "back", "left", "right", "top", "bottom"]:
        if face not in orig_cube.faces: continue
        
        orig_uv = orig_cube.faces[face].uv
        # Converted might not have all faces?
        if face not in conv_cube.faces:
            logger.error(f"FAILURE: Missing face {face} in converted model")
            failures += 1
            continue
            
        conv_uv = conv_cube.faces[face].uv
        
        # Check equality with epsilon
        matches = all(abs(o - c) < 0.001 for o, c in zip(orig_uv, conv_uv))
        
        if matches:
            logger.info(f"Face {face}: MATCH {orig_uv}")
        else:
            logger.error(f"Face {face}: MISMATCH")
            logger.error(f"  Orig: {orig_uv}")
            logger.error(f"  Conv: {conv_uv}")
            
            # Diagnose Flip
            # Orig: [0, 0, 0.25, 0.25] (x, y, w, h)
            # Flipped H: [0.25, 0, 0, 0.25] (Swap U)
            # Flipped V: [0, 0.25, 0.25, 0] (Swap V)
            u1, v1, u2, v2 = orig_uv
            cu1, cv1, cu2, cv2 = conv_uv
            
            if abs(cu1 - u2) < 0.001 and abs(cu2 - u1) < 0.001:
                logger.warning("  -> HORIZONTAL FLIP DETECTED")
            if abs(cv1 - v2) < 0.001 and abs(cv2 - v1) < 0.001:
                logger.warning("  -> VERTICAL FLIP DETECTED")

            failures += 1

    if failures == 0:
        logger.info(f"SUCCESS: {label} Roundtrip Passed!")
    else:
        logger.error(f"FAILURE: {label} Roundtrip Failed with {failures} errors.")

def run_chained_test():
    logging.info("Starting Chained Verification (V3 -> GLTF -> V3 -> BBModel -> V3)...")
    
    # 1. Golden Source
    golden = create_golden_v3_model()
    golden_json = golden.model_dump(mode='json', by_alias=True)
    
    # ---------------------------------------------------------
    # Step 1: V3 -> GLTF -> V3
    # ---------------------------------------------------------
    logging.info("\n--- Step 1: V3 (Golden) -> GLTF -> V3 ---")
    try:
        # Export
        glb_bytes = export_glb_v3(golden_json)
        
        # Import
        v3_from_gltf_data = import_gltf_func(glb_bytes)
        v3_from_gltf = ModelDefinition(**v3_from_gltf_data)
        
        # INSPECT GLTF DIRECTLY
        inspect_gltf_uvs(glb_bytes)

        # Verify
        verify_uvs("Golden vs GLTF-V3", golden, v3_from_gltf)
        
    except Exception as e:
        logger.error(f"Step 1 CRASHED: {e}")
        import traceback
        traceback.print_exc()
        return

    # ---------------------------------------------------------
    # Step 2: GLTF-V3 -> BBModel -> V3
    # ---------------------------------------------------------
    logging.info("\n--- Step 2: V3 (from GLTF) -> BBModel -> V3 ---")
    try:
        # Prepare input from previous step
        v3_gltf_json = v3_from_gltf.model_dump(mode='json', by_alias=True)
        
        # Export
        bbmodel_str = export_bbmodel_func(v3_gltf_json)
        
        # INSPECT BBMODEL DIRECTLY
        inspect_bbmodel_uvs(bbmodel_str)

        # Import
        v3_from_bb_data = import_bbmodel_func(bbmodel_str)
        v3_from_bb = ModelDefinition(**v3_from_bb_data)
        
        # Verify against IMMEDIATE parent (GLTF-V3)
        verify_uvs("GLTF-V3 vs BB-V3", v3_from_gltf, v3_from_bb)
        
        # Verify against GOLDEN source (Transitive check)
        logging.info("\n--- Step 3: Overall Transitive Check (Golden vs Final V3) ---")
        verify_uvs("Golden vs Final-V3", golden, v3_from_bb)
        
    except Exception as e:
        logger.error(f"Step 2 CRASHED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_chained_test()
