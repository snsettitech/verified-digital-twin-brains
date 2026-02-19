"""
Load a persona config JSON into an existing twin.

Usage:
    python persona_configs/load_persona.py <twin_id> persona_configs/shambhavi_mishra.json

Updates the twin's settings with the system_prompt and metadata from the config.
Requires: SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables.
"""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from supabase import create_client


def load_persona(twin_id: str, config_path: str):
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
    if not url or not key:
        print("ERROR: Set SUPABASE_URL and SUPABASE_SERVICE_KEY in .env")
        sys.exit(1)

    sb = create_client(url, key)

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    settings = config.get("settings", {})

    # Fetch current twin
    twin_res = sb.table("twins").select("*").eq("id", twin_id).single().execute()
    if not twin_res.data:
        print(f"ERROR: Twin {twin_id} not found")
        sys.exit(1)

    twin = twin_res.data
    current_settings = twin.get("settings") or {}
    print(f"Found twin: {twin.get('name')} (id: {twin_id})")

    # Merge — persona config values take precedence
    merged_settings = {**current_settings, **settings}

    sb.table("twins").update({
        "settings": merged_settings,
        "description": config.get("description", twin.get("description")),
    }).eq("id", twin_id).execute()

    prompt_len = len(settings.get("system_prompt", ""))
    print(f"Done. Updated twin settings ({prompt_len} char system prompt).")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python persona_configs/load_persona.py <twin_id> <config.json>")
        sys.exit(1)

    load_persona(sys.argv[1], sys.argv[2])
