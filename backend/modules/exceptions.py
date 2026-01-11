"""
Custom Exceptions Module: Standardized error handling for the application.

This module defines custom exceptions to provide consistent error handling
across the application and improve debugging with context-rich error messages.
"""
from typing import Optional, Dict, Any


class VerifiedQnAError(Exception):
    """Base exception for verified QnA operations."""
    
    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        """
        Initialize VerifiedQnA error.
        
        Args:
            message: Error message
            context: Optional context dictionary with additional details
        """
        super().__init__(message)
        self.message = message
        self.context = context or {}


class EmbeddingError(Exception):
    """Exception raised when embedding generation fails."""
    
    def __init__(self, message: str, text: Optional[str] = None, context: Optional[Dict[str, Any]] = None):
        """
        Initialize embedding error.
        
        Args:
            message: Error message
            text: Optional text that failed to embed
            context: Optional context dictionary with additional details
        """
        super().__init__(message)
        self.message = message
        self.text = text
        self.context = context or {}


class RetrievalError(Exception):
    """Exception raised when retrieval operations fail."""
    
    def __init__(self, message: str, query: Optional[str] = None, context: Optional[Dict[str, Any]] = None):
        """
        Initialize retrieval error.
        
        Args:
            message: Error message
            query: Optional query that failed
            context: Optional context dictionary with additional details
        """
        super().__init__(message)
        self.message = message
        self.query = query
        self.context = context or {}


class TwinAccessError(Exception):
    """Exception raised when user doesn't have access to a twin."""
    
    def __init__(self, message: str, twin_id: Optional[str] = None, user_id: Optional[str] = None):
        """
        Initialize twin access error.
        
        Args:
            message: Error message
            twin_id: Optional twin ID that was accessed
            user_id: Optional user ID that attempted access
        """
        super().__init__(message)
        self.message = message
        self.twin_id = twin_id
        self.user_id = user_id


class DatabaseError(Exception):
    """Exception raised when database operations fail."""
    
    def __init__(self, message: str, operation: Optional[str] = None, context: Optional[Dict[str, Any]] = None):
        """
        Initialize database error.
        
        Args:
            message: Error message
            operation: Optional operation that failed (e.g., 'insert', 'select')
            context: Optional context dictionary with additional details
        """
        super().__init__(message)
        self.message = message
        self.operation = operation
        self.context = context or {}


class ExternalServiceError(Exception):
    """Exception raised when external service calls fail."""
    
    def __init__(self, message: str, service: Optional[str] = None, context: Optional[Dict[str, Any]] = None):
        """
        Initialize external service error.
        
        Args:
            message: Error message
            service: Optional service name (e.g., 'openai', 'pinecone', 'supabase')
            context: Optional context dictionary with additional details
        """
        super().__init__(message)
        self.message = message
        self.service = service
        self.context = context or {}

