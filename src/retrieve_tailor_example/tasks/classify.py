"""Classification prompts and logic."""

import json
import time
from pathlib import Path

from retrieve_tailor_example.agent import Agent

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


def classify_all_papers(
    md_dir: str | Path,
    agent: Agent,
    output_path: str | Path = "ignore_me/real_world_papers.json",
    delay: float = 0.2,
) -> list[dict]:
    """Classify all papers in md_dir and save results to JSON."""
    md_dir = Path(md_dir)
    output_path = Path(output_path)
    md_files = sorted(md_dir.glob("*.md"))

    print(f"Found {len(md_files)} .md files in {md_dir}/\n")

    results: list[dict] = []
    for i, md_path in enumerate(md_files, 1):
        print(f"[{i}/{len(md_files)}] {md_path.name}...", end=" ", flush=True)
        try:
            text = md_path.read_text(encoding="utf-8")
            result = classify_paper(text, agent)
            result["file"] = md_path.name
            tag = "YES" if result["is_real_world_application"] else "no"
            print(f"{tag} — {result['reason']}")
            results.append(result)
        except Exception as e:
            print(f"ERROR: {e}")
            results.append(
                {
                    "file": md_path.name,
                    "is_real_world_application": False,
                    "reason": f"error: {e}",
                }
            )

        if i < len(md_files):
            time.sleep(delay)

    output_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    real_world = [r for r in results if r["is_real_world_application"]]
    print(f"\n{'=' * 60}")
    print(f"Total papers: {len(results)}")
    print(f"Real-world application papers: {len(real_world)}")
    print(f"\nResults saved to {output_path}")
    print("\nReal-world application papers:")
    for r in real_world:
        print(f"  - {r['file']}: {r['reason']}")

    return results
