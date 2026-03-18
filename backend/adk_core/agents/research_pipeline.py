"""ADK research workflow."""

from __future__ import annotations

from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent

from adk_core.tools.research_tools import gather_public_research


def build_research_pipeline_agent(*, model: str) -> SequentialAgent:
    gather_agent = LlmAgent(
        name="research_gatherer",
        model=model,
        instruction="""
Gather bounded public-source research material for the subject.

Always call gather_public_research exactly once using the session state
values for subject_name, research_location, research_company, and
research_website. Do not add any analysis yet.
""".strip(),
        tools=[gather_public_research],
        output_key="research_gather_summary",
    )
    identity_analyst = LlmAgent(
        name="identity_analyst",
        model=model,
        instruction="""
Read the gathered research payload: {gathered_research_json}

Produce a compact JSON object with:
- canonical_name
- public_roles
- organizations
- locations
- expertise_topics
- short_bio
- evidence_notes

Stay strictly grounded in the gathered sources.
""".strip(),
        output_key="identity_analysis_json",
    )
    evidence_analyst = LlmAgent(
        name="evidence_analyst",
        model=model,
        instruction="""
Read the gathered research payload: {gathered_research_json}

Produce a compact JSON object with:
- extracted_claims: array of {claim_id, text, claim_type, confidence, source_ids}
- timeline: array of {date_or_range, event, confidence, source_ids}
- quote_candidates: array of {quote, source_id, confidence, context}

Stay strictly grounded in the gathered sources.
""".strip(),
        output_key="evidence_analysis_json",
    )
    synthesis_agent = LlmAgent(
        name="research_synthesizer",
        model=model,
        instruction="""
You are compiling the final research artifact.

Inputs:
- gathered research: {gathered_research_json}
- identity analysis: {identity_analysis_json}
- evidence analysis: {evidence_analysis_json}

Return a single JSON object with exactly these keys:
- subject_identity
- source_registry
- extracted_claims
- timeline
- verified_quote_candidates
- synthesis_summary
- compile_metadata

Keep it faithful to the evidence and ready for persona compilation.
""".strip(),
        output_key="research_artifact_json",
    )
    return SequentialAgent(
        name="research_pipeline",
        sub_agents=[
            gather_agent,
            ParallelAgent(
                name="research_parallel_analysis",
                sub_agents=[identity_analyst, evidence_analyst],
            ),
            synthesis_agent,
        ],
    )
