"""
Smart UV Rectangle Packer

Packs generic rectangles into a power-of-2 atlas.
Recreated for BlockSmith OSS compatibility.
"""

import math
from typing import List, Tuple, Dict, Any

def next_power_of_2(n: int) -> int:
    """Return the next power of 2 >= n."""
    if n <= 0:
        return 1
    return 2 ** math.ceil(math.log2(n))

class ShelfPacker:
    """Packs rectangles using a greedy shelf algorithm."""
    
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.shelves: List[Dict] = []
        
    def pack(self, width: int, height: int) -> Tuple[int, int]:
        """Try to pack a rect. Returns (x, y) or None if fails."""
        # Try existing shelves
        for shelf in self.shelves:
            if width <= self.width - shelf['x'] and height <= shelf['height']:
                x = shelf['x']
                y = shelf['y']
                shelf['x'] += width
                return x, y
        
        # New shelf
        new_y = sum(s['height'] for s in self.shelves)
        if new_y + height > self.height or width > self.width:
            return None
            
        self.shelves.append({
            'y': new_y,
            'height': height,
            'x': width
        })
        return 0, new_y

def pack_rectangles(rects: List[Tuple[int, int, Any]]) -> Tuple[List[Dict[str, Any]], int, int]:
    """
    Pack rectangles into the smallest power-of-2 atlas.
    
    Args:
        rects: List of (width, height, id) tuples
        
    Returns:
        Tuple of:
        - List of dicts with keys 'id', 'x', 'y', 'width', 'height'
        - Atlas width
        - Atlas height
    """
    if not rects:
        return [], 16, 16
        
    # Sort by height (tallest first)
    # rects[1] is height
    sorted_rects = sorted(rects, key=lambda r: (r[1], r[0]), reverse=True)
    
    min_size = 16
    max_size = 8192
    
    # Calculate simple area lower bound
    total_area = sum(r[0] * r[1] for r in rects)
    min_dim = math.ceil(math.sqrt(total_area))
    start_size = max(min_size, next_power_of_2(min_dim))
    
    # Also verify simplest single rect fit
    max_w = max(r[0] for r in rects)
    max_h = max(r[1] for r in rects)
    start_size = max(start_size, next_power_of_2(max(max_w, max_h)))
    
    atlas_size = start_size
    
    while atlas_size <= max_size:
        packer = ShelfPacker(atlas_size, atlas_size)
        packed_results = []
        all_fit = True
        
        for w, h, rid in sorted_rects:
            pos = packer.pack(w, h)
            if pos:
                packed_results.append({
                    'id': rid,
                    'x': pos[0],
                    'y': pos[1],
                    'width': w,
                    'height': h
                })
            else:
                all_fit = False
                break
        
        if all_fit:
            return packed_results, atlas_size, atlas_size
            
        atlas_size *= 2
        
    raise RuntimeError(f"Could not pack rectangles into atlas up to {max_size}x{max_size}")
