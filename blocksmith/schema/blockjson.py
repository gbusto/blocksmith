"""
v3 Schema: Universal 3D Model Format

COORDINATE SYSTEM:
Right-handed, Y-up coordinate system

Camera Position:
- Camera is positioned along -Z axis, looking towards +Z
- Camera faces the model's +Z face (front)

Model Orientation:
- +X = East = Model's RIGHT side (camera's left when viewing)
- -X = West = Model's LEFT side (camera's right when viewing)  
- +Y = Up = Model's TOP
- -Y = Down = Model's BOTTOM
- +Z = North = Model's FRONT (facing camera)
- -Z = South = Model's BACK (away from camera)

Blockbench Alignment:
- +X matches Blockbench's East
- -X matches Blockbench's West
- +Y matches Blockbench's Up
- -Y matches Blockbench's Down
- +Z matches Blockbench's North
- -Z matches Blockbench's South

UNITS:
- 1.0 v3 unit = 1 Minecraft block = 16 pixels (normalized)
- Position/size coordinates are converted to this normalized system
- Scale factors remain dimensionless multipliers (no normalization)

UNIT CONVERSIONS:
- BBModel/Bedrock: pixel_value / 16.0 → v3_coordinate
- GLTF: meter_value → v3_coordinate (1 block = 1 meter)
- Scale: always 1:1 across all formats (dimensionless multiplier)

EXAMPLES:
- BBModel 32px → v3 2.0 coordinate
- BBModel scale 1.5 → v3 scale 1.5 (unchanged)
- GLTF 0.5m → v3 0.5 coordinate  
- GLTF scale 2.0 → v3 scale 2.0 (unchanged)

DESIGN PHILOSOPHY:
The v3 schema prioritizes PRESERVATION of source structure over normalization.

Import/Export Behavior:
- Importers faithfully preserve the hierarchy and structure of the source format
- No assumptions are made about future export targets
- Cross-format differences are expected and documented

Examples:
- BBModel → v3 → GLTF: May add scene nodes required by GLTF format
- GLTF → v3 → BBModel: Preserves GLTF scene nodes even if not typical in BBModel
- Roundtrips are lossless: Format → v3 → Same Format produces identical structure

This ensures users can trust that their model structure won't be modified unexpectedly,
while enabling clean cross-format conversion when deliberately chosen.

FORMAT-SPECIFIC COORDINATE SYSTEMS:

BBModel (Blockbench):
- Stores geometry in WORLD coordinates (pixels)
- Groups have origin/rotation that affect children
- Elements have from/to coords + origin/rotation + optional inflate
- Coordinate system: Y-up, with custom Z handling
- Storage: {"from": [x1,y1,z1], "to": [x2,y2,z2], "origin": [px,py,pz], "inflate": n}

GLTF 2.0:
- Stores geometry in LOCAL coordinates (meters/units)
- Hierarchical node transforms (Translation * Rotation * Scale)
- Meshes have vertices in model space, positioned by node transforms
- Coordinate system: Y-up, right-handed
- Storage: nodes with TRS + mesh primitives with vertex arrays

Bedrock (planned):
- Similar to BBModel but different coordinate conventions
- Uses pivot-based transforms
- Different rotation order and scaling approach

Conversion Implications:
- BBModel→v3: Convert world coords to local relative to pivot, handle inflate
- GLTF→v3: Use node local transforms directly, extract cuboids from mesh vertices
- v3→BBModel: Convert local coords back to world, recreate inflate if needed
- v3→GLTF: Use transforms as node TRS, generate mesh vertices from cuboid bounds
"""

from __future__ import annotations
from enum import Enum
from typing import List, Optional, Union, Literal, Dict, Any
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
import re

# Type aliases for better readability
Vec3 = List[float]
Quat4 = List[float]  # [w, x, y, z] for rotations (lossless)

#########################
# ENTITY MODELS
#########################

class BaseEntity(BaseModel):
    """
    Base class for all entities in the 3D scene graph.
    
    IMPORTANT: All coordinates and transforms are LOCAL (relative to parent entity).
    This preserves hierarchical relationships and enables lossless format conversion.
    
    Minimal fields for import compatibility. No joint fields—retrofitting via hierarchy rebuild.
    """
    model_config = ConfigDict(extra='forbid')

    id: str = Field(..., description="Unique identifier.")
    label: str = Field(..., description="Human-readable name.")
    parent: Optional[str] = Field(None, description="Parent ID or None for root.")
    pivot: Vec3 = Field(default=[0, 0, 0], description="LOCAL pivot point relative to parent (translation in parent space).")
    rotation: Quat4 = Field(default=[1, 0, 0, 0], description="LOCAL rotation relative to parent as quaternion [w, x, y, z].")
    scale: Vec3 = Field(default=[1, 1, 1], description="LOCAL scale relative to parent.")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Source-specific data for lossless round-trips (e.g., {'bbmodel': {...}, 'original_euler': [rx, ry, rz]}).")

class FaceEnum(str, Enum):
    front = "front"
    back = "back"
    left = "left"
    right = "right"
    top = "top"
    bottom = "bottom"

class FaceTexture(BaseModel):
    atlas_id: str = Field(..., description="Atlas ID from meta.atlases for this face.")
    uv: List[float] = Field(..., description="[u1, v1, u2, v2] normalized (0-1).", min_length=4, max_length=4)

class CuboidEntity(BaseEntity):
    type: Literal['cuboid'] = 'cuboid'
    from_: Vec3 = Field(..., alias='from', description="LOCAL min corner relative to entity pivot [x, y, z].")
    to: Vec3 = Field(..., description="LOCAL max corner relative to entity pivot [x, y, z].")
    faces: Dict[FaceEnum, FaceTexture] = Field(..., description="Per-face texture definitions (inline for direct association with geometry).")
    inflate: float = Field(default=0.0, description="""
        Uniform expansion in blocks (BBModel/Bedrock only).
        
        IMPORTANT: This is NOT the same as scale!
        - Inflate is ADDITIVE: adds value to each face
        - Scale is MULTIPLICATIVE: multiplies size
        - Inflate can turn zero-thickness into non-zero
        - Scale cannot (0 × anything = 0)
        
        Import behavior:
        - BBModel/Bedrock: Stored separately, not baked into from/to
        - GLTF: Always 0 (uses scale instead, which we bake into geometry)
        
        Export behavior:
        - To BBModel/Bedrock: Applied as native inflate property
        - To GLTF: Baked into vertex positions
    """)

    @model_validator(mode='after')
    def validate_bounds(self):
        size = [self.to[i] - self.from_[i] for i in range(3)]
        if any(s < 0 for s in size):
            raise ValueError("'to' must be >= 'from' in all dimensions")
        return self

    @field_validator('faces')
    @classmethod
    def validate_faces(cls, v):
        if set(v.keys()) != set(FaceEnum):
            raise ValueError("Must define all six faces")
        return v

class GroupEntity(BaseEntity):
    type: Literal['group'] = 'group'

Entity = Union[CuboidEntity, GroupEntity]

#########################
# ATLAS
#########################

class AtlasDefinition(BaseModel):
    data: str = Field(..., description="Base64-encoded image data.")
    mime: str = Field(..., description="MIME type (e.g., 'image/png').")
    resolution: List[int] = Field(..., description="[width, height] pixels.", min_length=2, max_length=2)

#########################
# ANIMATION MODELS
#########################

class Channel(BaseModel):
    """
    A single animation channel targeting a property on an entity.
    """
    target_id: str = Field(..., description="Entity ID to animate (cuboid or group).")
    property: Literal['position', 'rotation', 'scale'] = Field(..., description="Property to animate.")
    interpolation: Literal['linear', 'step', 'cubic'] = Field('linear', description="Interpolation between keyframes.")
    frames: List[Dict[str, Any]] = Field(..., description="Keyframes: [{'time': int (absolute ticks from 0), 'value': Vec3 or Quat4}] (max 128).")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Source extras (e.g., {'bedrock_expression': 'math.sin(...)'}, GLTF tangents).")

    @field_validator('frames')
    @classmethod
    def validate_frames(cls, v, info):
        if len(v) > 128:
            raise ValueError("Max 128 keyframes per channel")
        prev_time = -1
        property = info.data.get('property')
        for kf in v:
            if 'time' not in kf or 'value' not in kf:
                raise ValueError("Each frame must have 'time' and 'value'")
            time = kf['time']
            value = kf['value']
            if not isinstance(time, int) or time <= prev_time:
                raise ValueError("Times must be increasing integers")
            if property == 'rotation':
                if not (isinstance(value, list) and len(value) == 4):
                    raise ValueError("Rotation values must be Quat4 [w, x, y, z]")
            else:
                if not (isinstance(value, list) and len(value) == 3):
                    raise ValueError("Position/scale values must be Vec3 [x, y, z]")
            prev_time = time
        return v

class Animation(BaseModel):
    """
    A single animation clip containing channels.
    """
    name: str = Field(..., description="Animation name (e.g., 'walk').")
    duration: float = Field(..., description="Total duration in seconds (or ticks).")
    loop_mode: Optional[Literal['once', 'repeat', 'pingpong']] = Field('repeat', description="Playback mode.")
    channels: List[Channel] = Field(..., description="Channels in this animation.")

#########################
# TOP-LEVEL MODELS
#########################

class MetaModel(BaseModel):
    model_config = ConfigDict(extra='forbid')

    schema_version: str = Field('3.0', description="Schema version.")
    fps: int = Field(24, description="Animation ticks per second.")
    texel_density: int = Field(16, description="Pixels per unit for scaling.")
    atlases: Dict[str, AtlasDefinition] = Field(..., description="Embedded atlases (at least one, e.g., 'main').")
    import_source: Optional[Literal['bbmodel', 'gltf', 'bedrock']] = Field(None, description="Source for round-trips.")

class ModelDefinition(BaseModel):
    model_config = ConfigDict(extra='forbid')

    meta: MetaModel
    entities: List[Entity]
    animations: Optional[List[Animation]] = Field(None, description="Optional animations (keyframe-based; expressions in metadata).")

# Rebuild models for forward references
BaseEntity.model_rebuild()
CuboidEntity.model_rebuild()
GroupEntity.model_rebuild()
Channel.model_rebuild()
Animation.model_rebuild()
MetaModel.model_rebuild()
ModelDefinition.model_rebuild()