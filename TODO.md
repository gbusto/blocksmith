# BlockSmith v0.1 TODO List

Improvements for alpha release before sharing publicly.

## 1. Better Error Handling ✅ **COMPLETE**

**Goal:** Improve user-facing error messages and disable automatic retries.

**Changes:**
- Set default `num_retries=0` in `LLMClient` (fail fast, let user decide)
- Add friendly, generic error messages for common API errors:
  - `429`: "Rate limit exceeded - you'll need to wait before trying again. Please review your plan with your AI provider."
  - `503`: "The AI service is temporarily unavailable. Please try again in a moment."
  - `403`: "Permission denied - please check your API key and permissions with your AI provider."
  - `401`: "Invalid API key - please check your GEMINI_API_KEY or OPENAI_API_KEY environment variable."
- Keep technical details in logs but show user-friendly messages

**Files to modify:**
- `blocksmith/llm/client.py`
- `blocksmith/llm/exceptions.py` (possibly add more specific exceptions)

---

## 2. Update API - Remove Lazy Loading, Add Usage Info ✅ **COMPLETE**

**Goal:** Make API more explicit and return generation metadata.

**Current State:**
```python
result = bs.generate("a cube")
result.dsl       # Python DSL string
result.json      # LAZY LOADED - confusing!
result.save()    # Saves to file
```

**New API:**
```python
@dataclass
class GenerationResult:
    dsl: str                    # Python DSL code
    tokens: TokenUsage          # Token usage (prompt/completion/total)
    cost: Optional[float]       # Cost in USD (None for local models)
    model: str                  # Model used

    def to_json(self) -> dict:
        """Explicitly convert DSL to BlockJSON"""
        return convert_python_to_json(self.dsl)

    def save(self, path: str, filetype: str = None):
        """Save to file"""
        ...
```

**Usage:**
```python
result = bs.generate("a cube")
print(result.dsl)      # Python code
print(result.tokens)   # TokenUsage(prompt=100, completion=50, total=150)
print(result.cost)     # 0.0023 or None

# Explicit conversion
block_json = result.to_json()

# Save still works
result.save("cube.glb")
```

**Session stats:**
```python
result1 = bs.generate("a cube")
result2 = bs.generate("a tree")

stats = bs.get_stats()
# {
#   "model": "gemini/gemini-2.5-pro",
#   "call_count": 2,
#   "total_tokens": 350,
#   "total_cost": 0.0056,
#   "avg_tokens_per_call": 175
# }
```

**Files to modify:**
- `blocksmith/client.py` (GenerationResult class)
- `blocksmith/generator/engine.py` (return tokens/cost/model)
- Update all tests that use `.json` property

---

## 3. Conversion API ✅ **COMPLETE**

**Goal:** Easy format conversion without regenerating models.

**API:**
```python
from blocksmith import convert

# Module-level converter
convert("input.glb", "output.bbmodel")
convert("cube.bbmodel", "cube.json")

# Or on Blocksmith instance
bs = Blocksmith()
bs.convert("input.glb", "output.bbmodel")
```

**Implementation:**
- Create `blocksmith/convert.py` with `convert(input_path, output_path)` function
- Auto-detect input format from extension
- Auto-detect output format from extension
- Use existing converters under the hood

**Files to create/modify:**
- `blocksmith/convert.py` (new)
- `blocksmith/__init__.py` (export `convert`)
- Add tests in `tests/test_convert.py`

---

## 4. Image Support (Multimodal Generation) ✅ **COMPLETE**

**Goal:** Allow users to provide reference images for generation.

**API:**
```python
# Local image
result = bs.generate("turn this into blocks", image="./photo.jpg")

# Remote image (HTTP/HTTPS)
result = bs.generate("make this blocky", image="https://example.com/car.jpg")
```

**Implementation:**
- Update `LLMClient.complete()` to handle multimodal messages
- Support local file paths (read and encode as base64)
- Support HTTP/HTTPS URLs (pass URL directly to LLM)
- Update message format to include image content
- Test with Gemini (supports vision) and handle non-vision models gracefully

**Files modified:**
- `blocksmith/llm/client.py` (added image message support with base64 encoding and URL support)
- `blocksmith/generator/engine.py` (accepts image parameter)
- `blocksmith/client.py` (exposes image parameter in generate())
- `tests/test_client.py` (removed all mocks, integration tests run locally)

---

## 5. CLI Support

**Goal:** Command-line interface for easy usage.

**Commands:**
```bash
# Generate models
blocksmith generate "a castle" -o castle.glb
blocksmith generate "a tree" -o tree.bbmodel --model gemini-flash
blocksmith generate "blocky car" -o car.glb --image photo.jpg

# Convert between formats
blocksmith convert input.glb output.bbmodel

# View stats (optional)
blocksmith generate "a cube" -o cube.glb --verbose  # Show token/cost info
```

**Implementation:**
- Use `click` or `argparse` for CLI
- Create `blocksmith/cli.py` with commands
- Add entry point in `pyproject.toml`:
  ```toml
  [project.scripts]
  blocksmith = "blocksmith.cli:main"
  ```
- Handle API keys from environment
- Pretty print errors and stats
- Progress indicators for long operations?

**Files to create/modify:**
- `blocksmith/cli.py` (new)
- `pyproject.toml` (add scripts entry point)
- `README.md` (update with CLI examples)
- Add integration tests

---

## 6. Visualization (MAYBE - Nice to Have)

**Goal:** Easy way to preview generated models.

**Options considered:**
- Open browser with embedded glTF viewer
- Launch Blockbench if installed
- ASCII art in terminal (too complex for voxels)

**API:**
```python
result = bs.generate("a castle")
result.visualize()  # Opens browser to glTF viewer
result.visualize(method="blockbench")  # Launch Blockbench
```

**Status:** Lower priority, maybe skip for v0.1

---

## 7. Benchmarks (Future)

Create benchmark suite to test model quality across different:
- Model providers (Gemini, OpenAI, Claude)
- Model sizes (pro, flash, lite)
- Prompt styles
- Model complexity

---

## Notes

- This is for v0.1 alpha before public sharing
- Delete this file once all items are complete
- Keep commits small and focused
- Update tests for each change
- Update README with new features
