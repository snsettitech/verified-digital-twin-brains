# backend/modules/_core/response_evaluator.py
"""Response Quality Evaluator: Three-tier evaluation system for user responses.

Classifies user responses before processing to ensure meaningful data collection.
Uses rule-based checks, heuristics, and LLM classification.
"""

from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
import re

from modules.clients import get_async_openai_client


class ResponseQuality(BaseModel):
    """Response quality evaluation result."""
    is_substantive: bool = Field(description="Whether the response contains meaningful information")
    quality_score: float = Field(description="Quality score from 0.0 to 1.0")
    tier: int = Field(description="Evaluation tier used (1=rule, 2=heuristic, 3=LLM)")
    relevance_score: Optional[float] = Field(None, description="Relevance to current slot")
    suggested_follow_up: Optional[str] = Field(None, description="Suggested follow-up prompt")
    reason: str = Field(description="Reason for the evaluation")


# Tier 1: Rule-based fast check patterns
NON_ANSWERS = {
    # Greetings
    "hi", "hello", "hey", "hola", "yo", "sup", "what's up",
    # Acknowledgments
    "ok", "okay", "k", "yes", "no", "yep", "nope", "yeah", "nah",
    # Uncertainty
    "idk", "i don't know", "dunno", "not sure", "maybe", "perhaps",
    # Testing
    "test", "testing", "test message",
    # Placeholders
    "hmm", "huh", "what", "?"
}


class ResponseEvaluator:
    """Three-tier response quality evaluator."""
    
    @staticmethod
    async def evaluate_response(
        message: str,
        current_question: Optional[Dict[str, Any]] = None,
        current_slot: Optional[Dict[str, Any]] = None,
        use_llm: bool = True
    ) -> ResponseQuality:
        """
        Evaluate response quality using three tiers.
        
        Args:
            message: User's response message
            current_question: Current question being asked (optional)
            current_slot: Current slot being filled (optional)
            use_llm: Whether to use LLM for Tier 3 (default: True)
        
        Returns:
            ResponseQuality object with evaluation results
        """
        msg_lower = message.lower().strip()
        msg_words = msg_lower.split()
        msg_length = len(message.strip())
        word_count = len(msg_words)
        
        # Tier 1: Rule-based fast check (no API call)
        tier1_result = ResponseEvaluator._tier1_rule_based(msg_lower, msg_words, word_count)
        if tier1_result:
            return tier1_result
        
        # Tier 2: Heuristic analysis
        tier2_result = ResponseEvaluator._tier2_heuristic(
            message, msg_lower, word_count, msg_length, current_question, current_slot
        )
        if tier2_result:
            # If heuristic gives strong signal, return it
            if tier2_result.quality_score < 0.4 or tier2_result.quality_score > 0.8:
                return tier2_result
        
        # Tier 3: LLM classification (for borderline cases)
        if use_llm:
            tier3_result = await ResponseEvaluator._tier3_llm_classification(
                message, current_question, current_slot
            )
            if tier3_result:
                return tier3_result
        
        # Fallback: If no LLM or LLM fails, use heuristic result
        return tier2_result or ResponseQuality(
            is_substantive=True,
            quality_score=0.7,
            tier=2,
            reason="Heuristic analysis (no strong signal)"
        )
    
    @staticmethod
    def _tier1_rule_based(msg_lower: str, msg_words: List[str], word_count: int) -> Optional[ResponseQuality]:
        """Tier 1: Fast rule-based rejection."""
        
        # Check for exact match with non-answers
        if msg_lower in NON_ANSWERS:
            return ResponseQuality(
                is_substantive=False,
                quality_score=0.1,
                tier=1,
                reason=f"Matched non-answer pattern: '{msg_lower}'"
            )
        
        # Check for too short responses (less than 3 words)
        if word_count < 3:
            # Exception: Single word answers that are substantive (e.g., "Enterprise", "SaaS")
            # These are usually too short but might be valid - let heuristics/LLM decide
            if word_count == 1 and len(msg_lower) > 5:
                # Likely a single substantive word
                return None
            return ResponseQuality(
                is_substantive=False,
                quality_score=0.2,
                tier=1,
                reason=f"Too short: {word_count} word(s)"
            )
        
        # Check for only punctuation/whitespace
        if not re.search(r'[a-zA-Z0-9]', msg_lower):
            return ResponseQuality(
                is_substantive=False,
                quality_score=0.0,
                tier=1,
                reason="No alphanumeric characters"
            )
        
        return None  # Pass to next tier
    
    @staticmethod
    def _tier2_heuristic(
        message: str,
        msg_lower: str,
        word_count: int,
        msg_length: int,
        current_question: Optional[Dict[str, Any]],
        current_slot: Optional[Dict[str, Any]]
    ) -> ResponseQuality:
        """Tier 2: Heuristic analysis."""
        
        score = 0.5  # Start at neutral
        
        # Word count scoring
        if word_count >= 10:
            score += 0.2
        elif word_count >= 5:
            score += 0.1
        elif word_count < 3:
            score -= 0.3
        
        # Character length scoring
        if msg_length >= 50:
            score += 0.2
        elif msg_length >= 20:
            score += 0.1
        elif msg_length < 10:
            score -= 0.2
        
        # Check for question marks (user asking questions back)
        if "?" in message:
            score -= 0.1  # Slight penalty, but not a rejection
        
        # Check for domain-specific keywords if slot provided
        if current_slot:
            slot_id = current_slot.get("slot_id", "").lower()
            # Simple keyword matching for common slot types
            if "use_case" in slot_id or "purpose" in slot_id:
                domain_keywords = ["twin", "brain", "help", "for", "use", "want", "create", "build"]
                if any(kw in msg_lower for kw in domain_keywords):
                    score += 0.15
            elif "audience" in slot_id:
                domain_keywords = ["who", "team", "people", "users", "customers", "clients"]
                if any(kw in msg_lower for kw in domain_keywords):
                    score += 0.15
            elif "thesis" in slot_id or "sector" in slot_id:
                domain_keywords = ["focus", "sector", "theme", "area", "invest", "market"]
                if any(kw in msg_lower for kw in domain_keywords):
                    score += 0.15
        
        # Clamp score between 0.0 and 1.0
        score = max(0.0, min(1.0, score))
        
        is_substantive = score >= 0.5
        
        return ResponseQuality(
            is_substantive=is_substantive,
            quality_score=score,
            tier=2,
            relevance_score=score if current_slot else None,
            reason=f"Heuristic: {word_count} words, {msg_length} chars"
        )
    
    @staticmethod
    async def _tier3_llm_classification(
        message: str,
        current_question: Optional[Dict[str, Any]],
        current_slot: Optional[Dict[str, Any]]
    ) -> Optional[ResponseQuality]:
        """Tier 3: LLM-based classification for borderline cases."""
        
        try:
            client = get_async_openai_client()
            
            # Build context about what we're asking
            context = ""
            if current_question:
                question_text = current_question.get("question", "")
                examples = current_question.get("examples", "")
                context = f"Current question: {question_text}"
                if examples:
                    context += f"\nExamples: {examples}"
            elif current_slot:
                slot_id = current_slot.get("slot_id", "").replace("_", " ")
                context = f"Current topic: {slot_id}"
            
            system_prompt = """You are a response quality evaluator for a cognitive interview system.
Your goal is to determine if a user's response contains meaningful information relevant to the interview question.

Classify the response as:
- is_substantive: true if the response contains actual information (not just greetings, acknowledgments, or non-answers)
- quality_score: 0.0 to 1.0 based on how substantive and relevant the response is
- relevance_score: 0.0 to 1.0 based on how relevant the response is to the current question/topic
- suggested_follow_up: A brief clarification prompt if needed (null if response is good)

Examples of non-substantive responses:
- "hi", "hello", "ok", "yes", "no", "idk", "test"
- Responses less than 3 words (unless they're single substantive words)
- Pure acknowledgments without content

Examples of substantive responses:
- "I want to create a VC brain for my investment decisions"
- "It will be used by my team of 5 analysts"
- "Enterprise SaaS companies focused on B2B"
"""
            
            user_prompt = f"""Evaluate this user response:
{context if context else "General interview context"}

User response: "{message}"

Return JSON with: is_substantive (bool), quality_score (float 0.0-1.0), relevance_score (float 0.0-1.0), suggested_follow_up (string or null), reason (string)"""
            
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.0
            )
            
            result = response.choices[0].message.content
            import json
            data = json.loads(result)
            
            return ResponseQuality(
                is_substantive=data.get("is_substantive", True),
                quality_score=float(data.get("quality_score", 0.5)),
                tier=3,
                relevance_score=float(data.get("relevance_score", 0.5)) if data.get("relevance_score") else None,
                suggested_follow_up=data.get("suggested_follow_up"),
                reason=f"LLM: {data.get('reason', 'Classified by model')}"
            )
            
        except Exception as e:
            print(f"[ResponseEvaluator] LLM classification failed: {e}")
            return None  # Fall back to heuristic
