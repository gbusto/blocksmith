"""
Test BlockSmith client with mocked LLM responses
"""
import pytest
import os
import tempfile
from unittest.mock import Mock, patch
from blocksmith import Blocksmith, GenerationResult


# Sample DSL that will be returned by mocked LLM
MOCK_DSL_OUTPUT = """
def create_model():
    return [
        cuboid("cube", [0, 0, 0], [1, 1, 1])
    ]
"""


class TestBlocksmithClient:
    """Test Blocksmith client initialization and basic flow"""

    def test_client_initializes_with_defaults(self):
        """Test that Blocksmith initializes with default model"""
        bs = Blocksmith()
        assert bs.default_model == "gemini/gemini-2.5-pro"

    def test_client_accepts_custom_model(self):
        """Test that custom model can be specified"""
        bs = Blocksmith(default_model="gemini/gemini-2.0-flash")
        assert bs.default_model == "gemini/gemini-2.0-flash"

    @patch('blocksmith.llm.client.litellm.completion')
    def test_generate_returns_result(self, mock_completion):
        """Test that generate() returns a GenerationResult"""
        # Mock the LiteLLM response
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content=MOCK_DSL_OUTPUT))]
        mock_response.usage = Mock(prompt_tokens=10, completion_tokens=20, total_tokens=30)
        mock_completion.return_value = mock_response

        bs = Blocksmith()
        result = bs.generate("a cube")

        assert isinstance(result, GenerationResult)
        # Compare stripped versions (engine strips the code output)
        assert result.dsl.strip() == MOCK_DSL_OUTPUT.strip()

    @patch('blocksmith.llm.client.litellm.completion')
    def test_result_has_to_json_method(self, mock_completion):
        """Test that GenerationResult can explicitly convert DSL to JSON"""
        # Mock the LiteLLM response
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content=MOCK_DSL_OUTPUT))]
        mock_response.usage = Mock(prompt_tokens=10, completion_tokens=20, total_tokens=30)
        mock_completion.return_value = mock_response

        bs = Blocksmith()
        result = bs.generate("a cube")

        # Test usage metadata
        assert result.tokens.total_tokens == 30
        assert result.tokens.prompt_tokens == 10
        assert result.tokens.completion_tokens == 20
        assert result.model == "gemini/gemini-2.5-pro"

        # Explicitly convert to JSON
        json_data = result.to_json()
        assert "entities" in json_data
        assert len(json_data["entities"]) == 1

    @patch('blocksmith.llm.client.litellm.completion')
    def test_result_saves_to_file(self, mock_completion):
        """Test that GenerationResult.save() creates files"""
        # Mock the LiteLLM response
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content=MOCK_DSL_OUTPUT))]
        mock_response.usage = Mock(prompt_tokens=10, completion_tokens=20, total_tokens=30)
        mock_completion.return_value = mock_response

        bs = Blocksmith()
        result = bs.generate("a cube")

        with tempfile.TemporaryDirectory() as tmpdir:
            # Test Python DSL save
            py_path = os.path.join(tmpdir, "cube.py")
            result.save(py_path)
            assert os.path.exists(py_path)

            # Test JSON save
            json_path = os.path.join(tmpdir, "cube.json")
            result.save(json_path)
            assert os.path.exists(json_path)

            # Test BBModel save
            bbmodel_path = os.path.join(tmpdir, "cube.bbmodel")
            result.save(bbmodel_path)
            assert os.path.exists(bbmodel_path)

    def test_missing_api_key_gives_clear_error(self):
        """Test that missing API key gives a clear error message"""
        # Clear environment variables
        env_backup = {}
        for key in ['GEMINI_API_KEY', 'OPENAI_API_KEY']:
            if key in os.environ:
                env_backup[key] = os.environ[key]
                del os.environ[key]

        try:
            # LiteLLM should raise an error when no API key is found
            with pytest.raises(Exception) as exc_info:
                bs = Blocksmith()
                bs.generate("a cube")

            # Error should mention API key
            error_msg = str(exc_info.value).lower()
            assert "api" in error_msg or "key" in error_msg or "gemini" in error_msg

        finally:
            # Restore environment
            for key, value in env_backup.items():
                os.environ[key] = value

    def test_invalid_filetype_raises_error(self):
        """Test that invalid file extension raises clear error"""
        from blocksmith.llm.client import TokenUsage

        bs = Blocksmith()

        # Create a mock result
        result = GenerationResult(
            dsl=MOCK_DSL_OUTPUT,
            tokens=TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
            cost=0.001,
            model="test-model",
            _bs=bs
        )

        with pytest.raises(ValueError) as exc_info:
            result.save("model.invalid")

        assert "Supported" in str(exc_info.value)
        assert ".glb" in str(exc_info.value)
