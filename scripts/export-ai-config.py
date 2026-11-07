#!/usr/bin/env python3
"""Export the AI prompts, schemas, and limits from cube-mvp/server.py to worker/ai-config.json.

server.py is the single source of truth. The Cloudflare Worker reads the exported JSON, so
both back ends send the model identical prompts. Run this after editing a prompt or schema:

    python3 scripts/export-ai-config.py

tests/worker_parity_test.py fails if the JSON falls out of sync with server.py.
"""
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "worker" / "ai-config.json"


def build():
    for key in ("GEMINI_TEXT_MODEL", "GEMINI_VISION_MODEL"):
        os.environ.pop(key, None)
    sys.path.insert(0, str(ROOT / "cube-mvp"))
    import server  # noqa: E402

    return {
        "_note": "Generated from cube-mvp/server.py by scripts/export-ai-config.py. Do not edit by hand.",
        "text_model": server.TEXT_MODEL,
        "vision_model": server.VISION_MODEL,
        "idea_system_prompt": server.IDEA_SYSTEM_PROMPT,
        "steps_system_prompt": server.STEPS_SYSTEM_PROMPT,
        "sources_system_prompt": server.SOURCES_SYSTEM_PROMPT,
        "identify_system_prompt": server.IDENTIFY_SYSTEM_PROMPT,
        "plausibility": server.PLAUSIBILITY,
        "idea_schema": server.api_schema(server.IDEA_SCHEMA),
        "steps_schema": server.api_schema(server.STEPS_SCHEMA),
        "sources_schema": server.api_schema(server.SOURCES_SCHEMA),
        "identify_schema": server.api_schema(server.IDENTIFY_SCHEMA),
        "limits": {
            "min_ideas": server.MIN_IDEAS,
            "max_ideas": server.MAX_IDEAS,
            "max_recipes": server.MAX_RECIPES,
            "max_final": server.MAX_FINAL,
            "max_qty": server.MAX_QTY,
            "max_body_bytes": server.MAX_BODY_BYTES,
            "max_image_b64_chars": server.MAX_IMAGE_B64_CHARS,
            "allowed_image_types": sorted(server.ALLOWED_IMAGE_TYPES),
        },
    }


def render():
    return json.dumps(build(), indent=2, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    OUT.write_text(render())
    print(f"Wrote {OUT.relative_to(ROOT)}")
