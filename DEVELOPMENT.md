# Development Guide

Quick guide for testing BlockSmith locally before it's published to PyPI.

## Quick Start (Using uv - Recommended)

**uv** is much faster than pip/venv. Install it first:

```bash
# Install uv (Rust-based, super fast)
curl -LsSf https://astral.sh/uv/install.sh | sh
# or: brew install uv
```

Then install and test:

```bash
# Navigate to the project directory
cd blocksmith

# Create venv and install in editable mode (one command!)
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e .

# Set your API key
export GEMINI_API_KEY="your-key-here"

# Test it!
python examples/quickstart.py
```

## Alternative: Standard pip/venv

If you prefer the standard Python workflow:

```bash
cd blocksmith

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in editable mode
pip install -e .

# Set API key
export GEMINI_API_KEY="your-key-here"

# Test
python examples/quickstart.py
```

## Install Blender

BlockSmith requires Blender for GLTF/GLB export:

**macOS:**
```bash
brew install --cask blender
```

**Linux:**
```bash
sudo apt install blender  # Ubuntu/Debian
```

**Windows:**
Download from [blender.org/download](https://www.blender.org/download/)

**Verify Blender is in PATH:**
```bash
blender --version
```

**Custom Blender Path (if not in PATH):**

If Blender isn't in your PATH, set the `BLENDER_PATH` environment variable:

```bash
# macOS
export BLENDER_PATH="/Applications/Blender.app/Contents/MacOS/blender"

# Linux
export BLENDER_PATH="/usr/bin/blender"

# Windows
set BLENDER_PATH="C:\Program Files\Blender Foundation\Blender\blender.exe"
```

## Quick Test

```python
# test.py
from blocksmith import Blocksmith

bs = Blocksmith()
result = bs.generate("a simple red cube")

# Test without Blender
result.save("cube.py")     # Python DSL
result.save("cube.json")   # BlockJSON

# Test with Blender
result.save("cube.glb")    # Requires Blender
print("✅ All tests passed!")
```

Run it:
```bash
python test.py
```

## Running Tests

BlockSmith has a comprehensive test suite for validating converters and UV mapping.

**Run the full suite:**
```bash
pytest
```

**Run specific UV roundtrip verification (Critical for Converters):**
This test verifies that models can be converted between formats (V3 -> GLTF -> BBModel -> V3) without losing UV data or orientation.

```bash
python3 tests/test_uv_roundtrip.py
```


## Project Structure

```
blocksmith/
├── blocksmith/              # Main package
│   ├── __init__.py
│   ├── client.py            # Blocksmith + GenerationResult
│   ├── generator/           # LLM-based generation
│   ├── schema/              # BlockJSON schema
│   └── converters/          # Format converters
├── examples/                # Example scripts
├── pyproject.toml           # Package config
└── README.md                # User docs
```

## Troubleshooting

### "No API key found"
Set your LLM API key:
```bash
export GEMINI_API_KEY="your-key"
# or
export OPENAI_API_KEY="your-key"
```

### "blender: command not found"
Blender needs to be in your PATH. After installing:
- **macOS**: It's usually at `/Applications/Blender.app/Contents/MacOS/blender`
- **Linux**: Should be in PATH after `apt install`
- **Windows**: Add Blender install dir to PATH

### Import errors
Make sure you're in the venv:
```bash
which python  # Should show .venv/bin/python or venv/bin/python
```

If not, activate it:
```bash
source .venv/bin/activate  # or venv/bin/activate
```

## Next Steps

Once you've tested locally:
1. Push to GitHub
2. Publish to PyPI (`uv build && uv publish`)
3. Update README to remove development instructions
