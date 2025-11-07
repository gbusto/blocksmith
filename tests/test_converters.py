"""
Test format converters (Python DSL → JSON → BBModel)
"""
import pytest
import json
from blocksmith.converters import import_python, export_bbmodel
from blocksmith.schema.blockjson import ModelDefinition


class TestPythonToJSON:
    """Test Python DSL → BlockJSON conversion"""

    def test_simple_cube_converts(self):
        """Test that a simple cube DSL converts to valid JSON"""
        dsl = """
def create_model():
    return [
        cuboid("cube", [0, 0, 0], [1, 1, 1])
    ]
"""
        result = import_python(dsl)

        # Should be valid BlockJSON
        model = ModelDefinition.model_validate(result)

        # Should have one entity
        assert len(model.entities) == 1
        assert model.entities[0].id == "cube"
        assert model.entities[0].type == "cuboid"

    def test_grouped_model_converts(self):
        """Test that a model with groups converts properly"""
        dsl = """
def create_model():
    return [
        group("root", [0, 0, 0]),
        cuboid("body", [0, 1, 0], [1, 2, 0.5], parent="root"),
        cuboid("head", [0, 3, 0], [0.75, 0.75, 0.75], parent="root")
    ]
"""
        result = import_python(dsl)
        model = ModelDefinition.model_validate(result)

        # Should have 3 entities (1 group + 2 cuboids)
        assert len(model.entities) == 3

        # Check hierarchy
        cuboids = [e for e in model.entities if e.type == "cuboid"]
        assert all(c.parent == "root" for c in cuboids)

    def test_invalid_dsl_returns_empty(self):
        """Test that invalid Python DSL returns empty dict"""
        bad_dsl = """
def create_model():
    return [
        this_function_does_not_exist("invalid", [0, 0, 0])
    ]
"""
        result = import_python(bad_dsl)
        assert result == {}  # Importer returns {} on error

    def test_missing_create_model_returns_empty(self):
        """Test that DSL without create_model() returns empty dict"""
        bad_dsl = """
def some_other_function():
    return []
"""
        result = import_python(bad_dsl)
        assert result == {}  # Importer returns {} on error


class TestJSONToBlockJSON:
    """Test BlockJSON validation - integration test"""

    def test_python_dsl_produces_valid_json(self):
        """Test that Python DSL → JSON produces valid BlockJSON"""
        dsl = """
def create_model():
    return [
        cuboid("cube", [0, 0, 0], [1, 1, 1])
    ]
"""
        result = import_python(dsl)

        # Should be valid BlockJSON that ModelDefinition can validate
        model = ModelDefinition.model_validate(result)
        assert len(model.entities) == 1
        assert model.entities[0].id == "cube"
