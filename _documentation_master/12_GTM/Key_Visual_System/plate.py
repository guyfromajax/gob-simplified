#!/usr/bin/env python3
"""Base plates for the rivals key visual.

The job of a plate is NOT to look finished. It is to fix the three things a generator
should not be allowed to decide: WHO is in frame, WHERE they sit, and WHAT the light is
doing. Everything below the crop -- torsos, arms, a ball, an environment -- is left
deliberately empty so Nano Banana has somewhere to work and no reason to repaint a face.

Two tiers, because the open question is how far the figures can travel from their source
crop before the faces stop being Jamie's players:

  A  waist-up, squared off      -- generator invents shoulders and background only
  B  dynamic, full body implied -- generator invents ~75% of each figure

Heads are never rotated. These portraits are dead-on frontal; any turn has to come from
the body, so lean is applied as a whole-cutout tilt, which shears nothing in the face.
"""
import pathlib
from PIL import Image
import numpy as np

ROOT = pathlib.Path(__file__).parent
OUT = ROOT / "plates"; OUT.mkdir(exist_ok=True)
W, H = 3840, 2160

BLUE_SRC   = ROOT / "source" / "rozier_portrait_trimmed.png"      # #22 Sterling Knights, dark fade, neutral
ORANGE_SRC = ROOT / "source" / "buckles_portrait_trimmed.png"    # Johnnies, long dark hair, serious

INK    = np.array([10, 12, 18], dtype=np.float32)     # near-black field
COOL   = np.array([28, 46, 88], dtype=np.float32)     # cold blue, left
WARM   = np.array([116, 46, 6], dtype=np.float32)     # deep orange, right


def ground(split=0.5, strength=0.55, floor=0.30):
    """Dark field, cold on the left and warm on the right, meeting at `split`.

    Kept dark on purpose: a generator handed a bright plate tends to raise the whole
    frame to match, and the brand is cool-and-dark with one hot accent.
    """
    x = np.linspace(0, 1, W)[None, :, None]
    t = np.clip((x - split) * 3.2, -1, 1)                     # -1 cold .. +1 warm
    side = np.where(t < 0, COOL[None, None, :], WARM[None, None, :])
    field = INK[None, None, :] + side * (np.abs(t) ** 1.5) * strength

    # vertical falloff: light lives at head height, floor and ceiling go to black
    y = np.linspace(0, 1, H)[:, None, None]
    vign = floor + (1 - floor) * np.exp(-((y - 0.42) ** 2) / 0.10)
    return Image.fromarray(np.clip(field * vign, 0, 255).astype(np.uint8))


def place(layer, src, head_h, cx, head_top, tilt=0.0, fade=0.0):
    """Scale a cutout so the visible subject is `head_h` px tall, centre it on `cx`,
    put its top edge at `head_top`, and lean it by `tilt` degrees.

    `fade` dissolves the bottom fraction of the cutout to nothing. The source portraits
    are cut off square at mid-chest, and once a cutout is tilted that square cut swings
    into frame as a hard diagonal slab -- which is both ugly and, more to the point, a
    lie: it tells the generator the body ENDS there. Fading it says "continue from here"
    instead, which is exactly the instruction we want the plate to carry.
    """
    im = Image.open(src).convert("RGBA")
    s = head_h / im.height
    im = im.resize((max(1, int(im.width * s)), head_h), Image.LANCZOS)
    if fade:
        a = np.array(im, dtype=np.float32)
        n = int(im.height * fade)
        ramp = np.linspace(1, 0, n) ** 0.75
        a[-n:, :, 3] *= ramp[:, None]
        im = Image.fromarray(a.astype(np.uint8))
    if tilt:
        im = im.rotate(tilt, resample=Image.BICUBIC, expand=True)
    layer.alpha_composite(im, (int(cx - im.width / 2), int(head_top)))


def plate(name, blue, orange, split=0.5, strength=0.55, note=""):
    base = ground(split, strength).convert("RGBA")
    subj = Image.new("RGBA", (W, H), (0, 0, 0, 0))     # subjects alone, for the metric
    # far figure first so the near one overlaps
    order = sorted([("b", blue), ("o", orange)], key=lambda kv: kv[1]["head_h"])
    for k, cfg in order:
        place(subj, BLUE_SRC if k == "b" else ORANGE_SRC, **cfg)
    base.alpha_composite(subj)
    out = base.convert("RGB")
    out.save(OUT / f"{name}.png")
    out.resize((210, 118), Image.LANCZOS).save(OUT / f"{name}_210.png")

    # how much of the frame is still empty ground -- that is the generator's workspace
    a = np.array(subj)[:, :, 3]
    print(f"{name:5s} subject {100*(a>10).mean():4.1f}% of frame, "
          f"{100-100*(a>10).mean():4.1f}% open   {note}")


if __name__ == "__main__":
    # ---- TIER A: squared off, waist-up. Heads big, bodies cropped by frame bottom. ----
    plate("A1",
          blue  =dict(head_h=2050, cx=1180, head_top=250),
          orange=dict(head_h=2050, cx=2660, head_top=250),
          note="upright, symmetrical, type in the centre gap")

    plate("A2",
          blue  =dict(head_h=2100, cx=1120, head_top=210, tilt=-7),
          orange=dict(head_h=2100, cx=2720, head_top=210, tilt=7),
          note="5 deg opposing lean -- shoulders angle in, faces stay frontal")

    # ---- TIER B: dynamic. Small heads, offset, big open lower frame for bodies. ----
    plate("B1",
          blue  =dict(head_h=1230, cx=1090, head_top=200, tilt=-11, fade=0.30),
          orange=dict(head_h=1330, cx=2760, head_top=330, tilt=9, fade=0.30),
          note="offset heights + lean, ~60% of frame left for bodies and court")

    plate("B2",
          blue  =dict(head_h=1560, cx=1250, head_top=430, tilt=-8, fade=0.26),
          orange=dict(head_h=1120, cx=2830, head_top=170, tilt=13, fade=0.34),
          note="depth: blue near and low, orange far and high -- implies low camera")
