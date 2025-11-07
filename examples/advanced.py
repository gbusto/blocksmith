"""
BlockSmith Advanced Example

This example demonstrates accessing intermediate formats and saving
multiple file types from a single generation.
"""

from blocksmith import Blocksmith
import json

# Initialize
bs = Blocksmith()

# Generate a model
print("Generating a spaceship...")
result = bs.generate("a futuristic spaceship with wings")

# Access intermediate formats
print("\n--- Python DSL Preview ---")
print(result.dsl[:500] + "...")  # Show first 500 chars

print("\n--- BlockJSON JSON Preview ---")
print(json.dumps(result.json, indent=2)[:500] + "...")

# Save in multiple formats
print("\n--- Saving in multiple formats ---")
result.save("output/spaceship.glb")
print("✅ Saved GLB (requires Blender)")

result.save("output/spaceship.gltf")
print("✅ Saved GLTF (requires Blender)")

result.save("output/spaceship.bbmodel")
print("✅ Saved BBModel (Blockbench)")

result.save("output/spaceship.json")
print("✅ Saved BlockJSON")

result.save("output/spaceship.py")
print("✅ Saved Python DSL")

print("\nAll formats saved! Check the output/ directory.")
