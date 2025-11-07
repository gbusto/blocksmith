# GLTF Import/Export for v3 Schema

This directory contains Blender-based scripts for converting between GLTF/GLB files and the v3 schema format.

## Requirements

- Blender 3.x or higher (tested with Blender 4.4.0)
- Python (comes with Blender)

## Usage

### Import GLTF to v3

```bash
/Applications/Blender.app/Contents/MacOS/Blender --background --python importer.py -- --input model.gltf --output model.v3.json
```

### Export v3 to GLTF

```bash
/Applications/Blender.app/Contents/MacOS/Blender --background --python exporter.py -- --input model.v3.json --output model.glb
```

## Scale Strategy

The v3 schema uses a specific scale handling strategy for GLTF compatibility:

### Import (GLTF → v3)
- Bakes all transforms (position, rotation, scale) into geometry coordinates
- Sets scale to [1,1,1] for all entities
- Stores geometry in world space using from/to bounds

### Export (v3 → GLTF)
- Uses pre-baked geometry coordinates directly
- Creates mesh vertices at the exact positions specified by from/to
- Maintains scale as [1,1,1] for clean GLTF output

This ensures perfect roundtrip conversion while keeping the GLTF files clean and simple.

## Coordinate System

v3 uses a Y-up, Z-forward coordinate system:
- +Y = Up (top)
- -Y = Down (bottom)
- +Z = Forward/North (front)
- -Z = Back/South (back)
- +X = Right/East
- -X = Left/West

The scripts handle the conversion to/from Blender's Z-up, Y-forward system automatically.

### ⚠️ CRITICAL BUG: Coordinate Transformation Mismatch

**Issue**: The coordinate transformations between the importer and exporter are NOT inverses of each other, causing position shifts in roundtrip conversions.

**What Was Found**:
- **Importer** (Blender→v3): Uses transformation `X,Y,Z → X,Z,-Y`
  - Code: `pivot = [obj.location.x, obj.location.z, -obj.location.y]`
- **Exporter** (v3→Blender): Uses transformation `X,Y,Z → -X,Z,Y`
  - Code: `pivot_b = [-pivot[0], pivot[2], pivot[1]]`

**Testing the roundtrip**:
```
Blender [1, 2, 3] → v3 [1, 3, -2] → Blender [-1, -2, 3] ❌
```

**Why It Went Undiscovered**:
1. GLTF→v3→GLTF roundtrips work perfectly because the importer stores the original Blender transforms in metadata
2. The exporter checks for this metadata and uses it directly, completely bypassing the transformation
3. This metadata workaround has been masking the underlying coordinate transformation bug
4. Python export/import doesn't preserve metadata, exposing the bug

**The Fix**:
The exporter's transformation should be the mathematical inverse of the importer's:
- Importer: `X,Y,Z → X,Z,-Y`
- Exporter should be: `X,Y,Z → X,-Z,Y` (the true inverse)
- Current exporter: `X,Y,Z → -X,Z,Y` (WRONG - includes unnecessary X flip)

**Implementation Notes**:
- The X-axis flip in the exporter appears intentional (see "reversed winding order due to X-axis flip" comment)
- However, this flip breaks the mathematical relationship between import/export
- The fix will only affect cases where metadata is not present, maintaining compatibility with existing GLTF roundtrips

## Texture Handling

- Textures are embedded as base64-encoded PNG data in the v3 schema
- The exporter uses Blender's tempfile approach for reliable texture loading
- Nearest-neighbor filtering is applied for pixel art textures
- Currently supports a single atlas named "main"

## Troubleshooting

### Black textures in export
If textures appear black in the exported GLB:
1. Ensure the v3 file has valid atlas data
2. Check that the base64 data decodes to a valid PNG
3. Verify UV coordinates are in 0-1 range

### Scale issues
If models appear scaled incorrectly:
1. Verify the v3 file has scale=[1,1,1] for all entities
2. Check that from/to bounds contain the expected world-space coordinates
3. Ensure you're using the latest version of the scripts

## Archive

The `archive/` directory contains previous implementations and experimental code for reference:
- Original pygltflib-based importer/exporter
- Modular texture handling system
- Various texture processing utilities