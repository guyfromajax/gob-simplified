"""
Recruit portrait painting — the portable, deterministic recolor core.

Turns a recruit's stored KIT (pre-finish white RGBA bust + precomputed tank
mask, in R2) into:
  - a finished WHITE display master (weeks 1-34 UI), or
  - a finished UNIFORMED master painted into a team's colors (post-signing).

No AI and no segmentation here: the mask was baked at generation time, so this
is pure masked-recolor + wordmark + canvas-finish. It is a VERBATIM port of the
proven league pipeline (scripts/apply_team_uniforms.recolor_and_stamp +
scripts/finish_portraits.finish), so recruit portraits render pixel-identical to
the live league players. This is also the "portable core" a future downloadable
build reimplements.

Deps: numpy, scipy, Pillow. Functions take/return PNG bytes (in-memory) so the
lazy paint service can read a kit from R2 and write a master back with no disk.
"""
import io
import os

# ---- framing / wordmark constants (identical to the league finish stage) -----
CANVAS_W, CANVAS_H = 3530, 3412
CROP_KEEP_FRAC = 0.966          # fraction of bust height the finish crop keeps
WM_VISIBLE_FRAC = 0.50          # fraction of wordmark letter-height shown above the crop
WM_WIDTH_FRAC = 0.72            # wordmark width as a fraction of tank width

_HERE = os.path.dirname(os.path.abspath(__file__))
# Bundled first (deterministic across OSes), then common system locations.
WM_FONT_CANDIDATES = [
    os.path.join(_HERE, "..", "assets", "fonts", "LiberationSans-Bold.ttf"),
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
]


def _find_wm_font():
    for p in WM_FONT_CANDIDATES:
        if os.path.exists(p):
            return p
    return WM_FONT_CANDIDATES[0]


def hex2rgb(h):
    h = str(h or "").lstrip("#") or "000000"
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _lum(a):
    return 0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]


def recolor_and_stamp(a, alpha, tank, primary, secondary, wordmark):
    """Paint the tank `primary`, trim `secondary`, stamp the wordmark; return the
    recolored RGBA (person on transparent bg). a=RGB float array, alpha=0-255
    person mask, tank=bool tank mask. VERBATIM from apply_team_uniforms."""
    import numpy as np
    from scipy import ndimage
    from PIL import Image, ImageDraw, ImageFont

    H, W, _ = a.shape
    ys, xs = np.where(tank)
    if len(ys) == 0:
        raise ValueError("no tank found")
    top, bot = ys.min(), ys.max()
    cx = int((xs.min() + xs.max()) / 2)
    tone = np.clip(_lum(a) / 238.0, 0.55, 1.12)[..., None]     # preserve folds
    P = np.array(primary, np.float32)
    S = np.array(secondary, np.float32)

    out = a.copy()
    soft = ndimage.gaussian_filter(tank.astype(np.float32), 1.2)[..., None]
    out = out * (1 - soft) + (P[None, None, :] * tone) * soft

    # trim ring: collar + armholes (not the cropped bottom)
    rim = tank & ~ndimage.binary_erosion(tank, iterations=8)
    rim[int(bot - 6):] = False
    rimS = ndimage.gaussian_filter(rim.astype(np.float32), 0.6)[..., None]
    out = out * (1 - rimS) + (S[None, None, :] * tone) * rimS

    # WORDMARK — bold block (Liberation) with a keyline, placed LOW so the finish
    # crop shows only its top slice. Fill = secondary; keyline flips for contrast.
    tank_w = xs.max() - xs.min()
    s_lum = 0.299 * secondary[0] + 0.587 * secondary[1] + 0.114 * secondary[2]
    keyline = (26, 28, 46) if s_lum > 200 else (238, 242, 250)
    fill = tuple(int(v) for v in secondary)
    wm_font = _find_wm_font()
    target = int(tank_w * WM_WIDTH_FRAC)
    probe = ImageDraw.Draw(Image.new("L", (10, 10)))
    font, ow, b = None, 4, (0, 0, 0, 0)
    for sz in range(420, 60, -8):
        f = ImageFont.truetype(wm_font, sz)
        ow = max(4, round(sz * 0.055))
        b = probe.textbbox((0, 0), wordmark, font=f, stroke_width=ow)
        if b[2] - b[0] <= target:
            font = f
            break
    if font is None:
        font = ImageFont.truetype(wm_font, 68)
    wm_h = b[3] - b[1]
    tx = cx - (b[2] - b[0]) // 2 - b[0]
    ty = int(CROP_KEEP_FRAC * H - WM_VISIBLE_FRAC * wm_h) - b[1]
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(layer).text((tx, ty), wordmark, font=font, fill=fill + (255,),
                               stroke_width=ow, stroke_fill=keyline + (255,))
    lay = np.asarray(layer).astype(np.float32)

    # very mild arc so the visible slice reads as a natural chest print
    amp = max(2, int(0.018 * (bot - top)))
    half = max(1.0, 0.5 * tank_w)
    shift = np.clip((amp * ((np.arange(W) - cx) / half) ** 2), 0, amp).astype(int)
    arced = np.zeros_like(lay)
    for x in range(W):
        s = int(shift[x])
        arced[s:, x] = lay[:H - s, x] if s else lay[:, x]

    la = ndimage.gaussian_filter(arced[..., 3] / 255.0, 0.6)       # screen-print softness
    la = la * ndimage.binary_erosion(tank, iterations=1)           # clip to cloth
    a_lay = la[..., None]
    out = out * (1 - 0.96 * a_lay) + arced[..., :3] * (0.96 * a_lay)

    return np.dstack([np.clip(out, 0, 255), alpha]).astype("uint8")


def _finish_rgba(im):
    """Scale to the canvas width, top-align, clean the alpha edge -> the 3530x3412
    finished master. VERBATIM transform from finish_portraits.finish."""
    import numpy as np
    from scipy import ndimage
    from PIL import Image

    arr = np.asarray(im.convert("RGBA"))
    rgb = arr[..., :3].copy()
    alpha = arr[..., 3]
    if (alpha > 20).sum() == 0:
        raise ValueError("empty image")

    a = ndimage.binary_erosion(alpha > 20, iterations=2).astype(np.float32)
    a = ndimage.gaussian_filter(a, 1.5)
    alpha = np.clip(a * 255, 0, 255).astype(np.uint8)

    src = Image.fromarray(np.dstack([rgb, alpha]), "RGBA")
    scale = CANVAS_W / src.width
    new_h = max(1, round(src.height * scale))
    src = src.resize((CANVAS_W, new_h), Image.LANCZOS)

    canvas = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    canvas.alpha_composite(src, (0, 0))
    return canvas


def _png_bytes(im):
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def make_white_master(kit_png):
    """kit bust PNG bytes -> finished WHITE display master PNG bytes (no recolor)."""
    from PIL import Image
    im = Image.open(io.BytesIO(kit_png)).convert("RGBA")
    return _png_bytes(_finish_rgba(im))


def make_signed_master(kit_png, mask_png, primary_hex, secondary_hex, wordmark):
    """kit bust + tank mask (PNG bytes) recolored into a team uniform ->
    finished UNIFORMED master PNG bytes. Colors are hex strings; wordmark text."""
    import numpy as np
    from PIL import Image

    arr = np.asarray(Image.open(io.BytesIO(kit_png)).convert("RGBA"))
    a = arr[..., :3].astype(np.float32)
    alpha = arr[..., 3]
    tank = np.asarray(Image.open(io.BytesIO(mask_png)).convert("L")) > 128
    rgba = recolor_and_stamp(a, alpha, tank,
                             hex2rgb(primary_hex), hex2rgb(secondary_hex),
                             str(wordmark or "").upper())
    return _png_bytes(_finish_rgba(Image.fromarray(rgba, "RGBA")))
