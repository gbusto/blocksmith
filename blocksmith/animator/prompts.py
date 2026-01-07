"""System prompts for animation generation"""

import os
from pathlib import Path

# Load system prompt from markdown file
_prompt_path = Path(__file__).parent / "SYSTEM_PROMPT.md"
with open(_prompt_path, 'r') as f:
    ANIMATION_SYSTEM_PROMPT = f.read()
