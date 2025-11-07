"""
Geometry filter for detecting non-visual geometry in GLTF imports.

This module helps identify collision boxes, hitboxes, and other non-visual
geometry that might be present in GLTF models but shouldn't be rendered.
"""

def is_non_visual_geometry(name, entity_data=None):
    """
    Check if an object is likely non-visual geometry based on its name and properties.
    
    Args:
        name: The object name to check
        entity_data: Optional entity data dict with size/volume information
        
    Returns:
        bool: True if the object is likely non-visual geometry
    """
    # Common keywords for non-visual geometry
    non_visual_keywords = [
        'collision', 'collider', 'hitbox', 'hit_box', 'physics',
        'trigger', 'sensor', 'bounds', 'bbox', 'bounding',
        'navmesh', 'nav_mesh', 'occluder', 'occlusion',
        'area', 'zone', 'volume', 'region'
    ]
    
    name_lower = name.lower()
    
    # Check if name contains any non-visual keywords
    for keyword in non_visual_keywords:
        if keyword in name_lower:
            return True
    
    # If entity data is provided, check for unusually large volumes
    if entity_data and entity_data.get('from') and entity_data.get('to'):
        from_pos = entity_data['from']
        to_pos = entity_data['to']
        size = [abs(to_pos[i] - from_pos[i]) for i in range(3)]
        volume = size[0] * size[1] * size[2]
        
        # Flag if any dimension is very large (e.g., > 100 units) or volume is huge
        if any(s > 100 for s in size) or volume > 10000:
            # But only if it also has a suspicious name pattern
            suspicious_patterns = ['box', 'cube', 'volume', 'area', 'zone']
            if any(pattern in name_lower for pattern in suspicious_patterns):
                return True
    
    return False