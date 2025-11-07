"""
Core BlockSmith client API

Provides the main Blocksmith class for generating models and the GenerationResult
class for handling conversions and saving.
"""

import json
import os
from typing import Optional, Literal

from blocksmith.generator.engine import ModelGenerator
from blocksmith.converters import import_python, export_glb, export_gltf, export_bbmodel


class GenerationResult:
    """
    Represents a generated model with lazy format conversions.

    This class provides access to the model in different formats:
    - dsl: Python DSL source code
    - json: BlockJSON schema

    Conversions are performed lazily and cached for efficiency.
    """

    def __init__(self, dsl: str, blocksmith_instance: "Blocksmith"):
        """
        Initialize a generation result.

        Args:
            dsl: Python DSL source code for the model
            blocksmith_instance: Parent Blocksmith instance for conversions
        """
        self._dsl = dsl
        self._bs = blocksmith_instance
        self._json = None

    @property
    def dsl(self) -> str:
        """Python DSL source code"""
        return self._dsl

    @property
    def json(self) -> dict:
        """
        BlockJSON JSON schema (converted on first access)

        Returns:
            dict: Model in BlockJSON schema format
        """
        if self._json is None:
            self._json = self._bs._dsl_to_json(self._dsl)
        return self._json

    def save(self, path: str, filetype: Optional[str] = None) -> None:
        """
        Save model to file with automatic format detection.

        Args:
            path: Output file path
            filetype: File format ('py', 'json', 'bbmodel', 'gltf', 'glb').
                     If None, inferred from file extension.
                     Note: GLTF/GLB export requires Blender installed.

        Examples:
            >>> result.save("model.glb")      # Requires Blender
            >>> result.save("model.bbmodel")  # Blockbench format
            >>> result.save("model.json")     # BlockJSON format
            >>> result.save("model.py")       # Python DSL
        """
        if filetype is None:
            filetype = self._infer_filetype(path)

        if filetype == "py":
            with open(path, 'w') as f:
                f.write(self.dsl)
        elif filetype == "json":
            with open(path, 'w') as f:
                json.dump(self.json, f, indent=2)
        elif filetype == "bbmodel":
            # Export BBModel (Blockbench format)
            bbmodel_str = self._bs._json_to_bbmodel(self.json)
            with open(path, 'w') as f:
                f.write(bbmodel_str)
        elif filetype == "gltf":
            # Export GLTF via Blender (returns string)
            gltf_str = self._bs._json_to_gltf(self.json)
            with open(path, 'w') as f:
                f.write(gltf_str)
        elif filetype == "glb":
            # Export GLB via Blender (returns bytes)
            glb_bytes = self._bs._json_to_glb(self.json)
            with open(path, 'wb') as f:
                f.write(glb_bytes)
        else:
            raise ValueError(f"Unsupported filetype: {filetype}")

    @staticmethod
    def _infer_filetype(path: str) -> str:
        """Infer file type from extension"""
        ext = path.split('.')[-1].lower()
        if ext in ['glb', 'gltf', 'bbmodel', 'json', 'py']:
            return ext
        raise ValueError(
            f"Cannot infer filetype from extension: {ext}. "
            f"Supported: .glb, .gltf, .bbmodel, .json, .py"
        )


class Blocksmith:
    """
    Main BlockSmith client for generating voxel/block models from text prompts.

    Examples:
        Basic usage:
        >>> bs = Blocksmith()
        >>> bs.generate("a red cube").save("cube.glb")

        Access intermediate formats:
        >>> result = bs.generate("a tree")
        >>> print(result.dsl)   # Python DSL
        >>> print(result.json)  # BlockJSON schema

        Multiple saves from one generation:
        >>> result.save("model.glb")
        >>> result.save("model.json")
    """

    def __init__(self, default_model: str = "gemini/gemini-2.5-pro"):
        """
        Initialize BlockSmith client.

        Args:
            default_model: Default LLM model to use for generation
                          API keys read from environment (GEMINI_API_KEY or OPENAI_API_KEY)
        """
        self.default_model = default_model
        self.generator = ModelGenerator(model=default_model)

    def generate(
        self,
        prompt: str,
        model: Optional[str] = None
    ) -> GenerationResult:
        """
        Generate a block model from a text prompt.

        Args:
            prompt: Text description of the model to generate
            model: LLM model to use (overrides default_model if provided)

        Returns:
            GenerationResult: Object with model in various formats

        Examples:
            >>> bs = Blocksmith()
            >>> result = bs.generate("a medieval castle")
            >>> result.save("castle.glb")
        """
        model_name = model or self.default_model
        dsl = self.generator.generate(prompt, model=model_name)
        return GenerationResult(dsl, self)

    def _dsl_to_json(self, dsl: str) -> dict:
        """Convert Python DSL to BlockJSON schema"""
        return import_python(dsl)

    def _json_to_glb(self, json_schema: dict) -> bytes:
        """Convert BlockJSON schema to GLB format (via Blender)"""
        return export_glb(json_schema)

    def _json_to_bbmodel(self, json_schema: dict) -> str:
        """Convert BlockJSON schema to BBModel format (Blockbench)"""
        return export_bbmodel(json_schema)

    def _json_to_gltf(self, json_schema: dict) -> str:
        """Convert BlockJSON schema to GLTF format (via Blender)"""
        return export_gltf(json_schema)

