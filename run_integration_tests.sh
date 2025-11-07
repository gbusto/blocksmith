#!/bin/bash

# Integration test runner for BlockSmith
# These tests make real API calls and cost real money!

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}  BlockSmith Integration Tests${NC}"
echo -e "${YELLOW}  ⚠️  WARNING: Makes real API calls (costs money!)${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo

# Check for API keys
if [ -z "$GEMINI_API_KEY" ] && [ -z "$OPENAI_API_KEY" ]; then
    echo -e "${RED}❌ Error: No API key found${NC}"
    echo
    echo "Set an API key before running integration tests:"
    echo "  export GEMINI_API_KEY=\"your-key-here\""
    echo "  OR"
    echo "  export OPENAI_API_KEY=\"your-key-here\""
    echo
    echo "Or source your .env file:"
    echo "  source .env"
    exit 1
fi

# Check which key is set
if [ -n "$GEMINI_API_KEY" ]; then
    echo -e "${GREEN}✓ Using GEMINI_API_KEY${NC}"
fi
if [ -n "$OPENAI_API_KEY" ]; then
    echo -e "${GREEN}✓ Using OPENAI_API_KEY${NC}"
fi

echo
echo -e "${YELLOW}Running integration tests...${NC}"
echo

# Run tests
.venv/bin/python -m pytest tests/integration/ -v -s "$@"

# Show summary
if [ $? -eq 0 ]; then
    echo
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}  ✓ All integration tests passed!${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
else
    echo
    echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${RED}  ❌ Some integration tests failed${NC}"
    echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    exit 1
fi
