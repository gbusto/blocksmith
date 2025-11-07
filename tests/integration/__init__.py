"""
Integration tests that make real API calls.

These tests:
- Require valid API keys (GEMINI_API_KEY or OPENAI_API_KEY)
- Make real LLM API calls (cost real money)
- Are excluded from CI/CD
- Should be run locally before commits/pushes

Run with:
    pytest tests/integration/ -v
"""
