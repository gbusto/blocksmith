"""
GLTF/GLB importer wrapper using Blender

Provides Python-callable interface to import GLTF/GLB files to v3 BlockJSON schema.
"""

import json
import subprocess
import tempfile
import os
from pathlib import Path
from typing import Dict, Any


def import_gltf(file_path: str, include_non_visual: bool = False) -> Dict[str, Any]:
    """
    Import GLTF/GLB file to BlockJSON v3 schema using Blender.

    Args:
        file_path: Path to GLTF or GLB file
        include_non_visual: Include non-visual geometry (joints, etc)

    Returns:
        BlockJSON v3 schema dict

    Raises:
        FileNotFoundError: If Blender or input file not found
        ValueError: If Blender import fails

    Example:
        >>> block_json = import_gltf("model.glb")
        >>> print(block_json["entities"])
    """
    # Find Blender
    blender_path = _find_blender()
    if not blender_path:
        raise FileNotFoundError(
            "Blender not found. Please install Blender to import GLB/GLTF files.\n"
            "Install from: https://www.blender.org/download/\n"
            "Or set BLENDER_PATH environment variable."
        )

    # Find importer script
    script_path = Path(__file__).parent / "importer.py"
    if not script_path.exists():
        raise FileNotFoundError(f"Importer script not found: {script_path}")

    # Check input file exists
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Input file not found: {file_path}")

    # Create temp output file
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False, mode='w') as tmp:
        output_path = tmp.name

    try:
        # Build Blender command
        cmd = [
            blender_path,
            "--background",
            "--python", str(script_path),
            "--",
            "--input", str(file_path),
            "--output", output_path
        ]

        if include_non_visual:
            cmd.append("--include-non-visual")

        # Run Blender
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise ValueError(
                f"Blender import failed.\n"
                f"Error: {result.stderr}\n"
                f"Make sure Blender is properly installed."
            )

        # Read output JSON
        with open(output_path, 'r') as f:
            return json.load(f)

    finally:
        # Clean up temp file
        if os.path.exists(output_path):
            os.unlink(output_path)


def _find_blender() -> str:
    """Find Blender executable"""
    # Check environment variable
    if os.getenv("BLENDER_PATH"):
        return os.getenv("BLENDER_PATH")

    # Check common locations
    common_paths = [
        "/Applications/Blender.app/Contents/MacOS/Blender",  # macOS
        "/usr/bin/blender",  # Linux
        "/usr/local/bin/blender",  # Linux
        "blender",  # In PATH
    ]

    for path in common_paths:
        try:
            result = subprocess.run([path, "--version"], capture_output=True)
            if result.returncode == 0:
                return path
        except FileNotFoundError:
            continue

    return None


# Alias for consistency
import_glb = import_gltf
