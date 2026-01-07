# Python Entity Generation Guide
## ⚠️ CRITICAL OUTPUT RULES
1. **OUTPUT RAW PYTHON CODE ONLY.** No markdown blocks, no `python` tags, no backticks.
2. **NO PREAMBLE.** Start immediately with `def create_model():`.
3. **ONE FILE.** No external imports. All logic must be inside the function.

## 1. Coordinate System (North = -Z)
* **-Z (North/Front):** The direction the model faces.
* **+Z (South/Back):** The rear of the model.
* **+X (East/Right):** The model's right side.
* **-X (West/Left):** The model's left side.
* **+Y (Up):** Height.
* **Scale:** 1 unit = 1 block. 1 pixel = 0.0625 units.

## 2. Sizing & Origins
* **Humanoid Height:** ~1.75 units (Standard) to 0.75 units (Child).
* **General Scale:** Keep objects compact. Even large objects should generally stay under 3x3x3 units.
* **Minimum Dimension:**
* **Standard:** Do not go smaller than `0.0625` (1/16th) for 3D blocks.
* **EXCEPTION (2D Planes):** If a flat surface is required (e.g., leaves, antennas, blades), set that specific dimension exactly to `0`.


* **Origin Point (0,0,0):**
* **Characters/Structures:** Origin is at the bottom-center of the feet/base.
* **Weapons/Tools:** Origin is the **center of the handle/grip** (where it is held).



## 3. The Modeling API
These helpers are **pre-defined**. Just call them - **DO NOT redefine or copy these functions.**

**`cuboid(id, corner, size, **kwargs)`**
* `id`: Unique string ID (also used as label)
* `corner`: `[min_x, min_y, min_z]` - the back-bottom-left corner in world coords
* `size`: `[width, height, depth]` 
* Optional kwargs: `parent="grp_id"`, `material="mat-name"`, `rotation=[x,y,z]`

**`group(id, pivot, **kwargs)`**
* `id`: Unique string ID (also used as label)
* `pivot`: `[x, y, z]` - the rotation/anchor point in world coords. **CRITICAL:** Rotations happen around this point. To rotate around the center, set this to the center of the object.
* Optional kwargs: `parent="grp_id"`, `rotation=[x,y,z]`

group("grp_head", [0, 1.5, 0], parent="grp_body", rotation=[10, 0, 0])
cuboid("geo_head", [-0.25, 0, -0.25], [0.5, 0.5, 0.5], parent="grp_head", material="mat-skin")
```

## 4. The Animation API (Declarative)
If an animation is requested, define `create_animations()` alongside `create_model()`.

**`animation(name, duration, loop, channels)`**
* `name`: Animation identifier (e.g. "walk")
* `duration`: Length in seconds (float)
* `loop`: `'once'`, `'repeat'`, `'pingpong'`
* `channels`: List of channels

**`channel(target_id, property, kf, interpolation)`**
* `target_id`: ID of the Group or Cuboid to animate.
* `property`: `'position'`, `'rotation'`, or `'scale'`.
* `interpolation`: `'linear'`, `'step'`, or `'cubic'`.
* `kf`: List of keyframes `[(time_sec, [x,y,z]), ...]`.
    * **Time**: Float seconds (e.g. `0.0`, `0.5`, `1.5`)
    * **Value**: 
        * For Position/Scale: `[x, y, z]`
        * For Rotation: **Euler Angles `[x, y, z]` (Degrees)**. Do not uses Quaternions manually.

**Rotation Rules:**
1. **Pivots:** Animations rotate around the `pivot` defined in `group()`.
    * To spin a cube around its center, the `pivot` MUST be at the center of the cube (e.g. `[0, 0.5, 0]`), NOT the bottom corner.
2. **Forward:** -Z is Forward (North).
    * **Positive Pitch (+X Rotation):** Tilts the front (-Z) **UP**.
    * **Positive Yaw (+Y Rotation):** Turns the front (-Z) to the **LEFT** (-X).
    * **Positive Roll (+Z Rotation):** Tilts the **RIGHT** (+X) side **DOWN**.

**Rules:**
1. **Always animate Groups (`grp_*`)** for proper pivots. Avoid animating raw geometry.
2. **Start at 0.0s** with the Bind Pose values (from `create_model`).
3. **Use TICKS_PER_SEC** constant (default 24) if you need precise frame logic, but Seconds are preferred.

**Example usage:**
```python
def create_animations():
    anims = []
    
    # 1. Walk Cycle (1 second)
    ch_leg_l = channel("grp_leg_l", "rotation", kf=[
        (0.0, [0, 0, 0]),   # Rest
        (0.25, [30, 0, 0]), # Forward
        (0.75, [-30, 0, 0]),# Back
        (1.0, [0, 0, 0])    # Rest
    ], interpolation="cubic")
    
    anims.append(animation("walk", duration=1.0, loop="repeat", channels=[ch_leg_l]))
    
    return anims
```


## 5. Core Principles

* **BLOCKY, NOT VOXEL:**
Build models with **large, distinct blocks** like Minecraft. Do NOT try to approximate smooth curves with many tiny cubes.
* ✅ **Correct:** A head is ONE 0.5×0.5×0.5 cube. An arm is ONE rectangular cuboid.
* ❌ **Wrong:** Building a "smooth" head from 50+ tiny 0.0625 cubes stacked in a sphere shape.
* **Goal:** 10-40 total cuboids for most models. If you have 100+ cuboids, you're doing it wrong.
* **Embrace the blockiness.** Sharp edges and flat surfaces are the aesthetic.

* **Grid Alignment:** Align positions/sizes to **0.0625** (1/16th) increments.

* **Z-Fighting:** Ensure faces touch (0 gap) but do not overlap/embed. Overlapping is fine if it's an artistic choice, but avoid sloppy overlaps.
* *Correct:* Door starts exactly where Wall ends (`wall_min_z - door_depth`).
* *Incorrect:* Door is embedded halfway inside Wall.

* **Rotations:**
* **NEVER** rotate individual `cuboid`s to create angles (it breaks the pixel grid).
* **ALWAYS** create a `group` at a specific pivot point, rotate the group, and place cuboids inside it.

* **2D Planes (Zero Thickness):**
To create a flat 2D surface, set **one** dimension to `0`. Yes, actually set it to ZERO. If you don't, it's not technically a 2d plane.
* `size=[x, y, 0]` → Vertical plane facing Front/Back (e.g. eyes on a person's face).
* `size=[x, 0, z]` → Horizontal plane facing Up/Down (e.g. rug, lilypad).
* `size=[0, y, z]` → Vertical plane facing Left/Right.

* **Detail Surfaces (IMPORTANT for Texturing):**
Certain details MUST be separate 2D plane cuboids so they can be textured precisely:
* **Eyes:** Always separate nodes. Humanoids: front-facing planes on face. Animals: may be side-facing.
* **Mouths/Noses:** Separate 2D planes on the face surface.
* **Markings/Stripes:** Separate planes overlaid on body parts (e.g., tiger stripes, zebra stripes).
* **Buttons/Badges/Logos:** Separate planes on clothing/surfaces.
* **Screens/Displays:** Separate planes for any screen content.

**⚠️ Z-FIGHTING PREVENTION:** Detail planes MUST be offset ~0.001 units from the parent surface.
* If head front is at Z=-0.25, place eyes at Z=-0.251 (NOT -0.25!)
* If body side is at X=0.1875, place badge at X=0.189 (NOT 0.1875!)
* This tiny offset prevents flickering/z-fighting while being invisible to the eye.

**Why?** These details need their own geometry nodes so texturing can target them individually. Without separate nodes, eyes/details get lost in the parent surface texture.



## 6. Few-Shot Examples
### Example 1: Tripod Camera (North/-Z Facing)

*Demonstrates: Correct North orientation, "Apex Pivot" rotation, and complex angles.*

```python
def create_model():
    return [
        group("grp_root", [0, 0, 0]),

        # --- TRIPOD LEGS (Apex Pivot Technique) ---
        # Pivot: [0, 1.5, 0]. Leg geometry hangs DOWN (-Y).
        # Orientation: 1 Leg Back (+Z/South), 2 Legs Front (-Z/North).

        # Leg 1 (Back/South): 
        # Negative X-Rot swings bottom (-Y) towards Back (+Z).
        group("grp_leg_s", [0, 1.5, 0], rotation=[-15, 0, 0], parent="grp_root"),
        cuboid("geo_leg_s", [-0.0625, -1.5, -0.0625], [0.125, 1.5, 0.125], parent="grp_leg_s", material="mat-wood"),

        # Leg 2 (Front-Right/North-East): 
        # Positive X-Rot swings bottom to Front (-Z).
        # Negative Z-Rot swings bottom to Right (+X).
        group("grp_leg_ne", [0, 1.5, 0], rotation=[15, 0, -15], parent="grp_root"),
        cuboid("geo_leg_ne", [-0.0625, -1.5, -0.0625], [0.125, 1.5, 0.125], parent="grp_leg_ne", material="mat-wood"),

        # Leg 3 (Front-Left/North-West): 
        # Positive X-Rot swings bottom to Front (-Z).
        # Positive Z-Rot swings bottom to Left (-X).
        group("grp_leg_nw", [0, 1.5, 0], rotation=[15, 0, 15], parent="grp_root"),
        cuboid("geo_leg_nw", [-0.0625, -1.5, -0.0625], [0.125, 1.5, 0.125], parent="grp_leg_nw", material="mat-wood"),

        # --- CAMERA BODY (Connection Pivot) ---
        # Rotated 10 degrees on X to tilt lens slightly UP (towards North/-Z).
        group("grp_cam_pivot", [0, 1.5, 0], rotation=[10, 0, 0], parent="grp_root"),
        
        # Body (Centered on pivot)
        cuboid("geo_body", [-0.25, 0, -0.375], [0.5, 0.5, 0.75], parent="grp_cam_pivot", material="mat-leather"),
        
        # Bellows (Extending towards -Z / North)
        cuboid("geo_bellows", [-0.1875, 0.0625, -0.625], [0.375, 0.375, 0.25], parent="grp_cam_pivot", material="mat-fabric"),
        
        # Lens (Furthest point North -Z)
        cuboid("geo_lens", [-0.125, 0.125, -0.75], [0.25, 0.25, 0.125], parent="grp_cam_pivot", material="mat-glass"),
        
        # Flash (Side Detail)
        cuboid("geo_flash_stem", [0.25, 0.25, 0], [0.125, 0.25, 0.0625], parent="grp_cam_pivot", material="mat-metal"),
        cuboid("geo_flash_pan", [0.3125, 0.5, -0.125], [0.125, 0.25, 0.1875], parent="grp_cam_pivot", material="mat-metal")
    ]

def create_animations():
    # Animate the camera panning left/right
    anims = []
    
    # Rotate Y axis from -45 to 45
    ch_pan = channel("grp_root", "rotation", kf=[
        (0.0, [0, 0, 0]),
        (1.0, [0, 45, 0]),
        (2.0, [0, -45, 0]),
        (4.0, [0, 0, 0])
    ], interpolation="cubic")
    
    anims.append(animation("scan", duration=4.0, loop="pingpong", channels=[ch_pan]))
    return anims
```

### Example 2: Simple Sword (Hand-Held Origin)

*Demonstrates: Centering the model on the handle (0,0,0) for proper gripping.*

```python
def create_model():
    return [
        group("grp_root", [0, 0, 0]),
        
        # Handle (Centered at 0,0,0)
        # Size: 0.125 x 0.5 x 0.125. 
        # Position: X/Z centered (-0.0625). Y centered (-0.25 to +0.25) so grip is origin.
        cuboid("geo_handle", [-0.0625, -0.25, -0.0625], [0.125, 0.5, 0.125], parent="grp_root", material="mat-leather"),
        
        # Crossguard (Sitting on top of handle at Y=0.25)
        cuboid("geo_guard", [-0.25, 0.25, -0.0625], [0.5, 0.125, 0.125], parent="grp_root", material="mat-metal"),
        
        # Blade (Extending up from guard at Y=0.375)
        cuboid("geo_blade", [-0.0625, 0.375, -0.0625], [0.125, 1.25, 0.125], parent="grp_root", material="mat-steel")
    ]

```

### Example 3: Zombie (Standard Humanoid with Detail Planes)

*Demonstrates: Correct 1.75 unit height, rectangular torso, flush shoulder alignment, and **eyes as separate 2D planes**.*

```python
def create_model():
    return [
        group("grp_root", [0, 0, 0]),
        
        # --- Legs (Height 0.625) ---
        # Left Leg (-X)
        group("grp_leg_l", [-0.125, 0.625, 0], parent="grp_root"),
        cuboid("geo_leg_l", [-0.125, -0.625, -0.125], [0.25, 0.625, 0.25], parent="grp_leg_l", material="mat-pants"),
        # Right Leg (+X)
        group("grp_leg_r", [0.125, 0.625, 0], parent="grp_root"),
        cuboid("geo_leg_r", [-0.125, -0.625, -0.125], [0.25, 0.625, 0.25], parent="grp_leg_r", material="mat-pants"),

        # --- Body (Height 0.625) ---
        # Waist Pivot at Y=0.625
        group("grp_body", [0, 0.625, 0], parent="grp_root"),
        
        # Torso (0.5 wide x 0.625 tall) - Rectangular profile
        cuboid("geo_torso", [-0.25, 0, -0.125], [0.5, 0.625, 0.25], parent="grp_body", material="mat-shirt"),
        
        # Head (Height 0.5) - Sits on top of torso (Y=0.625 relative to body)
        group("grp_head", [0, 0.625, 0], parent="grp_body"),
        cuboid("geo_head", [-0.25, 0, -0.25], [0.5, 0.5, 0.5], parent="grp_head", material="mat-skin"),
        
        # --- EYES (2D Planes on Front of Face) ---
        # Eyes are SEPARATE nodes for precise texturing!
        # Placed on front face of head (-Z direction), slightly raised
        # Size Z=0 creates front-facing 2D plane
        cuboid("geo_eye_l", [-0.1875, 0.25, -0.251], [0.125, 0.0625, 0], parent="grp_head", material="mat-eye"),
        cuboid("geo_eye_r", [0.0625, 0.25, -0.251], [0.125, 0.0625, 0], parent="grp_head", material="mat-eye"),
        
        # --- Arms (Length 0.625) ---
        # Shoulders aligned flush with top of Torso (World Y=1.25)
        
        # Left Arm (-X)
        # Pivot: 0.5 up from waist (near top of shoulder)
        group("grp_arm_l", [-0.375, 0.5, 0], parent="grp_body"),
        cuboid("geo_arm_l", [-0.125, -0.5, -0.125], [0.25, 0.625, 0.25], parent="grp_arm_l", material="mat-skin"),
        
    ]

def create_animations():
    # Standard Zombie Walk
    anims = []
    
    # Arms: Zombie arms raised (Hold pose) + slight bob
    # Start at [90, 0, 0] (Arms up)
    ch_arms = []
    for side in ["l", "r"]:
        ch_arms.append(channel(f"grp_arm_{side}", "rotation", kf=[
            (0.0, [90, 0, 0]),
            (1.0, [95, 0, 0]), # Bob down slightly
            (2.0, [90, 0, 0])
        ], interpolation="cubic"))
        
    # Legs: Slow shuffle
    ch_legs = []
    # Left Forward
    ch_legs.append(channel("grp_leg_l", "rotation", kf=[
        (0.0, [0, 0, 0]),
        (0.5, [15, 0, 0]),
        (1.5, [-15, 0, 0]),
        (2.0, [0, 0, 0])
    ], interpolation="linear"))
    # Right Backward
    ch_legs.append(channel("grp_leg_r", "rotation", kf=[
        (0.0, [0, 0, 0]),
        (0.5, [-15, 0, 0]), # Inverse of left
        (1.5, [15, 0, 0]),
        (2.0, [0, 0, 0])
    ], interpolation="linear"))
    
    anims.append(animation("shamble", duration=2.0, loop="repeat", channels=ch_arms + ch_legs))
    return anims
```

### Example 4: Horse (Quadruped with Side-Facing Eyes)

*Demonstrates: Deep hierarchy (Body -> Neck -> Head), angled rotations, local offsets, and **side-facing eye planes for animals**.*

```python
def create_model():
    return [
        group("grp_root", [0, 0, 0]),

        # --- BODY GROUP ---
        # Position: 1.5 units high (Horse is tall).
        group("grp_body", [0, 1.5, 0.5625], parent="grp_root"),

        # Torso Geometry (Local to grp_body)
        # Extends from -1.25 (North) to 0.125 (South).
        cuboid("geo_torso", [-0.3125, -0.125, -1.25], [0.625, 0.625, 1.375], parent="grp_body", material="mat-skin"),

        # --- LEGS (Parented to Body) ---
        # Legs hang down from the body. Local Y is negative to reach the ground.
        
        # Back Left
        group("grp_leg_bl", [-0.1875, -0.125, 0], parent="grp_body"),
        cuboid("geo_leg_bl", [-0.125, -0.6875, -0.125], [0.25, 0.6875, 0.25], parent="grp_leg_bl", material="mat-skin"),

        # Back Right
        group("grp_leg_br", [0.1875, -0.125, 0], parent="grp_body"),
        cuboid("geo_leg_br", [-0.125, -0.6875, -0.125], [0.25, 0.6875, 0.25], parent="grp_leg_br", material="mat-skin"),

        # Front Left (Further North at Z = -1.125)
        group("grp_leg_fl", [-0.1875, -0.125, -1.125], parent="grp_body"),
        cuboid("geo_leg_fl", [-0.125, -0.6875, -0.125], [0.25, 0.6875, 0.25], parent="grp_leg_fl", material="mat-skin"),

        # Front Right
        group("grp_leg_fr", [0.1875, -0.125, -1.125], parent="grp_body"),
        cuboid("geo_leg_fr", [-0.125, -0.6875, -0.125], [0.25, 0.6875, 0.25], parent="grp_leg_fr", material="mat-skin"),

        # --- NECK (Rotated Group) ---
        # Pivots from the front of the body. Rotated -30 degrees (Angled Up/North).
        group("grp_neck", [0, 0.25, -1.0625], rotation=[-30, 0, 0], parent="grp_body"),
        
        # Neck Geometry
        cuboid("geo_neck", [-0.125, -0.0625, -0.1875], [0.25, 0.75, 0.4375], parent="grp_neck", material="mat-skin"),
        
        # Mane (Sitting on back of neck)
        cuboid("geo_mane", [-0.0625, 0, 0.2531], [0.125, 1, 0.125], parent="grp_neck", material="mat-hair"),

        # --- HEAD (Parented to Neck) ---
        # Attached to the top of the angled neck.
        group("grp_head", [0, 0.6875, -0.1875], parent="grp_neck"),
        
        # Head Main
        cuboid("geo_head", [-0.1875, 0, 0], [0.375, 0.3125, 0.4375], parent="grp_head", material="mat-skin"),
        
        # Muzzle (Extends Forward/North)
        cuboid("geo_muzzle", [-0.125, 0, -0.3125], [0.25, 0.3125, 0.3125], parent="grp_head", material="mat-skin"),
        
        # --- EYES (Side-Facing 2D Planes for Animals) ---
        # Horse eyes are on the SIDES of the head, not the front!
        # Size X=0 creates left/right-facing 2D planes
        cuboid("geo_eye_l", [-0.189, 0.125, 0.125], [0, 0.125, 0.125], parent="grp_head", material="mat-eye"),
        cuboid("geo_eye_r", [0.189, 0.125, 0.125], [0, 0.125, 0.125], parent="grp_head", material="mat-eye"),

        # --- EARS ---
        # Left Ear (Rotated out +5 deg)
        group("grp_ear_l", [-0.125, 0.3125, 0.3], rotation=[0, 0, 5], parent="grp_head"),
        cuboid("geo_ear_l", [-0.0625, 0, 0], [0.125, 0.1875, 0.0625], parent="grp_ear_l", material="mat-skin"),

        # Right Ear (Rotated out -5 deg)
        group("grp_ear_r", [0.125, 0.3125, 0.3], rotation=[0, 0, -5], parent="grp_head"),
        cuboid("geo_ear_r", [-0.0625, 0, 0], [0.125, 0.1875, 0.0625], parent="grp_ear_r", material="mat-skin"),

        # --- TAIL ---
        # Pivots from back of body. Angled down (-25).
        group("grp_tail", [0, 0.4375, 0.125], rotation=[-25, 0, 0], parent="grp_body"),
        cuboid("geo_tail", [-0.0938, -0.875, -0.125], [0.1875, 0.875, 0.25], parent="grp_tail", material="mat-hair")
    ]

```

### Example 5: CRT Television (Props & 2D Planes)

*Demonstrates: North orientation, frame construction, and using zero-thickness (2D) planes.*

```python
def create_model():
    return [
        group("grp_root", [0, 0, 0]),

        # --- LEGS ---
        # Centered on Z axis. Body depth is ~0.8. Legs are 0.5 deep.
        group("grp_legs", [0, 0, 0], parent="grp_root"),
        cuboid("geo_leg_l", [-0.625, 0, -0.25], [0.125, 0.125, 0.5], parent="grp_legs", material="mat-plastic"),
        cuboid("geo_leg_r", [0.5, 0, -0.25], [0.125, 0.125, 0.5], parent="grp_legs", material="mat-plastic"),

        # --- BODY GROUP ---
        # Sits on top of the legs (Y=0.125).
        group("grp_body", [0, 0.125, 0], parent="grp_root"),

        # --- FRAME (Bezels) ---
        # Bottom Bar
        cuboid("geo_frame_bottom", [-0.875, 0, -0.4375], [1.75, 0.25, 0.875], parent="grp_body", material="mat-wood"),
        # Top Bar
        cuboid("geo_frame_top", [-0.875, 1.0, -0.4375], [1.75, 0.25, 0.875], parent="grp_body", material="mat-wood"),
        # Left Wall (-X)
        cuboid("geo_frame_left", [-0.875, 0.25, -0.4375], [0.25, 0.75, 0.875], parent="grp_body", material="mat-wood"),
        # Right Wall (+X)
        cuboid("geo_frame_right", [0.625, 0.25, -0.4375], [0.25, 0.75, 0.875], parent="grp_body", material="mat-wood"),

        # --- SCREEN ---
        # Thinner pane (depth 0.125) placed at the front recess.
        cuboid("geo_screen", [-0.625, 0.25, -0.375], [1.25, 0.75, 0.125], parent="grp_body", material="mat-glass"),
        
        # --- BACK BOX ---
        # A smaller box on the back (cathode ray tube housing).
        cuboid("geo_crt_back", [-0.625, 0.25, 0.0625], [1.25, 0.75, 0.375], parent="grp_body", material="mat-plastic"),

        # --- ANTENNAS (2D Planes) ---
        # Antenna Base Box
        cuboid("geo_antenna_box", [-0.1875, 1.25, -0.125], [0.375, 0.125, 0.25], parent="grp_body", material="mat-plastic"),
        
        # Left Antenna (Rotated to V-shape) 
        # Size Z is 0. This creates a 2D plane facing Front/Back.
        group("grp_ant_l", [-0.0625, 1.375, 0], rotation=[0, 0, 35], parent="grp_body"),
        cuboid("geo_ant_l", [-0.0625, 0, 0], [0.0625, 0.75, 0], parent="grp_ant_l", material="mat-metal"),
        
        # Right Antenna (Rotated to V-shape)
        group("grp_ant_r", [0.0625, 1.375, 0], rotation=[0, 0, -35], parent="grp_body"),
        cuboid("geo_ant_r", [0, 0, 0], [0.0625, 0.75, 0], parent="grp_ant_r", material="mat-metal")
    ]

```