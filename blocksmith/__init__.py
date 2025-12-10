"""
BlockSmith - Generate voxel/block-based 3D models from text prompts using AI

A minimal, powerful Python library for generating block-style 3D models
that are perfect for games, voxel art, and procedural content.
"""

from blocksmith.client import Blocksmith, GenerationResult
from blocksmith.converters.convert import convert

__version__ = "0.0.1"
__all__ = ["Blocksmith", "GenerationResult", "convert"]
