#!/usr/bin/env python3
"""Preview SKY wordmark DESIGN variants on the normalized colored masters, so we
can pick a look before locking it into finish_chapel_hill_colored.py."""
import os, sys
sys.path.insert(0, "scripts")
import numpy as np
from scipy import ndimage
from PIL import Image, ImageDraw, ImageFont
from normalize_chapel_hill import reframe
import finish_chapel_hill_colored as fc
from apply_team_uniforms import team_info, hex2rgb, _lum, WM_WIDTH_FRAC, \
    CROP_KEEP_FRAC, WM_VISIBLE_FRAC

LIB_BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
LIB_ITAL = "/usr/share/fonts/truetype/liberation/LiberationSans-BoldItalic.ttf"
BEBAS = "FrontEnd/static/fonts/BebasNeuePro-Bold.otf"
NAVY = hex2rgb("#1e2f5b")
WHITE = (238, 242, 250)


def erased_base(name):
    """reframe + erase old wordmark + recolor jersey — but DO NOT stamp."""
    _, _, p, s = team_info("Chapel Hill")
    rf = reframe(Image.open(f"tmp/portrait-pilot/designed/{name}.png"), np, ndimage)
    arr = np.asarray(rf); rgb = arr[..., :3].astype(np.float32); alpha = arr[..., 3]
    person = alpha > 128; H, W, _ = rgb.shape
    jersey, body, navy, _ = fc.jersey_masks(rgb, person, np, ndimage)
    ys, xs = np.where(jersey)
    interior = ndimage.binary_erosion(jersey, iterations=10)
    jtop, jbot = ys.min(), ys.max(); jcx, jw = (xs.min()+xs.max())/2, xs.max()-xs.min()
    YY, XX = np.mgrid[0:H, 0:W]
    zone = interior & (YY > jtop+0.04*(jbot-jtop)) & (np.abs(XX-jcx) < 0.46*jw)
    med = np.median(rgb[body & interior], 0)
    feather = ndimage.gaussian_filter(zone.astype(np.float32), 6.0)[..., None]
    rgb = rgb*(1-feather) + med[None, None, :]*feather
    P = np.array(hex2rgb(p), np.float32)
    tone = np.clip(_lum(rgb)/190.0, 0.6, 1.12)[..., None]
    out = rgb.copy()
    trim = navy & ~ndimage.binary_erosion(jersey, iterations=12)
    bodysoft = ndimage.gaussian_filter((jersey & ~trim).astype(np.float32), 1.0)[..., None]
    out = out*(1-bodysoft) + (P[None, None, :]*tone)*bodysoft
    S = np.array(hex2rgb(s), np.float32)
    trimsoft = ndimage.gaussian_filter(trim.astype(np.float32), 0.6)[..., None]
    tnavy = np.clip(_lum(rgb)/90.0, 0.7, 1.2)[..., None]
    out = out*(1-trimsoft) + (S[None, None, :]*tnavy)*trimsoft
    return out, alpha, jersey, trim, (jtop, jbot, jcx, jw)


def stamp(out, jersey, trim, geo, font_path, italic_px=0, outline=0,
          fold=False, size_frac=WM_WIDTH_FRAC):
    """Render SKY with the given design onto the (already recolored) jersey."""
    H, W, _ = out.shape
    jtop, jbot, jcx, jw = geo
    cx = int(jcx); tank_w = jw
    # fit font to width
    target = int(tank_w * size_frac)
    for sz in range(260, 40, -6):
        f = ImageFont.truetype(font_path, sz)
        d0 = ImageDraw.Draw(Image.new("L", (10, 10)))
        bb = d0.textbbox((0, 0), "SKY", font=f, stroke_width=outline)
        if bb[2]-bb[0] <= target:
            break
    wm_h = bb[3]-bb[1]
    # render letters (navy) + white keyline on an RGBA layer, then composite
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    tx = cx - (bb[2]-bb[0])//2 - bb[0]
    ty = int(CROP_KEEP_FRAC*H - WM_VISIBLE_FRAC*wm_h) - bb[1]
    if outline:
        d.text((tx, ty), "SKY", font=f, fill=NAVY+(255,),
               stroke_width=outline, stroke_fill=WHITE+(255,))
    else:
        d.text((tx, ty), "SKY", font=f, fill=NAVY+(255,))
    lay = np.asarray(layer).astype(np.float32)
    la = lay[..., 3:4]/255.0
    if italic_px:  # shear for athletic lean (top pushed right)
        lay2 = np.zeros_like(lay)
        for y in range(H):
            sh = int(italic_px*(1-(y)/H))
            if 0 <= sh < W:
                lay2[y, sh:] = lay[y, :W-sh]
        lay = lay2; la = lay[..., 3:4]/255.0
    ink = lay[..., :3]
    if fold:  # let the fabric folds modulate the ink so it reads as printed-on
        tonef = np.clip(_lum(out)/np.maximum(_lum(out)[jersey].mean(), 1)*1.0, 0.8, 1.12)[..., None]
        ink = ink*tonef
    a = ndimage.gaussian_filter((la[..., 0]), 0.6)[..., None]     # print softness
    a = a * ndimage.binary_erosion(jersey & ~trim, iterations=1)[..., None]
    return out*(1-a) + ink*a


def main():
    players = ["Dale Butler", "Otis Nixon"]
    variants = [
        ("A: current (Bebas navy)", dict(font_path=BEBAS, outline=0)),
        ("B: LibBold + white keyline", dict(font_path=LIB_BOLD, outline=7)),
        ("C: italic + keyline + fold", dict(font_path=LIB_ITAL, outline=7, italic_px=22, fold=True)),
    ]
    C = 460
    sheet = Image.new("RGB", (C*len(variants), (300+26)*len(players)), (235, 235, 238))
    dr = ImageDraw.Draw(sheet)
    fnt = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
    for row, pl in enumerate(players):
        base, alpha, jersey, trim, geo = erased_base(pl)
        for col, (label, kw) in enumerate(variants):
            out = stamp(base.copy(), jersey, trim, geo, **kw)
            H = out.shape[0]
            rgba = np.dstack([np.clip(out, 0, 255), alpha]).astype("uint8")
            im = Image.fromarray(rgba, "RGBA")
            crop = im.crop((int(0.12*im.width), int(0.60*H), int(0.88*im.width), H))
            crop.thumbnail((C, 300))
            bg = Image.new("RGBA", (C, 300), (235, 235, 238, 255))
            bg.alpha_composite(crop, ((C-crop.width)//2, 0))
            x, y = col*C, row*(300+26)
            dr.rectangle([x, y, x+C, y+26], fill=(28, 42, 68))
            dr.text((x+6, y+5), f"{pl.split()[0]} - {label}", fill=(135, 181, 230), font=fnt)
            sheet.paste(bg.convert("RGB"), (x, y+26))
    sheet.save("tmp/portrait-pilot/qc/ch_wm_designs.png")
    print("saved")


if __name__ == "__main__":
    main()
