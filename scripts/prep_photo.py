"""
Prepare the profile photo for clean, perfectly framed ASCII conversion:
  1. Crop around subject's head and shoulders (matching portfolio avatar framing)
  2. Detect and wash out sky background to clean pure white (maps to spaces)
  3. Boost local contrast and normalize grayscale histogram

Output: source-prepped.png, consumed by make_ascii_svg.py.
"""
import os
import sys
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
INP = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "source-photo.png")
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "..", "source-prepped.png")

im = Image.open(INP).convert("RGB")
w, h = im.size

# Frame head and shoulders (matching portfolio hero avatar placement)
crop_size = 520
left = max(0, (w - crop_size) // 2)
top = 500
right = left + crop_size
bottom = min(h, top + crop_size)
cropped = im.crop((left, top, right, bottom))

rgb = np.array(cropped, dtype=float)
r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]

# Detect sky blue background
bg_mask = (b > 115) & (b > r + 18) & (b > g + 8)

gray = np.array(cropped.convert("L"), dtype=float)
# Map background to pure white (255) -> maps to empty spaces in ASCII
gray[bg_mask] = 255.0

prepped = Image.fromarray(gray.astype(np.uint8))
prepped = ImageOps.autocontrast(prepped, cutoff=2)
prepped = ImageEnhance.Contrast(prepped).enhance(1.22)
prepped.save(OUT)

print(f"wrote {OUT} (size: {prepped.size})")
