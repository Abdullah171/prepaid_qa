import json
import json_repair
import re
from typing import Any

def _first_balanced_object(text: str) -> str:
    start = text.find("{")
    if start < 0:
        raise ValueError(f"No JSON object found in LLM response: {text[:200]!r}")

    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]

    raise ValueError("Unterminated JSON object in LLM response.")

def extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        stripped = fenced.group(1).strip()

    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        try:
            parsed = json.loads(_first_balanced_object(stripped))
        except ValueError:
            parsed = json_repair.loads(stripped)

    if not isinstance(parsed, dict):
        raise ValueError("Expected a JSON object from the LLM.")
    return parsed

try:
    extract_json_object("```json\n[{\"a\": 1}]\n```")
except Exception as e:
    print("Test 1 error:", repr(e))

try:
    extract_json_object("Here is the JSON: ```json\n{\"a\": 1}\n```")
except Exception as e:
    print("Test 2 error:", repr(e))
