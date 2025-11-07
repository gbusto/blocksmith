"""Custom exceptions for LLM client operations"""


class LLMError(Exception):
    """Base exception for LLM errors"""
    pass


class LLMAPIError(LLMError):
    """API errors (auth, rate limits, invalid requests)"""
    pass


class LLMServiceError(LLMError):
    """Provider service errors (503, downtime)"""
    pass


class LLMTimeoutError(LLMError):
    """Request timeout"""
    pass
