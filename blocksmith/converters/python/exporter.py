"""
v3 Schema → Python Code Exporter

Exports v3 schema to Python code using the modeling API.
Uses centralized rotation utilities for consistent quaternion/Euler conversions.
"""

from typing import Dict, Any, Union, Optional, List
from pathlib import Path
import logging
import json

# Import centralized rotation utilities
from blocksmith.converters.rotation_utils import quaternion_to_euler, is_gimbal_lock
from blocksmith.schema.blockjson import ModelDefinition, CuboidEntity, GroupEntity

logger = logging.getLogger(__name__)


def format_number(n: float) -> str:
    """Format a number for clean Python code output."""
    # Use 4 decimal places for good balance between accuracy and learnability
    n = round(n, 4)
    if abs(n - round(n)) < 0.0001:
        return str(int(round(n)))
    # Format with up to 4 decimal places, removing trailing zeros
    s = f"{n:.4f}".rstrip('0').rstrip('.')
    return s


def format_list(lst: List[float]) -> str:
    """Format a list of numbers for Python code."""
    return f"[{', '.join(format_number(x) for x in lst)}]"


def is_default_value(value: Any, default: Any) -> bool:
    """Check if a value is the default (accounting for float precision)."""
    if isinstance(value, list) and isinstance(default, list):
        if len(value) != len(default):
            return False
        # Use tighter tolerance to match higher precision output
        return all(abs(v - d) < 1e-10 for v, d in zip(value, default))
    return value == default


class V3ToPythonConverter:
    """Converts v3 schema to Python code using centralized rotation utilities."""
    
    def __init__(self):
        self.entities: List[Any] = []
        self.entity_map: Dict[str, Any] = {}
        self.root_entities: List[str] = []
        self.code_lines: List[str] = []
        
    def convert(self, schema_data: Dict[str, Any]) -> str:
        """
        Convert v3 schema to Python code.
        
        Args:
            schema_data: v3 schema dictionary
            
        Returns:
            Python code string
        """
        # Validate and parse
        model = ModelDefinition.model_validate(schema_data)
        
        # Build entity map and find roots
        self._build_entity_map(model.entities)
        
        # Generate code
        self._generate_header()
        self._generate_entities()
        self._generate_footer()
        
        return '\n'.join(self.code_lines)
    
    def _build_entity_map(self, entities: List[Any]) -> None:
        """Build entity lookup map and identify root entities."""
        for entity in entities:
            self.entity_map[entity.id] = entity
            if entity.parent is None:
                self.root_entities.append(entity.id)
    
    def _generate_header(self) -> None:
        """Generate Python code header."""
        self.code_lines.extend([
            '"""',
            'Generated from v3 schema using centralized rotation utilities',
            'Uses XYZ Euler order for consistent, LLM-friendly rotations',
            '"""',
            '',
            'UNIT = 0.0625',
            '',
            'def create_model():',
            '    return ['
        ])
    
    def _generate_footer(self) -> None:
        """Generate Python code footer."""
        # Remove trailing comma from last line if present
        if self.code_lines[-1].endswith(','):
            self.code_lines[-1] = self.code_lines[-1][:-1]
        
        self.code_lines.extend([
            '    ]'
        ])
    
    def _generate_entities(self) -> None:
        """Generate entities in dependency order (parents before children)."""
        processed = set()
        
        def process_entity(entity_id: str, indent: int = 8) -> None:
            if entity_id in processed:
                return
            
            entity = self.entity_map[entity_id]
            
            # Process parent first if it exists
            if entity.parent and entity.parent not in processed:
                process_entity(entity.parent, indent)
            
            # Generate code for this entity
            if entity.type == 'cuboid':
                self._generate_cuboid(entity, indent)
            elif entity.type == 'group':
                self._generate_group(entity, indent)
            
            processed.add(entity_id)
            
            # Process children
            for child_id, child in self.entity_map.items():
                if child.parent == entity_id:
                    process_entity(child_id, indent)
        
        # Start with root entities
        for root_id in self.root_entities:
            process_entity(root_id)
    
    def _generate_cuboid(self, entity: CuboidEntity, indent: int) -> None:
        """Generate cuboid() call using centralized rotation utilities."""
        spaces = ' ' * indent
        
        # Calculate corner from from/to and pivot
        corner = [entity.from_[i] + entity.pivot[i] for i in range(3)]
        size = [entity.to[i] - entity.from_[i] for i in range(3)]
        
        # Start building the call
        args = [f'"{entity.id}"', f'corner={format_list(corner)}', f'size={format_list(size)}']
        
        # Add optional parameters only if non-default
        if entity.label != entity.id:
            args.append(f'label="{entity.label}"')
        
        if not is_default_value(entity.pivot, [0, 0, 0]):
            args.append(f'pivot={format_list(entity.pivot)}')
        
        # Convert quaternion to Euler using centralized utilities
        if not is_default_value(entity.rotation, [1, 0, 0, 0]):
            euler = quaternion_to_euler(entity.rotation)
            # Always include rotation if quaternion is not identity
            # Even if Euler angles are very small, they're still important!
            args.append(f'rotation={format_list(euler)}')
            
            # Add warning comment if near gimbal lock
            if is_gimbal_lock(euler):
                self.code_lines.append(f'{spaces}# WARNING: Near gimbal lock - rotation may have multiple representations')
        
        if not is_default_value(entity.scale, [1, 1, 1]):
            args.append(f'scale={format_list(entity.scale)}')
        
        if entity.parent:
            args.append(f'parent="{entity.parent}"')
        
        # Format the call
        if len(args) <= 3:
            # Single line for simple cuboids
            self.code_lines.append(f'{spaces}cuboid({", ".join(args)}),')
        else:
            # Multi-line for complex cuboids
            self.code_lines.append(f'{spaces}cuboid(')
            for i, arg in enumerate(args):
                line = f'{spaces}    {arg}'
                if i < len(args) - 1:
                    line += ','
                self.code_lines.append(line)
            self.code_lines.append(f'{spaces}),')
    
    def _generate_group(self, entity: GroupEntity, indent: int) -> None:
        """Generate group() call using centralized rotation utilities."""
        spaces = ' ' * indent
        
        # Start building the call
        args = [f'"{entity.id}"']
        
        # Add optional parameters only if non-default
        if entity.label != entity.id:
            args.append(f'label="{entity.label}"')
        
        if not is_default_value(entity.pivot, [0, 0, 0]):
            args.append(f'pivot={format_list(entity.pivot)}')
        
        # Convert quaternion to Euler using centralized utilities
        if not is_default_value(entity.rotation, [1, 0, 0, 0]):
            euler = quaternion_to_euler(entity.rotation)
            # Always include rotation if quaternion is not identity
            # Even if Euler angles are very small, they're still important!
            args.append(f'rotation={format_list(euler)}')
            
            # Add warning comment if near gimbal lock
            if is_gimbal_lock(euler):
                self.code_lines.append(f'{spaces}# WARNING: Near gimbal lock - rotation may have multiple representations')
        
        if not is_default_value(entity.scale, [1, 1, 1]):
            args.append(f'scale={format_list(entity.scale)}')
        
        if entity.parent:
            args.append(f'parent="{entity.parent}"')
        
        # Format the call
        if len(args) <= 2:
            # Single line for simple groups
            self.code_lines.append(f'{spaces}group({", ".join(args)}),')
        else:
            # Multi-line for complex groups
            self.code_lines.append(f'{spaces}group(')
            for i, arg in enumerate(args):
                line = f'{spaces}    {arg}'
                if i < len(args) - 1:
                    line += ','
                self.code_lines.append(line)
            self.code_lines.append(f'{spaces}),')


def export_python(
    v3_data: Dict[str, Any],
    output_path: Union[str, Path],
    options: Dict[str, Any] = None
) -> str:
    """
    Export v3 schema to Python code.
    
    Args:
        v3_data: v3 schema dictionary
        output_path: Path to output .py file
        options: Export options (currently unused)
    
    Returns:
        str: Path to the exported file
        
    Raises:
        ValueError: If v3 data is invalid
        IOError: If file writing fails
    """
    if options is None:
        options = {}
    
    output_path = Path(output_path)
    
    logger.info(f"Exporting v3 schema to Python: {output_path}")
    
    try:
        # Convert to Python code
        converter = V3ToPythonConverter()
        python_code = converter.convert(v3_data)
        
        # Write to file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(python_code)
        
        logger.info(f"Successfully exported Python code to {output_path}")
        return str(output_path)
        
    except Exception as e:
        logger.error(f"Failed to export Python code: {e}")
        raise