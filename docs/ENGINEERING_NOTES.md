# BlockSmith Engineering Notes & Troubleshooting Guide

**Date:** Jan 7, 2026
**Topic:** Animation System Internals & Quirks

## Overview

The Animation System allows users to generate Python-based animations for existing BlockSmith models and link them into a single GLB file.

### Core Components used in Linking
1.  **`drone.py` (Model)**: Defines the geometry and hierarchy (Groups, Cuboids, Pivots).
2.  **`drone_props.py` (Animation)**: Defines a `create_animations()` function that returns a list of dictionaries describing keyframes.
3.  **`blocksmith link` (CLI)**:
    *   Loads the Model (Python -> V3 Schema).
    *   Loads Animations (Python -> V3 Schema).
    *   Merges them into a single structure.
    *   Exports to GLB using a **Single-Pass** or **Multi-Pass Clean Room** strategy.

---

## Known Issues (The "Linker" Glitch)

**Symptom:**
When linking multiple animations (e.g., `propeller_spin` + `scan`), sometimes only the *last* animation appears in the final GLB, or the first one is silent/empty.

**Root Cause (Suspected):**
The Blender-based exporter uses a "Clean Room" strategy:
1.  Pass 0: Export Master Model + Animation 0.
2.  Pass 1: Export Animation 1 (Isolated).
3.  Pass N: Export Animation N (Isolated).
4.  **Merge:** Binaries are concatenated using `pygltflib`.

If `pygltflib` is missing or fails, the merge silently returns the Master bytes (Anim 0 only) or just the last pass, effectively dropping data.

**How to Verify:**
If you see file sizes like `20KB` (Base) -> `20KB` (After Link), it failed.
If you see `50KB` (After Link), it succeeded (geometry was duplicated for isolation).

**Quick Fix:**
Ensure `pygltflib` is installed in the active environment:
```bash
pip install pygltflib
```

---

## Debugging Tips

If animations are missing or look wrong:

### 1. Inspect the Intermediate GLBs
Run the linker with the environment variable `KEEP_V3_GLTF_TMP=1`.
```bash
KEEP_V3_GLTF_TMP=1 blocksmith link ...
```
This will print the location of temporary folders (e.g., `/tmp/v3_export_xyz/`). Open the `.glb` files inside those folders in a viewer (like `gltf-viewer.donmccurdy.com`) to see if the animation exists *before* merging.

### 2. Check "Duration Leaks"
If a short animation (e.g., "Attack", 1.0s) has 4 seconds of "frozen" dead air at the end:
*   This usually means it inherited the timeline length of a longer animation (e.g., "Walk", 5.0s) during export.
*   **Fix:** The `exporter.py` (`_sanitize_gltf` function) attempts to trim this. Check if it's correctly calculating the `max_t` for your specific animation channels.

### 3. Check Pivot Points
If a limb rotates around the wrong spot:
*   The `.py` model file defines the `pivot`. Open it and verify the `[x, y, z]` coordinates.
*   **Visual Debug:** Generate a model with "debug cubes" at the pivot locations to see where they actually are.

---

## Configuration "Dials & Knobs"

Adjust these to fine-tune the system:

### 1. LLM Model Selection
Different models have different "spatial IQ".
*   **Gemini 2.5 Pro (Default):** Best overall for logic and complex math.
*   **Gemini 2.0 Flash:** Faster, but prone to "floating limbs" or math errors in rotations.
*   **Use:** `blocksmith animate "..." --model gemini/gemini-2.0-flash`

### 2. Prompt Engineering (The "DSL")
The animation quality depends entirely on the prompt.
*   **Speed:** Explicitly state "very fast" or "slow, heavy". The prompt logic converts this to `TICKS_PER_SEC` multipliers.
*   **Looping:** "Continuous loop" vs "One-shot" vs "Ping-pong".
    *   *Tip:* "Make it loop seamlessly" often helps the LLM align start/end frames (t=0 and t=last).
*   **Body Parts:** Use the specific Group IDs from your model (e.g., "rotate `grp_arm_l`...").

### 3. Ticks Per Second
Defined in `blocksmith/generator/prompts.py` (or implied in `importer.py`).
*   Default: `24` ticks = 1 second.
*   McFunction/Minecraft standard: `20` ticks = 1 second.
*   If animations look too fast/slow in-game, check if this constant matches your engine's tick rate.

---

## Future Roadmap

*   **Native GLTF Export:** Rewrite the exporter to skip Blender entirely and write binary GLTF directly from Python. This would solve 99% of the "Clean Room" and merging complexity.
*   **Visual Editor:** A simple web-UI to tweak keyframes instead of re-generating via prompt.
