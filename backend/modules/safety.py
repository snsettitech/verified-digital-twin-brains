"""
Safety Module
Implements guardrails, prompt injection detection, and policy enforcement.
"""
from typing import List, Dict, Any, Optional
import re
from modules.governance import get_governance_policies, AuditLogger

class GuardrailEngine:
    """Evaluates prompts and responses against governance policies."""
    
    def __init__(self, twin_id: str):
        self.twin_id = twin_id
        try:
            self.policies = get_governance_policies(twin_id)
        except Exception as e:
            # Graceful fallback if governance tables don't exist or query fails
            print(f"[Guardrails] Warning: Could not load governance policies: {e}")
            self.policies = []
    
    def check_prompt(self, prompt: str) -> Optional[str]:
        """
        Scans prompt for violations or injection attempts.
        Returns refusal message if violation found, else None.
        """
        # 1. Basic Prompt Injection Heuristics
        injection_patterns = [
            r"ignore all previous instructions",
            r"system (command|prompt|role)",
            r"you are now a",
            r"disregard (everything|above)",
        ]
        
        for pattern in injection_patterns:
            if re.search(pattern, prompt, re.IGNORECASE):
                AuditLogger.log(self.twin_id, "SAFETY_VIOLATION", "PROMPT_INJECTION_DETECTED", metadata={"prompt_fragment": prompt[:50]})
                return "I'm sorry, I cannot process this request as it violates my security guardrails."
        
        # 2. Refusal Rules from Policies
        for policy in self.policies:
            try:
                if policy.get("policy_type") == "refusal_rule":
                    # Basic keyword/regex check against policy content
                    pattern = policy.get("content", "")
                    if pattern and re.search(pattern, prompt, re.IGNORECASE):
                        try:
                            AuditLogger.log(self.twin_id, "SAFETY_VIOLATION", "REFUSAL_RULE_TRIGGERED", metadata={"policy_name": policy.get("name", "unknown")})
                        except Exception:
                            # Fallback if audit logging fails
                            pass
                        return f"I cannot assist with this request. [Policy: {policy.get('name', 'unknown')}]"
            except Exception as e:
                # Skip malformed policies gracefully
                print(f"[Guardrails] Warning: Error processing policy: {e}")
                continue
        
        return None

    def enforce_tool_sandbox(self, tool_name: str, args: Dict[str, Any]):
        """
        Enforces constraints on tool execution.
        """
        for policy in self.policies:
            try:
                if policy.get("policy_type") == "tool_restriction":
                    # e.g., restriction could be "disallow:system_exec"
                    content = policy.get("content", "")
                    if tool_name in content:
                        try:
                            AuditLogger.log(self.twin_id, "SAFETY_VIOLATION", "TOOL_ACCESS_DENIED", metadata={"tool": tool_name})
                        except Exception:
                            # Fallback if audit logging fails
                            pass
                        raise PermissionError(f"Access to tool '{tool_name}' is restricted by governance policy.")
            except PermissionError:
                # Re-raise permission errors
                raise
            except Exception as e:
                # Skip malformed policies gracefully
                print(f"[Guardrails] Warning: Error processing tool restriction policy: {e}")
                continue
        
        return True

def apply_guardrails(twin_id: str, prompt: str) -> Optional[str]:
    """Shorthand for checking a prompt."""
    engine = GuardrailEngine(twin_id)
    return engine.check_prompt(prompt)
