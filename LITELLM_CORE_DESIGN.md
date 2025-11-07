  Design: Generic LLM Client

  Architecture

  blocksmith/
  ├── llm/
  │   ├── __init__.py          # Exports: LLMClient, LLMResponse, TokenUsage
  │   ├── client.py            # Main LLMClient class
  │   └── exceptions.py        # Custom exceptions

  Core Classes

  # blocksmith/llm/client.py

  from dataclasses import dataclass
  from typing import Optional, Dict, Any, List
  import litellm
  import logging

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
              from .exceptions import LLMServiceError
              logger.error(f"Service unavailable (503): {e}")
              raise LLMServiceError(f"Provider overloaded: {e}") from e

          except litellm.exceptions.Timeout as e:
              from .exceptions import LLMTimeoutError
              logger.error(f"Request timeout: {e}")
              raise LLMTimeoutError(f"Request timed out: {e}") from e

          except litellm.exceptions.RateLimitError as e:
              from .exceptions import LLMAPIError
              logger.error(f"Rate limit exceeded: {e}")
              raise LLMAPIError(f"Rate limit: {e}") from e

          except Exception as e:
              from .exceptions import LLMAPIError
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

  # blocksmith/llm/exceptions.py

  class LLMError(Exception):
      """Base exception for LLM errors"""
      pass

  class LLMAPIError(LLMError):
      """API errors (auth, rate limits, invalid requests)"""
      pass

  class LLMServiceError(LLMError):
      """Provider service errors (503, downtime)"""
      pass

  class LLMTimeoutError(LLMError):
      """Request timeout"""
      pass

  # blocksmith/llm/__init__.py

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

  ---
  Usage Examples

  Basic Usage

  from blocksmith.llm import LLMClient

  # Remote API
  client = LLMClient("gemini/gemini-2.5-pro", temperature=0.7)
  response = client.complete([
      {"role": "user", "content": "Write a function to reverse a string"}
  ])

  print(response.content)
  print(f"Tokens: {response.tokens.total_tokens}")
  print(f"Cost: ${response.cost:.4f}")

  Local Model

  # Ollama
  client = LLMClient("ollama/llama3.2", temperature=0.7)
  response = client.complete([...])
  print(f"Cost: {response.cost}")  # None for local

  Session Tracking

  client = LLMClient("gemini/gemini-2.5-pro")

  # Make multiple calls
  for prompt in prompts:
      response = client.complete([{"role": "user", "content": prompt}])
      print(response.content)

  # Get totals
  stats = client.get_stats()
  print(f"Total cost: ${stats['total_cost']:.2f}")
  print(f"Total tokens: {stats['total_tokens']}")
  print(f"Average tokens/call: {stats['avg_tokens_per_call']:.0f}")

  Error Handling

  from blocksmith.llm import LLMClient, LLMServiceError, LLMAPIError

  client = LLMClient("gemini/gemini-2.5-pro")

  try:
      response = client.complete([...])
  except LLMServiceError as e:
      print(f"Provider overloaded: {e}")
      # Maybe switch to different model or retry later
  except LLMAPIError as e:
      print(f"API error: {e}")
      # Check API key, rate limits, etc

  In Your Model Generator

  # blocksmith/generator/engine.py

  from blocksmith.llm import LLMClient

  class ModelGenerator:
      def __init__(self, model: str = "gemini/gemini-2.5-pro"):
          self.llm = LLMClient(model, temperature=0.7, max_tokens=25000)

      def generate(self, prompt: str) -> str:
          messages = [
              {"role": "system", "content": SYSTEM_PROMPT},
              {"role": "user", "content": prompt}
          ]

          response = self.llm.complete(messages)

          # Parse response.content for code extraction
          code = self._extract_code(response.content)

          # User can see stats
          print(f"Generation used {response.tokens.total_tokens} tokens")
          if response.cost:
              print(f"Cost: ${response.cost:.4f}")

          return code

  ---
  Benefits of This Design

  ✅ Generic - Not tied to 3D model generation
  ✅ Clean API - Simple, intuitive methods
  ✅ Provider Agnostic - Works with 100+ providers + local
  ✅ Token Tracking - Always visible
  ✅ Cost Estimation - Automatic when available
  ✅ Robust Errors - Clear exception hierarchy
  ✅ Session Stats - Track usage across multiple calls
  ✅ Future Ready - Easy to add streaming, images, etc
  ✅ Well Documented - Docstrings for everything
  ✅ Testable - Easy to mock for unit tests

  Future Extensions (Not Implementing Now)

  # Easy to add later:

  # 1. Streaming
  def stream(self, messages: List[Dict]) -> Iterator[str]:
      response = litellm.completion(..., stream=True)
      for chunk in response:
          yield chunk.choices[0].delta.content

  # 2. Images (multimodal)
  def complete_with_image(self, text: str, image_url: str) -> LLMResponse:
      messages = [{
          "role": "user",
          "content": [
              {"type": "text", "text": text},
              {"type": "image_url", "image_url": {"url": image_url}}
          ]
      }]
      return self.complete(messages)

  # 3. Function calling
  def complete_with_tools(self, messages, tools: List[Dict]) -> LLMResponse:
      return self.complete(messages, tools=tools)

  ---
  Does this design make sense? Want me to implement it in the actual codebase?
