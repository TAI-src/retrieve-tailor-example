"""Classification prompts and logic."""

import json

from rich.console import Console

from retrieve_tailor_example.agent import Agent

console = Console()

CLASSIFICATION_PROMPT = """\
Is this paper primarily about a real-world application (e.g. engineering, \
healthcare, logistics, energy systems, software engineering on real codebases, \
etc.) as opposed to being purely theoretical, a benchmark study on synthetic \
problems, or a survey/editorial?

Respond with ONLY a JSON object in this exact format, no other text:
{"is_real_world_application": true, "reason": "short reason here"}
"""

SYSTEM_PROMPT = (
    "You are a research paper classifier. You classify papers as being about "
    "real-world applications or not. Respond only with the requested JSON."
)

# Only send the first N chars (title + abstract + intro is enough)
MAX_CHARS = 3000
# Skip files smaller than this (likely slides, posters, or empty)
MIN_CHARS = 5000


def classify_paper(text: str, agent: Agent) -> dict:
    """Classify a single paper. Returns dict with is_real_world_application and reason."""
    if len(text) < MIN_CHARS:
        return {
            "is_real_world_application": False,
            "reason": "skipped: too short (likely slides/poster)",
        }

    truncated = text[:MAX_CHARS]
    raw = agent.ask(
        truncated,
        CLASSIFICATION_PROMPT,
        system=SYSTEM_PROMPT,
        max_tokens=256,
    )

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start != -1 and end > start:
            result = json.loads(raw[start:end])
        else:
            result = {
                "is_real_world_application": False,
                "reason": f"parse error: {raw[:200]}",
            }

    return {
        "is_real_world_application": result["is_real_world_application"],
        "reason": result.get("reason", ""),
    }
