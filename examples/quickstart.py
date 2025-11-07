"""
BlockSmith Quick Start Example

This example shows the basic usage of BlockSmith to generate simple models.
"""

from blocksmith import Blocksmith

# Initialize BlockSmith (reads API key from environment)
bs = Blocksmith()

print("Generating a simple cube...")
bs.generate("a red cube").save("output/cube.glb")
print("✅ Saved to output/cube.glb")

print("\nGenerating a tree...")
bs.generate("a blocky tree with green leaves").save("output/tree.glb")
print("✅ Saved to output/tree.glb")

print("\nGenerating a house...")
bs.generate("a small village house with a door").save("output/house.glb")
print("✅ Saved to output/house.glb")

print("\nDone! Check the output/ directory for your models.")
