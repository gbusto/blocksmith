"""System prompts for model generation"""

import os
from pathlib import Path

# Load system prompt from markdown file
_prompt_path = Path(__file__).parent / "SYSTEM_PROMPT.md"
with open(_prompt_path, 'r') as f:
    SYSTEM_PROMPT = f.read()
