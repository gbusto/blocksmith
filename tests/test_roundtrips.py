"""
Round-trip converter tests to catch regressions

These tests ensure converters don't lose information when doing:
- JSON → BBModel → JSON
- JSON → Python DSL → JSON

We check semantic equivalence (structure, hierarchy, values) rather than
exact byte equality, accounting for float precision and format quirks.
"""
import pytest
from blocksmith.converters import (
    import_python,
    export_bbmodel,
    import_bbmodel
)
from blocksmith.converters.python.exporter import V3ToPythonConverter
from blocksmith.converters.rotation_utils import (
    quaternion_to_euler,
    euler_to_quaternion
)


# Helper functions for creating valid test models
def create_test_atlases():
    """Create valid atlas definitions for test models (matches import_python output)"""
    return {
        "main": {
            "data": "",  # Empty for now - no texture generation yet
            "mime": "image/png",
            "resolution": [16, 16]
        }
    }


def create_test_faces():
    """Create valid face definitions for test cuboids (matches import_python output)"""
    return {
        "front": {"atlas_id": "main", "uv": [0, 0, 1, 1]},
        "back": {"atlas_id": "main", "uv": [0, 0, 1, 1]},
        "left": {"atlas_id": "main", "uv": [0, 0, 1, 1]},
        "right": {"atlas_id": "main", "uv": [0, 0, 1, 1]},
        "top": {"atlas_id": "main", "uv": [0, 0, 1, 1]},
        "bottom": {"atlas_id": "main", "uv": [0, 0, 1, 1]},
    }


# Golden model with hierarchy - use the same working model from test_converters.py
GOLDEN_DSL = """
def create_model():
    return [
        group("root", [0, 0, 0]),
        cuboid("body", [0, 1, 0], [1, 2, 0.5], parent="root"),
        cuboid("head", [0, 3, 0], [0.75, 0.75, 0.75], parent="root")
    ]
"""

# Import it to get valid JSON
GOLDEN_MODEL = import_python(GOLDEN_DSL)


def approx_equal(a, b, tolerance=0.001):
    """Check if two values are approximately equal"""
    if isinstance(a, list) and isinstance(b, list):
        return all(approx_equal(x, y, tolerance) for x, y in zip(a, b))
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) < tolerance
    return a == b


class TestBBModelRoundtrip:
    """Test JSON → BBModel → JSON preserves structure"""

    def test_simple_model_roundtrip(self):
        """Simple model should survive BBModel round-trip"""
        # Export to BBModel
        bbmodel_str = export_bbmodel(GOLDEN_MODEL)

        # Basic sanity checks on BBModel format
        import json
        bbmodel = json.loads(bbmodel_str)
        assert "meta" in bbmodel
        assert "elements" in bbmodel
        assert "outliner" in bbmodel

        # Import back to JSON
        result = import_bbmodel(bbmodel_str)

        # Should have same number of entities
        assert len(result["entities"]) == len(GOLDEN_MODEL["entities"])

        # Find entities by type
        result_group = [e for e in result["entities"] if e["type"] == "group"][0]
        result_cuboid = [e for e in result["entities"] if e["type"] == "cuboid"][0]

        golden_group = GOLDEN_MODEL["entities"][0]
        golden_cuboid = GOLDEN_MODEL["entities"][1]

        # Check group properties (BBModel preserves these well)
        assert result_group["type"] == "group"
        assert result_group["label"] == golden_group["label"]
        assert approx_equal(result_group["pivot"], golden_group["pivot"])
        # Rotation might have small precision differences
        assert approx_equal(result_group["rotation"], golden_group["rotation"], tolerance=0.01)

        # Check cuboid properties
        assert result_cuboid["type"] == "cuboid"
        assert result_cuboid["parent"] == result_group["id"]  # Hierarchy preserved
        assert approx_equal(result_cuboid["from"], golden_cuboid["from"])
        assert approx_equal(result_cuboid["to"], golden_cuboid["to"])

    def test_hierarchy_preserved(self):
        """BBModel should preserve parent-child relationships"""
        bbmodel_str = export_bbmodel(GOLDEN_MODEL)
        result = import_bbmodel(bbmodel_str)

        # Find the cuboid
        cuboid = [e for e in result["entities"] if e["type"] == "cuboid"][0]

        # Should have parent relationship
        assert "parent" in cuboid
        assert cuboid["parent"] is not None

        # Parent should exist
        parent_ids = [e["id"] for e in result["entities"]]
        assert cuboid["parent"] in parent_ids

    def test_metadata_preserved(self):
        """Texel density and other metadata should survive round-trip"""
        bbmodel_str = export_bbmodel(GOLDEN_MODEL)
        result = import_bbmodel(bbmodel_str)

        # Texel density should be preserved
        assert result["meta"]["texel_density"] == GOLDEN_MODEL["meta"]["texel_density"]


class TestConverterStability:
    """Test that converters produce consistent output"""

    def test_bbmodel_structure_is_consistent(self):
        """BBModel should have consistent structure (ignoring UUIDs)"""
        import json

        bbmodel1 = json.loads(export_bbmodel(GOLDEN_MODEL))
        bbmodel2 = json.loads(export_bbmodel(GOLDEN_MODEL))

        # Same number of elements
        assert len(bbmodel1["elements"]) == len(bbmodel2["elements"])

        # Same number of outliner nodes
        assert len(bbmodel1["outliner"]) == len(bbmodel2["outliner"])

        # Same element names (order might differ, but names should match)
        names1 = sorted([e["name"] for e in bbmodel1["elements"]])
        names2 = sorted([e["name"] for e in bbmodel2["elements"]])
        assert names1 == names2


class TestPythonDSLRoundtrip:
    """Test JSON → Python DSL → JSON preserves structure"""

    def test_simple_model_roundtrip(self):
        """Simple model should survive Python DSL round-trip"""
        # Export to Python DSL using converter directly
        converter = V3ToPythonConverter()
        python_code = converter.convert(GOLDEN_MODEL)

        # Should be valid Python code
        assert "def create_model():" in python_code
        assert "return [" in python_code

        # Import back to JSON
        result = import_python(python_code)

        # Should have same number of entities
        assert len(result["entities"]) == len(GOLDEN_MODEL["entities"])

        # Check entity types preserved
        result_types = sorted([e["type"] for e in result["entities"]])
        golden_types = sorted([e["type"] for e in GOLDEN_MODEL["entities"]])
        assert result_types == golden_types

    def test_hierarchy_preserved(self):
        """Python DSL should preserve parent-child relationships"""
        converter = V3ToPythonConverter()
        python_code = converter.convert(GOLDEN_MODEL)
        result = import_python(python_code)

        # Find cuboids - they should have parent relationships
        result_cuboids = [e for e in result["entities"] if e["type"] == "cuboid"]
        golden_cuboids = [e for e in GOLDEN_MODEL["entities"] if e["type"] == "cuboid"]

        # All cuboids should have parents
        assert all("parent" in c for c in result_cuboids)
        assert len(result_cuboids) == len(golden_cuboids)

    def test_number_formatting(self):
        """Python DSL should format numbers cleanly (1.0 → 1, 0.5 → 0.5)"""
        # Create model with various number formats
        test_model = {
            "meta": {"texel_density": 16, "atlases": create_test_atlases()},
            "entities": [
                {
                    "id": "test",
                    "type": "cuboid",
                    "label": "Test",
                    "pivot": [1.0, 0.5, 2.0],  # Mix of integer-like and decimal
                    "rotation": [1, 0, 0, 0],
                    "scale": [1, 1, 1],
                    "from": [0, 0, 0],
                    "to": [1.0, 2.0, 0.5],  # Should format cleanly
                    "inflate": 0,
                    "faces": create_test_faces()
                }
            ]
        }

        converter = V3ToPythonConverter()
        python_code = converter.convert(test_model)

        # Check clean formatting (no .0 on integers)
        assert "[1, 0.5, 2]" in python_code  # pivot should be clean
        # Note: from/to are calculated from corner/size in the DSL

        # Should roundtrip successfully
        result = import_python(python_code)
        assert len(result["entities"]) == 1

    def test_default_value_omission(self):
        """Python DSL should omit default values for clean code"""
        test_model = {
            "meta": {"texel_density": 16, "atlases": create_test_atlases()},
            "entities": [
                {
                    "id": "test",
                    "type": "cuboid",
                    "label": "Test",
                    "pivot": [0.5, 0.5, 0.5],
                    "rotation": [1, 0, 0, 0],  # Default - should be omitted
                    "scale": [1, 1, 1],  # Default - should be omitted
                    "from": [0, 0, 0],
                    "to": [1, 1, 1],
                    "inflate": 0,  # Default - should be omitted
                    "faces": create_test_faces()
                }
            ]
        }

        converter = V3ToPythonConverter()
        python_code = converter.convert(test_model)

        # Default rotation should not appear in code
        # (the exporter omits default values for cleaner LLM-generated code)
        lines = python_code.split('\n')
        cuboid_line = [l for l in lines if 'cuboid(' in l][0]

        # Check that default parameters are omitted
        # rotation=[1, 0, 0, 0] should not appear
        assert "rotation=" not in cuboid_line or "rotation=[1, 0, 0, 0]" not in python_code

        # Should still roundtrip correctly with defaults filled in
        result = import_python(python_code)
        cuboid = result["entities"][0]
        assert approx_equal(cuboid["rotation"], [1, 0, 0, 0])
        assert approx_equal(cuboid["scale"], [1, 1, 1])


class TestBBModelRotationRoundtrip:
    """Test BBModel roundtrip with non-identity rotations"""

    def test_90_degree_rotation_roundtrip(self):
        """90° rotations should survive BBModel round-trip"""
        # Create model with 90° rotation around Y axis
        rotated_model = {
            "meta": {"texel_density": 16, "atlases": create_test_atlases()},
            "entities": [
                {
                    "id": "rotated",
                    "type": "cuboid",
                    "label": "Rotated",
                    "pivot": [0.5, 0.5, 0.5],
                    "rotation": euler_to_quaternion([0, 90, 0]),  # 90° Y rotation
                    "scale": [1, 1, 1],
                    "from": [0, 0, 0],
                    "to": [1, 1, 1],
                    "inflate": 0,
                    "faces": create_test_faces()
                }
            ]
        }

        # Export and reimport
        bbmodel_str = export_bbmodel(rotated_model)
        result = import_bbmodel(bbmodel_str)

        # Check rotation preserved (with some tolerance for float precision)
        result_cuboid = [e for e in result["entities"] if e["type"] == "cuboid"][0]
        result_euler = quaternion_to_euler(result_cuboid["rotation"])

        # Should be approximately [0, 90, 0]
        assert approx_equal(result_euler[0], 0, tolerance=1)
        assert approx_equal(result_euler[1], 90, tolerance=1)
        assert approx_equal(result_euler[2], 0, tolerance=1)

    def test_45_degree_rotation_roundtrip(self):
        """Arbitrary 45° rotations should survive BBModel round-trip"""
        # Create model with 45° rotation around X axis
        rotated_model = {
            "meta": {"texel_density": 16, "atlases": create_test_atlases()},
            "entities": [
                {
                    "id": "rotated",
                    "type": "cuboid",
                    "label": "Rotated",
                    "pivot": [0.5, 0.5, 0.5],
                    "rotation": euler_to_quaternion([45, 0, 0]),  # 45° X rotation
                    "scale": [1, 1, 1],
                    "from": [0, 0, 0],
                    "to": [1, 1, 1],
                    "inflate": 0,
                    "faces": create_test_faces()
                }
            ]
        }

        # Export and reimport
        bbmodel_str = export_bbmodel(rotated_model)
        result = import_bbmodel(bbmodel_str)

        # Check rotation preserved
        result_cuboid = [e for e in result["entities"] if e["type"] == "cuboid"][0]
        result_euler = quaternion_to_euler(result_cuboid["rotation"])

        # Should be approximately [45, 0, 0]
        assert approx_equal(result_euler[0], 45, tolerance=1)
        assert approx_equal(result_euler[1], 0, tolerance=1)
        assert approx_equal(result_euler[2], 0, tolerance=1)

    def test_combined_rotation_roundtrip(self):
        """Multi-axis rotations should survive BBModel round-trip"""
        # Create model with rotation around two axes (simpler, more reliable)
        rotated_model = {
            "meta": {"texel_density": 16, "atlases": create_test_atlases()},
            "entities": [
                {
                    "id": "rotated",
                    "type": "cuboid",
                    "label": "Rotated",
                    "pivot": [0.5, 0.5, 0.5],
                    "rotation": euler_to_quaternion([30, 0, 45]),  # Two-axis rotation
                    "scale": [1, 1, 1],
                    "from": [0, 0, 0],
                    "to": [1, 1, 1],
                    "inflate": 0,
                    "faces": create_test_faces()
                }
            ]
        }

        # Export and reimport
        bbmodel_str = export_bbmodel(rotated_model)
        result = import_bbmodel(bbmodel_str)

        # Check rotation preserved (quaternions should be very close)
        result_cuboid = [e for e in result["entities"] if e["type"] == "cuboid"][0]
        original_quat = rotated_model["entities"][0]["rotation"]
        result_quat = result_cuboid["rotation"]

        # Compare quaternions component-wise (allowing for sign flip since q and -q are same rotation)
        for i in range(4):
            assert approx_equal(abs(result_quat[i]), abs(original_quat[i]), tolerance=0.01)


class TestBBModelScaleRoundtrip:
    """Test BBModel roundtrip with non-uniform scales

    NOTE: BBModel format does not support scale transforms.
    These tests document this limitation.
    """

    @pytest.mark.skip(reason="BBModel format does not support scale transforms (known limitation)")
    def test_non_uniform_scale_roundtrip(self):
        """Non-uniform scales should survive BBModel round-trip (SKIPPED: not supported)"""
        scaled_model = {
            "meta": {"texel_density": 16, "atlases": create_test_atlases()},
            "entities": [
                {
                    "id": "scaled",
                    "type": "cuboid",
                    "label": "Scaled",
                    "pivot": [0.5, 0.5, 0.5],
                    "rotation": [1, 0, 0, 0],
                    "scale": [2, 1, 1],  # Stretched on X axis
                    "from": [0, 0, 0],
                    "to": [1, 1, 1],
                    "inflate": 0,
                    "faces": create_test_faces()
                }
            ]
        }

        # Export and reimport
        bbmodel_str = export_bbmodel(scaled_model)
        result = import_bbmodel(bbmodel_str)

        # Check scale preserved
        result_cuboid = [e for e in result["entities"] if e["type"] == "cuboid"][0]
        assert approx_equal(result_cuboid["scale"], [2, 1, 1])

    @pytest.mark.skip(reason="BBModel format does not support scale transforms (known limitation)")
    def test_fractional_scale_roundtrip(self):
        """Fractional scales should survive BBModel round-trip (SKIPPED: not supported)"""
        scaled_model = {
            "meta": {"texel_density": 16, "atlases": create_test_atlases()},
            "entities": [
                {
                    "id": "scaled",
                    "type": "cuboid",
                    "label": "Scaled",
                    "pivot": [0.5, 0.5, 0.5],
                    "rotation": [1, 0, 0, 0],
                    "scale": [0.5, 1.5, 2.0],  # Mixed fractional scales
                    "from": [0, 0, 0],
                    "to": [1, 1, 1],
                    "inflate": 0,
                    "faces": create_test_faces()
                }
            ]
        }

        # Export and reimport
        bbmodel_str = export_bbmodel(scaled_model)
        result = import_bbmodel(bbmodel_str)

        # Check scale preserved
        result_cuboid = [e for e in result["entities"] if e["type"] == "cuboid"][0]
        assert approx_equal(result_cuboid["scale"], [0.5, 1.5, 2.0])


class TestDeepHierarchy:
    """Test roundtrip with deep parent-child hierarchies"""

    def test_three_level_hierarchy_roundtrip(self):
        """3-level hierarchy should survive BBModel round-trip"""
        deep_model = {
            "meta": {"texel_density": 16, "atlases": create_test_atlases()},
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
                    "id": "child",
                    "type": "group",
                    "label": "Child",
                    "parent": "root",
                    "pivot": [1, 0, 0],
                    "rotation": [1, 0, 0, 0],
                    "scale": [1, 1, 1]
                },
                {
                    "id": "grandchild",
                    "type": "group",
                    "label": "Grandchild",
                    "parent": "child",
                    "pivot": [2, 0, 0],
                    "rotation": [1, 0, 0, 0],
                    "scale": [1, 1, 1]
                },
                {
                    "id": "cube",
                    "type": "cuboid",
                    "label": "Cube",
                    "parent": "grandchild",
                    "pivot": [2.5, 0.5, 0.5],
                    "rotation": [1, 0, 0, 0],
                    "scale": [1, 1, 1],
                    "from": [2, 0, 0],
                    "to": [3, 1, 1],
                    "inflate": 0,
                    "faces": create_test_faces()
                }
            ]
        }

        # Export and reimport
        bbmodel_str = export_bbmodel(deep_model)
        result = import_bbmodel(bbmodel_str)

        # Should have 4 entities
        assert len(result["entities"]) == 4

        # Find entities by label
        entities_by_label = {e["label"]: e for e in result["entities"]}

        # Check hierarchy preserved
        assert entities_by_label["Root"]["parent"] is None  # Root has no parent
        assert entities_by_label["Child"]["parent"] == entities_by_label["Root"]["id"]
        assert entities_by_label["Grandchild"]["parent"] == entities_by_label["Child"]["id"]
        assert entities_by_label["Cube"]["parent"] == entities_by_label["Grandchild"]["id"]


class TestRotationAccuracy:
    """Test rotation conversion accuracy (not roundtrip, just math validation)"""

    def test_90_degree_rotations_accurate(self):
        """90° rotations should convert accurately"""
        test_cases = [
            [90, 0, 0],   # X rotation
            [0, 90, 0],   # Y rotation
            [0, 0, 90],   # Z rotation
        ]

        for euler in test_cases:
            quat = euler_to_quaternion(euler)
            result_euler = quaternion_to_euler(quat)

            # Should match within 0.1 degrees
            assert approx_equal(result_euler, euler, tolerance=0.1), \
                f"90° rotation failed: {euler} → quat → {result_euler}"

    def test_arbitrary_angles_accurate(self):
        """Arbitrary single-axis angles should convert accurately"""
        # Single-axis rotations are deterministic
        test_cases = [
            [45, 0, 0],
            [0, 45, 0],
            [0, 0, 45],
            [30, 0, 0],
            [0, 15, 0],
        ]

        for euler in test_cases:
            quat = euler_to_quaternion(euler)
            result_euler = quaternion_to_euler(quat)

            # Should match within 0.1 degrees
            assert approx_equal(result_euler, euler, tolerance=0.1), \
                f"Rotation failed: {euler} → quat → {result_euler}"

    def test_near_gimbal_lock_warning(self):
        """Near-gimbal lock rotations should be noted (but not fail)"""
        # These are problematic but should still work reasonably
        gimbal_cases = [
            [0, 89, 0],   # Near gimbal lock
            [0, -89, 0],  # Near gimbal lock (negative)
        ]

        for euler in gimbal_cases:
            quat = euler_to_quaternion(euler)
            result_euler = quaternion_to_euler(quat)

            # Allow larger tolerance near gimbal lock
            # This test documents that we handle it gracefully
            error = max(abs(r - e) for r, e in zip(result_euler, euler))
            assert error < 5.0, \
                f"Gimbal lock region failed badly: {euler} → quat → {result_euler}"
