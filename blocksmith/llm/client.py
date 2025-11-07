"""Generic LLM client supporting any provider via LiteLLM"""

from dataclasses import dataclass
from typing import Optional, Dict, Any, List
import litellm
import logging

from .exceptions import LLMAPIError, LLMServiceError, LLMTimeoutError

logger = logging.getLogger(__name__)


@dataclass
class TokenUsage:
    """Token usage for a single LLM call"""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass
class LLMResponse:
    """Structured response from any LLM provider"""
    content: str
    model: str
    tokens: TokenUsage
    cost: Optional[float]  # None for local models
    raw_response: Any  # Full litellm response for advanced use


class LLMClient:
    """
    Generic LLM client supporting any provider via LiteLLM.

    Supports:
    - Remote APIs: OpenAI, Gemini, Claude, Cohere, etc
    - Local models: Ollama, LlamaCpp, GGUF files

    Features:
    - Automatic token tracking
    - Cost estimation (when available)
    - Session statistics
    - Robust error handling with retries

    Example:
        >>> client = LLMClient("gemini/gemini-2.5-pro", temperature=0.7)
        >>> response = client.complete([
        ...     {"role": "user", "content": "Hello!"}
        ... ])
        >>> print(f"Cost: ${response.cost:.4f}, Tokens: {response.tokens.total_tokens}")
    """

    def __init__(
        self,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **litellm_kwargs
    ):
        """
        Initialize LLM client.

        Args:
            model: Model identifier (e.g., "gemini/gemini-2.5-pro", "ollama/llama3.2")
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens in response
            **litellm_kwargs: Additional args passed to litellm.completion()
        """
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.litellm_kwargs = litellm_kwargs

        # Session tracking
        self._total_tokens = 0
        self._total_cost = 0.0
        self._call_count = 0

        logger.info(f"Initialized LLMClient with model: {model}")

    def complete(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        num_retries: int = 3,
        **override_kwargs
    ) -> LLMResponse:
        """
        Send completion request to LLM.

        Args:
            messages: List of message dicts with 'role' and 'content'
                      Example: [{"role": "user", "content": "Hello"}]
            temperature: Override default temperature
            max_tokens: Override default max_tokens
            num_retries: Number of retries on transient errors (default: 3)
            **override_kwargs: Override any litellm parameters

        Returns:
            LLMResponse with content, tokens, cost, etc.

        Raises:
            LLMAPIError: On API errors (rate limits, auth, etc)
            LLMTimeoutError: On timeout
            LLMServiceError: On provider service issues (503, etc)
        """
        # Build params
        params = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature or self.temperature,
            "max_tokens": max_tokens or self.max_tokens,
            "num_retries": num_retries,
            **self.litellm_kwargs,
            **override_kwargs
        }

        try:
            # Make call
            logger.debug(f"LLM call to {self.model}: {len(messages)} messages")
            response = litellm.completion(**params)

            # Extract data
            content = response.choices[0].message.content
            usage = response.usage

            # Token tracking
            tokens = TokenUsage(
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                total_tokens=usage.total_tokens
            )

            # Cost estimation (0 for local models)
            cost = None
            if not self._is_local_model():
                try:
                    cost = litellm.completion_cost(completion_response=response)
                except Exception as e:
                    logger.warning(f"Could not calculate cost: {e}")
                    cost = None

            # Update session stats
            self._total_tokens += tokens.total_tokens
            if cost is not None:
                self._total_cost += cost
            self._call_count += 1

            # Log
            cost_str = f"${cost:.4f}" if cost is not None else "N/A (local)"
            logger.info(
                f"LLM response: {tokens.total_tokens} tokens, "
                f"cost: {cost_str}"
            )

            return LLMResponse(
                content=content,
                model=self.model,
                tokens=tokens,
                cost=cost,
                raw_response=response
            )

        except litellm.exceptions.ServiceUnavailableError as e:
            logger.error(f"Service unavailable (503): {e}")
            raise LLMServiceError(f"Provider overloaded: {e}") from e

        except litellm.exceptions.Timeout as e:
            logger.error(f"Request timeout: {e}")
            raise LLMTimeoutError(f"Request timed out: {e}") from e

        except litellm.exceptions.RateLimitError as e:
            logger.error(f"Rate limit exceeded: {e}")
            raise LLMAPIError(f"Rate limit: {e}") from e

        except Exception as e:
            logger.error(f"LLM error: {e}")
            raise LLMAPIError(f"LLM call failed: {e}") from e

    def get_stats(self) -> Dict[str, Any]:
        """
        Get session statistics.

        Returns:
            Dict with total_tokens, total_cost, call_count, model, etc.
        """
        return {
            "model": self.model,
            "call_count": self._call_count,
            "total_tokens": self._total_tokens,
            "total_cost": self._total_cost if not self._is_local_model() else 0.0,
            "avg_tokens_per_call": (
                self._total_tokens / self._call_count if self._call_count > 0 else 0
            )
        }

    def reset_stats(self):
        """Reset session statistics"""
        self._total_tokens = 0
        self._total_cost = 0.0
        self._call_count = 0
        logger.debug("Session stats reset")

    def _is_local_model(self) -> bool:
        """Check if model is local (Ollama, LlamaCpp, etc)"""
        local_prefixes = ["ollama/", "ollama_chat/", "openai/localhost"]
        return any(self.model.startswith(prefix) for prefix in local_prefixes)
