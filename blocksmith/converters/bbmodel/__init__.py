"""
BBModel ↔ v3 Schema Converters

Format-specific import/export functions for Blockbench .bbmodel files.
These handle the direct conversion between BBModel JSON and v3 schema,
focused on lossless round-trips with minimal metadata.
"""

from .importer import import_bbmodel
from .exporter import export_bbmodel

__all__ = ['import_bbmodel', 'export_bbmodel']