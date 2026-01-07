"""
Core BlockSmith client API

Provides the main Blocksmith class for generating models and the GenerationResult
class for handling conversions and saving.
"""

import json
import os
from typing import Optional, Literal
from dataclasses import dataclass

from blocksmith.generator.engine import ModelGenerator
from blocksmith.converters import import_python, export_glb, export_gltf, export_bbmodel
from blocksmith.llm.client import TokenUsage
from blocksmith.generator.prompts import ANIMATION_SYSTEM_PROMPT


@dataclass
class GenerationResult:
    """
    Represents a generated model with usage metadata.

    Attributes:
        dsl: Python DSL source code
        tokens: Token usage (prompt/completion/total)
        cost: Generation cost in USD (None for local models)
        model: Model used for generation
    """
    dsl: str
    tokens: TokenUsage
    cost: Optional[float]
    model: str
    _bs: "Blocksmith" = None  # Private reference to parent instance

    def to_json(self) -> dict:
        """
        Explicitly convert Python DSL to BlockJSON schema.

        Returns:
            dict: Model in BlockJSON schema format

        Example:
            >>> result = bs.generate("a cube")
            >>> block_json = result.to_json()
            >>> print(block_json["entities"])
        """
        return self._bs._dsl_to_json(self.dsl)

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
            block_json = self.to_json()
            with open(path, 'w') as f:
                json.dump(block_json, f, indent=2)
        elif filetype == "bbmodel":
            # Export BBModel (Blockbench format)
            block_json = self.to_json()
            bbmodel_str = self._bs._json_to_bbmodel(block_json)
            with open(path, 'w') as f:
                f.write(bbmodel_str)
        elif filetype == "gltf":
            # Export GLTF via Blender (returns string)
            block_json = self.to_json()
            gltf_str = self._bs._json_to_gltf(block_json)
            with open(path, 'w') as f:
                f.write(gltf_str)
        elif filetype == "glb":
            # Export GLB via Blender (returns bytes)
            block_json = self.to_json()
            glb_bytes = self._bs._json_to_glb(block_json)
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
        model: Optional[str] = None,
        image: Optional[str] = None
    ) -> GenerationResult:
        """
        Generate a block model from a text prompt with optional reference image.

        Args:
            prompt: Text description of the model to generate
            model: LLM model to use (overrides default_model if provided)
            image: Optional reference image (local file path or HTTP/HTTPS URL)
                   Supports: .jpg, .jpeg, .png, .gif, .webp

        Returns:
            GenerationResult: Object with model, usage metadata, and save methods

        Examples:
            >>> bs = Blocksmith()
            >>> result = bs.generate("a medieval castle")
            >>> print(result.dsl)      # Python DSL code
            >>> print(result.tokens)   # Token usage
            >>> print(result.cost)     # Cost in USD
            >>> result.save("castle.glb")

            >>> # With reference image
            >>> result = bs.generate("turn this into blocks", image="photo.jpg")
            >>> result.save("model.glb")

            >>> # With remote image URL
            >>> result = bs.generate("blocky version", image="https://example.com/car.jpg")
        """
        # Pass model as-is (None or explicit value) so generator can use persistent client
        # when no model override is specified (needed for session stats tracking)
        gen_response = self.generator.generate(prompt, model=model, image=image)

        return GenerationResult(
            dsl=gen_response.code,
            tokens=gen_response.tokens,
            cost=gen_response.cost,
            model=gen_response.model,
            _bs=self
        )

    def animate(
        self,
        prompt: str,
        model_code: str,
        model: Optional[str] = None
    ) -> GenerationResult:
        """
        Generate animations for an existing model structure.

        Args:
            prompt: Description of the animation (e.g., "walk cycle")
            model_code: The Python source code of the existing model (defines IDs)
            model: Optional LLM model override

        Returns:
            GenerationResult: Contains the generated create_animations() code
        """
        # Construct specific prompt for animation
        # We embed the model code so the LLM knows the IDs
        full_prompt = f"""# Animation Request
{prompt}

# Existing Model Structure
Use the Group IDs defined in this code:
{model_code}
"""
        
        # Call generator with specific system prompt
        gen_response = self.generator.generate(
            prompt=full_prompt,
            model=model,
            system_prompt=ANIMATION_SYSTEM_PROMPT
        )
        
        return GenerationResult(
            dsl=gen_response.code,
            tokens=gen_response.tokens,
            cost=gen_response.cost,
            model=gen_response.model,
            _bs=self
        )

    def get_stats(self):
        """
        Get session statistics across all generations.

        Returns:
            Dict with total tokens, cost, call count, etc.

        Example:
            >>> bs = Blocksmith()
            >>> bs.generate("a cube")
            >>> bs.generate("a tree")
            >>> print(bs.get_stats())
            {'model': 'gemini/gemini-2.5-pro', 'call_count': 2, ...}
        """
        return self.generator.get_stats()

    def reset_stats(self):
        """Reset session statistics"""
        self.generator.reset_stats()

    def convert(self, input_path: str, output_path: str) -> None:
        """
        Convert a model from one format to another.

        Convenience method that wraps the module-level convert() function.
        Automatically detects formats from file extensions.

        Args:
            input_path: Path to input file
            output_path: Path to output file

        Example:
            >>> bs = Blocksmith()
            >>> bs.convert("model.glb", "model.bbmodel")
        """
        from blocksmith.converters.convert import convert
        convert(input_path, output_path)

    def _dsl_to_json(self, dsl: str) -> dict:
        """Convert Python DSL to BlockJSON schema"""
        # 1. Convert DSL to basic v3 JSON
        v3_json = import_python(dsl)
        
        if not v3_json:
            # Import failed, return empty or raise error?
            # Existing behavior of import_python is to return {} on error/log it.
            # We should probably pass it through or log a warning, but definitely not try to process it.
            return {}

        # 2. Generate Clay Atlas (Textures & UVs)
        # Ensure metadata exists
        if "meta" not in v3_json:
            v3_json["meta"] = {}
        
        v3_json["meta"]["texel_density"] = 16
        
        # Build the atlas (this modifies v3_json in place or returns new dict)
        # It generates the 'main' atlas and assigns UVs to all faces
        from blocksmith.texturing.clay_atlas import build_clay_atlas_with_compiler
        v3_json = build_clay_atlas_with_compiler(v3_json)

        # 3. Final Metadata Updates
        v3_json["meta"]["schema_version"] = "3.0"
        
        return v3_json

    def _json_to_glb(self, json_schema: dict) -> bytes:
        """Convert BlockJSON schema to GLB format (via Blender)"""
        return export_glb(json_schema)

    def _json_to_bbmodel(self, json_schema: dict) -> str:
        """Convert BlockJSON schema to BBModel format (Blockbench)"""
        return export_bbmodel(json_schema)

    def _json_to_gltf(self, json_schema: dict) -> str:
        """Convert BlockJSON schema to GLTF format (via Blender)"""
        return export_gltf(json_schema)

