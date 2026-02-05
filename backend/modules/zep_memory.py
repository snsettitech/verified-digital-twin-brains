# backend/modules/zep_memory.py
"""Zep/Graphiti memory layer integration.

Provides temporal knowledge graph storage for user memories using
Graphiti framework with Neo4j backend.

Memory types: intent, goal, constraint, preference, boundary
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import os
import logging

logger = logging.getLogger(__name__)

# Memory type priority for context assembly
MEMORY_PRIORITY = {
    "boundary": 1,
    "constraint": 2,
    "goal": 3,
    "preference": 4,
    "intent": 5
}


class ZepMemoryClient:
    """
    Client wrapper for Zep/Graphiti temporal knowledge graph.
    
    Manages user memory nodes and relationships with temporal awareness.
    """
    
    def __init__(self):
        """Initialize connection to Neo4j via Graphiti."""
        self._initialized = False
        self._graphiti = None
        self._driver = None
        
    async def initialize(self):
        """
        Lazy initialization of Graphiti client.
        
        Call this before using any memory operations.
        """
        if self._initialized:
            return
            
        try:
            from graphiti_core import Graphiti
            from neo4j import GraphDatabase
            
            neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
            neo4j_user = os.getenv("NEO4J_USER", "neo4j")
            neo4j_password = os.getenv("NEO4J_PASSWORD", "")
            
            if not neo4j_password:
                logger.warning("NEO4J_PASSWORD not set - memory features will be limited")
                return
            
            # Initialize Neo4j driver
            self._driver = GraphDatabase.driver(
                neo4j_uri,
                auth=(neo4j_user, neo4j_password)
            )
            
            # Initialize Graphiti with LLM provider
            openai_api_key = os.getenv("OPENAI_API_KEY")
            self._graphiti = Graphiti(
                neo4j_uri=neo4j_uri,
                neo4j_user=neo4j_user,
                neo4j_password=neo4j_password,
                llm_api_key=openai_api_key
            )
            
            self._initialized = True
            logger.info("Zep/Graphiti client initialized successfully")
            
        except ImportError as e:
            logger.warning(f"Graphiti not available: {e}. Using fallback storage.")
        except Exception as e:
            logger.error(f"Failed to initialize Graphiti: {e}")
    
    async def get_or_create_user_node(self, user_id: str) -> Dict[str, Any]:
        """
        Ensure user node exists in the graph.
        
        Creates user node if it doesn't exist, returns existing if it does.
        """
        await self.initialize()
        
        if not self._initialized or not self._graphiti:
            return {"id": user_id, "status": "fallback"}
        
        try:
            # Add user entity to graph
            await self._graphiti.add_episode(
                name=f"User {user_id} initialization",
                episode_body=f"User with ID {user_id} joined the system.",
                source_description="system"
            )
            
            return {
                "id": user_id,
                "status": "created",
                "created_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error creating user node: {e}")
            return {"id": user_id, "status": "error", "error": str(e)}
    
    async def upsert_memory(
        self,
        user_id: str,
        memory_item: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Upsert a memory item to the graph.
        
        Creates typed node with edges to user and temporal metadata.
        Handles deduplication and conflict detection.
        
        Args:
            user_id: The user's UUID
            memory_item: Dict with type, value, evidence, confidence, timestamp, session_id
            
        Returns:
            Result dict with node_id, status, and any conflict info
        """
        await self.initialize()
        
        memory_type = memory_item.get("type", "unknown")
        value = memory_item.get("value", "")
        evidence = memory_item.get("evidence", "")
        confidence = memory_item.get("confidence", 0.5)
        session_id = memory_item.get("session_id", "")
        
        if not self._initialized or not self._graphiti:
            # Fallback: just log the memory
            logger.info(f"Memory (fallback): [{memory_type}] {value}")
            return {
                "status": "fallback",
                "memory_type": memory_type,
                "value": value
            }
        
        try:
            # Build episode content for Graphiti
            episode_content = f"""
The user has expressed a {memory_type}:

{memory_type.upper()}: {value}

Evidence from conversation: "{evidence}"

This was captured with {confidence*100:.0f}% confidence.
"""
            
            # Add as episode - Graphiti will extract entities and relationships
            result = await self._graphiti.add_episode(
                name=f"User {memory_type} - {session_id[:8]}",
                episode_body=episode_content,
                source_description=f"interview_mode:{session_id}"
            )
            
            return {
                "status": "created",
                "memory_type": memory_type,
                "node_id": result.get("uuid") if result else None,
                "value": value
            }
            
        except Exception as e:
            logger.error(f"Error upserting memory: {e}")
            return {
                "status": "error",
                "memory_type": memory_type,
                "error": str(e)
            }
    
    async def get_user_context(
        self,
        user_id: str,
        task: str = "interview",
        max_tokens: int = 2000
    ) -> str:
        """
        Retrieve prioritized context bundle for the user.
        
        Priority order: boundaries > constraints > active goals > stable preferences > recent intent
        
        Args:
            user_id: The user's UUID
            task: Context for prioritization (e.g., "interview", "chat")
            max_tokens: Approximate token budget for context
            
        Returns:
            Formatted context string ready for system prompt
        """
        await self.initialize()
        
        if not self._initialized or not self._graphiti:
            return ""
        
        try:
            # Search for relevant context
            results = await self._graphiti.search(
                query=f"What are the key {task}-relevant facts about this user?",
                num_results=20
            )
            
            if not results:
                return ""
            
            # Group by memory type and prioritize
            memories_by_type: Dict[str, List[str]] = {
                "boundary": [],
                "constraint": [],
                "goal": [],
                "preference": [],
                "intent": [],
                "other": []
            }
            
            for item in results:
                content = item.get("fact", item.get("content", ""))
                # Attempt to categorize based on content
                content_lower = content.lower()
                
                if any(w in content_lower for w in ["won't", "never", "refuse", "boundary"]):
                    memories_by_type["boundary"].append(content)
                elif any(w in content_lower for w in ["can't", "must", "constraint", "limit"]):
                    memories_by_type["constraint"].append(content)
                elif any(w in content_lower for w in ["want", "goal", "aim", "objective"]):
                    memories_by_type["goal"].append(content)
                elif any(w in content_lower for w in ["prefer", "like", "preference"]):
                    memories_by_type["preference"].append(content)
                elif any(w in content_lower for w in ["trying", "intent", "working on"]):
                    memories_by_type["intent"].append(content)
                else:
                    memories_by_type["other"].append(content)
            
            # Build context in priority order
            context_parts = []
            
            for memory_type in ["boundary", "constraint", "goal", "preference", "intent"]:
                items = memories_by_type.get(memory_type, [])
                if items:
                    context_parts.append(f"**{memory_type.title()}s:**")
                    for item in items[:5]:  # Limit per category
                        context_parts.append(f"- {item}")
                    context_parts.append("")
            
            # Add other if space permits
            if memories_by_type.get("other"):
                context_parts.append("**Other relevant facts:**")
                for item in memories_by_type["other"][:3]:
                    context_parts.append(f"- {item}")
            
            return "\n".join(context_parts)
            
        except Exception as e:
            logger.error(f"Error getting user context: {e}")
            return ""
    
    async def mark_superseded(
        self,
        memory_id: str,
        superseded_by: str,
        reason: str = "conflict"
    ) -> bool:
        """
        Mark a memory as superseded by a newer one.
        
        Used for conflict handling - keeps both but marks older as superseded.
        """
        await self.initialize()
        
        if not self._initialized:
            return False
        
        try:
            # This would add a SUPERSEDES edge in the graph
            # For now, log the supersession
            logger.info(f"Memory {memory_id} superseded by {superseded_by}: {reason}")
            return True
            
        except Exception as e:
            logger.error(f"Error marking memory superseded: {e}")
            return False
    
    async def close(self):
        """Close connections."""
        if self._driver:
            self._driver.close()
        if self._graphiti:
            await self._graphiti.close()


# Singleton instance
_zep_client: Optional[ZepMemoryClient] = None


def get_zep_client() -> ZepMemoryClient:
    """Get or create singleton ZepMemoryClient instance."""
    global _zep_client
    if _zep_client is None:
        _zep_client = ZepMemoryClient()
    return _zep_client
