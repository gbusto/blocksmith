"""
Python Code → v3 Schema Importer

Imports Python code using the modeling API to v3 schema format.
"""

from typing import Dict, Any, Union, Optional, List
from pathlib import Path
import logging
import sys
import os
import json
import traceback
import math
import random
import itertools
from collections import defaultdict, deque
from pydantic import ValidationError

# Import centralized rotation utilities and models
from blocksmith.converters.rotation_utils import euler_to_quaternion
from blocksmith.schema.blockjson import Entity, CuboidEntity, GroupEntity, MetaModel, ModelDefinition

logger = logging.getLogger(__name__)


class SafeImporter:
    """Handles safe importing of whitelisted modules."""
    
    # Whitelist of safe modules that LLMs can import
    SAFE_MODULES = {
        'math': math,
        'random': random,
        'itertools': itertools,
        'collections': {'defaultdict': defaultdict, 'deque': deque},
    }
    
    def __init__(self):
        self.imported_modules = {}
    
    def safe_import(self, name, *args, **kwargs):
        """Safe import function that only allows whitelisted modules."""
        if name in self.SAFE_MODULES:
            module = self.SAFE_MODULES[name]
            self.imported_modules[name] = module
            return module
        else:
            raise ImportError(f"Import of '{name}' is not allowed for security reasons. "
                            f"Allowed modules: {list(self.SAFE_MODULES.keys())}")


class PythonExecutor:
    """Executes Python code safely and extracts entities."""
    
    def __init__(self):
        self.safe_importer = SafeImporter()
        
        # Helper functions for entity creation
        def cuboid(id, *args, **kwargs):
            """Create a cuboid entity."""
            # Extract arguments
            corner = None
            position = None
            size = kwargs.pop('size', None)
            
            # Handle positional arguments
            if len(args) == 2:
                corner, size = args
            elif len(args) == 1:
                size = args[0]
            
            # Handle keyword arguments
            corner = kwargs.pop('corner', corner)
            position = kwargs.pop('position', position)
            
            if size is None:
                raise ValueError("'size' is required for cuboid()")
            
            # Extract v3 extended features first (before calculating from/to)
            label = kwargs.pop('label', id)
            pivot = kwargs.pop('pivot', [0, 0, 0])
            rotation = kwargs.pop('rotation', [0, 0, 0])
            scale = kwargs.pop('scale', [1, 1, 1])
            parent = kwargs.pop('parent', None)
            
            # Calculate from/to based on what was provided
            if corner is not None:
                # Corner mode: from/to are relative to pivot
                # corner = from + pivot, so from = corner - pivot
                from_ = [corner[i] - pivot[i] for i in range(3)]
                to = [from_[i] + size[i] for i in range(3)]
            elif position is not None:
                # Position mode: position is center, calculate from/to relative to pivot
                from_ = [position[i] - size[i]/2 - pivot[i] for i in range(3)]
                to = [position[i] + size[i]/2 - pivot[i] for i in range(3)]
            else:
                raise ValueError("Either 'corner' or 'position' must be supplied for cuboid()")
            
            # Convert Euler rotation to quaternion using centralized utilities
            quat_rotation = euler_to_quaternion(rotation)
            
            # Generate placeholder face textures (all using 'main' atlas)
            faces = {}
            for face in ['front', 'back', 'left', 'right', 'top', 'bottom']:
                faces[face] = {
                    'atlas_id': 'main',
                    'uv': [0.0, 0.0, 1.0, 1.0]  # Full texture for now
                }
            
            return {
                'id': id,
                'type': 'cuboid',
                'label': label,
                'parent': parent,
                'pivot': pivot,
                'rotation': quat_rotation,
                'scale': scale,
                'from': from_,
                'to': to,
                'faces': faces,
                'inflate': 0.0,
            }
        
        def group(id, position=None, **kwargs):
            """Create a group entity."""
            position = position or [0, 0, 0]
            label = kwargs.pop('label', id)
            
            # v3 extended features
            pivot = kwargs.pop('pivot', position)
            rotation = kwargs.pop('rotation', [0, 0, 0])
            scale = kwargs.pop('scale', [1, 1, 1])
            parent = kwargs.pop('parent', None)
            
            # Convert Euler rotation to quaternion using centralized utilities
            quat_rotation = euler_to_quaternion(rotation)
            
            return {
                'id': id,
                'type': 'group',
                'label': label,
                'parent': parent,
                'pivot': pivot,
                'rotation': quat_rotation,
                'scale': scale,
            }
        
        # Store functions as instance variables so they can be referenced in safe_globals
        self.cuboid = cuboid
        self.group = group
        
        # Create safe execution environment
        self.safe_globals = {
            '__builtins__': {
                # Basic types and operations
                'list': list, 'dict': dict, 'tuple': tuple, 'set': set,
                'len': len, 'range': range, 'enumerate': enumerate,
                'zip': zip, 'reversed': reversed, 'sorted': sorted,
                'sum': sum, 'any': any, 'all': all, 'filter': filter, 'map': map,
                'min': min, 'max': max, 'abs': abs, 'round': round,
                'float': float, 'int': int, 'str': str, 'bool': bool,
                'True': True, 'False': False, 'None': None,
                'isinstance': isinstance, 'type': type,
                '__import__': self.safe_importer.safe_import,
            },
            # Helper functions
            'cuboid': self.cuboid,
            'group': self.group,
            'UNIT': 1.0 / 16,
            # Pre-imported common modules
            'math': math,
            'random': random,
            'itertools': itertools,
            'defaultdict': defaultdict,
            'deque': deque,
        }
    
    def execute_python_code(self, code: str) -> List[Dict[str, Any]]:
        """Execute Python code and extract entities."""
        try:
            local_namespace = {}
            exec(code, self.safe_globals, local_namespace)
            
            # Try to find entities
            entities = None
            
            # Method 1: Look for 'entities' variable
            if 'entities' in local_namespace:
                entities = local_namespace['entities']
            # Method 2: Look for 'create_model()' function
            elif 'create_model' in local_namespace:
                entities = local_namespace['create_model']()
            # Method 3: Look for any function that returns a list
            else:
                for name, obj in local_namespace.items():
                    if callable(obj) and not name.startswith('_'):
                        try:
                            result = obj()
                            if isinstance(result, list):
                                entities = result
                                break
                        except:
                            continue
            
            if entities is None:
                raise ValueError("No entities found. Code should define 'entities' variable or 'create_model()' function.")
            
            if not isinstance(entities, list):
                raise ValueError(f"Entities must be a list, got {type(entities)}")
            
            if not entities:
                raise ValueError("Entities list is empty")
            
            return entities
            
        except Exception as e:
            logger.error(f"Error executing Python code: {e}")
            logger.error("Traceback:", exc_info=True)
            raise


def import_python(
    python_code: str,
) -> Dict[str, Any]:
    """
    Import Python code to v3 schema.
    
    Args:
        code: Python code
    
    Returns:
        Dict[str, Any]: v3 schema dictionary
        
    Raises:
        SyntaxError: If Python code has syntax errors
        RuntimeError: If code execution fails
    """
    try:
        # Execute Python code to get entities
        executor = PythonExecutor()
        entity_dicts = executor.execute_python_code(python_code)
        
        # Validate entities
        entities = []
        for entity_dict in entity_dicts:
            # Fill in defaults
            entity_dict.setdefault('parent', None)
            entity_dict.setdefault('pivot', [0, 0, 0])
            entity_dict.setdefault('rotation', [1, 0, 0, 0])
            entity_dict.setdefault('scale', [1, 1, 1])
            
            # Validate based on type
            entity_type = entity_dict.get('type')
            if entity_type == 'cuboid':
                entity = CuboidEntity(**entity_dict)
            elif entity_type == 'group':
                entity = GroupEntity(**entity_dict)
            else:
                raise ValueError(f"Unknown entity type: {entity_type}")
            
            entities.append(entity)
        
        # Create full model definition with required atlases
        meta = MetaModel(
            atlases={"main": {
                "data": "",  # Empty texture data for Python models
                "mime": "image/png",
                "resolution": [16, 16]
            }}
        )
        model_def = ModelDefinition(
            meta=meta,
            entities=entities,
            animations=None
        )
        
        # Convert to dict
        json_data = model_def.model_dump(exclude_none=False, by_alias=True)

        return json_data

    except Exception as e:
        logger.error(f"Error importing Python code: {e}")
        return {}

def import_python_from_file(
    file_path: Union[str, Path], 
    options: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Import Python code to v3 schema.
    
    Args:
        file_path: Path to .py file
        options: Import options (currently unused)
    
    Returns:
        Dict[str, Any]: v3 schema dictionary
        
    Raises:
        FileNotFoundError: If input file doesn't exist
        SyntaxError: If Python code has syntax errors
        RuntimeError: If code execution fails
    """
    if options is None:
        options = {}
    
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Python file not found: {file_path}")
    
    logger.info(f"Importing Python code from {file_path}")
    
    # Read the Python code
    with open(file_path, 'r', encoding='utf-8') as f:
        python_code = f.read()
    
    model_json = import_python(python_code)

    if not model_json:
        raise Exception("Error generating v3 schema from Python code")

    return model_json
