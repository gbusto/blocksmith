"""
Test BlockSmith client (non-API tests only)

Integration tests with real API calls should be in tests/integration/
"""
import pytest
import os
from blocksmith import Blocksmith, GenerationResult
from blocksmith.llm.client import TokenUsage


# Sample DSL for testing result operations
SAMPLE_DSL = """
def create_model():
    return [
        cuboid("cube", [0, 0, 0], [1, 1, 1])
    ]
"""


class TestBlocksmithClient:
    """Test Blocksmith client without API calls"""

    def test_client_initializes_with_defaults(self):
        """Test that Blocksmith initializes with default model"""
        bs = Blocksmith()
        assert bs.default_model == "gemini/gemini-2.5-pro"

    def test_client_accepts_custom_model(self):
        """Test that custom model can be specified"""
        bs = Blocksmith(default_model="gemini/gemini-2.0-flash")
        assert bs.default_model == "gemini/gemini-2.0-flash"

    def test_invalid_filetype_raises_error(self):
        """Test that invalid file extension raises clear error"""
        bs = Blocksmith()

        # Create a result object for testing
        result = GenerationResult(
            dsl=SAMPLE_DSL,
            tokens=TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
            cost=0.001,
            model="test-model",
            _bs=bs
        )

        with pytest.raises(ValueError) as exc_info:
            result.save("model.invalid")

        assert "Supported" in str(exc_info.value)
        assert ".glb" in str(exc_info.value)

    def test_stats_api_exists(self):
        """Test that get_stats() and reset_stats() methods exist"""
        bs = Blocksmith()

        # get_stats() should return a dict with expected keys
        stats = bs.get_stats()
        assert isinstance(stats, dict)
        assert "call_count" in stats
        assert "total_tokens" in stats
        assert "model" in stats
        assert stats["model"] == "gemini/gemini-2.5-pro"

        # reset_stats() should not raise an error
        bs.reset_stats()

        # After reset, call_count should still be accessible
        stats = bs.get_stats()
        assert "call_count" in stats

    def test_generate_with_missing_image_raises_error(self):
        """Test that missing image file raises clear error"""
        bs = Blocksmith()

        with pytest.raises(FileNotFoundError) as exc_info:
            bs.generate("test", image="nonexistent.jpg")

        assert "nonexistent.jpg" in str(exc_info.value)

    def test_result_to_json_works(self):
        """Test that GenerationResult.to_json() converts DSL properly"""
        bs = Blocksmith()

        result = GenerationResult(
            dsl=SAMPLE_DSL,
            tokens=TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
            cost=0.001,
            model="test-model",
            _bs=bs
        )

        # Should convert DSL to BlockJSON
        json_data = result.to_json()
        assert "entities" in json_data
        assert len(json_data["entities"]) == 1
        assert json_data["entities"][0]["id"] == "cube"
