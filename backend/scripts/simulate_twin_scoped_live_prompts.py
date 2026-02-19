import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.answerability import evaluate_answerability
from modules.observability import supabase
from modules.retrieval import retrieve_context

PROMPTS = [
    "Summarize the twin in 3 bullets",
    "What does this twin optimize for in founders?",
    "Give me the top 3 red flags this twin would pass on",
    "How would a 30-minute office hours session go?",
    "Give feedback the way this twin would",
    "Would this twin like a B2B payroll SaaS?",
]


def _root_doc_from_section(section_path: str) -> str:
    normalized = str(section_path or "").strip()
    if not normalized or normalized.lower() == "unknown":
        return "unknown"
    return normalized.split("/", 1)[0].strip() or "unknown"


def _find_twin_by_source_name(
    required_tokens: List[str],
    *,
    limit: int = 1000,
) -> Tuple[Optional[str], Optional[str]]:
    try:
        rows = (
            supabase.table("sources")
            .select("twin_id,filename")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
            .data
            or []
        )
    except Exception as e:
        print(f"[simulate] Failed to query sources: {e}")
        return None, None

    lower_tokens = [tok.lower() for tok in required_tokens]
    for row in rows:
        filename = str((row or {}).get("filename") or "").strip()
        twin_id = str((row or {}).get("twin_id") or "").strip()
        if not filename or not twin_id:
            continue
        lowered = filename.lower()
        if all(token in lowered for token in lower_tokens):
            return twin_id, filename
    return None, None


async def _run_prompt_for_twin(twin_id: str, prompt: str) -> Dict[str, Any]:
    contexts = await retrieve_context(prompt, twin_id, top_k=6)
    answerability = await evaluate_answerability(prompt, contexts)
    state = str(answerability.get("answerability") or "insufficient").strip().lower()
    planner_action = "answer" if state in {"direct", "derivable"} else "clarify"

    sections: List[str] = []
    doc_names: List[str] = []
    pages: List[int] = []
    for row in contexts:
        if not isinstance(row, dict):
            continue
        section = str(row.get("section_path") or row.get("section_title") or "unknown").strip() or "unknown"
        if section not in sections:
            sections.append(section)

        doc_name = str(row.get("doc_name") or "").strip()
        if not doc_name:
            doc_name = _root_doc_from_section(section)
        if doc_name not in doc_names:
            doc_names.append(doc_name)

        page_number = row.get("page_number")
        if isinstance(page_number, int) and page_number not in pages:
            pages.append(page_number)
        elif isinstance(page_number, str) and page_number.strip().isdigit():
            as_int = int(page_number.strip())
            if as_int not in pages:
                pages.append(as_int)

    return {
        "prompt": prompt,
        "chunk_count": len(contexts),
        "doc_names": doc_names,
        "pages": sorted(pages),
        "sections": sections,
        "evaluator_state": state,
        "planner_action": planner_action,
    }


async def main() -> None:
    load_dotenv()

    sham_twin_id, sham_source = _find_twin_by_source_name(["sham", "knowledge", "base"])
    sai_twin_id, sai_source = _find_twin_by_source_name(["sai_twin.docx"])

    if not sham_twin_id or not sai_twin_id:
        raise RuntimeError(
            "Unable to resolve Sham/Sai twin IDs from sources table. "
            f"Resolved: sham={sham_twin_id} ({sham_source}), sai={sai_twin_id} ({sai_source})"
        )

    output: Dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "twins": [
            {"label": "sham", "twin_id": sham_twin_id, "matched_source": sham_source},
            {"label": "sai", "twin_id": sai_twin_id, "matched_source": sai_source},
        ],
        "results": [],
    }

    for twin in output["twins"]:
        label = str(twin["label"])
        twin_id = str(twin["twin_id"])
        for prompt in PROMPTS:
            row = await _run_prompt_for_twin(twin_id, prompt)
            row["twin_label"] = label
            row["twin_id"] = twin_id
            output["results"].append(row)
            sections_preview = ", ".join(row["sections"][:2]) if row["sections"] else "none"
            print(
                f"[simulate] twin={label} prompt={prompt[:42]!r} "
                f"chunks={row['chunk_count']} state={row['evaluator_state']} "
                f"docs={row['doc_names'][:2]} sections={sections_preview}"
            )

    out_path = os.path.join("tmp", "live_prompt_eval_twin_scoped.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fp:
        json.dump(output, fp, indent=2)
    print(f"[simulate] wrote {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
