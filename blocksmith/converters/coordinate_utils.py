"""
Centralized coordinate transformation utilities for v3 schema.

All format engines (GLTF, Bedrock, BBModel, Python) should use these utilities
to ensure consistent coordinate system transformations.

Coordinate Systems:
- v3: Y-up, Z-forward (north), X-right (east)
- Blender: Z-up, Y-forward, X-right
- GLTF: Y-up, Z-forward, X-right (same as v3)

Key insight: GLTF uses the same coordinate system as v3, but Blender transforms
it during import/export, so we need to handle the Blender transformations.
"""

import math
from typing import List, Tuple


def transform_position_blender_to_v3(pos: List[float]) -> List[float]:
    """
    Transform position from Blender to v3 coordinate system.
    
    Blender (Z-up): X, Y, Z
    v3 (Y-up): X, Y, Z
    
    Mapping (based on actual GLTF import/export behavior):
    - Blender X → v3 X (unchanged)
    - Blender Y → v3 -Z (Blender forward to v3 north, but negated)
    - Blender Z → v3 Y (up in both systems)
    
    Args:
        pos: Position in Blender coordinates [x, y, z]
        
    Returns:
        Position in v3 coordinates [x, y, z]
    """
    x, y, z = pos
    return [x, z, -y]


def transform_position_v3_to_blender(pos: List[float]) -> List[float]:
    """
    Transform position from v3 to Blender coordinate system.
    
    This is the inverse of transform_position_blender_to_v3.
    
    v3 (Y-up): X, Y, Z
    Blender (Z-up): X, Y, Z
    
    Mapping:
    - v3 X → Blender X (unchanged)
    - v3 Y → Blender Z (up in both systems)
    - v3 Z → Blender -Y (v3 north to Blender forward, but negated)
    
    Args:
        pos: Position in v3 coordinates [x, y, z]
        
    Returns:
        Position in Blender coordinates [x, y, z]
    """
    x, y, z = pos
    return [x, -z, y]


def transform_quaternion_blender_to_v3(quat: List[float]) -> List[float]:
    """
    Transform quaternion from Blender to v3 coordinate system.
    
    Quaternions represent rotations, and their components must be
    transformed to match the coordinate system change.
    
    Blender quaternion [w, x, y, z] represents rotation around:
    - x: X-axis
    - y: Y-axis (forward)
    - z: Z-axis (up)
    
    v3 quaternion [w, x, y, z] represents rotation around:
    - x: X-axis
    - y: Y-axis (up)
    - z: Z-axis (forward)
    
    Following the position mapping (X→X, Y→-Z, Z→Y):
    - Blender [w, x, y, z] → v3 [w, x, z, -y]
    
    Args:
        quat: Quaternion in Blender format [w, x, y, z]
        
    Returns:
        Quaternion in v3 format [w, x, y, z]
    """
    w, x, y, z = quat
    # Transform components to match axis remapping with negation
    return [w, x, z, -y]


def transform_quaternion_v3_to_blender(quat: List[float]) -> List[float]:
    """
    Transform quaternion from v3 to Blender coordinate system.
    
    This is the inverse of transform_quaternion_blender_to_v3.
    
    v3 [w, x, y, z] → Blender [w, x, -z, y]
    
    Args:
        quat: Quaternion in v3 format [w, x, y, z]
        
    Returns:
        Quaternion in Blender format [w, x, y, z]
    """
    w, x, y, z = quat
    # Transform components (inverse of the forward transform)
    return [w, x, -z, y]


def normalize_quaternion(quat: List[float]) -> List[float]:
    """
    Normalize a quaternion to unit length and ensure consistent sign (w >= 0).
    
    Args:
        quat: Quaternion [w, x, y, z]
        
    Returns:
        Normalized quaternion [w, x, y, z] with w >= 0
    """
    w, x, y, z = quat
    magnitude = math.sqrt(w*w + x*x + y*y + z*z)
    if magnitude == 0:
        return [1, 0, 0, 0]  # Identity quaternion
    
    # Normalize to unit length
    normalized = [w/magnitude, x/magnitude, y/magnitude, z/magnitude]
    
    # Ensure w component is non-negative for consistent representation
    # (q and -q represent the same rotation, so we choose w >= 0 convention)
    if normalized[0] < 0:
        normalized = [-x for x in normalized]
    
    return normalized


def test_roundtrip_transforms():
    """Test that our transformations are proper inverses."""
    print("Testing coordinate transformations...")
    
    # Test position roundtrip
    test_positions = [
        [1, 2, 3],
        [0, 0, 0],
        [-5, 10, -15],
        [0.5, -0.5, 0.25]
    ]
    
    for pos in test_positions:
        # Blender → v3 → Blender
        v3_pos = transform_position_blender_to_v3(pos)
        roundtrip = transform_position_v3_to_blender(v3_pos)
        assert roundtrip == pos, f"Position roundtrip failed: {pos} → {v3_pos} → {roundtrip}"
    
    print("✓ Position transformations are correct inverses")
    
    # Test quaternion roundtrip
    test_quats = [
        [1, 0, 0, 0],  # Identity
        [0.7071, 0.7071, 0, 0],  # 90° X rotation
        [0.7071, 0, 0.7071, 0],  # 90° Y rotation
        [0.7071, 0, 0, 0.7071],  # 90° Z rotation
        [0.5, 0.5, 0.5, 0.5],    # Combined rotation
    ]
    
    for quat in test_quats:
        # Normalize input
        quat = normalize_quaternion(quat)
        
        # Blender → v3 → Blender
        v3_quat = transform_quaternion_blender_to_v3(quat)
        roundtrip = transform_quaternion_v3_to_blender(v3_quat)
        
        # Check components match (within floating point tolerance)
        for i in range(4):
            assert abs(roundtrip[i] - quat[i]) < 1e-10, \
                f"Quaternion roundtrip failed: {quat} → {v3_quat} → {roundtrip}"
    
    print("✓ Quaternion transformations are correct inverses")
    
    # Test specific case from simple-cube-2
    print("\nTesting specific cases from simple-cube-2:")
    
    # cube.001 on North face
    blender_loc = [0.0, 0.3125, 0.375]
    v3_pivot = transform_position_blender_to_v3(blender_loc)
    print(f"  Blender location {blender_loc} → v3 pivot {v3_pivot}")
    print(f"  Expected v3 pivot: [0.0, 0.375, -0.3125]")
    assert v3_pivot == [0.0, 0.375, -0.3125], "North face cube transformation failed"
    
    # cube.002 on top face  
    blender_loc2 = [0.0, 0.1875, 0.5]
    v3_pivot2 = transform_position_blender_to_v3(blender_loc2)
    print(f"  Blender location {blender_loc2} → v3 pivot {v3_pivot2}")
    print(f"  Expected v3 pivot: [0.0, 0.5, -0.1875]")
    assert v3_pivot2 == [0.0, 0.5, -0.1875], "Top face cube transformation failed"
    
    print("\n✓ All tests passed!")


if __name__ == "__main__":
    test_roundtrip_transforms()