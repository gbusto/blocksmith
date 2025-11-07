# Integration Tests

⚠️ **WARNING**: These tests make real API calls and cost real money!

## Requirements

- Valid API key in environment:
  ```bash
  export GEMINI_API_KEY="your-key-here"
  # OR
  export OPENAI_API_KEY="your-key-here"
  ```
- Internet connection
- Blender installed (for GLB export tests)

## Running Integration Tests

```bash
# Run all integration tests
pytest tests/integration/ -v -s

# Run specific test file
pytest tests/integration/test_generation.py -v -s

# Run specific test
pytest tests/integration/test_generation.py::TestBasicGeneration::test_simple_generation -v -s
```

## What Gets Tested

- ✅ Basic model generation with real LLM
- ✅ Custom model selection
- ✅ DSL to JSON conversion
- ✅ Image support (local files)
- ✅ Image support (remote URLs)
- ✅ Full pipeline (generate → save → convert)
- ✅ Session statistics tracking
- ✅ Error handling

## Git Hooks (Optional)

You can set up a pre-push hook to run integration tests before pushing:

```bash
# Create .git/hooks/pre-push
cat > .git/hooks/pre-push << 'EOF'
#!/bin/bash
echo "Running integration tests..."
pytest tests/integration/ -v --tb=short
if [ $? -ne 0 ]; then
    echo "Integration tests failed. Push aborted."
    exit 1
fi
EOF

chmod +x .git/hooks/pre-push
```

## Cost Considerations

Each test makes 1-2 API calls. With Gemini 2.5 Pro:
- ~1000-2000 tokens per generation
- ~$0.001-0.003 per test
- Full suite: ~$0.02-0.05

Use `gemini/gemini-2.0-flash-exp` for cheaper testing (10x less expensive).

## CI/CD

Integration tests are **excluded from CI** by default. They only run when explicitly called locally.
