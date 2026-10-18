"""
Prepare the profile photo for clean ASCII conversion:
  1. Remove / wash out the background to white
  2. Normalize contrast and smooth high-frequency noise
  3. Crop square around subject's face and upper body
  4. Composite onto white canvas

Output: source-prepped.png (grayscale), consumed by make_ascii_svg.py.

    python scripts/prep_photo.py [source-photo.png] [source-prepped.png]
"""
import os
import sys
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
INP = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "source-photo.png")
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "..", "source-prepped.png")

im = Image.open(INP).convert("RGB")
rgb = np.array(im, dtype=float)
r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]

# Detect blue studio/sky background: blue channel is higher than red and green
bg_mask = (b > 125) & (b > r + 30) & (b > g + 12)

# Convert to grayscale
gray = np.array(im.convert("L"), dtype=float)

# Map background to pure white (255) so it maps to blank space (' ') in ASCII
gray[bg_mask] = 255.0

# Gentle Gaussian blur to remove paper/sensor noise while keeping edges
prepped = Image.fromarray(gray.astype(np.uint8))
prepped = prepped.filter(ImageFilter.GaussianBlur(radius=0.8))

# Enhance contrast on facial features
enhancer = ImageEnhance.Contrast(prepped)
prepped = enhancer.enhance(1.2)

prepped.save(OUT)
print(f"wrote {OUT} (size: {prepped.size})")
