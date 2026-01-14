# BlockSmith Examples

This directory contains example scripts showing how to use BlockSmith.

## Setup

Make sure you have BlockSmith installed and your API key set:

```bash
pip install blocksmith
```

**Set your API key:**

**Option 1: direnv (Recommended)** - See [main README](../README.md#2-set-up-api-key) for setup

**Option 2: Manual export**
```bash
export GEMINI_API_KEY="your-key-here"
```

## Running Examples

### Quick Start

Basic usage showing simple model generation:

```bash
python quickstart.py
```

Generates:
- `output/cube.glb` - A simple red cube
- `output/tree.glb` - A blocky tree
- `output/house.glb` - A small house

### Advanced

Shows accessing intermediate formats and saving multiple file types:

```bash
python advanced.py
```

Generates spaceship in multiple formats:
- `output/spaceship.glb` - Binary GLB
- `output/spaceship.gltf` - GLTF JSON
- `output/spaceship.json` - BlockJSON schema
- `output/spaceship.py` - Python DSL

## Output Directory

Examples save files to `output/` directory. Create it if needed:

```bash
mkdir -p output
```

## Viewing Models

View GLB/GLTF files using:
- [gltf-viewer](https://gltf-viewer.donmccurdy.com/)
- Blender (File > Import > GLTF 2.0)
- [Three.js Editor](https://threejs.org/editor/)
- Any game engine that supports GLTF

## Tips

- Start with simple prompts and iterate
- Be specific about details you want
- Mention "blocky" or "voxel" style if needed
- Check the Python DSL to understand the structure
