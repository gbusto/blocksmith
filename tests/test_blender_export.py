"""
Integration tests for Blender export (GLB/GLTF)

These tests require Blender to be installed.
They're skipped locally if Blender isn't found, but required in CI.
"""
import pytest
import json
import tempfile
import os
import shutil
import subprocess
from pathlib import Path

from blocksmith.converters import export_glb, export_gltf


def blender_available():
    """Check if Blender is available"""
    # Check for BLENDER_PATH env var
    blender_path = os.environ.get('BLENDER_PATH')
    if blender_path and os.path.exists(blender_path):
        return True

    # Check if 'blender' command works
    try:
        result = subprocess.run(
            ['blender', '--version'],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


# Skip these tests locally if Blender not found, but fail in CI
skip_if_no_blender = pytest.mark.skipif(
    not blender_available() and not os.environ.get('CI'),
    reason="Blender not installed (required in CI)"
)


class TestBlenderExport:
    """Test actual Blender export functionality"""

    @skip_if_no_blender
    def test_simple_cube_exports_to_glb(self):
        """Test that a simple cube can be exported to GLB via Blender"""
        # Simple BlockJSON model
        blockjson = {
            "meta": {
                "texel_density": 16,
                "atlases": {}
            },
            "entities": [
                {
                    "id": "cube",
                    "type": "cuboid",
                    "label": "TestCube",
                    "pivot": [0.5, 0.5, 0.5],
                    "rotation": [1, 0, 0, 0],
                    "scale": [1, 1, 1],
                    "from": [0, 0, 0],
                    "to": [1, 1, 1],
                    "inflate": 0,
                    "faces": {}
                }
            ]
        }

        # Export to GLB
        glb_bytes = export_glb(blockjson)

        # Should return bytes
        assert isinstance(glb_bytes, bytes)
        assert len(glb_bytes) > 0

        # GLB files start with magic bytes "glTF"
        assert glb_bytes[:4] == b'glTF'

    @skip_if_no_blender
    def test_simple_cube_exports_to_gltf(self):
        """Test that a simple cube can be exported to GLTF via Blender"""
        blockjson = {
            "meta": {
                "texel_density": 16,
                "atlases": {}
            },
            "entities": [
                {
                    "id": "cube",
                    "type": "cuboid",
                    "label": "TestCube",
                    "pivot": [0.5, 0.5, 0.5],
                    "rotation": [1, 0, 0, 0],
                    "scale": [1, 1, 1],
                    "from": [0, 0, 0],
                    "to": [1, 1, 1],
                    "inflate": 0,
                    "faces": {}
                }
            ]
        }

        # Export to GLTF
        gltf_str = export_gltf(blockjson)

        # Should return string
        assert isinstance(gltf_str, str)
        assert len(gltf_str) > 0

        # Should be valid JSON
        gltf_data = json.loads(gltf_str)

        # Should have GLTF structure
        assert "asset" in gltf_data
        assert "scenes" in gltf_data
        assert "nodes" in gltf_data
        assert "meshes" in gltf_data

    @skip_if_no_blender
    def test_grouped_model_exports_to_glb(self):
        """Test that a model with groups exports correctly"""
        blockjson = {
            "meta": {
                "texel_density": 16,
                "atlases": {}
            },
            "entities": [
                {
                    "id": "root",
                    "type": "group",
                    "label": "Root",
                    "pivot": [0, 0, 0],
                    "rotation": [1, 0, 0, 0],
                    "scale": [1, 1, 1]
                },
                {
                    "id": "cube1",
                    "type": "cuboid",
                    "label": "Cube1",
                    "parent": "root",
                    "pivot": [0.5, 0.5, 0.5],
                    "rotation": [1, 0, 0, 0],
                    "scale": [1, 1, 1],
                    "from": [0, 0, 0],
                    "to": [1, 1, 1],
                    "inflate": 0,
                    "faces": {}
                },
                {
                    "id": "cube2",
                    "type": "cuboid",
                    "label": "Cube2",
                    "parent": "root",
                    "pivot": [1.5, 0.5, 0.5],
                    "rotation": [1, 0, 0, 0],
                    "scale": [1, 1, 1],
                    "from": [1, 0, 0],
                    "to": [2, 1, 1],
                    "inflate": 0,
                    "faces": {}
                }
            ]
        }

        # Export to GLB
        glb_bytes = export_glb(blockjson)

        # Should succeed
        assert isinstance(glb_bytes, bytes)
        assert len(glb_bytes) > 0
        assert glb_bytes[:4] == b'glTF'

    @skip_if_no_blender
    def test_glb_can_be_written_to_file(self):
        """Test that GLB export can be written to a file"""
        blockjson = {
            "meta": {
                "texel_density": 16,
                "atlases": {}
            },
            "entities": [
                {
                    "id": "cube",
                    "type": "cuboid",
                    "label": "TestCube",
                    "pivot": [0.5, 0.5, 0.5],
                    "rotation": [1, 0, 0, 0],
                    "scale": [1, 1, 1],
                    "from": [0, 0, 0],
                    "to": [1, 1, 1],
                    "inflate": 0,
                    "faces": {}
                }
            ]
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "test.glb")

            # Export and write
            glb_bytes = export_glb(blockjson)
            with open(output_path, 'wb') as f:
                f.write(glb_bytes)

            # File should exist and have content
            assert os.path.exists(output_path)
            assert os.path.getsize(output_path) > 0

            # Should be valid GLB
            with open(output_path, 'rb') as f:
                content = f.read()
                assert content[:4] == b'glTF'
