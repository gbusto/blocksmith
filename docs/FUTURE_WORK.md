# Future Engineering Context

This document captures high-value features that were brainstormed but not yet implemented. It defines the technical gap between the current state ("Path A/B") and the desired future state.

## 1. Animation Retargeting ("Path C": Appending to GLB)
**User Story:**
> "I have a cool `robot.glb` I bought online or made locally. I want to use BlockSmith to generate a 'wave' animation and **append** it to this file without breaking its existing animations or structure."

### The Workflows
*   **Path A (Current):** Generate Model (BS) → Generate Anim (BS) → Link. (Requires source).
*   **Path B (Current):** Import GLB (BS) → Convert to Source → Generate Anim (BS) → Link. (Re-exports entirely).
*   **Path C (Goal):** Import GLB → Generate Anim (BS) → **Inject Anim into original GLB**.

### Technical Challenge: "Node Index Chaos"
*   **Problem:** Animations in GLB reference nodes by **Index** (e.g., "Rotate Node #12").
*   In `Path C`, the "Wave" animation is generated in a vacuum. It might think "Right Arm" is Node #3.
*   If we just copy the data into the original GLB (where "Right Arm" is Node #12), the animation will break.

### Implementation Plan
Build a "Smart Retargeter" in `pygltflib` or `blocksmith link`:
1.  **Map Target:** Read `robot.glb`. Map Node Names -> Indices (`"arm_r": 12`).
2.  **Map Source:** Read `wave_temp.glb`. Map Node Names -> Indices (`"arm_r": 3`).
3.  **Rewrite:** Iterate through the new animation's accessors. Rewrite Node #3 references to Node #12.
4.  **Append:** Safely append the rewritten binary data to the original file.

---

## 2. BBModel Animation Export
**User Story:**
> "I want to start an animation in BlockSmith (AI) but finish it in Blockbench (GUI). Blockbench is the best visual auditor for blocky models."

### Current State
*   We export models to `.bbmodel` (geometry/textures only).
*   We export animations to `.glb` / `.gltf` (geometry/textures/animations).
*   **Gap:** We cannot currently write animations into the `.bbmodel` JSON structure.

### Implementation Plan
1.  **Exporter Update:** Update `blocksmith/converters/bbmodel/exporter.py`. This is where the JSON structure for Blockbench is built.
2.  **Converter Logic:**
    *   **Quaternions -> Euler:** BBModel requires Euler angles. We must implement a robust converter to avoid gimbal lock flip-flopping.
    *   **Time:** BBModel uses seconds (float), but snapped to specific framerates (usually 24fps).
    *   **UUIDs:** BBModel relies heavily on UUIDs for linking animations to bones. We must ensure our generated UUIDs match the bone UUIDs.

---

## 3. The "Universal Translator" (Full Roundtrip)
**User Story:**
> "I want to import a random `zombie_run.glb` OR `zombie.bbmodel` file, converting EVERYTHING (Mesh + Textures + Animations) into a BlockSmith Project (JSON/Python). This lets me edit the animation logic via code or AI, then re-export."

### Current State
*   `blocksmith convert` handles: **Geometry** and **Textures**.
*   It does **not** import Animations. The `animations` field in the recovered JSON is `None`.

### Implementation Plan
1.  **Extract Animations:**
    *   **GLTF:** In `converters/gltf/importer.py`, read the `animations` array.
    *   **BBModel:** In `converters/bbmodel/importer.py`, read the `animations` array.
2.  **Un-Bake Keyframes:**
    *   GLTF stores baked samples. BBModel stores explicit keyframes (but in Euler).
    *   Both need to be normalized to the BlockSmith v3 Animation Schema within the importer.
3.  **Program Synthesis (Optional/Hard):**
    *   **Is the DSL ready?** Yes. The DSL strictly expects a list of keyframe dicts (`frames=[...]`). It does not verify *how* that list was created.
    *   **The Trade-off:** "Baked DSL" (a hardcoded list of 100 values) is valid code, but harder for humans to edit than the original procedural code (`for i in range(10): ...`).
    *   **Pragmatic Approach:** Generate "Baked DSL" code:
        ```python
        # Generated from import (Baked Keyframes)
        frames = [
            {'time': 0, 'value': [0,0,0]},
            {'time': 1, 'value': [0,0.1,0]},
            # ... big list ...
        ]
        ```
    *   This allows the user to copy-paste this list into an LLM context and say "Simplify this curve" or "Make it faster".

### 4. Schema Evolution (The "Lossless" Requirement)
*   **Current Constraint:** The v3 Schema enforces `time` as **Integers (Ticks)**.
*   **The Problem:** Importing a GLTF with arbitrary timing (e.g., `0.1234s`) into a 24fps tick system results in quantization errors (snapping to grid).
*   **Future Requirement:** To support a truly lossless roundtrip for any external file, we would need to:
    1.  **Update Schema:** Update `blocksmith/schema/blockjson.py` to allow `time` to be `float` (seconds) or `int`.
    2.  **Update Converters:**
        *   `importer.py` (GLTF & BBModel): Need to assign float times instead of rounding.
        *   `exporter.py` (GLTF & BBModel): Need to read float times and write them out without tick conversion.
    3.  **Update Prompt:** Update `blocksmith/animator/SYSTEM_PROMPT.md` to teach the LLM how to handle floating-point timing if exposed.
    *This is only strictly necessary if we aim for pixel-perfect preservation of external animation data.*
