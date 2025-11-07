"""
Core model generation engine

Simplified generator that uses DSPy to generate Python DSL code for block models.
This is a streamlined version without expert routing - just clean, simple generation.
"""

import dspy
import logging
from typing import Optional
from blocksmith.generator.prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# Disable DSPy disk cache for simplicity
dspy.configure_cache(enable_disk_cache=False)


class PythonCodeGenerator(dspy.Signature):
    """Generate Python code for 3D block model creation"""
    user_prompt: str = dspy.InputField(desc="User's prompt describing the model to create")
    code: str = dspy.OutputField(desc="Clean Python code without markdown formatting or extra text")


class ModelGenerator:
    """
    Generates Python DSL code for block models using LLMs.

    This is a simplified generator that uses a single system prompt and
    generates clean Python code using the BlockSmith modeling API.
    """

    def __init__(self, model: str = "gemini/gemini-2.5-pro"):
        """
        Initialize the model generator.

        Args:
            model: LLM model to use (default: gemini/gemini-2.5-pro)
                   API keys read from environment (GEMINI_API_KEY or OPENAI_API_KEY)
        """
        self.model_name = model

        # Initialize DSPy LM (reads API keys from environment automatically)
        self.lm = dspy.LM(
            model=model,
            cache=False,
            temperature=0.7,
            max_tokens=25000,
        )

        # Create the generator
        with dspy.context(lm=self.lm):
            self.generator = dspy.ChainOfThought(PythonCodeGenerator)
            logger.info(f"Generator initialized with model: {model}")

    def generate(self, prompt: str, model: Optional[str] = None) -> str:
        """
        Generate Python DSL code from a text prompt.

        Args:
            prompt: Text description of the model to generate
            model: Override the default model (optional)

        Returns:
            Python DSL code as a string

        Examples:
            >>> generator = ModelGenerator()
            >>> code = generator.generate("a red cube")
            >>> print(code)
        """
        logger.info(f"Generating model for prompt: {prompt[:100]}...")

        # Combine system prompt with user request
        full_prompt = f"""{SYSTEM_PROMPT}

# User Request
{prompt}

# Instructions
Generate clean Python code that creates the requested model using the helpers provided above.
Return ONLY the Python code without any markdown formatting, explanations, or extra text.
"""

        # Use different model if specified
        if model:
            temp_lm = dspy.LM(
                model=model,
                cache=False,
                temperature=0.7,
                max_tokens=25000,
            )
            with dspy.context(lm=temp_lm):
                temp_generator = dspy.ChainOfThought(PythonCodeGenerator)
                result = temp_generator(user_prompt=full_prompt)
        else:
            with dspy.context(lm=self.lm):
                result = self.generator(user_prompt=full_prompt)

        python_code = result.code

        # Basic validation
        if not python_code or len(python_code.strip()) < 20:
            raise ValueError("Generated code is too short or empty")

        logger.info(f"Successfully generated {len(python_code)} characters of Python code")
        return python_code
