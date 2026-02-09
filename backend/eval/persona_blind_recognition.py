"""
Persona Blind Recognition

Transcript-only recognizability scoring:
- Given candidate persona fingerprints and transcript samples,
  predict which persona authored each transcript.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from pydantic import BaseModel, Field

# Add backend directory to path
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)


class PersonaFingerprint(BaseModel):
    persona_id: str
    display_name: str
    signature_keywords: List[str] = Field(default_factory=list)
    banned_phrases: List[str] = Field(default_factory=list)
    structure_preference: str = "paragraph"  # paragraph|bullets
    target_words_min: int = 20
    target_words_max: int = 120
    question_style: str = "medium"  # low|medium|high


class TranscriptSample(BaseModel):
    transcript_id: str
    persona_id: str
    text: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RecognitionDataset(BaseModel):
    version: str = "v1"
    personas: List[PersonaFingerprint] = Field(default_factory=list)
    transcripts: List[TranscriptSample] = Field(default_factory=list)


def _word_count(text: str) -> int:
    return len((text or "").split())


def _bullet_ratio(text: str) -> float:
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    if not lines:
        return 0.0
    bullets = sum(1 for line in lines if line.startswith("- ") or line.startswith("* "))
    return bullets / len(lines)


def _question_count(text: str) -> int:
    return (text or "").count("?")


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _contains_any(text: str, phrases: Sequence[str]) -> int:
    lower = (text or "").lower()
    count = 0
    for phrase in phrases:
        p = str(phrase or "").strip().lower()
        if p and p in lower:
            count += 1
    return count


def _score_transcript_for_persona(
    *,
    transcript: TranscriptSample,
    persona: PersonaFingerprint,
) -> float:
    text = transcript.text or ""
    words = _word_count(text)

    keyword_hits = _contains_any(text, persona.signature_keywords)
    keyword_score = (keyword_hits / len(persona.signature_keywords)) if persona.signature_keywords else 0.5

    banned_hits = _contains_any(text, persona.banned_phrases)
    banned_penalty = 0.20 if banned_hits > 0 else 0.0

    if persona.structure_preference == "bullets":
        format_score = 1.0 if _bullet_ratio(text) >= 0.35 else 0.2
    else:
        format_score = 1.0 if _bullet_ratio(text) < 0.35 else 0.2

    if words < persona.target_words_min:
        length_score = _clamp(words / max(1, persona.target_words_min))
    elif words > persona.target_words_max:
        overflow = words - persona.target_words_max
        window = max(10, persona.target_words_max - persona.target_words_min)
        length_score = _clamp(1.0 - (overflow / window))
    else:
        length_score = 1.0

    q_count = _question_count(text)
    if persona.question_style == "low":
        question_score = 1.0 if q_count == 0 else 0.5 if q_count == 1 else 0.2
    elif persona.question_style == "high":
        question_score = 1.0 if q_count >= 1 else 0.2
    else:
        question_score = 1.0 if q_count <= 1 else 0.6

    score = (
        (0.50 * keyword_score)
        + (0.20 * format_score)
        + (0.20 * length_score)
        + (0.10 * question_score)
        - banned_penalty
    )
    return round(_clamp(score), 6)


def evaluate_blind_recognition(
    *,
    personas: Sequence[PersonaFingerprint],
    transcripts: Sequence[TranscriptSample],
    min_accuracy: float = 0.80,
) -> Dict[str, Any]:
    if not personas:
        raise ValueError("At least one persona fingerprint is required")
    if not transcripts:
        raise ValueError("At least one transcript sample is required")

    results: List[Dict[str, Any]] = []
    correct = 0
    confusion: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for transcript in transcripts:
        candidates = [
            {
                "persona_id": persona.persona_id,
                "score": _score_transcript_for_persona(transcript=transcript, persona=persona),
            }
            for persona in personas
        ]
        ranked = sorted(candidates, key=lambda item: item["score"], reverse=True)
        predicted = ranked[0]["persona_id"]
        is_correct = predicted == transcript.persona_id
        if is_correct:
            correct += 1

        confusion[transcript.persona_id][predicted] += 1
        results.append(
            {
                "transcript_id": transcript.transcript_id,
                "actual_persona_id": transcript.persona_id,
                "predicted_persona_id": predicted,
                "correct": is_correct,
                "scores": ranked,
            }
        )

    total = len(transcripts)
    accuracy = round(correct / total, 6)
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total": total,
        "correct": correct,
        "accuracy": accuracy,
        "min_accuracy": min_accuracy,
        "passed": accuracy >= min_accuracy,
        "confusion_matrix": {actual: dict(predictions) for actual, predictions in confusion.items()},
        "results": results,
    }


def _load_dataset(path: str) -> RecognitionDataset:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return RecognitionDataset.model_validate(raw)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Persona blind recognition evaluator")
    parser.add_argument("--dataset", required=True, type=str, help="JSON with personas + transcripts")
    parser.add_argument("--output", type=str, default=None, help="Optional output JSON path")
    parser.add_argument("--min-accuracy", type=float, default=0.80)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    dataset = _load_dataset(args.dataset)
    summary = evaluate_blind_recognition(
        personas=dataset.personas,
        transcripts=dataset.transcripts,
        min_accuracy=args.min_accuracy,
    )
    output = json.dumps(summary, indent=2)
    print(output)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(output, encoding="utf-8")
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

