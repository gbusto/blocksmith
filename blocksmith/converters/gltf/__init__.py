"""
GLTF to v3 Schema Conversion Package

Provides Blender-based import/export scripts for GLTF/GLB files to/from v3 schema format.

Usage:
    Import GLTF to v3:
    /Applications/Blender.app/Contents/MacOS/Blender --background --python importer.py -- --input model.gltf --output model.v3.json

    Export v3 to GLTF:
    /Applications/Blender.app/Contents/MacOS/Blender --background --python exporter.py -- --input model.v3.json --output model.glb

Note: These scripts require Blender to be installed and run as command-line tools.
"""

# Since these are Blender scripts, they can't be imported as Python modules
# They must be executed with Blender's Python interpreter

__all__ = []