"""
Clarification Manager

Generates a single targeted clarification question and a memory write proposal
for Owner Memory gaps. Deterministic: no model calls.
"""

from typing import Dict, Any, List


def _default_options_for_type(memory_type: str, topic: str) -> List[Dict[str, Any]]:
    if memory_type == "stance":
        return [
            {
                "label": "Support",
                "stance": "positive",
                "intensity": 7,
                "value": f"I generally support {topic}."
            },
            {
                "label": "Oppose",
                "stance": "negative",
                "intensity": 7,
                "value": f"I generally oppose {topic}."
            },
            {
                "label": "Neutral / depends",
                "stance": "neutral",
                "intensity": 4,
                "value": f"My stance on {topic} depends on context."
            }
        ]
    if memory_type == "preference":
        return [
            {"label": "Prefer speed over depth", "value": f"I prefer speed over depth when it comes to {topic}."},
            {"label": "Prefer depth over speed", "value": f"I prefer depth over speed when it comes to {topic}."},
            {"label": "No strong preference", "value": f"I don't have a strong preference about {topic}."}
        ]
    if memory_type == "lens":
        return [
            {"label": "Pragmatic ROI lens", "value": f"I view {topic} through a pragmatic ROI lens."},
            {"label": "Ethics/values-first lens", "value": f"I evaluate {topic} through an ethics-first lens."},
            {"label": "Long-term risk lens", "value": f"I prioritize long-term risk when assessing {topic}."}
        ]
    if memory_type == "tone_rule":
        return [
            {"label": "Direct and concise", "value": f"When discussing {topic}, be direct and concise."},
            {"label": "Warm and explanatory", "value": f"When discussing {topic}, be warm and explanatory."},
            {"label": "Analytical and cautious", "value": f"When discussing {topic}, be analytical and cautious."}
        ]
    # belief (default)
    return [
        {"label": "Core belief (one sentence)", "value": f"My core belief about {topic} is: [fill in one sentence]."},
        {"label": "Skeptical by default", "value": f"I'm generally skeptical about {topic} until proven otherwise."},
        {"label": "Optimistic by default", "value": f"I'm generally optimistic about {topic}."}
    ]


def build_clarification(
    query: str,
    topic: str,
    memory_type: str
) -> Dict[str, Any]:
    topic = topic or "this topic"
    memory_type = memory_type or "stance"

    if memory_type == "stance":
        question = f"What's your stance on {topic}? Choose one (or answer in one sentence)."
    elif memory_type == "preference":
        question = f"What's your preference regarding {topic}? Choose one (or answer in one sentence)."
    elif memory_type == "lens":
        question = f"What lens should guide decisions about {topic}? Choose one (or answer in one sentence)."
    elif memory_type == "tone_rule":
        question = f"How should your twin talk about {topic}? Choose one (or answer in one sentence)."
    else:
        question = f"What core belief do you hold about {topic}? One sentence is enough."

    options = _default_options_for_type(memory_type, topic)

    memory_write_proposal = {
        "topic": topic,
        "memory_type": memory_type,
        "value_template": options[0]["value"] if options else "",
        "confidence": 0.7,
        "source": "owner_clarification"
    }

    return {
        "question": question,
        "options": options,
        "memory_write_proposal": memory_write_proposal
    }
