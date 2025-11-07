"""
Integration tests for model generation with real API calls.

⚠️  WARNING: These tests make real API calls and cost real money!

Requirements:
- Valid API key in environment (GEMINI_API_KEY or OPENAI_API_KEY)
- Internet connection
- Tests will be skipped if API key is not set

Run with:
    pytest tests/integration/test_generation.py -v -s
"""

import pytest
import os
import tempfile
from pathlib import Path
from blocksmith import Blocksmith


# Default model for integration tests (cheap and fast)
DEFAULT_TEST_MODEL = "gemini/gemini-2.5-flash-lite"


# Skip all tests in this file if no API key is set
pytestmark = pytest.mark.skipif(
    not os.getenv("GEMINI_API_KEY") and not os.getenv("OPENAI_API_KEY"),
    reason="No API key found - set GEMINI_API_KEY or OPENAI_API_KEY to run integration tests"
)


class TestBasicGeneration:
    """Test basic model generation with real API calls"""

    def test_simple_generation(self):
        """Test generating a simple model"""
        bs = Blocksmith(default_model=DEFAULT_TEST_MODEL)
        result = bs.generate("a simple red cube")

        # Verify result structure
        assert result.dsl is not None
        assert len(result.dsl) > 0
        assert "def create_model" in result.dsl or "create_model" in result.dsl

        # Verify metadata
        assert result.tokens.total_tokens > 0
        assert result.tokens.prompt_tokens > 0
        assert result.tokens.completion_tokens > 0
        assert result.model is not None

        # Cost may be None for local models
        print(f"\n✓ Generated {len(result.dsl)} chars of code")
        print(f"  Tokens: {result.tokens.total_tokens}")
        print(f"  Cost: ${result.cost:.4f}" if result.cost else "  Cost: N/A (local model)")

    def test_generation_with_custom_model(self):
        """Test generation with a different model"""
        bs = Blocksmith(default_model=DEFAULT_TEST_MODEL)
        result = bs.generate("a blue sphere", model="gemini/gemini-2.0-flash-exp")

        assert result.dsl is not None
        assert len(result.dsl) > 0
        assert result.model == "gemini/gemini-2.0-flash-exp"

        print(f"\n✓ Generated with {result.model}")
        print(f"  Tokens: {result.tokens.total_tokens}")

    def test_dsl_to_json_conversion(self):
        """Test that generated DSL can be converted to JSON"""
        bs = Blocksmith(default_model=DEFAULT_TEST_MODEL)
        result = bs.generate("a small green cube")

        # Convert to JSON
        json_data = result.to_json()

        assert "entities" in json_data
        assert isinstance(json_data["entities"], list)
        assert len(json_data["entities"]) > 0

        print(f"\n✓ DSL converted to BlockJSON")
        print(f"  Entities: {len(json_data['entities'])}")


class TestImageGeneration:
    """Test generation with reference images"""

    def test_generation_with_local_image(self):
        """Test generation with a local image file"""
        bs = Blocksmith(default_model=DEFAULT_TEST_MODEL)

        # Use the test image we created
        test_image = Path(__file__).parent.parent / "test_image.jpg"

        if not test_image.exists():
            pytest.skip("Test image not found")

        result = bs.generate(
            "create a blocky version of this",
            image=str(test_image)
        )

        assert result.dsl is not None
        assert len(result.dsl) > 0
        assert result.tokens.total_tokens > 0

        print(f"\n✓ Generated with local image: {test_image.name}")
        print(f"  Tokens: {result.tokens.total_tokens}")

    @pytest.mark.skip(reason="Remote image test - uncomment to run manually")
    def test_generation_with_remote_image(self):
        """Test generation with a remote image URL"""
        bs = Blocksmith(default_model=DEFAULT_TEST_MODEL)

        # Using a public domain image
        image_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3a/Cat03.jpg/240px-Cat03.jpg"

        result = bs.generate(
            "create a blocky cat based on this image",
            image=image_url
        )

        assert result.dsl is not None
        assert len(result.dsl) > 0

        print(f"\n✓ Generated with remote image")
        print(f"  Tokens: {result.tokens.total_tokens}")


class TestFullPipeline:
    """Test the complete generation and export pipeline"""

    def test_generate_and_save_all_formats(self):
        """Test generating a model and saving to all formats"""
        bs = Blocksmith(default_model=DEFAULT_TEST_MODEL)
        result = bs.generate("a tiny yellow cube")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Save as Python DSL
            py_path = tmpdir / "model.py"
            result.save(str(py_path))
            assert py_path.exists()
            assert py_path.read_text() == result.dsl

            # Save as JSON
            json_path = tmpdir / "model.json"
            result.save(str(json_path))
            assert json_path.exists()

            # Save as BBModel
            bbmodel_path = tmpdir / "model.bbmodel"
            result.save(str(bbmodel_path))
            assert bbmodel_path.exists()

            # Save as GLB (requires Blender)
            try:
                glb_path = tmpdir / "model.glb"
                result.save(str(glb_path))
                assert glb_path.exists()
                assert glb_path.stat().st_size > 0
                print(f"\n✓ Exported to all formats (including GLB)")
            except Exception as e:
                print(f"\n✓ Exported to py/json/bbmodel (GLB export failed: {e})")

    def test_session_stats(self):
        """Test session statistics tracking"""
        bs = Blocksmith(default_model=DEFAULT_TEST_MODEL)

        # Reset stats
        bs.reset_stats()
        initial_stats = bs.get_stats()
        assert initial_stats["call_count"] == 0
        assert initial_stats["total_tokens"] == 0

        # Make two generations
        bs.generate("a cube")
        bs.generate("a sphere")

        # Check stats
        final_stats = bs.get_stats()
        assert final_stats["call_count"] == 2
        assert final_stats["total_tokens"] > 0
        assert final_stats["avg_tokens_per_call"] > 0

        print(f"\n✓ Session stats after 2 generations:")
        print(f"  Total tokens: {final_stats['total_tokens']}")
        print(f"  Avg tokens/call: {final_stats['avg_tokens_per_call']:.1f}")
        if final_stats.get("total_cost"):
            print(f"  Total cost: ${final_stats['total_cost']:.4f}")


class TestErrorHandling:
    """Test error handling with real API"""

    def test_missing_image_file_error(self):
        """Test that missing image file raises clear error"""
        bs = Blocksmith(default_model=DEFAULT_TEST_MODEL)

        with pytest.raises(FileNotFoundError) as exc_info:
            bs.generate("test", image="nonexistent_file.jpg")

        assert "nonexistent_file.jpg" in str(exc_info.value)
        print(f"\n✓ Missing image error handled correctly")

    def test_invalid_save_format_error(self):
        """Test that invalid save format raises clear error"""
        bs = Blocksmith(default_model=DEFAULT_TEST_MODEL)
        result = bs.generate("a cube")

        with pytest.raises(ValueError) as exc_info:
            result.save("model.invalid_extension")

        assert "Supported" in str(exc_info.value)
        print(f"\n✓ Invalid format error handled correctly")
