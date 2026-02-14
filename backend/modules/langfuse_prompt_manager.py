# backend/modules/langfuse_prompt_manager.py
"""Langfuse Prompt Management Integration

Provides version-controlled prompts fetched from Langfuse cloud with local fallback.
Tracks prompt usage in traces for debugging and A/B testing.
"""

import os
import logging
from typing import Optional, Dict, Any, List
from pathlib import Path
from functools import lru_cache

logger = logging.getLogger(__name__)

# Prompt directory for local fallback
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

# Default prompt versions
DEFAULT_PROMPT_VERSIONS = {
    "chat_system": "v1.0",
    "scribe_extraction": "v1.0",
    "hyde_generator": "v1.0",
    "query_expansion": "v1.0",
    "style_analyzer": "v1.0",
    "router": "v1.0",
    "planner": "v1.0",
    "realizer": "v1.0",
}


class LangfusePromptManager:
    """Manages prompts with Langfuse as primary source and local fallback."""
    
    def __init__(self):
        self._client = None
        self._local_cache: Dict[str, Dict[str, Any]] = {}
        self._langfuse_available = False
        self._fetch_remote_prompts = (
            os.getenv("LANGFUSE_PROMPT_FETCH_ENABLED", "false").lower() == "true"
        )
        self._init_client()
    
    def _init_client(self):
        """Initialize Langfuse client if credentials are available."""
        try:
            from langfuse import Langfuse
            
            public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
            secret_key = os.getenv("LANGFUSE_SECRET_KEY")
            host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
            
            if public_key and secret_key:
                self._client = Langfuse(
                    public_key=public_key,
                    secret_key=secret_key,
                    host=host,
                )
                self._langfuse_available = True
                logger.info("Langfuse Prompt Manager initialized successfully")
            else:
                logger.warning("Langfuse credentials not found, using local prompts only")
        except ImportError:
            logger.warning("Langfuse SDK not installed, using local prompts only")
        except Exception as e:
            logger.error(f"Failed to initialize Langfuse client: {e}")
    
    def get_prompt(
        self, 
        name: str, 
        version: Optional[str] = None,
        label: Optional[str] = None,
        fetch_if_missing: bool = True
    ) -> Dict[str, Any]:
        """
        Get a prompt by name from Langfuse or local fallback.
        
        Args:
            name: Prompt name (e.g., 'chat_system')
            version: Specific version to fetch (e.g., 'v1.0')
            label: Label to fetch (e.g., 'production', 'latest')
            fetch_if_missing: Whether to fetch from Langfuse if not in cache
        
        Returns:
            Dict with 'text', 'name', 'version', 'source' keys
        """
        cache_key = f"{name}:{version or 'default'}:{label or 'none'}"
        
        # Check local cache first
        if cache_key in self._local_cache:
            return self._local_cache[cache_key]
        
        # Try Langfuse if available
        if fetch_if_missing and self._langfuse_available and self._fetch_remote_prompts:
            try:
                prompt = self._fetch_from_langfuse(name, version, label)
                if prompt:
                    self._local_cache[cache_key] = prompt
                    return prompt
            except Exception as e:
                logger.warning(f"Failed to fetch prompt '{name}' from Langfuse: {e}")
        
        # Fallback to local
        prompt = self._fetch_from_local(name, version)
        self._local_cache[cache_key] = prompt
        return prompt
    
    def _fetch_from_langfuse(
        self, 
        name: str, 
        version: Optional[str] = None,
        label: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Fetch prompt from Langfuse API."""
        if not self._client:
            return None
        
        try:
            # Try to get by label first, then by version
            if label:
                prompt_obj = self._client.get_prompt(name, label=label)
            elif version:
                prompt_obj = self._client.get_prompt(name, version=version)
            else:
                # Get latest production version
                prompt_obj = self._client.get_prompt(name, label="production")
            
            if prompt_obj and prompt_obj.prompt:
                return {
                    "text": prompt_obj.prompt,
                    "name": name,
                    "version": prompt_obj.version,
                    "label": label or "production",
                    "source": "langfuse",
                    "prompt_obj": prompt_obj,  # Keep reference for compilation
                }
        except Exception as e:
            logger.debug(f"Langfuse prompt fetch failed for '{name}': {e}")
        
        return None
    
    def _fetch_from_local(self, name: str, version: Optional[str] = None) -> Dict[str, Any]:
        """Fetch prompt from local files or defaults."""
        version = version or DEFAULT_PROMPT_VERSIONS.get(name, "v1.0")
        
        # Try to load from file
        prompt_file = PROMPTS_DIR / f"{name}_{version}.txt"
        if prompt_file.exists():
            text = prompt_file.read_text(encoding="utf-8")
            return {
                "text": text,
                "name": name,
                "version": version,
                "source": "local_file",
            }
        
        # Fallback to default prompts
        text = self._get_default_prompt(name)
        return {
            "text": text,
            "name": name,
            "version": version,
            "source": "local_default",
        }
    
    def compile_prompt(
        self, 
        name: str, 
        variables: Dict[str, Any],
        version: Optional[str] = None,
        label: Optional[str] = None
    ) -> str:
        """
        Get and compile a prompt with variables.
        
        Args:
            name: Prompt name
            variables: Dict of variables to substitute (e.g., {'twin_id': '123'})
            version: Specific version
            label: Label to use
        
        Returns:
            Compiled prompt string
        """
        prompt_data = self.get_prompt(name, version, label)
        
        # Try to use Langfuse's compile method if available
        if prompt_data.get("source") == "langfuse" and "prompt_obj" in prompt_data:
            try:
                compiled = prompt_data["prompt_obj"].compile(**variables)
                self._track_prompt_usage(name, prompt_data["version"], "langfuse")
                return compiled
            except Exception as e:
                logger.warning(f"Langfuse compile failed for '{name}', using string format: {e}")
        
        # Fallback to string formatting
        try:
            compiled = prompt_data["text"].format(**variables)
            self._track_prompt_usage(name, prompt_data["version"], prompt_data["source"])
            return compiled
        except KeyError as e:
            logger.error(f"Missing variable {e} for prompt '{name}'")
            raise
        except Exception as e:
            logger.error(f"Failed to compile prompt '{name}': {e}")
            raise
    
    def _track_prompt_usage(self, name: str, version: str, source: str):
        """Track prompt usage in current Langfuse observation."""
        try:
            from langfuse.decorators import langfuse_context
            langfuse_context.update_current_observation(
                metadata={
                    "prompt_name": name,
                    "prompt_version": version,
                    "prompt_source": source,
                }
            )
        except Exception:
            pass  # Tracking is best-effort
    
    def _get_default_prompt(self, name: str) -> str:
        """Return default prompts for common operations."""
        defaults = {
            "chat_system": (
                "You are a digital twin that represents the owner's knowledge and perspective. "
                "Answer questions based on the provided context. If you don't have relevant "
                "information in your knowledge base, acknowledge this honestly."
            ),
            "scribe_extraction": (
                "You are an expert Knowledge Graph Scribe. Extract structured entities (Nodes) "
                "and relationships (Edges) from the conversation. Focus on factual claims, "
                "metrics, definitions, and proper nouns."
            ),
            "hyde_generator": (
                "You are a knowledgeable assistant. Write a brief, factual hypothetical answer "
                "to the user's question. Focus on relevant keywords and concepts."
            ),
            "query_expansion": (
                "Generate 3 search query variations based on the user's input to improve RAG "
                "retrieval. Focus on different aspects and synonyms."
            ),
            "style_analyzer": (
                "Analyze the owner's writing style from verified responses. Identify tone, "
                "vocabulary patterns, and communication preferences."
            ),
            "router": (
                "You are a Strategic Dialogue Router for a Digital Twin.\n"
                "Classify the user's intent to determine retrieval and evidence requirements.\n\n"
                "USER QUERY: {user_query}\n"
                "INTERACTION CONTEXT: {interaction_context}\n\n"
                "MODES:\n"
                "- SMALLTALK: Greetings, brief pleasantries, \"how are you\".\n"
                "- QA_FACT: Questions about objective facts, events, or public knowledge.\n"
                "- QA_RELATIONSHIP: Questions about people, entities, or connections.\n"
                "- STANCE_GLOBAL: Questions about beliefs/opinions.\n"
                "- REPAIR: User complaining about robotic or incorrect output.\n"
                "- TEACHING: Explicit user correction/teaching only.\n\n"
                "OUTPUT FORMAT (JSON):\n"
                "{{\n"
                "  \"mode\": \"SMALLTALK | QA_FACT | QA_RELATIONSHIP | STANCE_GLOBAL | REPAIR | TEACHING\",\n"
                "  \"is_person_specific\": bool,\n"
                "  \"requires_evidence\": bool,\n"
                "  \"reasoning\": \"Brief explanation\"\n"
                "}}"
            ),
            "planner": (
                "You are a Response Planner for a Digital Twin. "
                "Plan how to answer the user's question based on available context."
            ),
            "realizer": (
                "You are the Voice Realizer for a Digital Twin. "
                "Generate human-like responses that match the owner's voice and style."
            ),
        }
        return defaults.get(name, "")
    
    def list_available_prompts(self) -> List[str]:
        """List all available prompt names."""
        return list(DEFAULT_PROMPT_VERSIONS.keys())
    
    def get_prompt_versions(self, name: str) -> List[str]:
        """Get all versions available for a prompt (Langfuse + local)."""
        versions = []
        
        # Check Langfuse
        if self._langfuse_available:
            try:
                # This would need to be implemented based on Langfuse API
                # For now, just return the default
                versions.append("production")
            except Exception:
                pass
        
        # Check local files
        for file in PROMPTS_DIR.glob(f"{name}_*.txt"):
            version = file.stem.replace(f"{name}_", "")
            versions.append(version)
        
        # Add default if no others found
        if not versions and name in DEFAULT_PROMPT_VERSIONS:
            versions.append(DEFAULT_PROMPT_VERSIONS[name])
        
        return versions
    
    def clear_cache(self):
        """Clear the local prompt cache."""
        self._local_cache.clear()
        logger.info("Prompt cache cleared")


# Singleton instance
_prompt_manager: Optional[LangfusePromptManager] = None


def get_prompt_manager() -> LangfusePromptManager:
    """Get or create the singleton prompt manager."""
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = LangfusePromptManager()
    return _prompt_manager


# Convenience functions
def get_prompt(name: str, version: Optional[str] = None) -> Dict[str, Any]:
    """Get a prompt by name (convenience function)."""
    return get_prompt_manager().get_prompt(name, version)


def compile_prompt(name: str, variables: Dict[str, Any], version: Optional[str] = None) -> str:
    """Compile a prompt with variables (convenience function)."""
    return get_prompt_manager().compile_prompt(name, variables, version)


def track_prompt_usage(prompt_name: str, prompt_version: str):
    """
    Manually track prompt usage in current observation.
    Call this inside an @observe'd function.
    """
    try:
        from langfuse.decorators import langfuse_context
        langfuse_context.update_current_observation(
            metadata={
                "prompt_name": prompt_name,
                "prompt_version": prompt_version,
            }
        )
    except Exception:
        pass
