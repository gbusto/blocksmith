"""
Core model generation engine

Simplified generator that uses LiteLLM to generate Python DSL code for block models.
This is a streamlined version without expert routing - just clean, simple generation.
"""

import logging
import re
from typing import Optional
from dataclasses import dataclass
from blocksmith.generator.prompts import SYSTEM_PROMPT
from blocksmith.llm import LLMClient, LLMResponse, TokenUsage

logger = logging.getLogger(__name__)


@dataclass
class GenerationResponse:
    """Response from model generation with usage metadata"""
    code: str                   # Generated Python DSL code
    tokens: TokenUsage          # Token usage
    cost: Optional[float]       # Cost in USD (None for local models)
    model: str                  # Model used


class ModelGenerator:
    """
    Generates Python DSL code for block models using LLMs.

    This is a simplified generator that uses a single system prompt and
    generates clean Python code using the BlockSmith modeling API.
    """

    def __init__(self, model: str = "gemini/gemini-3-pro-preview"):
        """
        Initialize the model generator.

        Args:
            model: LLM model to use (default: gemini/gemini-3-pro-preview)
                   API keys read from environment (GEMINI_API_KEY or OPENAI_API_KEY)
        """
        self.model_name = model

        # Initialize LLM client
        self.client = LLMClient(
            model=model,
            temperature=0.7,
            max_tokens=25000,
        )

        logger.info(f"Generator initialized with model: {model}")

    def _extract_code(self, response_text: str) -> str:
        """
        Extract Python code from LLM response.

        Handles responses that may be wrapped in markdown code blocks
        or contain extra text/explanations.

        Args:
            response_text: Raw text from LLM

        Returns:
            Extracted Python code
        """
        # Check for markdown code blocks
        code_block_pattern = r"```(?:python)?\n(.*?)```"
        matches = re.findall(code_block_pattern, response_text, re.DOTALL)

        if matches:
            # Return the first code block found
            return matches[0].strip()

        # If no code blocks, assume entire response is code
        return response_text.strip()

    def generate(self, prompt: str, model: Optional[str] = None, image: Optional[str] = None) -> GenerationResponse:
        """
        Generate Python DSL code from a text prompt with optional image.

        Args:
            prompt: Text description of the model to generate
            model: Override the default model (optional)
            image: Optional image path or URL for multimodal generation
                   Supports local files (.jpg, .png, etc) or HTTP/HTTPS URLs

        Returns:
            GenerationResponse with code, tokens, cost, and model info

        Examples:
            >>> generator = ModelGenerator()
            >>> response = generator.generate("a cube")
            >>> print(response.code)

            >>> # With image
            >>> response = generator.generate("turn this into blocks", image="photo.jpg")
        """
        logger.info(f"Generating model for prompt: {prompt[:100]}...")
        if image:
            logger.info(f"Using image: {image}")

        # Build user content (text + optional image)
        user_prompt_text = f"""# User Request
{prompt}

# Instructions
Generate clean Python code that creates the requested model using the helpers provided above.
Return ONLY the Python code without any markdown formatting, explanations, or extra text."""

        user_content = LLMClient._build_multimodal_content(user_prompt_text, image)

        # Build messages for LLM
        messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": user_content
            }
        ]

        # Use different client if model override specified
        if model:
            temp_client = LLMClient(
                model=model,
                temperature=0.7,
                max_tokens=25000,
            )
            llm_response = temp_client.complete(messages)
            model_used = model
        else:
            llm_response = self.client.complete(messages)
            model_used = self.model_name

        # Extract Python code from response
        python_code = self._extract_code(llm_response.content)

        # Basic validation
        if not python_code or len(python_code.strip()) < 20:
            raise ValueError("Generated code is too short or empty")

        # Log token usage and cost
        logger.info(
            f"Successfully generated {len(python_code)} characters of Python code. "
            f"Tokens: {llm_response.tokens.total_tokens}, "
            f"Cost: ${llm_response.cost:.4f}" if llm_response.cost else f"Tokens: {llm_response.tokens.total_tokens}"
        )

        return GenerationResponse(
            code=python_code,
            tokens=llm_response.tokens,
            cost=llm_response.cost,
            model=model_used
        )

    def get_stats(self):
        """
        Get session statistics (total tokens, cost, call count).

        Returns:
            Dict with session statistics
        """
        return self.client.get_stats()

    def reset_stats(self):
        """Reset session statistics"""
        self.client.reset_stats()
