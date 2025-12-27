"""
Tests for the conversion API
"""
import pytest
import os
import tempfile
import json
from blocksmith import convert
from blocksmith.converters import import_python


# Sample Python DSL for testing
SAMPLE_DSL = """
def create_model():
    return [
        cuboid("cube", [0, 0, 0], [1, 1, 1])
    ]
"""


class TestConvertAPI:
    """Test the module-level convert() function"""

    def test_convert_json_to_bbmodel(self):
        """Test converting JSON to BBModel"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a JSON file
            json_path = os.path.join(tmpdir, "model.json")
            bbmodel_path = os.path.join(tmpdir, "model.bbmodel")

            block_json = import_python(SAMPLE_DSL)
            with open(json_path, 'w') as f:
                json.dump(block_json, f)

            # Convert
            convert(json_path, bbmodel_path)

            # Verify output exists and is valid JSON
            assert os.path.exists(bbmodel_path)
            with open(bbmodel_path, 'r') as f:
                bbmodel = json.load(f)
                assert "outliner" in bbmodel

    def test_convert_json_to_glb(self):
        """Test converting JSON to GLB (requires Blender)"""
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = os.path.join(tmpdir, "model.json")
            glb_path = os.path.join(tmpdir, "model.glb")

            block_json = import_python(SAMPLE_DSL)
            with open(json_path, 'w') as f:
                json.dump(block_json, f)

            # Convert
            convert(json_path, glb_path)

            # Verify GLB was created
            assert os.path.exists(glb_path)
            # GLB files start with magic bytes "glTF"
            with open(glb_path, 'rb') as f:
                magic = f.read(4)
                assert magic == b'glTF'

    def test_convert_bbmodel_to_json(self):
        """Test converting BBModel back to JSON"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a JSON, convert to BBModel, then back to JSON
            json_path = os.path.join(tmpdir, "model.json")
            bbmodel_path = os.path.join(tmpdir, "model.bbmodel")
            json_output_path = os.path.join(tmpdir, "output.json")

            block_json = import_python(SAMPLE_DSL)
            with open(json_path, 'w') as f:
                json.dump(block_json, f)

            # JSON -> BBModel
            convert(json_path, bbmodel_path)

            # BBModel -> JSON
            convert(bbmodel_path, json_output_path)

            # Verify output
            assert os.path.exists(json_output_path)
            with open(json_output_path, 'r') as f:
                output_json = json.load(f)
                assert "entities" in output_json

    def test_convert_invalid_input_path(self):
        """Test that convert raises error for non-existent input"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "output.json")

            with pytest.raises(FileNotFoundError):
                convert("nonexistent.json", output_path)

    def test_convert_unsupported_format(self):
        """Test that convert raises error for unsupported formats"""
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = os.path.join(tmpdir, "model.json")
            output_path = os.path.join(tmpdir, "output.xyz")

            # Create a dummy input file
            with open(input_path, 'w') as f:
                json.dump({"entities": []}, f)

            with pytest.raises(ValueError) as exc_info:
                convert(input_path, output_path)

            assert "Unsupported" in str(exc_info.value)

    def test_convert_auto_detects_formats(self):
        """Test that formats are auto-detected from extensions"""
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = os.path.join(tmpdir, "model.json")
            bbmodel_path = os.path.join(tmpdir, "model.bbmodel")

            block_json = import_python(SAMPLE_DSL)
            with open(json_path, 'w') as f:
                json.dump(block_json, f)

            # Should auto-detect json -> bbmodel
            convert(json_path, bbmodel_path)

            assert os.path.exists(bbmodel_path)

    def test_convert_json_to_python(self):
        """Test converting JSON to Python DSL"""
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = os.path.join(tmpdir, "model.json")
            python_path = os.path.join(tmpdir, "model.py")

            block_json = import_python(SAMPLE_DSL)
            with open(json_path, 'w') as f:
                json.dump(block_json, f)

            # Convert JSON -> Python DSL
            convert(json_path, python_path)

            # Verify output exists
            assert os.path.exists(python_path)

            # Verify it's valid Python code
            with open(python_path, 'r') as f:
                python_code = f.read()
                assert "def create_model():" in python_code
                assert "return [" in python_code
                assert "cuboid(" in python_code

    def test_convert_glb_to_python(self):
        """Test converting GLB to Python DSL (requires Blender)"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a GLB file first
            json_path = os.path.join(tmpdir, "model.json")
            glb_path = os.path.join(tmpdir, "model.glb")
            python_path = os.path.join(tmpdir, "model.py")

            block_json = import_python(SAMPLE_DSL)
            with open(json_path, 'w') as f:
                json.dump(block_json, f)

            # JSON -> GLB
            convert(json_path, glb_path)

            # GLB -> Python DSL
            convert(glb_path, python_path)

            # Verify output exists
            assert os.path.exists(python_path)

            # Verify it's valid Python code
            with open(python_path, 'r') as f:
                python_code = f.read()
                assert "def create_model():" in python_code
                assert "return [" in python_code

    def test_convert_python_roundtrip(self):
        """Test that JSON -> Python -> JSON preserves structure"""
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = os.path.join(tmpdir, "model.json")
            python_path = os.path.join(tmpdir, "model.py")
            json_output_path = os.path.join(tmpdir, "output.json")

            # Start with BlockJSON
            block_json = import_python(SAMPLE_DSL)
            with open(json_path, 'w') as f:
                json.dump(block_json, f)

            # JSON -> Python
            convert(json_path, python_path)

            # Python -> JSON
            convert(python_path, json_output_path)

            # Verify structure preserved
            with open(json_output_path, 'r') as f:
                output_json = json.load(f)
                assert "entities" in output_json
                assert len(output_json["entities"]) == len(block_json["entities"])
