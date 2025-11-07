"""
Tests for BlockSmith CLI

These tests verify the CLI command structure and error handling.
They do NOT make real API calls (use integration tests for that).
"""

import pytest
import tempfile
import json
from pathlib import Path
from click.testing import CliRunner
from blocksmith.cli import cli


class TestCLI:
    """Test CLI command structure and basic functionality"""

    def test_cli_help(self):
        """Test that CLI help works"""
        runner = CliRunner()
        result = runner.invoke(cli, ['--help'])
        assert result.exit_code == 0
        assert 'BlockSmith' in result.output
        assert 'generate' in result.output
        assert 'convert' in result.output

    def test_cli_version(self):
        """Test that version flag works"""
        runner = CliRunner()
        result = runner.invoke(cli, ['--version'])
        assert result.exit_code == 0

    def test_generate_help(self):
        """Test that generate command help works"""
        runner = CliRunner()
        result = runner.invoke(cli, ['generate', '--help'])
        assert result.exit_code == 0
        assert 'Generate a block model' in result.output
        assert '--output' in result.output
        assert '--model' in result.output
        assert '--image' in result.output
        assert '--verbose' in result.output

    def test_generate_missing_output(self):
        """Test that generate command requires output flag"""
        runner = CliRunner()
        result = runner.invoke(cli, ['generate', 'a cube'])
        assert result.exit_code != 0
        assert 'output' in result.output.lower() or 'required' in result.output.lower()

    def test_generate_missing_image_file(self):
        """Test that generate command handles missing image file"""
        runner = CliRunner()
        with tempfile.NamedTemporaryFile(suffix='.glb', delete=False) as f:
            output_path = f.name

        result = runner.invoke(cli, [
            'generate',
            'a cube',
            '-o', output_path,
            '--image', '/nonexistent/file.jpg'
        ])

        # Should exit with error
        assert result.exit_code != 0
        assert 'nonexistent' in result.output or 'not found' in result.output.lower()

        # Clean up
        Path(output_path).unlink(missing_ok=True)

    def test_convert_help(self):
        """Test that convert command help works"""
        runner = CliRunner()
        result = runner.invoke(cli, ['convert', '--help'])
        assert result.exit_code == 0
        assert 'Convert a model' in result.output
        assert 'INPUT_PATH' in result.output
        assert 'OUTPUT_PATH' in result.output

    def test_convert_missing_input(self):
        """Test that convert command handles missing input file"""
        runner = CliRunner()
        result = runner.invoke(cli, [
            'convert',
            '/nonexistent/input.glb',
            '/tmp/output.bbmodel'
        ])

        assert result.exit_code != 0
        assert 'not found' in result.output.lower() or 'nonexistent' in result.output

    def test_convert_works(self):
        """Test that convert command works with valid files"""
        from blocksmith.converters import import_python
        runner = CliRunner()

        # Create a valid v3 schema JSON file using our converter
        dsl = """
def create_model():
    return [
        cuboid("test_cube", [0, 0, 0], [1, 1, 1])
    ]
"""
        test_json = import_python(dsl)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(test_json, f)
            input_path = f.name

        output_path = input_path.replace('.json', '.bbmodel')

        # Run convert
        result = runner.invoke(cli, [
            'convert',
            input_path,
            output_path,
            '-v'
        ])

        # Should succeed
        if result.exit_code != 0:
            print(f"Exit code: {result.exit_code}")
            print(f"Output: {result.output}")
            if result.exception:
                print(f"Exception: {result.exception}")
        assert result.exit_code == 0
        assert 'Success' in result.output
        assert Path(output_path).exists()

        # Clean up
        Path(input_path).unlink(missing_ok=True)
        Path(output_path).unlink(missing_ok=True)

    def test_convert_verbose_flag(self):
        """Test that convert command accepts verbose flag"""
        runner = CliRunner()

        # Create minimal test file
        test_json = {"entities": []}
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(test_json, f)
            input_path = f.name

        output_path = input_path.replace('.json', '.bbmodel')

        result = runner.invoke(cli, [
            'convert',
            input_path,
            output_path,
            '--verbose'
        ])

        # Verbose flag should be accepted
        assert 'Converting:' in result.output or result.exit_code == 0

        # Clean up
        Path(input_path).unlink(missing_ok=True)
        Path(output_path).unlink(missing_ok=True)
