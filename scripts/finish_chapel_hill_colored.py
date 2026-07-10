#!/usr/bin/env python3
"""
Finish the bespoke COLORED Chapel Hill masters: normalize framing to Durham AND
replace every player's varied SKY wordmark with one identical stamp.

Why the colored masters (not the white tanks): their Sky-blue jersey is a solid,
easy-to-detect color (nowhere near skin), so the two things that were hard on the
white tanks become trivial here -- the fabric segments cleanly and the wordmark
can be erased and re-stamped with no skin-bleed and no ghosting.

Per player:
  1. segment (flood-fill U GrabCut) + face-anchor reframe to Durham's spec
  2. detect the Sky jersey; the wordmark = INTERIOR navy (trim = edge navy)
  3. inpaint the wordmark away using the surrounding uniform light-blue jersey
  4. recolor the jersey to the canonical Sky hex (body primary, trim secondary)
  5. stamp ONE identical SKY at 50%-visible (same machinery/placement as Durham)
  6. finish to 3530x3412

    python3 scripts/finish_chapel_hill_colored.py            # all 12 -> QC sheet
    python3 scripts/finish_chapel_hill_colored.py --only "Stanley Keith"

Inputs:  tmp/portrait-pilot/designed/<Name>.(png|jpg)
Output:  tmp/portrait-pilot/ch_final/<Name>.png   (name-QC master)
         tmp/portrait-pilot/qc/ch_colored_final.png
"""
import os
import sys
import glob
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from apply_team_uniforms import fit_font, _lum, hex2rgb, team_info, \
    CROP_KEEP_FRAC, WM_VISIBLE_FRAC, WM_WIDTH_FRAC
from normalize_chapel_hill import reframe, finish, BOX

SRC_DIR = "tmp/portrait-pilot/designed"
FINAL_DIR = "tmp/portrait-pilot/ch_final"
QC = "tmp/portrait-pilot/qc"


def jersey_masks(a, person, np, ndimage):
    """Return (jersey, body, navy, wordmark). Sky jersey = blue-ish below the
    neck. body = light blue, navy = dark blue (trim + wordmark). wordmark = navy
    in the jersey INTERIOR (trim hugs the edges), so it separates from the trim."""
    H = a.shape[0]
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    blueish = (b - r > 10) & (b > 60) & person
    blueish[:int(0.42 * H)] = False
    jersey = ndimage.binary_closing(blueish, iterations=4)
    lbl, n = ndimage.label(jersey)
    if n >= 1:
        jersey = lbl == (1 + int(np.argmax(
            ndimage.sum(np.ones_like(lbl), lbl, range(1, n + 1)))))
    jersey = ndimage.binary_fill_holes(jersey)
    body = jersey & (b > 130) & (b - r > 10)                   # clean light-blue fabric
    navy = jersey & (b <= 130)
    interior = ndimage.binary_erosion(jersey, iterations=14)   # off the trim edge
    # (a) COLOR term: interior pixels that aren't clean light-blue (navy fill,
    #     white/light outlines) -> catches high-contrast wordmarks.
    color_wm = interior & ~body
    # (b) TEXTURE term: letters are high-frequency luminance deviations from the
    #     smooth fabric, so a SAME-TONE light-blue wordmark still shows here.
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    smooth = ndimage.gaussian_filter(lum * interior, 22) / \
        np.maximum(ndimage.gaussian_filter(interior.astype(float), 22), 1e-6)
    tex_wm = interior & (np.abs(lum - smooth) > 10)
    wordmark = color_wm | tex_wm
    wordmark = ndimage.binary_opening(wordmark, iterations=1)   # drop specks
    wordmark = ndimage.binary_closing(wordmark, iterations=3)   # solid letters
    return jersey, body, navy, wordmark


def apply_sky_colored(reframed, np, ndimage, primary, secondary):
    import cv2
    from PIL import Image, ImageDraw, ImageFont
    arr = np.asarray(reframed)
    rgb = arr[..., :3].astype(np.float32)
    alpha = arr[..., 3]
    person = alpha > 128
    H, W, _ = rgb.shape

    jersey, body, navy, _ = jersey_masks(rgb, person, np, ndimage)
    ys, xs = np.where(jersey)
    if len(ys) == 0:
        raise ValueError("no jersey found")

    # 1) ERASE any baked-in wordmark by RECONSTRUCTING the lower-central jersey
    #    zone as clean folded fabric. Detection can't beat a same-tone wordmark,
    #    so instead of finding letters we rebuild the whole zone: keep the
    #    low-frequency fold shading (gaussian-smoothed luminance) but discard
    #    everything letter-sized, painted in the median body color. Bulletproof
    #    against navy / white-outline / tone-on-tone designs alike.
    interior = ndimage.binary_erosion(jersey, iterations=10)
    jtop, jbot = ys.min(), ys.max()
    jcx, jw = (xs.min() + xs.max()) / 2.0, xs.max() - xs.min()
    YY, XX = np.mgrid[0:H, 0:W]
    # `interior` erodes the hem too, which would leave the old wordmark's bottom
    # slivers un-erased right at the crop line. The hem is the crop edge, not
    # trim, so extend the erase to the full jersey there.
    near_hem = jersey & (YY > jbot - 0.12 * (jbot - jtop))
    # zone starts just below the collar so it covers the WHOLE wordmark on these
    # bust crops, where the fabric band is short and the word sits high; central
    # 0.46 of the width catches wide marks; reaches the hem so nothing survives.
    zone = (interior | near_hem) & (YY > jtop + 0.04 * (jbot - jtop)) \
        & (np.abs(XX - jcx) < 0.46 * jw)
    bodypx = rgb[body & interior]
    if zone.sum() > 20 and len(bodypx) > 50:
        # rebuild as FLAT median body colour (a constant): guarantees no ghost of
        # any wordmark design. The band is small and the new SKY sits on top.
        med = np.median(bodypx, 0)
        feather = ndimage.gaussian_filter(zone.astype(np.float32), 6.0)[..., None]
        rgb = rgb * (1 - feather) + med[None, None, :] * feather

    # 2) recolor the jersey to the canonical Sky hex (body primary, trim secondary),
    #    so all 12 are identical regardless of the source's slightly different blues
    P = np.array(primary, np.float32)
    S = np.array(secondary, np.float32)
    tone = np.clip(_lum(rgb) / 190.0, 0.6, 1.12)[..., None]     # keep fabric folds
    out = rgb.copy()
    # trim = navy ONLY at the jersey edge (collar/armholes). The old interior
    # wordmark navy has already been erased to flat fabric, so recolor the WHOLE
    # non-trim interior -- excluding by ~navy here would leave the old letter
    # shapes unrecolored and ghosting through.
    trim = navy & ~ndimage.binary_erosion(jersey, iterations=12)
    bodysoft = ndimage.gaussian_filter((jersey & ~trim).astype(np.float32), 1.0)[..., None]
    out = out * (1 - bodysoft) + (P[None, None, :] * tone) * bodysoft
    trimsoft = ndimage.gaussian_filter(trim.astype(np.float32), 0.6)[..., None]
    tone_navy = np.clip(_lum(rgb) / 90.0, 0.7, 1.2)[..., None]
    out = out * (1 - trimsoft) + (S[None, None, :] * tone_navy) * trimsoft

    # 3) stamp ONE identical SKY -- bold block wordmark (Liberation Sans Bold)
    #    with a white keyline, so it reads as designed jersey typography rather
    #    than plain copy. 50%-visible at the finish crop line, arced onto the
    #    fabric, clipped to the jersey.
    LIB_BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
    WHITE = (238, 242, 250)
    top, bot = ys.min(), ys.max()
    cx = int((xs.min() + xs.max()) / 2)
    tank_w = xs.max() - xs.min()
    target = int(tank_w * WM_WIDTH_FRAC)
    probe = ImageDraw.Draw(Image.new("L", (10, 10)))
    font, ow, bb = None, 4, (0, 0, 0, 0)
    for sz in range(420, 60, -8):
        f = ImageFont.truetype(LIB_BOLD, sz)
        ow = max(4, round(sz * 0.055))
        bb = probe.textbbox((0, 0), "SKY", font=f, stroke_width=ow)
        if bb[2] - bb[0] <= target:
            font = f
            break
    if font is None:
        font = ImageFont.truetype(LIB_BOLD, 68)
    wm_h = bb[3] - bb[1]
    tx = cx - (bb[2] - bb[0]) // 2 - bb[0]
    ty = int(CROP_KEEP_FRAC * H - WM_VISIBLE_FRAC * wm_h) - bb[1]
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(layer).text((tx, ty), "SKY", font=font, fill=tuple(S.astype(int)) + (255,),
                               stroke_width=ow, stroke_fill=WHITE + (255,))
    lay = np.asarray(layer).astype(np.float32)
    # arc the whole layer onto the chest
    amp = max(2, int(0.018 * (bot - top)))
    half = max(1.0, 0.5 * tank_w)
    shift = np.clip((amp * ((np.arange(W) - cx) / half) ** 2), 0, amp).astype(int)
    arced = np.zeros_like(lay)
    for x in range(W):
        sh = int(shift[x])
        arced[sh:, x] = lay[:H - sh, x] if sh else lay[:, x]
    la = ndimage.gaussian_filter(arced[..., 3] / 255.0, 0.6)        # screen-print softness
    la = la * ndimage.binary_erosion(jersey & ~trim, iterations=1)   # clip to fabric
    a = la[..., None]
    ink = arced[..., :3]
    out = out * (1 - 0.96 * a) + ink * (0.96 * a)

    return np.dstack([np.clip(out, 0, 255), alpha]).astype("uint8")


def main():
    import numpy as np
    from scipy import ndimage
    from PIL import Image, ImageDraw, ImageFont

    import csv
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    ap.add_argument("--uuid", action="store_true",
                    help="also write UUID-named masters to assets_staging/players "
                         "(upload-ready); default only writes name-QC copies")
    ap.add_argument("--out", default="assets_staging/players",
                    help="UUID output dir (with --uuid)")
    args = ap.parse_args()

    _, _, prim, sec = team_info("Chapel Hill")
    primary, secondary = hex2rgb(prim), hex2rgb(sec)
    os.makedirs(FINAL_DIR, exist_ok=True)
    os.makedirs(QC, exist_ok=True)
    name2uuid = {r["name"]: r["_id"]
                 for r in csv.DictReader(open("scripts/players_archetypes.csv"))
                 if r["team"] == "Chapel Hill"}
    if args.uuid:
        os.makedirs(args.out, exist_ok=True)

    files = sorted(f for f in glob.glob(os.path.join(SRC_DIR, "*"))
                   if f.lower().endswith((".png", ".jpg", ".jpeg")))
    if args.only:
        files = [f for f in files if args.only.lower() in os.path.basename(f).lower()]
    results = []
    for f in files:
        name = os.path.splitext(os.path.basename(f))[0]
        try:
            rf = reframe(Image.open(f), np, ndimage)
            uni = apply_sky_colored(rf, np, ndimage, primary, secondary)
            fin = finish(uni, np, ndimage)
            fin.save(os.path.join(FINAL_DIR, name + ".png"))
            if args.uuid:
                uid = name2uuid.get(name)
                if not uid:
                    print(f"[warn] {name}: no UUID in archetypes csv; skipped uuid copy")
                else:
                    fin.save(os.path.join(args.out, uid + ".png"))
            results.append((name, fin))
            print(f"[ok] {name}" + (f" -> {name2uuid.get(name)}.png" if args.uuid else ""))
        except Exception as e:
            print(f"[fail] {name}: {type(e).__name__}: {str(e)[:120]}")

    C, cols = 340, 4
    rows = (len(results) + cols - 1) // cols + 1
    hdr = 24
    sheet = Image.new("RGB", (C * cols, (C + hdr) * rows), (238, 238, 240))
    dr = ImageDraw.Draw(sheet)
    fnt = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)

    def cell(img, x, y, label, col=(135, 181, 230)):
        thumb = img.copy(); thumb.thumbnail((C, C))
        bg = Image.new("RGBA", (C, C), (238, 238, 240, 255))
        bg.alpha_composite(thumb, ((C - thumb.width) // 2, 0))
        dr.rectangle([x, y, x + C, y + hdr], fill=(28, 42, 68))
        dr.text((x + 6, y + 4), label, fill=col, font=fnt)
        sheet.paste(bg.convert("RGB"), (x, y + hdr))

    for i, (name, img) in enumerate(results):
        cell(img, (i % cols) * C, (i // cols) * (C + hdr), name[:24])
    dref = [p for p in sorted(glob.glob("tmp/portrait-pilot/finished/*.png"))
            if " " in os.path.basename(p)
            and not os.path.basename(p).startswith(("durham", "wm"))][:cols]
    ry = (len(results) // cols + (1 if len(results) % cols else 0)) * (C + hdr)
    for i, p in enumerate(dref):
        cell(Image.open(p).convert("RGBA"), i * C, ry,
             "DURHAM: " + os.path.basename(p)[:-4][:16], col=(200, 169, 81))
    out = os.path.join(QC, "ch_colored_final.png")
    sheet.save(out)
    print(f"\n[sheet] -> {out}")


if __name__ == "__main__":
    main()
