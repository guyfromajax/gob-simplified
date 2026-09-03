#!/usr/bin/env python3
"""Re-stage the two cut-out figures into layouts a crop cannot produce.

Three deliverables need the players moved relative to each other rather than reframed:
the square (they must close the gap and overlap), the Discord icon (Rozier's whole head,
ball sacrificed), and a trailer thumbnail with the logo and OFFICIAL TRAILER on the left.

The ground is regenerated rather than borrowed. Each player keeps a pool of his own team
colour behind him, so moving Rozier to the right does not strand a blue player on orange.
"""
import pathlib
from PIL import Image, ImageDraw, ImageFont
import numpy as np
from scipy import ndimage

ROOT = pathlib.Path(__file__).parent
OUT = ROOT / "formats"; OUT.mkdir(exist_ok=True)
CUT = ROOT / "cutouts"
LOGO = ROOT / "assets" / "gob_logo.png"
FONT = str(ROOT / "source" / "BebasNeuePro-Bold.otf")

INK = np.array([9, 11, 17], np.float32)
COOL = np.array([34, 58, 112], np.float32)     # sampled from the master's left field
WARM = np.array([124, 52, 10], np.float32)     # and its right
ORANGE = (247, 148, 32)                        # #F79420, Styleguide.md


def ground(W, H, glows):
    """Near-black field with a soft pool of colour behind each figure."""
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    field = np.repeat(np.repeat(INK[None, None, :], H, 0), W, 1).copy()
    for xf, yf, rad, col, k in glows:
        d = np.sqrt(((xx / W - xf) * (W / H)) ** 2 + (yy / H - yf) ** 2) / rad
        field += col[None, None, :] * (k * np.exp(-(d ** 2) * 1.6))[..., None]
    return field


MASTER = ROOT / "master" / "GOB_KV_rivals_2752x1536.png"

# Buckles is always the REAR figure -- nothing ever passes behind him -- so he does not need
# a matte, and he should not have one. His outer locs sit less than 12 levels away from the
# background, below any threshold that does not also key noise, so the difference matte ran
# a straight vertical line down that side and sliced them off. Instead he is composited as a
# rectangular SLAB of the master, feathered in. The slab runs to the master's right edge, so
# only its left and top edges need to blend, and both of those are pure background.
BUCKLES_SLAB = (1420, 0, 2752, 1536)      # master pixels
BUCKLES_FIG = (1499, 2608, 101, 1527)     # his actual figure bounds inside the master


def fade_bottom(arr, frac):
    """Dissolve the bottom `frac` of an alpha channel, so a figure that stops mid-frame
    sinks into the ground instead of ending on a cut edge."""
    if not frac:
        return arr
    n = max(1, int(arr.shape[0] * frac))
    arr[-n:] *= (np.linspace(1, 0, n) ** 1.5)[:, None]
    return arr


def put_slab(canvas, master, height, cx, bottom, feather=0.16, fade=0.0):
    """Place a rectangular slab of the master, scaled so BUCKLES's figure lands at the
    given height/position, and dissolve its left and top edges into the ground."""
    H, W, _ = canvas.shape
    sx0, sy0, sx1, sy1 = BUCKLES_SLAB
    fx0, fx1, fy0, fy1 = BUCKLES_FIG
    scale = (height * H) / (fy1 - fy0)

    sw, sh = int((sx1 - sx0) * scale), int((sy1 - sy0) * scale)
    slab = np.array(master.crop(BUCKLES_SLAB).resize((sw, sh), Image.LANCZOS)).astype(np.float32)

    x0 = int(cx * W - ((fx0 + fx1) / 2 - sx0) * scale)
    y0 = int(bottom * H - (fy1 - sy0) * scale)

    fw = max(4, int(feather * sw))
    mask = np.ones((sh, sw), np.float32)
    mask[:, :fw] *= np.linspace(0, 1, fw)[None, :] ** 0.8
    mask[:int(fw * 0.9)] *= np.linspace(0, 1, int(fw * 0.9))[:, None] ** 0.8
    if fade:
        cut = int((fy1 - sy0) * scale)          # fade from the figure's own base, not the slab's
        mask[:cut] = fade_bottom(mask[:cut], fade)
        mask[cut:] = 0.0

    xa, ya = max(0, x0), max(0, y0)
    xb, yb = min(W, x0 + sw), min(H, y0 + sh)
    if xb <= xa or yb <= ya:
        return
    src = slab[ya - y0:yb - y0, xa - x0:xb - x0]
    al = mask[ya - y0:yb - y0, xa - x0:xb - x0][..., None]
    canvas[ya:yb, xa:xb] = canvas[ya:yb, xa:xb] * (1 - al) + src * al


def put(canvas, fig, height, cx, bottom, fade=0.0):
    """Composite a cut-out at a given height, centred on cx, with its base at `bottom`.
    All three are fractions of the canvas."""
    H, W, _ = canvas.shape
    h = int(height * H)
    w = max(1, int(fig.width * h / fig.height))
    f = np.array(fig.resize((w, h), Image.LANCZOS)).astype(np.float32)
    x0 = int(cx * W - w / 2)
    y0 = int(bottom * H - h)

    xa, ya = max(0, x0), max(0, y0)
    xb, yb = min(W, x0 + w), min(H, y0 + h)
    if xb <= xa or yb <= ya:
        return
    if fade:
        f[..., 3] = fade_bottom(f[..., 3], fade)
    src = f[ya - y0:yb - y0, xa - x0:xb - x0]
    al = src[..., 3:4] / 255.0
    canvas[ya:yb, xa:xb] = canvas[ya:yb, xa:xb] * (1 - al) + src[..., :3] * al


def contact_shadow(canvas, fig, height, cx, bottom, strength=0.45, blur=0.02):
    """A soft dark pool under and behind a figure, so the one in front reads as in front."""
    H, W, _ = canvas.shape
    h = int(height * H)
    w = max(1, int(fig.width * h / fig.height))
    a = np.array(fig.resize((w, h), Image.LANCZOS))[..., 3].astype(np.float32) / 255.0
    lay = np.zeros((H, W), np.float32)
    x0, y0 = int(cx * W - w / 2), int(bottom * H - h)
    xa, ya = max(0, x0), max(0, y0)
    xb, yb = min(W, x0 + w), min(H, y0 + h)
    if xb <= xa or yb <= ya:
        return
    lay[ya:yb, xa:xb] = a[ya - y0:yb - y0, xa - x0:xb - x0]
    lay = ndimage.gaussian_filter(lay, blur * W)
    canvas *= (1 - strength * lay)[..., None]


def text(canvas, s, size, cx, cy, fill=(255, 255, 255), track=0.14):
    """Letterspaced caps, centred on (cx, cy) in canvas fractions."""
    H, W, _ = canvas.shape
    f = ImageFont.truetype(FONT, size)
    tmp = Image.new("L", (8, 8)); d0 = ImageDraw.Draw(tmp)
    widths = [d0.textlength(c, font=f) for c in s]
    tw = sum(widths) + track * size * (len(s) - 1)
    im = Image.new("RGBA", (int(tw) + size, int(size * 1.7)), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    x = size / 2
    for c, wch in zip(s, widths):
        d.text((x, size * 0.12), c, font=f, fill=fill + (255,))
        x += wch + track * size
    arr = np.array(im)
    ys, xs = np.where(arr[..., 3] > 6)
    im = im.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
    put(canvas, im, im.height / H, cx, cy + im.height / H / 2)


def save(canvas, name, size=None):
    im = Image.fromarray(np.clip(canvas, 0, 255).astype(np.uint8))
    if size:
        im = im.resize(size, Image.LANCZOS)
    im.save(OUT / f"{name}.png")
    print(f"  {name:34s} {im.size[0]:>5} x {im.size[1]}")
    return im


if __name__ == "__main__":
    roz = Image.open(CUT / "rozier.png").convert("RGBA")
    master = Image.open(MASTER).convert("RGB")
    logo = Image.open(LOGO).convert("RGBA")

    # ---------- square: closed up, Rozier in front ---------------------------------
    W = H = 2160
    # Glows kept apart and weak. Overlapping them at full strength mixed to purple, which
    # is neither team's colour and read as a wash rather than two pools of light.
    c = ground(W, H, [(0.30, 0.42, 0.50, COOL, 0.80), (0.80, 0.40, 0.52, WARM, 0.80)])
    put_slab(c, master, height=0.86, cx=0.760, bottom=1.00, feather=0.30)
    contact_shadow(c, roz, height=0.96, cx=0.355, bottom=1.03, strength=0.5)
    put(c, roz, height=0.96, cx=0.355, bottom=1.03)
    save(c, "square_1080x1080", (1080, 1080))

    # ---------- Discord icon: whole head, ball is expendable ------------------------
    W = H = 1024
    c = ground(W, H, [(0.5, 0.45, 0.75, COOL, 1.0)])
    put(c, roz, height=1.55, cx=0.5, bottom=1.62)
    save(c, "discord_icon_512x512", (512, 512))

    # ---------- launch-trailer thumbnail -------------------------------------------
    W, H = 2560, 1440
    c = ground(W, H, [(0.18, 0.46, 0.44, COOL, 0.45), (0.62, 0.40, 0.46, COOL, 0.70),
                      (0.93, 0.44, 0.42, WARM, 0.85)])
    put_slab(c, master, height=0.90, cx=0.865, bottom=1.02)
    contact_shadow(c, roz, height=0.98, cx=0.580, bottom=1.05, strength=0.5)
    put(c, roz, height=0.98, cx=0.580, bottom=1.05)

    lw = int(W * 0.300)
    lg = logo.resize((lw, int(lw * logo.height / logo.width)), Image.LANCZOS)
    put(c, lg, lg.height / H, 0.200, 0.420)
    text(c, "OFFICIAL TRAILER", 104, 0.200, 0.560)
    save(c, "yt_thumbnail_trailer_1280x720", (1280, 720))
    save(c, "yt_thumbnail_trailer_2560x1440")

    # ---------- YouTube channel banner ---------------------------------------------
    # Desktop and mobile share the SAME 423px-tall band of the 1440 frame -- desktop is only
    # wider -- so everything that must be seen lives in 29% of the height.
    #
    # This is the X header's framing, which works, scaled to that band: ONE slab of the whole
    # master with both players at their own spacing. Compositing them separately put Buckles
    # on a slab whose background did not match the generated ground, and it read as a bright
    # rectangle behind him. A single slab has no internal join at all.
    #
    # Its left, right and top edges are the master's own pure background, so the frame is
    # filled by replicating those outward -- the extension begins with the pixels it
    # continues, so it cannot mismatch. The bottom is jersey, so instead of replicating it
    # (which smears) the figures are dissolved down into the dark ground.
    W, H = 2560, 1440
    HEAD_TOP, BALL_BOT = 119, 1153       # master rows: top of Rozier's hair, base of the ball
    BAND_TOP = (H - 423) // 2

    scale = 400 / (BALL_BOT - HEAD_TOP)  # that span must fit inside the 423px band
    cw, ch = int(2752 * scale), int(1536 * scale)
    ox, oy = (W - cw) // 2, (BAND_TOP + 7) - int(HEAD_TOP * scale)

    content = np.array(master.resize((cw, ch), Image.LANCZOS)).astype(np.float32)
    xs = np.clip(np.arange(W) - ox, 0, cw - 1)
    ys = np.clip(np.arange(H) - oy, 0, ch - 1)
    c = content[np.ix_(ys, xs)]

    # dissolve below the figures rather than repeating their last row down the frame
    # A gentle ramp is not enough: at half strength the repeated jersey rows still read as
    # vertical streaks running to the bottom of the frame. Take it to black within about
    # 200px of the figures' base so they dissolve rather than smear.
    base = oy + ch
    ramp = np.clip((np.arange(H) - (base - 60)) / 200.0, 0, 1)
    c *= (1 - 0.99 * ramp[:, None] ** 0.6)[..., None]

    save(c, "yt_banner_2560x1440")
