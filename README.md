# BlockSmith

[![Tests](https://github.com/gbusto/blocksmith/actions/workflows/tests.yml/badge.svg)](https://github.com/gbusto/blocksmith/actions/workflows/tests.yml)

**Generate block-based 3D models from text prompts using AI **

BlockSmith is a powerful Python library for generating block-style 3D models that are perfect for games, art, and procedural content.

## Features

- 🎨 **Text-to-3D**: Generate block models from simple text descriptions
- 🧱 **True Block Geometry**: Perfect cube geometry, not just "blocky-looking" models
- 🚀 **Lightweight**: Minimal dependencies, optimized for performance
- 🔄 **Multiple Formats**: Export to GLB, GLTF, BBModel (Blockbench), JSON, or Python DSL
- 🤖 **Agent-Friendly**: Clean API perfect for AI coding assistants
- 🎮 **Game-Ready**: Optimized for engines like Hytopia, Minecraft mods, and more

## Installation

> **Note:** This is an alpha release (v0.0.1). Not yet published to PyPI.

**Requirements:** Python 3.12+

### 1. Clone and Install

```bash
# Clone the repository
git clone https://github.com/gbusto/blocksmith.git
cd blocksmith

# Create virtual environment
python3.12 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in editable mode
pip install -e .
```

### 2. Set Up API Key

BlockSmith uses **Gemini 2.5 Pro** by default (best quality for block models).

**Get a free API key:**
1. Visit [Google AI Studio](https://aistudio.google.com/apikey)
2. Click "Create API Key" in the top left and follow the instructions
3. Copy your key

If you need help with this, let me know. OR, just use OpenAI, or even a free and local model if you want.

**Set the environment variable:**

```bash
# macOS/Linux - Add to ~/.bashrc or ~/.zshrc
export GEMINI_API_KEY="your-key-here"

# Or set for current session only
export GEMINI_API_KEY="your-key-here"

# Windows (PowerShell)
$env:GEMINI_API_KEY="your-key-here"

# Windows (Command Prompt)
set GEMINI_API_KEY=your-key-here
```

**Verify it's set:**
```bash
echo $GEMINI_API_KEY  # Should print your key
```

### 3. Install Blender (Optional)

**Skip this if you only need BBModel, JSON, or Python DSL formats!**

BlockSmith uses Blender's GLTF exporter for GLB/GLTF output. Install if you need 3D game-ready formats.

I recommend installing it straight from their site, and noting it's location on disk. OR, use one of the methods below to install it:

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

**Verify Blender is installed:**
```bash
blender --version  # Should print Blender version
```

If `blender` command not found, add Blender to your PATH or set `BLENDER_PATH`:
```bash
# macOS
export BLENDER_PATH="/Applications/Blender.app/Contents/MacOS/Blender"

# Linux (if not in PATH)
export BLENDER_PATH="/usr/bin/blender"
```

## Quick Start

```python
from blocksmith import Blocksmith

# Initialize (reads GEMINI_API_KEY from environment)
bs = Blocksmith()

# Generate a model
bs.generate("a medieval castle").save("castle.bbmodel")
```

**That's it!** You now have a 3D model ready to open in Blockbench.

## Usage

### Basic Generation

```python
from blocksmith import Blocksmith

bs = Blocksmith()

# Generate and save directly
bs.generate("a red sports car").save("car.glb")

# Or access intermediate formats
result = bs.generate("a tree")
print(result.dsl)   # Python DSL code
print(result.json)  # BlockJSON schema
print(result.gltf)  # GLTF dict
```

### Save Multiple Formats

```python
result = bs.generate("a spaceship")

# Save in different formats from the same generation
result.save("spaceship.glb")      # Binary GLB (requires Blender)
result.save("spaceship.gltf")     # GLTF JSON (requires Blender)
result.save("spaceship.bbmodel")  # Blockbench format
result.save("spaceship.json")     # BlockJSON schema
result.save("spaceship.py")       # Python DSL source
```

### Using Different LLM Models

BlockSmith defaults to **Gemini 2.5 Pro** (best quality) but supports other models:

```python
# Use Gemini Flash (faster, cheaper)
bs = Blocksmith(default_model="gemini/gemini-2.5-flash")

# Use Gemini Flash (fastest, cheapest)
bs = Blocksmith(default_model="gemini/gemini-2.5-lite")

# Use OpenAI (requires OPENAI_API_KEY)
bs = Blocksmith(default_model="gpt-5")

# Or override per-generation
result = bs.generate("a tree", model="gemini/gemini-2.5-flash")
```

**Supported Providers:**
- **Gemini** (recommended): `gemini/gemini-2.5-pro`, `gemini/gemini-2.5-flash`
- **OpenAI**: `gpt-5`
- Any model supported by [LiteLLM](https://docs.litellm.ai/docs/providers)

## Examples

> **Note:** Texture generation is not yet implemented (coming in v0.2). Models are currently monochrome geometry.

### Start Simple

```python
bs = Blocksmith()

# Basic shapes
bs.generate("a simple cube").save("cube.glb")
bs.generate("a pyramid").save("pyramid.glb")
bs.generate("a sphere made of blocks").save("sphere.glb")
```

### Simple Objects

```python
# Tools and items
bs.generate("a hammer").save("hammer.glb")
bs.generate("a torch").save("torch.glb")
bs.generate("a tree").save("tree.glb")
bs.generate("a chest").save("chest.glb")
```

### Characters

```python
# Keep it simple for best results
bs.generate("a minecraft-style person").save("person.glb")
bs.generate("a simple blocky robot").save("robot.glb")
```

### Buildings

```python
# Simple structures work better
bs.generate("a small house").save("house.glb")
bs.generate("a tower").save("tower.glb")
```

## Troubleshooting

### "No API key found" Error

**Problem:** `Exception: No GEMINI_API_KEY found`

**Solution:**
1. Make sure you set the environment variable:
   ```bash
   export GEMINI_API_KEY="your-key-here"
   ```
2. Verify it's set:
   ```bash
   echo $GEMINI_API_KEY
   ```
3. Restart your terminal or Python session after setting it

### "blender: command not found"

**Problem:** GLB/GLTF export fails with Blender not found

**Solution:**
1. **Option 1:** Install Blender (see installation instructions above)
2. **Option 2:** Use BBModel format instead (no Blender needed):
   ```python
   result.save("model.bbmodel")  # Works without Blender!
   ```
3. **Option 3:** Set BLENDER_PATH manually:
   ```bash
   export BLENDER_PATH="/Applications/Blender.app/Contents/MacOS/Blender"
   ```

### Models Look Wrong or Broken

**Problem:** Generated models have gaps, overlapping parts, or strange geometry

**Solutions:**
1. **Try a more specific prompt:** Instead of "a car", try "a simple blocky race car with wheels"
2. **Regenerate:** LLMs are non-deterministic, try generating again
3. **Use Gemini 2.5 Pro:** It's the best model for block geometry
   ```python
   bs = Blocksmith(default_model="gemini/gemini-2.5-pro")
   ```

### Import Errors

**Problem:** `ModuleNotFoundError: No module named 'blocksmith'`

**Solution:**
1. Make sure you installed the package:
   ```bash
   pip install -e .
   ```
2. Check you're in the right Python environment:
   ```bash
   which python  # Should point to your .venv
   pip list | grep blocksmith  # Should show blocksmith
   ```

## API Reference

### `Blocksmith`

Main client for generating models.

```python
Blocksmith(default_model="gemini/gemini-2.5-pro")
```

**Parameters:**
- `default_model` (str): LLM model to use (default: "gemini/gemini-2.5-pro")

**Methods:**
- `generate(prompt: str, model: str = None) -> GenerationResult`
  - `prompt`: Text description of the model to generate
  - `model`: Override the default model for this generation

### `GenerationResult`

Result object with lazy format conversions.

**Properties:**
- `dsl: str` - Python DSL source code
- `json: dict` - BlockJSON JSON schema (converted on first access)

**Methods:**
- `save(path: str, filetype: str = None)` - Save to file
  - `path`: Output file path
  - `filetype`: Optional format override ('py', 'json', 'bbmodel', 'gltf', 'glb')

## How It Works

1. **LLM Generation**: Uses an LLM to generate clean Python DSL code
2. **Validation**: Validates the generated code and entities
3. **Conversion**: Converts to BlockJSON schema, then to GLTF
4. **Export**: Outputs in your desired format

## BlockJSON Schema

BlockSmith uses a central JSON schema (BlockJSON) that makes it easy to convert between formats:

```
Python DSL ←→ BlockJSON ←→ GLTF/GLB
                 ↕
           Other formats
      (bedrock, bbmodel, etc)
```

This design allows for:
- Clean, human-readable Python code generation
- Easy validation and manipulation
- Support for multiple output formats

## Limitations (v0.0.1)

This is an early release focused on model generation. Current limitations:

- ⚠️ **Requires Blender** for GLB/GLTF export only
- ❌ No texture generation yet (coming in v0.2)
- ❌ No animation support yet (coming in v0.3)
- ✅ Geometry generation works great!

## Roadmap

- [ ] Texture generation
- [ ] Animation support
- [ ] CLI tool (`blocksmith generate "a castle" -o castle.glb`)
- [ ] Blockbench plugin
- [ ] Web UI

## Contact

Feel free to email me at blocksmithai.app @ gmail[.]com, or [reach out on X](https://x.com/gabebusto)

## Contributing

Contributions welcome! This is an early-stage project.

## License

MIT License - see [LICENSE](LICENSE) for details

## Links

- [GitHub](https://github.com/gbusto/blocksmith)
- [Documentation](https://github.com/gbusto/blocksmith#readme)
- [Issues](https://github.com/gbusto/blocksmith/issues)

---

**Made with ❤️ by Gabriel Busto**

Generate anything you can imagine, one block at a time.
