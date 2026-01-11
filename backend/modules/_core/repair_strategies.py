# backend/modules/_core/repair_strategies.py
"""Repair Strategy Manager: Handles non-substantive responses with escalating strategies.

Manages clarification prompts that escalate in intensity and offer different approaches
to help users provide meaningful answers.
"""

from typing import Dict, Any, Optional, List


class RepairStrategy:
    """Repair strategy result."""
    def __init__(
        self,
        message: str,
        strategy_type: str,
        attempt: int,
        should_skip: bool = False
    ):
        self.message = message
        self.strategy_type = strategy_type
        self.attempt = attempt
        self.should_skip = should_skip


class RepairManager:
    """Manages escalating clarification strategies."""
    
    MAX_ATTEMPTS = 4
    
    @staticmethod
    def get_repair_strategy(
        attempt: int,
        current_question: Optional[Dict[str, Any]] = None,
        current_slot: Optional[Dict[str, Any]] = None,
        user_message: Optional[str] = None
    ) -> RepairStrategy:
        """
        Get repair strategy based on attempt number.
        
        Args:
            attempt: Current clarification attempt (1-indexed)
            current_question: Current question dict (optional)
            current_slot: Current slot dict (optional)
            user_message: Original user message (optional, for context)
        
        Returns:
            RepairStrategy with message and strategy type
        """
        if attempt > RepairManager.MAX_ATTEMPTS:
            attempt = RepairManager.MAX_ATTEMPTS
        
        question_text = ""
        examples = ""
        slot_id = ""
        
        if current_question:
            question_text = current_question.get("question", "")
            examples = current_question.get("examples", "")
        elif current_slot:
            slot_id = current_slot.get("slot_id", "").replace("_", " ")
            question_text = f"Tell me about {slot_id}"
        
        # Strategy 1: Gentle re-ask
        if attempt == 1:
            if question_text:
                message = f"I didn't quite catch that. {question_text}"
            else:
                message = "I didn't quite catch that. Could you tell me more?"
            return RepairStrategy(
                message=message,
                strategy_type="gentle_reask",
                attempt=1
            )
        
        # Strategy 2: Provide examples
        elif attempt == 2:
            if examples:
                message = f"Let me give you an example: {examples}\n\nWhat about you?"
            elif question_text:
                message = f"{question_text}\n\nFor example, you might say something about your goals or what you want to achieve."
            else:
                message = "Could you provide a bit more detail? For example, you could describe what you're trying to accomplish."
            return RepairStrategy(
                message=message,
                strategy_type="provide_examples",
                attempt=2
            )
        
        # Strategy 3: Simplify question
        elif attempt == 3:
            if slot_id:
                simplified = f"In one sentence: what's your {slot_id}?"
            elif question_text:
                # Try to simplify the question
                simplified = question_text
                # Remove complex parts, keep the core
                if "?" in simplified:
                    # Take just the question part
                    parts = simplified.split("?")
                    if parts:
                        simplified = parts[0] + "?"
            else:
                simplified = "In one sentence: what should this twin help with?"
            
            message = f"Let me try a simpler question: {simplified}"
            return RepairStrategy(
                message=message,
                strategy_type="simplify_question",
                attempt=3
            )
        
        # Strategy 4: Offer escape
        else:
            if current_slot and current_slot.get("optional", False):
                message = "No problem! This is optional - we can skip this for now. Would you like to continue with something else?"
                return RepairStrategy(
                    message=message,
                    strategy_type="offer_skip_optional",
                    attempt=4,
                    should_skip=True
                )
            else:
                message = "That's okay - we can move on for now. We can always come back to this later. Ready for the next question?"
                return RepairStrategy(
                    message=message,
                    strategy_type="offer_escape",
                    attempt=4,
                    should_skip=False  # Don't mark as skipped, just move on
                )
    
    @staticmethod
    def detect_skip_request(message: str) -> bool:
        """Detect if user wants to skip the current question."""
        msg_lower = message.lower().strip()
        skip_patterns = [
            "skip", "next", "pass", "don't know", "dont know", "no idea",
            "can't answer", "cant answer", "not applicable", "na", "n/a",
            "move on", "continue", "later"
        ]
        return any(pattern in msg_lower for pattern in skip_patterns)
    
    @staticmethod
    def detect_off_topic(message: str, current_question: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """
        Detect if user went off-topic and provide redirect.
        
        Returns:
            Redirect message if off-topic detected, None otherwise
        """
        # This is a simple heuristic - could be enhanced with LLM
        # For now, just check if user asks a question back
        if "?" in message and len(message.split("?")) > 1:
            # User might be asking questions
            question_text = ""
            if current_question:
                question_text = current_question.get("question", "")
            
            if question_text:
                return f"Interesting question! We'll get to that. First, {question_text.lower()}"
            else:
                return "Interesting! Let's focus on the current question for now. Can you tell me more about that?"
        
        return None
