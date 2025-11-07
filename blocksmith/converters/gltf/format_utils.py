"""
GLTF Format Utilities

Helper functions for handling both dict and pygltflib object formats consistently.
"""

from typing import Any, Optional, Union, Dict


def get_field(obj: Any, field_name: str, default: Any = None) -> Any:
    """
    Get field from either dict or object format
    
    Args:
        obj: Dict or object to extract field from
        field_name: Name of field to extract
        default: Default value if field not found
        
    Returns:
        Field value or default
    """
    if obj is None:
        return default
    
    # Try object attribute first
    if hasattr(obj, field_name):
        value = getattr(obj, field_name)
        # Handle pygltflib objects that can have None values
        return value if value is not None else default
    
    # Fall back to dict access
    if isinstance(obj, dict):
        return obj.get(field_name, default)
    
    return default


def has_field(obj: Any, field_name: str) -> bool:
    """
    Check if object has field (either as attribute or dict key)
    
    Args:
        obj: Dict or object to check
        field_name: Name of field to check for
        
    Returns:
        True if field exists and is not None
    """
    if obj is None:
        return False
    
    # Check object attribute
    if hasattr(obj, field_name):
        return getattr(obj, field_name) is not None
    
    # Check dict key
    if isinstance(obj, dict):
        return field_name in obj and obj[field_name] is not None
    
    return False


def get_list_field(obj: Any, field_name: str, default: Optional[list] = None) -> list:
    """
    Get list field, handling both dict and object formats
    
    Args:
        obj: Dict or object to extract field from
        field_name: Name of list field to extract
        default: Default value if field not found
        
    Returns:
        List value or default (empty list if default is None)
    """
    if default is None:
        default = []
    
    value = get_field(obj, field_name, default)
    
    # Ensure we return a list
    if value is None:
        return default
    if not isinstance(value, list):
        return default
    
    return value


def safe_iterate(obj: Any, field_name: str):
    """
    Safely iterate over a list field, yielding (index, item) tuples
    
    Args:
        obj: Dict or object containing the list field
        field_name: Name of list field to iterate
        
    Yields:
        (index, item) tuples
    """
    items = get_list_field(obj, field_name, [])
    for idx, item in enumerate(items):
        yield idx, item