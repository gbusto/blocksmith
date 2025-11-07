# Python Code Import/Export for v3 Schema

This module handles bidirectional conversion between v3 schema and Python code representation. The Python format is designed to be LLM-friendly for training data while maintaining accuracy for model reconstruction.

## Overview

The conversion pipeline:
```
v3 schema → Python code → v3 schema
```

This allows LLMs to learn from and generate 3D models using readable Python code.

## Key Design Principles

### 1. Coordinate System Consistency
- v3 uses quaternions for rotations internally
- Python code uses Euler angles (degrees) for LLM readability
- Conversion uses fixed 'XYZ' order to ensure consistency

### 2. Precision Balance
- Python output uses 4 decimal places
- Balances accuracy vs. learnability for LLMs
- Excessive precision (12+ decimals) hurts generalization in training

### 3. Entity Representation

#### Cuboid Entities
Python code uses two modes for defining cuboids:

```python
# Corner mode (what the exporter generates)
cuboid("id", corner=[x, y, z], size=[w, h, d], pivot=[px, py, pz])

# Position mode (alternative)
cuboid("id", position=[cx, cy, cz], size=[w, h, d])
```

**Critical**: The `corner` parameter specifies the bottom-left-back corner in world space, NOT relative to pivot.

#### Group Entities
```python
group("id", pivot=[x, y, z], rotation=[rx, ry, rz])
```

## Import/Export Field Mappings

### Position/Geometry Fields

For cuboids, the relationship between fields is:
- `corner = from + pivot` (world space corner)
- `from = corner - pivot` (relative to pivot)
- `to = from + size` (relative to pivot)

The exporter outputs corner because it's more intuitive for humans/LLMs. The importer must reconstruct the relative from/to values.

### Rotation Fields

1. **v3 → Python (Export)**:
   - Quaternion `[w, x, y, z]` → Euler angles `[x°, y°, z°]`
   - Uses `quaternion_to_euler()` with XYZ order
   - Normalizes to [-180°, 180°] range

2. **Python → v3 (Import)**:
   - Euler angles `[x°, y°, z°]` → Quaternion `[w, x, y, z]`
   - Uses `euler_to_quaternion()` with XYZ order
   - Ensures consistent quaternion sign (w ≥ 0)

### Hierarchical Transforms

- `pivot`: The pivot point in parent's local space
- `rotation`: Applied around the pivot point
- `scale`: Applied from the pivot point

For hierarchical models (like arm1 with children), precision in pivot points is critical as errors accumulate down the hierarchy.

## Common Issues and Solutions

### Issue 1: Quaternion Sign Flipping
**Problem**: Quaternions q and -q represent the same rotation but have different components.

**Solution**: Normalize quaternions to always have w ≥ 0 for consistent representation.

### Issue 2: Precision Loss in Hierarchies
**Problem**: Rounding pivot points causes accumulated position errors in deep hierarchies.

**Solution**: Use sufficient precision (4 decimals) to minimize accumulation while keeping data LLM-friendly.

### Issue 3: Corner vs Position Confusion
**Problem**: Misinterpreting corner as center position leads to wrong geometry.

**Solution**: The importer explicitly handles both modes with clear documentation of the coordinate relationships.

### Issue 4: Gimbal Lock
**Problem**: At ±90° pitch, Euler angles become ambiguous.

**Solution**: The exporter adds warning comments when near gimbal lock. Multiple valid representations exist.

## Testing Import/Export Consistency

To verify round-trip accuracy:

```bash
# 1. Export v3 to Python
python -m engines.core.v3.python.exporter input.v3.json output.py

# 2. Import Python back to v3
python -m engines.core.v3.python.importer output.py output.v3.json

# 3. Compare the JSON files (should be functionally identical)
```

Key things to check:
- Entity positions and sizes remain correct
- Hierarchical relationships preserved
- Rotations equivalent (even if quaternion components differ slightly)

## Implementation Notes

### Rotation Utilities
All rotation conversions use centralized utilities in `engines/core/v3/rotation_utils.py`:
- `quaternion_to_euler()`: Consistent XYZ order
- `euler_to_quaternion()`: With quaternion normalization
- `is_gimbal_lock()`: Detection for warnings

### Coordinate Transformations  
Coordinate system transformations are in `engines/core/v3/coordinate_utils.py`:
- Handles Blender ↔ v3 transformations
- Used by GLTF importer/exporter

### Security
The Python importer uses a safe execution environment:
- Whitelisted imports only (math, random, itertools, collections)
- No file system access
- No network access
- No arbitrary code execution

## Future Improvements

1. **Texture Support**: Currently uses placeholder textures
2. **Animation Support**: Add keyframe import/export
3. **Material Properties**: Extend beyond basic face textures
4. **Validation**: Add stricter validation for imported Python code