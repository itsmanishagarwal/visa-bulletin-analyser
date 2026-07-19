#!/usr/bin/env python3
"""Generate og-image.png — the 1200x630 social-preview card.

Run after changing the title/branding, then commit the regenerated PNG:

    python gen_og_image.py

Requires Pillow (`pip install pillow`). Fonts are macOS Arial paths; adjust
BOLD/REG for other platforms.
"""
import os
from PIL import Image, ImageDraw, ImageFont

W, H = 1200, 630
BG = (14, 17, 23)          # #0e1117  (matches the app background)
PANEL = (26, 26, 46)       # #1a1a2e
GRID = (42, 42, 62)        # #2a2a3e
RED = (255, 75, 75)        # #ff4b4b  (brand accent)
GREEN = (74, 222, 128)     # #4ade80
WHITE = (250, 250, 250)
GREY = (154, 160, 170)

BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
REG = "/System/Library/Fonts/Supplemental/Arial.ttf"

img = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(img)

f_title = ImageFont.truetype(BOLD, 76)
f_sub = ImageFont.truetype(REG, 33)
f_tag = ImageFont.truetype(BOLD, 27)
f_dom = ImageFont.truetype(BOLD, 30)

d.rectangle([0, 0, 10, H], fill=RED)  # left brand accent bar

PAD = 80

# Chart motif (two ascending priority-date trends with a retrogression dip)
cx0, cy0, cx1, cy1 = PAD, 360, W - PAD, 545
for i in range(5):
    y = cy0 + (cy1 - cy0) * i / 4
    d.line([(cx0, y), (cx1, y)], fill=GRID, width=2)

def series(pts, color):
    xy = [(cx0 + (cx1 - cx0) * x, cy1 - (cy1 - cy0) * y) for x, y in pts]
    d.line(xy, fill=color, width=5, joint="curve")
    for x, y in xy:
        d.ellipse([x - 7, y - 7, x + 7, y + 7], fill=color)

series([(0, .18), (.2, .30), (.4, .28), (.6, .52), (.8, .60), (1, .82)], RED)
series([(0, .10), (.2, .16), (.4, .34), (.6, .40), (.8, .38), (1, .66)], GREEN)

d.text((PAD, 70), "Visa Bulletin Tracker", font=f_title, fill=WHITE)
d.text((PAD, 172), "20+ years of U.S. priority-date history & trends", font=f_sub, fill=GREY)

x, y = PAD, 250
for c in ["Final Action  ·  Filing", "EB & Family", "India · China · Mexico · Philippines"]:
    tw = d.textlength(c, font=f_tag)
    d.rounded_rectangle([x, y, x + tw + 40, y + 52], radius=10, fill=PANEL)
    d.text((x + 20, y + 12), c, font=f_tag, fill=RED)
    x += tw + 40 + 18

dom = "visa-bulletin-analyser.krutilabs.com"
d.text((W - PAD - d.textlength(dom, font=f_dom), 560), dom, font=f_dom, fill=RED)

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "og-image.png")
img.save(out, "PNG")
print("wrote", out, img.size)
