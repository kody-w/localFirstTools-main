#!/usr/bin/env python3
"""Debug script to test molt process."""

import sys
sys.path.insert(0, '/Users/kodyw/Projects/localFirstTools-main/scripts')

from pathlib import Path
from molt import build_molt_prompt, validate_molt_output
from copilot_utils import copilot_call, parse_llm_html, strip_copilot_wrapper

# Read the file
filepath = Path('/Users/kodyw/Projects/localFirstTools-main/apps/experimental-ai/self-aware-loading-screen.html')
html = filepath.read_text(encoding='utf-8')

print(f"File size: {len(html)} bytes")

# Build prompt
prompt = build_molt_prompt(html, 'self-aware-loading-screen.html', 1)
print(f"Prompt size: {len(prompt)} bytes")
print(f"Prompt preview (first 500 chars):\n{prompt[:500]}\n")

# Call Copilot
print("Calling Copilot CLI...")
raw_output = copilot_call(prompt, timeout=300)

print(f"\nRaw output type: {type(raw_output)}")
print(f"Raw output length: {len(raw_output) if raw_output else 0}")
if raw_output:
    print(f"Raw output preview (first 1000 chars):\n{raw_output[:1000]}\n")
    print(f"Raw output preview (last 500 chars):\n{raw_output[-500:]}\n")

    # Try stripping
    stripped = strip_copilot_wrapper(raw_output)
    print(f"\nStripped output length: {len(stripped)}")
    print(f"Stripped preview (first 500 chars):\n{stripped[:500]}\n")

    # Try parsing
    parsed = parse_llm_html(raw_output)
    print(f"\nParsed HTML length: {len(parsed) if parsed else 0}")
    if parsed:
        print(f"Parsed preview (first 500 chars):\n{parsed[:500]}\n")
else:
    print("Raw output is None or empty!")
