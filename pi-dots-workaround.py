#!/usr/bin/env python3
"""Inject <dots_function_call> workaround into Pi interactive-mode.js.

Detects OpenRouter's malformed <dots_...> XML-style tool call syntax that appears
in reasoning/thinking, and injects a synthetic error response so the agent
continues rather than hanging waiting for a JSON tool call response.
"""
import sys, re

TARGET = "/Users/billie/.nvm/versions/node/v22.22.3/lib/node_modules/@earendil-works/pi-coding-agent/dist/modes/interactive/interactive-mode.js"

with open(TARGET, "r") as f:
    lines = f.readlines()

# Find the exact insertion point: "for (const content of this.streamingMessage.content) {"
insert_idx = None
for i, line in enumerate(lines):
    if 'for (const content of this.streamingMessage.content)' in line:
        insert_idx = i
        break

if insert_idx is None:
    print("ERROR: anchor not found", file=sys.stderr)
    sys.exit(1)

# Workaround: before processing any content item, check if it looks like
# <dots_...> XML syntax (OpenRouter malpractice). If so, emit a synthetic
# tool-call-rejected event so the model gets an error response and continues.
patch = """\
                    // WORKAROUND: detect <dots_function_call> XML syntax from OpenRouter
                    // and inject synthetic error so the agent doesn't hang waiting for JSON.
                    // This pattern appears in thinking/reasoning when OpenRouter malforms tool calls.
                    if (
                        typeof content === 'object' && content !== null &&
                        (content.type === 'text' || content.type === undefined) &&
                        typeof content.text === 'string' && /<dots[_>]/.test(content.text)
                    ) {
                        // Inject a synthetic tool result so the model sees an error and continues.
                        // The content is OpenRouter's malformed dots XML, not a real tool call.
                        this.chatContainer.addText({
                            role: 'system',
                            content: '[Pi workaround] Detected <dots_function_call> XML syntax in model output (OpenRouter bug). Skipping malformed tool call. Use standard JSON tool_call format.'
                        });
                        continue;
                    }
"""

lines.insert(insert_idx, patch + "\n")

with open(TARGET, "w") as f:
    f.writelines(lines)

print(f"Patched {TARGET} at line {insert_idx+1}: <dots_function_call> workaround injected.")
