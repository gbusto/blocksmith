# Python Entity Generation Guide V2 - Ultra-Concise Edition

## Overview
This is the streamlined, ultra-token-efficient version using pythonic helper functions and patterns. **Focus on clean attachments between cuboids and avoiding z-fighting where faces meet.**

⚠️ **Z-fighting prevention:** When cuboids share faces or edges, ensure they align properly to avoid visual flickering. Offset overlapping faces by at least 0.001 units. Better yet, design your model so faces connect cleanly without overlapping.

### 🔗 Proper Attachment Rules - CRITICAL

**Parts must attach face-to-face, NOT be embedded inside each other!**

When attaching parts (windows, doors, handles, decorations), connect opposing faces with minimal gap (0.001-0.002 units):
- Window's **-X** face → Wall's **+X** face (window ON the wall, not IN it)
- Handle's **+Y** face → Body's **-Y** face (handle UNDER the body, not INSIDE it)
- Door's **-Z** face → Wall's **+Z** face (door IN FRONT of wall, not EMBEDDED)

**❌ WRONG - Embedded Parts:**
```python
# BAD: Window embedded in wall (same X position = overlapping)
wall = cuboid("wall", [2,1,0], [0.25,2,4])
window = cuboid("window", [2,1.5,0], [0.25,1,1])  # Same X as wall = EMBEDDED!

# BAD: Handle inside rifle body (same width, partial overlap)
body = cuboid("body", [0,1,0], [0.5,0.25,2])
handle = cuboid("handle", [0,0.875,0.5], [0.5,0.5,0.25])  # Same X width = OVERLAPPING!
```

**✅ CORRECT - Clean Attachments:**
```python
# GOOD: Window attached to wall surface
wall = cuboid("wall", [2,1,0], [0.25,2,4])  # Wall X: 2 to 2.25
window = cuboid("window", [2.251,1.5,0], [0.125,1,1])  # Window starts at 2.251

# GOOD: Handle attached below rifle body  
body = cuboid("body", [0,1,0], [0.5,0.25,2])  # Body Y: 1.0 to 1.25
handle = cuboid("handle", [0,0.499,0.5], [0.3,0.5,0.25])  # Handle top at 0.999
```

### ⚙️ Core Modeling API

These are the *only* functions you need to create a model.  All positions are **absolute world coordinates** measured from the model's global origin, and they are **corner-based** (back-bottom-left corner of each cuboid).

⚠️ **CRITICAL: Joint Usage** – **DO NOT** use `joint_name` or `joint_offset` unless animation is explicitly required.  Ninety-nine percent of models should have *zero* joints; use `group()` for organisation instead.

```python
UNIT = 0.0625  # 1 pixel

def cuboid(id, corner, size, **kwargs):
    """Create a cuboid by its MIN corner (absolute world coords)."""
    centre = [corner[i] + size[i] / 2 for i in range(3)]
    return dict(id=id, type="cuboid", position=centre, size=size,
                label=kwargs.get('label', id), shape="box", **kwargs)


def group(id, position=None, **kwargs):
    """Create an organizational group. Primarily meant for hierarchy, not animation"""
    return dict(id=id, type="group", position=position or [0, 0, 0],
                label=kwargs.get('label', id), **kwargs)


def joint(id, corner, size, joint_name, joint_offset=[0, 0, 0], **kwargs):
    """Similar to groups, except this should be used **only** when animation is requested. These should be targeted by animations."""
    return cuboid(id, corner, size, joint_name=joint_name,
                  joint_offset=joint_offset, **kwargs)
```

**Do NOT** redefine these helpers. `UNIT` constant is also pre-imported.

## Important Coordinate System & Positioning

### 🎯 Camera Orientation
The camera is assumed to be looking in the **-Z direction**:
- **+Z is "front"** - the face directly in front of the camera (closest to viewer)
- **-Z is "back"** - the opposite face (away from camera, can't be seen)
- **+X is model's "right" side** – appears on the **left** of the screen
- **-X is model's "left" side**  – appears on the **right** of the screen
- **+Y is top**, **-Y is bottom**

### 📍 Absolute Positioning (corner-based)
**NEW RULE**: A cuboid's `position` is the **bottom-left-back corner** (minimum X, minimum Y, minimum Z).  The helper automatically converts this to a centre for the internal schema – so what you type is what gets built.

**Clean attachments:** When cuboids connect, ensure their faces align properly to prevent gaps or overlaps. Using 1⁄16-block increments (0.0625) for sizes and positions often helps achieve this, but feel free to deviate for artistic effect or better visual results.

```python
# 2×2×2 cube sitting on ground, corner at origin
cube = cuboid("cube", [0, 0, 0], [0.125, 0.125, 0.125])  # 2 px each side

# Stack another cube directly on top – simply add previous height to Y
cube_top = cuboid("cube_top", [0, 0.125, 0], [0.125, 0.125, 0.125])
```

### ⚖️ Symmetry & Clean Alignment

When centering child cuboids on their parents (e.g. a head on a torso), consider:

1. **Even differences**: If the parent is 6 pixels wide and child is 4 pixels wide, they'll center naturally with clean edges.
2. **Odd differences**: If sizes differ by an odd number of pixels, you may need to offset slightly to keep one face flush.
3. **Offset parts**: Elements like ears, shoulder pads, or antennas don't need perfect centering since they're intentionally positioned to one side.

The key is ensuring faces that should connect actually touch without gaps or overlaps.

### 📝 Plan Before You Build
Before you write any `cuboid()` or `group()` calls, take one pass to *think*:
1. List every major part you will need (torso, head, barrel, stock, wheels, etc.).
2. Decide the overall **scale** (total height/length/depth) and jot down each part's size *relative* to that scale.
3. Compute key joint or attachment positions (e.g. where the barrel meets the receiver, where the head touches the neck).
4. Only after this quick outline should you start emitting code—this guarantees consistent proportions and prevents last-second "guess" numbers that create gaps or odd rotations.

# Good – positions are absolute world coordinates with clean connections
return [
    group("arm_group", [2, 1, 0]),           # Group at world position [2,1,0]
    cuboid("upper_arm", [2, 1.5, 0], ...)    # Block at [2,1.5,0]
]

# Avoid – relative positioning won't work; always use absolute world coordinates
return [
    group("arm_group", [2, 1, 0]),
    cuboid("upper_arm", [0, 0.1, 0], ...)    # WRONG: 0.1 not 1/16-aligned!
]
```

Even with parent-child relationships, you specify where you want things in world space.

### 🧭 Orientation Examples

```python
# Character facing the camera (+Z forward)
def create_character():
    return [
        cuboid("body", [-0.5,1,-0.25], [1,2,0.5], material="mat-body"),      # Body centered at origin
        cuboid("head", [-0.375,3.001,-0.375], [0.75,0.75,0.75], material="mat-skin"),  # Head on top of body
        cuboid("right_arm", [0.501,1.25,-0.1875], [0.5,1.5,0.375], material="mat-body"),   # Right arm attached to body
        cuboid("left_arm", [-1.001,1.25,-0.1875], [0.5,1.5,0.375], material="mat-body")  # Left arm attached to body
    ]

# Building with front door facing camera (demonstrating proper attachments)
def create_house():
    return [
        cuboid("front_wall", [0,1,2], [6,2,0.25], material="mat-brick"),     # Front wall Z: 2 to 2.25
        cuboid("door", [0,0.875,2.251], [1,1.75,0.125], material="mat-wood"), # Door starts at Z=2.251
        cuboid("back_wall", [0,1,-2], [6,2,0.25], material="mat-brick"),     # -Z = back wall
        cuboid("left_wall", [3,1,0], [0.25,2,4], material="mat-brick"),      # Left wall X: 3 to 3.25
        cuboid("window_left", [3.251,1.5,0], [0.125,1,1], material="mat-glass"), # Window starts at X=3.251
        cuboid("right_wall", [-3,1,0], [0.25,2,4], material="mat-brick")     # -X = right wall
    ]
```

### 📐 Quick Reference - Camera View

```
    Camera looking at model from -Z direction:
    
         +Y (up)
          ↑
          |
    +X ←--+--→ -X  
         /|    (model's **right**, appears left to camera)
        / |
       ↙  ↓
     +Z   -Y (down)
   (front)
   
    -Z (back, away from camera)
```

**Remember**: For semantic naming, **right arm = +X**, **left arm = -X**.

## Ultra-Concise Patterns

### Simple Stack (Before vs After)

**Before** (verbose):
```python
entities = []
entities.append({
    "id": "base",
    "type": "cuboid", 
    "position": [0, 0, 0],
    "size": [2, 1, 2],
    "material": "mat-stone"
})
entities.append({
    "id": "top", 
    "type": "cuboid",
    "position": [0, 1, 0], 
    "size": [1, 1, 1],
    "material": "mat-gold"
})
return entities
```

**After** (concise, 1/16-aligned):
```python
return [
    cuboid("base", [0,0,0], [2,1,2], material="mat-stone"),
    cuboid("top", [0,1,0], [1,1,1], material="mat-gold")
]
```

### Character with Joints

**Ultra-concise character (static)**:
```python
def create_model():
    return [
        group("body"),
        cuboid("torso", [0,1,0], [1.25,1.75,0.625], parent="body", material="mat-shirt"),
        cuboid("head", [0,2.375,0], [0.75,0.75,0.75], parent="body", material="mat-skin"),
        # Arms – RIGHT arm on +X, LEFT arm on -X
        cuboid("right_arm", [0.875,1.5,0], [0.375,1.25,0.375], parent="body", material="mat-shirt"),
        cuboid("left_arm", [-0.875,1.5,0], [0.375,1.25,0.375], parent="body", material="mat-shirt"),
        # Legs
        cuboid("right_leg", [0.25,-0.625,0], [0.375,1.25,0.375], parent="body", material="mat-pants"),
        cuboid("left_leg", [-0.25,-0.625,0], [0.375,1.25,0.375], parent="body", material="mat-pants")
    ]
```

### Programmatic Generation

**Repetitive structures with loops** (1/16-aligned):
```python
def create_model():
    parts = []
    
    # Foundation
    parts.append(cuboid("foundation", [0,-0.125,0], [6,0.25,4], material="mat-concrete"))
    
    # Walls using list comprehension
    wall_specs = [
        ("front_left", [-1.5,1,2], [1.5,2,0.25]),
        ("front_right", [1.5,1,2], [1.5,2,0.25]),
        ("back_left", [-1.5,1,-2], [1.5,2,0.25]),
        ("back_right", [1.5,1,-2], [1.5,2,0.25])
    ]
    
    parts.extend([cuboid(name, pos, size, material="mat-brick") 
                  for name, pos, size in wall_specs])
    
    # Side walls
    parts.extend([
        cuboid("left_wall", [3,1,0], [0.25,2,4], material="mat-brick"),
        cuboid("right_wall", [-3,1,0], [0.25,2,4], material="mat-brick")
    ])
    
    return parts
```

### Advanced Patterns

**Calculated positions** (1/16-aligned):
```python
def create_tower(levels=5):
    tower = []
    y = 0
    for i in range(levels):
        size = max(1, 3 - i * 0.375)  # Tapering tower
        tower.append(cuboid(f"level_{i}", [0,y,0], [size,1,size], 
                           material=f"mat-level{i}"))
        y += 1
    return tower
```

**Symmetric structures** (1/16-aligned):
```python
def create_bridge():
    parts = []
    
    # Pillars on both sides
    for x in [-5, 5]:
        parts.append(cuboid(f"pillar_{x}", [x,1,0], [1,4,1], material="mat-stone"))
    
    # Bridge deck
    parts.append(cuboid("deck", [0,3,0], [12,0.5,2], material="mat-wood"))
    
    return parts
```

**Proper attachment example - Rifle with handle**:
```python
def create_rifle():
    parts = []
    
    # Main body
    parts.append(cuboid("body", [0,1,0], [0.5,0.25,2], material="mat-metal"))
    parts.append(cuboid("barrel", [0,1,1], [0.25,0.25,1.5], material="mat-metal"))
    
    # Handle attached BELOW body, not embedded in it
    # Body bottom at Y=1.0, handle height 0.5, so handle starts at Y=0.499
    parts.append(cuboid("handle", [0,0.499,0.5], [0.3,0.5,0.25], material="mat-wood"))
    
    # Scope attached ABOVE body
    # Body top at Y=1.25, tiny gap, scope starts at Y=1.251
    parts.append(cuboid("scope", [0,1.251,0], [0.2,0.2,0.8], material="mat-glass"))
    
    return parts
```

## Most Concise Templates

### Template 1: Simple Object
```python
def create_model():
    return [
        cuboid("part1", [0,0,0], [1,1,1], material="mat-base"),
        cuboid("part2", [0,1,0], [0.5,0.5,0.5], material="mat-detail")
    ]
```

### Template 2: Character
```python
def create_model():
    return [
        group("body"),
        cuboid("torso", [-0.5,1,-0.25], [1,2,0.5], parent="body", material="mat-body"),
        cuboid("head", [-0.375,3.001,-0.375], [0.75,0.75,0.75], parent="body", material="mat-head"),  # Head on top of torso
        cuboid("right_arm", [0.501,1.25,-0.1875], [0.375,1.5,0.375], parent="body", material="mat-body"),
        cuboid("left_arm", [-0.876,1.25,-0.1875], [0.375,1.5,0.375], parent="body", material="mat-body")
    ]
```

### Template 3: Building
```python
def create_model():
    base = [cuboid("foundation", [0,0,0], [8,0.5,6], material="mat-concrete")]
    
    walls = [cuboid(f"wall_{name}", pos, size, material="mat-brick") 
             for name, pos, size in [
                 ("front", [0,1.5,3], [8,3,0.25]),
                 ("back", [0,1.5,-3], [8,3,0.25]),
                 ("left", [4,1.5,0], [0.25,3,6]),
                 ("right", [-4,1.5,0], [0.25,3,6])
             ]]
    
    roof = [cuboid("roof", [0,3.5,0], [9,0.25,7], material="mat-shingles")]
    
    return base + walls + roof
```

## Token Count Comparison

**Traditional approach** (~180 tokens):
```python
entities = []
entities.append({
    "id": "base",
    "type": "cuboid",
    "position": [0, 0, 0],
    "size": [2, 1, 2],
    "material": "mat-stone"
})
entities.append({
    "id": "top",
    "type": "cuboid", 
    "position": [0, 1, 0],
    "size": [1, 1, 1],
    "material": "mat-gold"
})
return entities
```

**Ultra-concise approach** (~45 tokens):
```python
return [
    cuboid("base", [0,0,0], [2,1,2], material="mat-stone"),
    cuboid("top", [0,1,0], [1,1,1], material="mat-gold")
]
```

**75% token reduction!** 🎉

## Available Shortcuts

- `cuboid(id, pos, size, **opts)` - Basic block
- `group(id, pos, **opts)` - Container
- `joint(id, pos, size, joint_name, offset, **opts)` - Animated block
- List comprehensions for repetitive structures
- Tuple unpacking with `*` operator
- Dictionary unpacking for option sets

## Naming Conventions & Animation Hierarchy

### Entity ID prefixes
- `grp_*` – logical grouping nodes (locators, bones, or animation joints). Models should *always* start with `grp_root` at the top level, under which all other nodes will go. This is good practice for organizing the model's nodes. Every other entity—groups or geometry—must ultimately descend from this root.
- `geo_*` – visible geometry / static cuboids
- `jnt_*` – intermediate joints automatically inserted for animation (pivot helpers)
- `anc_*` – anchor points exposed to the game engine (e.g. `anc_hand_right`)

### Left / Right / Front / Back suffixes
Use `<part>_<side>` where `<side>` is `left`, `right`, `front`, or `back`.  When needed, append an additional qualifier such as `front`/`back` – e.g. `wing_left_front`, `leg_right_back`.

### Humanoid reference hierarchy (example)
```text
grp_root
 └─ grp_hips
     └─ grp_spine
         └─ grp_chest
             ├─ grp_head
             │   └─ geo_head
             ├─ grp_arm_left
             │   └─ geo_arm_left
             └─ grp_arm_right
                 └─ geo_arm_right
```
Place anchors like `anc_hand_left` and `anc_hand_right` under the corresponding arm groups so equipment can be attached easily in-game. Add other anchors (`anc_head`, `anc_mount`, etc.) whenever they improve usability; helps with putting on items and things like that.

### Keep it self-contained
All helper calls *and* any constants you define must live inside the single `create_model()` function. **Do not import external modules** – only use plain Python and the helpers that are pre-injected by the runner.

## Best Practices

1. **Use helpers**: Always prefer `cuboid()` over manual dicts
2. **Think absolute**: All positions are world coordinates, not relative to parent
3. **Orient correctly**: +Z faces camera, +X is right side, -X is left side
4. **Positive sizes only**: Every `size = [x, y, z]` entry must be **positive**. If you need a wafer-thin surface, use a small positive value such as `0.01`—negative sizes are not supported.
5. **Plan first**: Draft the part list & proportions before emitting code (see "Plan Before You Build").
6. **List comprehensions**: For repetitive structures  
7. **Tuple unpacking**: `*walls` to flatten lists
8. **Calculated positions**: Use math for precision, prioritize clean attachments
9. **Meaningful IDs**: Keep them short but descriptive
10. **Clean connections**: Attach parts face-to-face (e.g., window's -X to wall's +X), never embed parts inside each other
11. **Follow naming conventions**: Apply the `grp_`, `geo_`, `jnt_`, and `anc_` prefixes and `<part>_<side>` pattern consistently
12. **Plan for animation**: Build a logical hierarchy (e.g. hips → spine → chest → arms/head) and add anchors like `anc_hand_right` & `anc_hand_left` when characters must hold items
13. **One-file rule**: Keep everything inside `create_model()` – no imports or global state
14. **Joint usage discipline**: **DO NOT** use `joint_name` and `joint_offset` unless there are explicit hints they're needed (animation data, joint-named entities, or explicit animation request). 99% of models should have ZERO joints.

## 🚫 Joint Usage: Almost Never Use Them

**DEFAULT RULE: DO NOT USE `joint_name` or `joint_offset`**

Only add joints if you have **explicit evidence** that they're needed:

### ✅ ONLY Use Joints When:
1. **Animation data exists**: There are animation channels targeting specific parts
2. **Joint hints in names**: Existing entities are named like `pivot_*`, `joint_*`, `jnt_*`  
3. **Explicit animation request**: User specifically asks for "animated" or "rigged" model
4. **Converting rigged model**: Source material already has joint structure

### ❌ NEVER Use Joints For:
- Regular model creation (99% of cases)
- Organizing parts into groups
- Positioning helpers
- Visual hierarchy
- "Just in case" future animation
- Making moveable-looking parts (doors, wheels, etc.) unless explicitly requested

### Examples
```python
# ✅ CORRECT - Normal model creation (NO JOINTS)
def create_robot():
    return [
        group("body_parts"),
        cuboid("torso", [0, 1, 0], [1, 2, 0.5], parent="body_parts", material="mat-metal"),
        cuboid("head", [0, 2.5, 0], [0.75, 0.75, 0.75], parent="body_parts", material="mat-metal"),
        cuboid("right_arm", [0.75, 1.5, 0], [0.375, 1.25, 0.375], parent="body_parts", material="mat-metal"),
        cuboid("left_arm", [-0.75, 1.5, 0], [0.375, 1.25, 0.375], parent="body_parts", material="mat-metal")
    ]

# ❌ WRONG - Adding joints without explicit need
def create_robot():
    return [
        joint("right_arm", [0.75, 1.5, 0], [0.375, 1.25, 0.375], 
              "shoulder_right", [0, 0.625, 0], material="mat-metal")  # DON'T DO THIS!
    ]

# ✅ ONLY CORRECT if user specifically requested "animated robot" or provided animation data
```

**Remember: 99% of models should have ZERO joints. Only add them with explicit evidence.**

## LLM Guidance
**Prompt**: "Generate models in block units. Focus on clean attachments between cuboids and avoiding z-fighting. Use 1⁄16-block increments (0.0625) when it helps achieve clean seams, but prioritize visual quality over strict grid adherence. Provide positions as the MIN (back-bottom-left) corner of each cuboid. Design for Hytopia/Minecraft scale (about 1.75–2 blocks tall for humanoids). Use +X for left arm (camera's right), -X for right arm (camera's left), +Z for front. **CRITICAL: DO NOT use joint_name or joint_offset unless there are explicit hints that animation is needed (existing animation data, joint-named entities, or explicit animation request). 99% of models should have ZERO joints.**"

---

# Model Examples

Below are some examples of good uses of our library with well structured models and good clean code.

## horse.py
```py
def create_model():
    """
    Creates a 3D model of a horse using a hierarchical structure.

    The model is constructed from several distinct component groups: the main body,
    a dedicated group for the legs, the neck and head assembly, and a detailed bridle.
    All parts are defined as static geometry or groups, with no animation joints,
    following the strict joint usage policy.

    The horse is oriented with its head facing the +Z direction (front).
    The hierarchy is designed for clear organization, with a central root, a body group,
    and a rotated neck/head structure. All entity positions are specified in
    absolute world coordinates.
    """

    # A small helper for converting center-based positions from the original JSON
    # to the corner-based positions required by the `cuboid` helper function.
    def from_center(center, size):
        return [c - s / 2 for c, s in zip(center, size)]

    # --- Groups (for logical organization and hierarchy) ---
    # These nodes define the skeleton and structure of the model.
    model_groups = [
        # A single root group is best practice for scene management.
        group("grp_root", [0, 0, 0]),
        
        # The core body group, to which all major components are attached.
        group("grp_body", [0.0, 0.8125, 0.5625], parent="grp_root", rotation=[0.0, 0.0, 0.0]),

        # A new group to contain all four legs, parented to the body.
        group("grp_legs", [0.0, 0.8125, 0.5625], parent="grp_body"),

        # The neck group is rotated 30 degrees forward (positive X rotation) to give the horse a natural downward gaze.
        group("grp_neck", [0.0, 1.0625, -0.5], parent="grp_body", rotation=[30.0, 0.0, 0.0]),

        # The head is parented to the rotated neck.
        group("grp_head", [0.0, 1.75, -0.6875], parent="grp_neck", rotation=[0.0, 0.0, 0.0]),

        # A separate group for bridle components allows them to be toggled easily.
        group("grp_bridle", [0.0, 1.0625, -0.5], parent="grp_head", rotation=[0.0, 0.0, 0.0]),
    ]

    # --- Torso and Attachments (Excluding Legs) ---
    # These parts are direct children of the 'grp_body'.
    torso_and_attachments = [
        # The main torso of the horse.
        cuboid("geo_torso", from_center([0.0, 1.0, 0.0], [0.625, 0.625, 1.375]), [0.625, 0.625, 1.375], parent="grp_body"),

        # The saddle placed on the horse's back.
        cuboid("geo_saddle", from_center([0.0, 1.03125, 0.0625], [0.625, 0.5625, 0.5625]), [0.625, 0.5625, 0.5625], parent="grp_body"),

        # The horse's tail.
        cuboid("geo_tail", from_center([0.0, 0.8125, 0.6875], [0.1875, 0.875, 0.25]), [0.1875, 0.875, 0.25], parent="grp_body"),
    ]

    # --- Legs ---
    # The four legs are now parented to their own group for better organization.
    legs = [
        cuboid("geo_leg_back_left", from_center([-0.1875, 0.34375, 0.5625], [0.25, 0.6875, 0.25]), [0.25, 0.6875, 0.25], parent="grp_legs"),
        cuboid("geo_leg_back_right", from_center([0.1875, 0.34375, 0.5625], [0.25, 0.6875, 0.25]), [0.25, 0.6875, 0.25], parent="grp_legs"),
        cuboid("geo_leg_front_left", from_center([-0.1875, 0.34375, -0.5625], [0.25, 0.6875, 0.25]), [0.25, 0.6875, 0.25], parent="grp_legs"),
        cuboid("geo_leg_front_right", from_center([0.1875, 0.34375, -0.5625], [0.25, 0.6875, 0.25]), [0.25, 0.6875, 0.25], parent="grp_legs"),
    ]

    # --- Neck and Mane ---
    # These parts are attached to the 'grp_neck' group.
    neck_and_mane = [
        # The main geometry for the neck.
        cuboid("geo_neck", from_center([0.0, 1.375, -0.46875], [0.25, 0.75, 0.4375]), [0.25, 0.75, 0.4375], parent="grp_neck"),
        
        # The horse's mane.
        cuboid("geo_mane", from_center([0.0, 1.5625, -0.184375], [0.125, 1.0, 0.125]), [0.125, 1.0, 0.125], parent="grp_neck"),
    ]
    
    # --- Head Components (Facial features and ears) ---
    # These parts are attached to the 'grp_head'.
    head_components = [
        # The main cuboid for the head.
        cuboid("geo_head", from_center([0.0, 1.90625, -0.46875], [0.375, 0.3125, 0.4375]), [0.375, 0.3125, 0.4375], parent="grp_head"),
        
        # The muzzle.
        cuboid("geo_muzzle", from_center([0.0, 1.90625, -0.84375], [0.25, 0.3125, 0.3125]), [0.25, 0.3125, 0.3125], parent="grp_head"),
        
        # Standard horse ears.
        cuboid("geo_ear_left", from_center([-0.03125, 2.09375, -0.281875], [0.125, 0.1875, 0.0625]), [0.125, 0.1875, 0.0625], parent="grp_head"),
        cuboid("geo_ear_right", from_center([0.03125, 2.09375, -0.281875], [0.125, 0.1875, 0.0625]), [0.125, 0.1875, 0.0625], parent="grp_head"),

        # Optional longer ears for a mule or donkey variant.
        cuboid("geo_mule_ear_left", from_center([0.125, 2.21875, -0.281875], [0.125, 0.4375, 0.0625]), [0.125, 0.4375, 0.0625], parent="grp_head"),
        cuboid("geo_mule_ear_right", from_center([-0.125, 2.21875, -0.281875], [0.125, 0.4375, 0.0625]), [0.125, 0.4375, 0.0625], parent="grp_head"),
    ]

    # --- Bridle Components (Harness on the head) ---
    # These parts are attached to the 'grp_bridle'.
    bridle_components = [
        # The two main strap pieces for the bridle geometry.
        cuboid("geo_bridle_strap", from_center([0.0, 1.90625, -0.75], [0.25, 0.3125, 0.125]), [0.25, 0.3125, 0.125], parent="grp_bridle"),
        cuboid("geo_bridle_main", from_center([0.0, 1.90625, -0.46875], [0.375, 0.3125, 0.4375]), [0.375, 0.3125, 0.4375], parent="grp_bridle"),

        # The bits on the left and right of the muzzle.
        cuboid("geo_bit_left", from_center([-0.15625, 1.875, -0.8125], [0.0625, 0.125, 0.125]), [0.0625, 0.125, 0.125], parent="grp_bridle"),
        cuboid("geo_bit_right", from_center([0.15625, 1.875, -0.8125], [0.0625, 0.125, 0.125]), [0.0625, 0.125, 0.125], parent="grp_bridle"),
    ]

    # --- Final Assembly ---
    # All component lists are concatenated into a single flat list for the final output.
    return model_groups + torso_and_attachments + legs + neck_and_mane + head_components + bridle_components
```

## scifi-sniper.py
```py
def create_model():
    """
    Creates a 3D model of a sniper rifle with a programmatic and hierarchical structure.

    This version demonstrates a more advanced, data-driven approach. Instead of
    defining every piece individually, it uses loops and data structures for
    efficiency and clarity:
    - A simple loop generates the five repeating heat shields on the barrel.
    - A data-driven loop creates all symmetrical left/right pairs (like bipod
      legs and magazine cells) from a single definition list.

    All cuboid positions are defined by their back-left-bottom corner, with the
    coordinates pre-calculated.
    """
    # --- Groups (for logical organization and hierarchy) ---
    # These nodes define the skeleton of the model.
    model_groups = [
        group("grp_root", position=[0.0, 0.0, 0.0]),
        group("grp_body", position=[0.0, 0.3125, 0.3125], parent="grp_root"),
        group("grp_stock", position=[0.0, 0.3125, 0.3125], parent="grp_body"),
        group("grp_barrel_assembly", position=[0.0, 0.28125, 0.3125], parent="grp_root"),
        group("grp_bipod", position=[0.0, 0.25, 0.0], parent="grp_barrel_assembly"),
        group("grp_scope", position=[0.0, 0.3125, 0.25], parent="grp_body"),
        group("grp_magazine", position=[0.0, 0.3125, 0.5], parent="grp_body"),
    ]

    # --- Main Components & Unique Parts ---
    # These parts are defined individually as they don't follow a simple pattern.
    # Cuboid corner positions are pre-calculated: [center - size / 2]
    main_components = [
        # Receiver, Grip, and Trigger
        cuboid("geo_receiver_main", [-0.125, 0.3125, -0.1875], [0.25, 0.3125, 1.0], parent="grp_body", material="mat-geo_receiver_main"),
        cuboid("geo_receiver_top_plate", [-0.15625, 0.625, -0.125], [0.3125, 0.0625, 0.875], parent="grp_body", material="mat-geo_receiver_top_plate"),
        cuboid("geo_ejection_port", [0.125, 0.4375, 0.1875], [0.03125, 0.125, 0.3125], parent="grp_body", material="mat-geo_ejection_port"),
        cuboid("geo_grip_1", [-0.09375, 0.125, -0.125], [0.1875, 0.25, 0.1875], parent="grp_body", material="mat-geo_grip_1"),
        cuboid("geo_grip_2", [-0.09375, -0.125, -0.125], [0.1875, 0.25, 0.1875], parent="grp_body", material="mat-geo_grip_2"),
        cuboid("geo_trigger_guard_front", [-0.0625, 0.1875, 0.1875], [0.125, 0.1875, 0.0625], parent="grp_body", material="mat-geo_trigger_guard_front"),
        cuboid("geo_trigger_guard_bottom", [-0.0625, 0.125, 0.0], [0.125, 0.0625, 0.25], parent="grp_body", material="mat-geo_trigger_guard_bottom"),
        cuboid("geo_trigger_guard_back", [-0.0625, 0.1875, 0.0], [0.125, 0.0625, 0.0625], parent="grp_body", material="mat-geo_trigger_guard_back"),
        cuboid("geo_trigger", [-0.03125, 0.21875, 0.09375], [0.0625, 0.125, 0.0625], parent="grp_body", material="mat-geo_trigger"),

        # Stock
        cuboid("geo_stock_arm", [-0.09375, 0.375, -0.6875], [0.1875, 0.1875, 0.5], parent="grp_stock", material="mat-geo_stock_arm"),
        cuboid("geo_stock_butt", [-0.125, 0.25, -0.8125], [0.25, 0.4375, 0.125], parent="grp_stock", material="mat-geo_stock_butt"),
        cuboid("geo_stock_cheek_rest", [-0.125, 0.5625, -0.625], [0.25, 0.125, 0.375], parent="grp_stock", material="mat-geo_stock_cheek_rest"),

        # Barrel and Suppressor
        cuboid("geo_barrel_base", [-0.15625, 0.3125, 0.8125], [0.3125, 0.3125, 0.25], parent="grp_barrel_assembly", material="mat-geo_barrel_base"),
        cuboid("geo_barrel_main", [-0.09375, 0.375, 1.0625], [0.1875, 0.1875, 1.25], parent="grp_barrel_assembly", material="mat-geo_barrel_main"),
        cuboid("geo_suppressor_body", [-0.15625, 0.3125, 2.3125], [0.3125, 0.3125, 0.5], parent="grp_barrel_assembly", material="mat-geo_suppressor_body"),
        cuboid("geo_suppressor_vent_top", [-0.09375, 0.625, 2.375], [0.1875, 0.0625, 0.375], parent="grp_barrel_assembly", material="mat-geo_suppressor_vent_top"),
        cuboid("geo_suppressor_vent_bottom", [-0.09375, 0.25, 2.375], [0.1875, 0.0625, 0.375], parent="grp_barrel_assembly", material="mat-geo_suppressor_vent_bottom"),

        # Scope
        cuboid("geo_scope_mount_rear", [-0.0625, 0.6875, -0.0625], [0.125, 0.0625, 0.125], parent="grp_scope", material="mat-geo_scope_mount_rear"),
        cuboid("geo_scope_mount_front", [-0.0625, 0.6875, 0.5625], [0.125, 0.0625, 0.125], parent="grp_scope", material="mat-geo_scope_mount_front"),
        cuboid("geo_scope_body", [-0.125, 0.75, -0.125], [0.25, 0.25, 0.875], parent="grp_scope", material="mat-geo_scope_body"),
        cuboid("geo_scope_lens_rear", [-0.15625, 0.71875, -0.1875], [0.3125, 0.3125, 0.0625], parent="grp_scope", material="mat-geo_scope_lens_rear"),
        cuboid("geo_scope_lens_front", [-0.15625, 0.71875, 0.75], [0.3125, 0.3125, 0.0625], parent="grp_scope", material="mat-geo_scope_lens_front"),
        cuboid("geo_scope_turret_top", [-0.0625, 1.0, 0.25], [0.125, 0.0625, 0.125], parent="grp_scope", material="mat-geo_scope_turret_top"),
        cuboid("geo_scope_turret_side", [0.125, 0.8125, 0.1875], [0.0625, 0.125, 0.125], parent="grp_scope", material="mat-geo_scope_turret_side"),

        # Magazine
        cuboid("geo_magazine_main", [-0.09375, -0.125, 0.375], [0.1875, 0.4375, 0.3125], parent="grp_magazine", material="mat-geo_magazine_main"),
        cuboid("geo_magazine_baseplate", [-0.125, -0.1875, 0.34375], [0.25, 0.0625, 0.375], parent="grp_magazine", material="mat-geo_magazine_baseplate"),

        # Bipod Mount
        cuboid("geo_bipod_mount", [-0.15625, 0.1875, 1.0], [0.3125, 0.125, 0.0625], parent="grp_bipod", material="mat-geo_bipod_mount"),
    ]

    # --- Programmatic Part Generation ---
    # This section uses loops to create repetitive and symmetrical parts.

    # 1. Create the repeating heat shields along the barrel
    heat_shields = []
    heat_shield_z_positions = [1.1875, 1.375, 1.5625, 1.75, 1.9375]
    for i, z_pos in enumerate(heat_shield_z_positions):
        heat_shields.append(
            cuboid(f"geo_heat_shield_{i}", [-0.1875, 0.25, z_pos], [0.375, 0.4375, 0.0625], parent="grp_barrel_assembly", material=f"mat-geo_heat_shield_{i}")
        )

    # 2. Create symmetrical left/right parts from a single data source
    symmetrical_parts = []
    # Data format: [name, [corner_x, y, z], [size_x, y, z], parent_group]
    sym_part_definitions = [
        ("bipod_leg", [0.15625, -0.25, 1.0], [0.0625, 0.5625, 0.0625], "grp_bipod"),
        ("bipod_foot", [0.125, -0.3125, 0.96875], [0.125, 0.0625, 0.125], "grp_bipod"),
        ("magazine_cell", [0.0625, -0.0625, 0.4375], [0.0625, 0.3125, 0.1875], "grp_magazine"),
    ]

    for name, r_corner, size, parent in sym_part_definitions:
        # Right side part
        symmetrical_parts.append(
            cuboid(f"geo_{name}_right", r_corner, size, parent=parent, material=f"mat-geo_{name}_right")
        )
        # Left side part (mirror the X position)
        l_corner = [-r_corner[0] - size[0], r_corner[1], r_corner[2]]
        symmetrical_parts.append(
            cuboid(f"geo_{name}_left", l_corner, size, parent=parent, material=f"mat-geo_{name}_left")
        )

    # --- Final Assembly ---
    # All component lists are concatenated into a single flat list.
    return model_groups + main_components + heat_shields + symmetrical_parts
```

## zombie.py
```py
def create_model():
    """
    Creates a 3D model of a standard blocky zombie.

    The model is constructed using a standard humanoid hierarchy, with distinct groups
    for the body, head, arms, and legs. This structure is clean, easy to manage,
    and suitable for animation, even though no explicit joints are defined, per the
    project's modeling guidelines.

    The zombie is oriented facing the +Z direction (front). All entity positions
    are specified in absolute world coordinates.
    """

    # A small helper for converting center-based positions from the original JSON
    # to the corner-based positions required by the `cuboid` helper function.
    def from_center(center, size):
        return [c - s / 2 for c, s in zip(center, size)]

    # --- Groups (for logical organization and hierarchy) ---
    # These nodes define the skeleton and structure of the model.
    model_groups = [
        # A single root group is best practice for scene management.
        group("grp_root", [0, 0, 0]),
        
        # The main body group acts as the parent for the limbs and head.
        group("grp_body", [0.0, 1.125, 0.0], parent="grp_root"),

        # A group for all head components, including the hat.
        group("grp_head", [0.0, 1.75, 0.0], parent="grp_body"),
        
        # Symmetrical groups for the arms.
        group("grp_arm_left", [-0.375, 1.125, 0.0], parent="grp_body"),
        group("grp_arm_right", [0.375, 1.125, 0.0], parent="grp_body"),

        # Symmetrical groups for the legs.
        group("grp_leg_left", [-0.11875, 0.375, 0.0], parent="grp_body"),
        group("grp_leg_right", [0.11875, 0.375, 0.0], parent="grp_body"),

        # Anchor points for holding items in each hand, as per best practices.
        group("anc_hand_left", [-0.375, 0.9375, 0.0625], parent="grp_arm_left"),
        group("anc_hand_right", [0.375, 0.9375, 0.0625], parent="grp_arm_right"),
    ]

    # --- Body Component ---
    body_components = [
        # The main torso of the zombie.
        cuboid("geo_torso", from_center([0.0, 1.125, 0.0], [0.5, 0.75, 0.25]), [0.5, 0.75, 0.25], parent="grp_body"),
    ]

    # --- Head Components ---
    # The head and hat, parented to 'grp_head'.
    head_components = [
        # The main head block.
        cuboid("geo_head_main", from_center([0.0, 1.75, 0.0], [0.5, 0.5, 0.5]), [0.5, 0.5, 0.5], parent="grp_head"),
        
        # A hat layer on top of the head.
        # Note: In the original file, this had the same size and position as the head,
        # but was intended as a separate overlay. A small size increase is added for visibility.
        cuboid("geo_hat", from_center([0.0, 1.75, 0.0], [0.53125, 0.53125, 0.53125]), [0.53125, 0.53125, 0.53125], parent="grp_head"),
    ]

    # --- Arm Components ---
    # Using a list comprehension for symmetrical parts is efficient and clean.
    arm_components = [
        cuboid(f"geo_arm_{side}", from_center([x_pos, 1.125, 0.0], [0.25, 0.75, 0.25]), [0.25, 0.75, 0.25], parent=f"grp_arm_{side}")
        for side, x_pos in [("left", -0.375), ("right", 0.375)]
    ]
    
    # --- Leg Components ---
    leg_components = [
        cuboid(f"geo_leg_{side}", from_center([x_pos, 0.375, 0.0], [0.25, 0.75, 0.25]), [0.25, 0.75, 0.25], parent=f"grp_leg_{side}")
        for side, x_pos in [("left", -0.11875), ("right", 0.11875)]
    ]
    
    # --- Final Assembly ---
    # All component lists are concatenated into a single flat list for the final output.
    return model_groups + body_components + head_components + arm_components + leg_components
```