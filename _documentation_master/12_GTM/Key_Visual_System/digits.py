#!/usr/bin/env python3
"""Jersey numerals for the KV.

Neither harvesting nor a matching font was available. Every numeral in all 98 portraits is
cut off partway down by the portrait crop -- Rozier's own "32" included -- so there is
nothing complete to lift. The repo carries only Bebas Neue Pro, Oswald and Liberation Sans;
the container adds DejaVu, FreeSans and Carlito. No varsity face anywhere.

First attempt drew the digits as hand-built polygons on a unit grid, aiming for a varsity
block face. It came out crude -- the 2's lower diagonal inverted into a wedge and the 3's
counters read as slots rather than bowls. Constructing letterforms by hand is a typographer's
job, not a geometry exercise, and it showed.

This does the boring reliable thing instead: a heavy grotesque, stretched wider to jersey
proportions, with a dark keyline and a soft drop shadow. Jamie's brief was "close enough not
to be distracting", and these land about 70px tall in the KV, where weight, width and colour
carry the read and letterform subtleties are invisible.
"""
import pathlib
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np

ROOT = pathlib.Path(__file__).parent
OUT = ROOT / "assets"; OUT.mkdir(exist_ok=True)
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

WIDEN = 1.18       # jersey numerals are far wider than a text face
TRACK = -0.02      # and set tight


def number(text, height, ink=(246, 246, 248), edge=(20, 18, 22),
           keyline=0.052, shadow=0.045, ss=3):
    """White numeral over a dark keyline, with a soft shadow under it."""
    f = ImageFont.truetype(FONT, height * ss)
    pad = int(height * ss * 0.35)
    probe = Image.new("L", (10, 10))
    w = int(sum(ImageDraw.Draw(probe).textlength(c, font=f) for c in text)
            + TRACK * height * ss * (len(text) - 1))
    im = Image.new("L", (w + pad * 2, int(height * ss * 1.6)), 0)
    d = ImageDraw.Draw(im)
    x = pad
    for c in text:
        d.text((x, pad // 2), c, font=f, fill=255)
        x += d.textlength(c, font=f) + TRACK * height * ss

    a = np.array(im)
    ys, xs = np.where(a > 8)
    im = Image.fromarray(a).crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))

    # to jersey proportions, then down from the supersample
    tgt_h = height
    tgt_w = int(im.width * (tgt_h / im.height) * WIDEN)
    core = im.resize((tgt_w, tgt_h), Image.LANCZOS)
    A = np.array(core).astype(np.float32) / 255.0

    k = max(1, int(height * keyline))
    pad2 = k * 3
    P = np.pad(A, pad2)
    grown = np.array(Image.fromarray((P * 255).astype(np.uint8))
                     .filter(ImageFilter.MaxFilter(k * 2 + 1))).astype(np.float32) / 255.0
    sh = np.array(Image.fromarray((grown * 255).astype(np.uint8))
                  .filter(ImageFilter.GaussianBlur(height * shadow))).astype(np.float32) / 255.0

    H, W = grown.shape
    out = np.zeros((H, W, 4), dtype=np.float32)
    out[..., :3] = np.array(edge, np.float32)
    out[..., 3] = np.clip(sh * 0.5 + grown, 0, 1) * 255
    out[..., :3] = out[..., :3] * (1 - P[..., None]) + np.array(ink, np.float32) * P[..., None]
    return Image.fromarray(out.astype(np.uint8))


if __name__ == "__main__":
    for t in ("32", "43"):
        n = number(t, 420); n.save(OUT / f"num_{t}.png"); print(f"num_{t} {n.size}")
    sheet = Image.new("RGB", (1600, 620), (38, 62, 122))
    for i, t in enumerate(("32", "43")):
        n = Image.open(OUT / f"num_{t}.png"); sheet.paste(n, (110 + i * 760, 90), n)
    sheet.save(ROOT / "_digits_check.png")
