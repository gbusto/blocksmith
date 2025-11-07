"""Generic LLM client module supporting any provider via LiteLLM

This module provides a clean, unified interface for LLM interactions with:
- Support for remote APIs (OpenAI, Gemini, Claude, etc) and local models (Ollama)
- Automatic token tracking and cost estimation
- Session statistics
- Robust error handling with retries

Example:
    >>> from blocksmith.llm import LLMClient
    >>> client = LLMClient("gemini/gemini-2.5-pro", temperature=0.7)
    >>> response = client.complete([
    ...     {"role": "user", "content": "Hello!"}
    ... ])
    >>> print(f"Cost: ${response.cost:.4f}, Tokens: {response.tokens.total_tokens}")
"""

from .client import LLMClient, LLMResponse, TokenUsage
from .exceptions import LLMError, LLMAPIError, LLMServiceError, LLMTimeoutError

__all__ = [
    "LLMClient",
    "LLMResponse",
    "TokenUsage",
    "LLMError",
    "LLMAPIError",
    "LLMServiceError",
    "LLMTimeoutError",
]
