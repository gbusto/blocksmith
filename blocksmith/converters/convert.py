"""
Format conversion utilities

Provides easy conversion between different 3D model formats without regenerating.
"""

import json
import os
from typing import Optional

from blocksmith.converters import (
    import_python,
    import_bbmodel,
    import_gltf,
    import_glb,
    export_glb,
    export_gltf,
    export_bbmodel
)
from blocksmith.converters.python.exporter import V3ToPythonConverter


def convert(input_path: str, output_path: str) -> None:
    """
    Convert a model from one format to another.

    Automatically detects input and output formats from file extensions.
    Supports: .json (BlockJSON), .bbmodel (Blockbench), .glb, .gltf, .py (Python DSL)

    Args:
        input_path: Path to input file
        output_path: Path to output file

    Raises:
        FileNotFoundError: If input file doesn't exist
        ValueError: If format is unsupported

    Examples:
        >>> convert("model.glb", "model.bbmodel")
        >>> convert("model.json", "model.glb")
        >>> convert("model.bbmodel", "output.json")
        >>> convert("model.glb", "model.py")
    """
    # Check input file exists
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    # Detect formats
    input_format = _detect_format(input_path)
    output_format = _detect_format(output_path)

    # Load input file to BlockJSON (our central format)
    block_json = _load_to_blockjson(input_path, input_format)

    # Ensure model has a valid atlas (Texture it if it's missing!)
    _ensure_textured(block_json)

    # Convert from BlockJSON to output format
    _save_from_blockjson(block_json, output_path, output_format)


def _ensure_textured(block_json: dict) -> None:
    """
    Check if model has a valid atlas, and if not, generate a clay atlas.
    
    This handles:
    1. Python DSL models (which have no textures)
    2. BBModel/GLTF models that might be untextured
    """
    if not block_json:
        return

    meta = block_json.get("meta", {})
    atlases = meta.get("atlases", {})
    
    # Check if we have a valid 'main' atlas with data
    has_valid_atlas = False
    if "main" in atlases:
        atlas_data = atlases["main"].get("data")
        if atlas_data and len(atlas_data) > 0:
            has_valid_atlas = True
            
    if not has_valid_atlas:
        # No texture found! Apply clay atlas.
        from blocksmith.texturing.clay_atlas import build_clay_atlas_with_compiler
        
        # Ensure minimal metadata
        if "meta" not in block_json:
            block_json["meta"] = {}
        
        # Default texel density if missing
        if "texel_density" not in block_json["meta"]:
            block_json["meta"]["texel_density"] = 16
        
        # Modify in-place/update
        updated_json = build_clay_atlas_with_compiler(block_json)
        block_json.update(updated_json)
        
        # Update schema version since we modified it
        block_json["meta"]["schema_version"] = "3.0"


def _detect_format(path: str) -> str:
    """Detect format from file extension"""
    ext = os.path.splitext(path)[1].lower()

    format_map = {
        '.json': 'json',
        '.bbmodel': 'bbmodel',
        '.glb': 'glb',
        '.gltf': 'gltf',
        '.py': 'py'
    }

    if ext not in format_map:
        raise ValueError(
            f"Unsupported file format: {ext}. "
            f"Supported: .json, .bbmodel, .glb, .gltf, .py"
        )

    return format_map[ext]


def _load_to_blockjson(path: str, format: str) -> dict:
    """Load any format and convert to BlockJSON"""
    if format == 'json':
        # Already BlockJSON
        with open(path, 'r') as f:
            return json.load(f)

    elif format == 'bbmodel':
        # BBModel -> BlockJSON
        with open(path, 'r') as f:
            bbmodel_str = f.read()
        return import_bbmodel(bbmodel_str)

    elif format == 'py':
        # Python DSL -> BlockJSON
        with open(path, 'r') as f:
            python_code = f.read()
        return import_python(python_code)

    elif format in ('glb', 'gltf'):
        # GLB/GLTF -> BlockJSON (requires Blender)
        return import_gltf(path)

    else:
        raise ValueError(f"Unsupported input format: {format}")


def _save_from_blockjson(block_json: dict, path: str, format: str) -> None:
    """Save BlockJSON to any format"""
    if format == 'json':
        # BlockJSON -> JSON file
        with open(path, 'w') as f:
            json.dump(block_json, f, indent=2)

    elif format == 'bbmodel':
        # BlockJSON -> BBModel
        bbmodel_str = export_bbmodel(block_json)
        with open(path, 'w') as f:
            f.write(bbmodel_str)

    elif format == 'glb':
        # BlockJSON -> GLB
        glb_bytes = export_glb(block_json)
        with open(path, 'wb') as f:
            f.write(glb_bytes)

    elif format == 'gltf':
        # BlockJSON -> GLTF
        gltf_str = export_gltf(block_json)
        with open(path, 'w') as f:
            f.write(gltf_str)

    elif format == 'py':
        # BlockJSON -> Python DSL
        converter = V3ToPythonConverter()
        python_code = converter.convert(block_json)
        with open(path, 'w') as f:
            f.write(python_code)

    else:
        raise ValueError(f"Unsupported output format: {format}")
