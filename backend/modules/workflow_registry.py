"""
Workflow registry for intent-driven execution.

This is intentionally deterministic and lightweight so routing decisions are
stable and auditable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional
import re


@dataclass(frozen=True)
class WorkflowSpec:
    name: str
    output_schema: str
    required_inputs: List[str]


WORKFLOW_REGISTRY: Dict[str, WorkflowSpec] = {
    "diagnose": WorkflowSpec(
        name="diagnose",
        output_schema="workflow.diagnose.v1",
        required_inputs=["problem_statement", "context"],
    ),
    "plan": WorkflowSpec(
        name="plan",
        output_schema="workflow.plan.v1",
        required_inputs=["objective", "constraints"],
    ),
    "critique": WorkflowSpec(
        name="critique",
        output_schema="workflow.critique.v1",
        required_inputs=["artifact"],
    ),
    "summarize": WorkflowSpec(
        name="summarize",
        output_schema="workflow.summarize.v1",
        required_inputs=["source_text"],
    ),
    "brainstorm": WorkflowSpec(
        name="brainstorm",
        output_schema="workflow.brainstorm.v1",
        required_inputs=["goal"],
    ),
    "evaluate": WorkflowSpec(
        name="evaluate",
        output_schema="workflow.evaluate.v1",
        required_inputs=["criteria", "options"],
    ),
    "write": WorkflowSpec(
        name="write",
        output_schema="workflow.write.v1",
        required_inputs=["audience", "goal"],
    ),
    "answer": WorkflowSpec(
        name="answer",
        output_schema="workflow.answer.v1",
        required_inputs=[],
    ),
}


def infer_workflow_intent(query: str) -> str:
    q = (query or "").strip().lower()
    if not q:
        return "answer"
    if any(tok in q for tok in ("diagnose", "diagnosis", "root cause", "why is this")):
        return "diagnose"
    if any(tok in q for tok in ("plan", "roadmap", "next steps", "execution plan")):
        return "plan"
    if any(tok in q for tok in ("critique", "review this", "what is wrong", "improve this")):
        return "critique"
    if any(tok in q for tok in ("summarize", "tl;dr", "recap", "brief")):
        return "summarize"
    if any(tok in q for tok in ("brainstorm", "ideas", "alternatives")):
        return "brainstorm"
    if any(tok in q for tok in ("evaluate", "score", "assess", "compare options", "readiness")):
        return "evaluate"
    if any(tok in q for tok in ("write", "draft", "compose", "message for")):
        return "write"
    return "answer"


def resolve_workflow_spec(intent: Optional[str]) -> WorkflowSpec:
    key = (intent or "answer").strip().lower()
    return WORKFLOW_REGISTRY.get(key, WORKFLOW_REGISTRY["answer"])


def detect_required_inputs_missing(
    *,
    workflow: WorkflowSpec,
    query: str,
    pinned_context: Optional[dict] = None,
) -> List[str]:
    """
    Determine whether required workflow inputs are available from query text
    or pinned context.
    """
    if not workflow.required_inputs:
        return []

    q = (query or "").strip().lower()
    ctx = pinned_context or {}
    missing: List[str] = []

    field_patterns: Dict[str, List[str]] = {
        "problem_statement": [r"\bproblem\b", r"\bpain\b", r"\bchallenge\b"],
        "context": [r"\bcontext\b", r"\bbackground\b", r"\bcurrently\b"],
        "objective": [r"\bgoal\b", r"\bobjective\b", r"\bwant to\b", r"\btarget\b"],
        "constraints": [r"\bconstraint\b", r"\blimit\b", r"\bbudget\b", r"\btime\b"],
        "artifact": [r"\bdocument\b", r"\bdraft\b", r"\bproposal\b", r"\bdeck\b", r"\btext\b"],
        "source_text": [r"\bbelow\b", r"\bfollowing\b", r"\btranscript\b", r"\bnotes\b"],
        "goal": [r"\bgoal\b", r"\btrying to\b", r"\bwant\b", r"\bneed to\b"],
        "criteria": [r"\bcriteria\b", r"\bscore\b", r"\bmeasure\b"],
        "options": [r"\bor\b", r"\boption\b", r"\balternative\b", r"\bcompare\b"],
        "audience": [r"\baudience\b", r"\bfor investors\b", r"\bfor founders\b", r"\bfor customers\b"],
    }

    for field in workflow.required_inputs:
        if field in ctx and ctx.get(field):
            continue
        patterns = field_patterns.get(field, [])
        if patterns and any(re.search(p, q) for p in patterns):
            continue
        missing.append(field)

    return missing


def build_clarifying_questions(workflow: WorkflowSpec, missing_inputs: List[str]) -> List[str]:
    questions: List[str] = []
    for field in missing_inputs[:3]:
        if field == "problem_statement":
            questions.append("What exact problem are you trying to solve right now?")
        elif field == "context":
            questions.append("What relevant context should I use before answering?")
        elif field == "objective":
            questions.append("What outcome do you want from this conversation?")
        elif field == "constraints":
            questions.append("What constraints should I respect (time, budget, team, risk)?")
        elif field == "artifact":
            questions.append("Can you share the artifact or text you want me to critique?")
        elif field == "source_text":
            questions.append("Please share the source text you want summarized.")
        elif field == "goal":
            questions.append("What specific goal should the ideas be optimized for?")
        elif field == "criteria":
            questions.append("Which criteria should I use for evaluation?")
        elif field == "options":
            questions.append("What options should I compare?")
        elif field == "audience":
            questions.append("Who is the target audience for this draft?")
    return questions[:3]

