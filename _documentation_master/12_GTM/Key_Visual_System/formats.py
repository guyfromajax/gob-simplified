#!/usr/bin/env python3
"""Cut every delivery format from the one master.

Rule established the hard way: nothing is ever independently reprocessed at another size.
Three separate bugs came from doing that -- a hardcoded pixel offset, a jersey mask that
moved when the pixels were resampled, and a keyline detector that under-performed at half
resolution. So the 2752x1536 master is the only source, and every format below is a
resample, a crop, or the master placed on a rebuilt ground.

The formats span 1:1 to 3:1, which no single crop can serve: a square crop of a two-shot
loses a player, and a 3:1 crop of it loses both heads. Two moves cover the range --
crop VERTICALLY for anything wider than 16:9, and EXTEND the ground for anything squarer.
Extending is possible because the master's background is a smooth separable gradient with
pure background along its top rows and both side columns, so it can be measured and
continued rather than invented.

Sizes verified against current platform guidance, Sept 2026.
"""
import pathlib
from PIL import Image
import numpy as np
from scipy import ndimage

ROOT = pathlib.Path(__file__).parent
OUT = ROOT / "formats"; OUT.mkdir(exist_ok=True)
MASTER = ROOT / "master" / "GOB_KV_rivals_2752x1536.png"


def place_extend(m, W, H, cw, ox, oy, falloff=0.34):
    """Master placed on a larger canvas, with the ground continued by edge replication.

    Not by synthesising a matching gradient -- I tried that, measuring the master's own
    horizontal colour profile and vertical falloff and rebuilding a separable field. It
    left a clearly visible rectangle where the content met the synthetic ground, because
    the real background is not perfectly separable and the join has nowhere to hide.

    Replicating the content's own edge pixels outward cannot mismatch: the extension
    literally begins with the pixels it is continuing. A gentle darkening with distance
    stops the replicated region reading as streaks.

    IMPORTANT: only extend past an edge that is pure background. The master's top and sides
    are; its bottom is jersey, so every layout here either fills the frame at the bottom or
    overflows it.
    """
    ch = int(round(cw * m.height / m.width))
    content = np.array(m.resize((cw, ch), Image.LANCZOS)).astype(np.float32)

    xs = np.clip(np.arange(W) - ox, 0, cw - 1)
    ys = np.clip(np.arange(H) - oy, 0, ch - 1)
    canvas = content[np.ix_(ys, xs)]

    dx = np.maximum(0, np.maximum(ox - np.arange(W), np.arange(W) - (ox + cw - 1))) / W
    dy = np.maximum(0, np.maximum(oy - np.arange(H), np.arange(H) - (oy + ch - 1))) / H
    d = np.sqrt(dx[None, :] ** 2 + dy[:, None] ** 2)
    canvas = canvas * (1 - falloff * np.clip(d / 0.30, 0, 1))[..., None]
    return Image.fromarray(np.clip(canvas, 0, 255).astype(np.uint8))


def band(m, y0f, y1f, W, H):
    """Vertical slice of the master, resampled to the target. For anything wider than 16:9."""
    src = m.crop((0, int(m.height * y0f), m.width, int(m.height * y1f)))
    # keep the aspect honest: widen the slice if the crop is still too tall
    want = W / H
    if src.width / src.height < want:
        need = int(src.width / want)
        cy = (src.height) // 2
        src = src.crop((0, max(0, cy - need // 2), src.width, min(src.height, cy + need - need // 2)))
    return src.resize((W, H), Image.LANCZOS)


def crop_to(m, cx, cy, half_w, W, H):
    """Tight crop around a point, in master fractions. For the square icon."""
    hw = half_w * m.width
    hh = hw * H / W
    box = (int(cx * m.width - hw), int(cy * m.height - hh),
           int(cx * m.width + hw), int(cy * m.height + hh))
    return m.crop(box).resize((W, H), Image.LANCZOS)


FORMATS = []


def emit(name, im, note):
    im.save(OUT / f"{name}.png")
    FORMATS.append((name, im.size, note))
    print(f"  {name:28s} {im.size[0]:>5} x {im.size[1]:<5} {note}")


if __name__ == "__main__":
    m = Image.open(MASTER).convert("RGB")
    print(f"master {m.size}\n")

    # --- 16:9 and near: straight resamples of the master -----------------------------
    # Named "kv" not "thumbnail": the launch-trailer thumbnail is a separate, typeset
    # layout built in stage.py, and these two must not get mixed up at upload time.
    emit("kv_16x9_1280x720", m.resize((1280, 720), Image.LANCZOS),
         "generic 16:9 key art")
    emit("x_post_1600x900", m.resize((1600, 900), Image.LANCZOS),
         "X in-feed post image")
    emit("discord_banner_960x540", m.resize((960, 540), Image.LANCZOS),
         "Discord server banner")

    # --- wider than 16:9: crop vertically, keeping heads and ball --------------------
    emit("x_header_1500x500", band(m, 0.04, 0.64, 1500, 500),
         "X profile header, 3:1")
    # 2.18:1 rather than a rounder number, chosen so the band clears the BOTTOM of both
    # numerals. Every ratio between about 2.4 and 3.0 slices a numeral in half.
    emit("web_hero_2560x1174", band(m, 0.00, 0.82, 2560, 1174),
         "landing page hero band")

    # --- YouTube banner: the safe area is only 1546x423 of 2560x1440 -----------------
    # Everything that must survive on a phone lives in that centre strip -- about 3.65:1 --
    # so the composition is scaled to sit inside it and the ground is extended to full bleed.
    # Full bleed at 2560 wide, pushed DOWN so the faces land inside the phone-safe strip
    # (y 508-931). Scaled to width the faces sit at y~314, so they need about +400. The
    # master then overflows the bottom, which is what we want -- the only extension is
    # upward into its own pure-background top edge.
    emit("yt_banner_2560x1440", place_extend(m, 2560, 1440, cw=2560, ox=0, oy=406),
         "YouTube channel banner (safe area 1546x423)")

    # --- squarer than 16:9: extend the ground above and below ------------------------
    # Bottom-aligned, so the extension is entirely upward. Centring it would have left a
    # gap below the jerseys, and replicating THAT edge downward smears the figures.
    emit("square_1080x1080", place_extend(m, 1080, 1080, cw=1080, ox=0,
                                          oy=1080 - int(1080 * m.height / m.width)),
         "square, both players")

    # --- 1:1 at icon size: a two-shot is unreadable, so feature Rozier and the ball ---
    emit("discord_icon_512x512", crop_to(m, cx=0.285, cy=0.44, half_w=0.135, W=512, H=512),
         "Discord server icon, Rozier + ball")

    print(f"\n{len(FORMATS)} formats written to {OUT}")
