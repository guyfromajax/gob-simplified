#!/usr/bin/env python3
"""
Normalize the bespoke Chapel Hill white-tank busts to Durham's framing, then run
them through the SAME Sky uniform + finish so they end up consistent with every
pipeline team.

Why this exists: Chapel Hill's art was hand-made, NOT built on our 5 reference
bodies, so its crop/zoom drifts and (in the colored versions) the Sky wordmark
varies. Because we have the WHITE-TANK versions, we never touch a baked-in
wordmark: we recolor the tank to Sky and stamp ONE SKY wordmark, identical
machinery to Durham. The only bespoke step is REFRAMING to Durham's canonical
bust spec (head-top ~9% down, shoulders ~full width, centered, torso to bottom).

Segmentation here is flood-fill (u2net is network-blocked in the sandbox); the
busts sit on clean neutral backgrounds so it's reliable.

    python3 scripts/normalize_chapel_hill.py            # all 12 -> QC sheet
    python3 scripts/normalize_chapel_hill.py --reframe-only   # skip uniform (frame proof)

Inputs:  tmp/portrait-pilot/ch_source/<Name>.(png|jpg)
Output:  tmp/portrait-pilot/ch_norm/<Name>.png          (reframed cutout bust)
         tmp/portrait-pilot/ch_final/<Name>.png         (3530x3412 master, name-QC)
         tmp/portrait-pilot/qc/ch_normalized.png        (comparison sheet)
"""
import os
import sys
import glob
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from apply_team_uniforms import fit_font, _lum, hex2rgb, team_info, _tank, \
    CROP_KEEP_FRAC, WM_VISIBLE_FRAC, WM_WIDTH_FRAC, FONT

SRC_DIR = "tmp/portrait-pilot/ch_source"
NORM_DIR = "tmp/portrait-pilot/ch_norm"
FINAL_DIR = "tmp/portrait-pilot/ch_final"
QC = "tmp/portrait-pilot/qc"

CANVAS_W, CANVAS_H = 3530, 3412

# Durham canonical bust spec (measured from the 12 Durham uniformed busts with
# the SAME Haar detector, so CH lands identically framed).
BOX = 1200                 # square work canvas (finish rescales to 3530 later)
FACE_H_FRAC = 0.375        # face height as fraction of frame (Durham median)
FACE_CY_FRAC = 0.393       # face-center vertical position (Durham median)
FACE_CX_FRAC = 0.50        # face-center horizontal position (centered)


def _floodfill(src, np, ndimage):
    """Border-connected background removal. Fast, but eats person regions that
    blend into a light/gradient background (white tank, arms)."""
    a = np.asarray(src.convert("RGB")).astype(np.float32)
    c = 40
    cor = np.concatenate([a[:c, :c].reshape(-1, 3), a[:c, -c:].reshape(-1, 3),
                          a[-c:, :c].reshape(-1, 3), a[-c:, -c:].reshape(-1, 3)])
    bg = np.median(cor, 0)
    bgsim = np.sqrt(((a - bg) ** 2).sum(2)) < 38
    lbl, n = ndimage.label(bgsim)
    border = set(np.unique(lbl[0, :])) | set(np.unique(lbl[-1, :])) \
        | set(np.unique(lbl[:, 0])) | set(np.unique(lbl[:, -1]))
    border.discard(0)
    background = np.isin(lbl, list(border)) if border else np.zeros_like(bgsim)
    return ndimage.binary_fill_holes(~background)


def _grabcut(src, np):
    """GrabCut with a near-full-frame rect. Recovers blended body/arm regions
    flood-fill drops, but can miss when its rect clips (e.g. narrow busts)."""
    import cv2
    im = np.asarray(src.convert("RGB"))
    H, W, _ = im.shape
    mask = np.zeros((H, W), np.uint8)
    rect = (int(0.04 * W), int(0.01 * H), int(0.92 * W), int(0.99 * H))
    try:
        cv2.grabCut(cv2.cvtColor(im, cv2.COLOR_RGB2BGR), mask, rect,
                    np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64),
                    5, cv2.GC_INIT_WITH_RECT)
    except Exception:
        return np.zeros((H, W), bool)
    return (mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD)


def segment_person(src, np, ndimage):
    """Person cutout = flood-fill UNION GrabCut. The two methods fail on
    different regions (flood-fill eats blended tank/arms; GrabCut clips narrow
    busts), so their union is robust across the bespoke set. GrabCut sometimes
    also pulls in background-colored haze (e.g. a gray halo around dark hair);
    that haze is dropped by removing GrabCut-only pixels that match the corner
    background color. On the user's machine the pipeline uses u2net; this is the
    sandbox-safe equivalent."""
    ff = _floodfill(src, np, ndimage)
    gc = _grabcut(src, np)
    a = np.asarray(src.convert("RGB")).astype(np.float32)
    c = 40
    cor = np.concatenate([a[:c, :c].reshape(-1, 3), a[:c, -c:].reshape(-1, 3),
                          a[-c:, :c].reshape(-1, 3), a[-c:, -c:].reshape(-1, 3)])
    bg = np.median(cor, 0)
    H = a.shape[0]
    bg_colored = np.sqrt(((a - bg) ** 2).sum(2)) < 45
    halo = gc & ~ff & bg_colored            # GrabCut-added, but background-colored
    halo[int(0.60 * H):] = False            # only in the hair zone; keep body/tank
    person = (ff | gc) & ~halo
    person = ndimage.binary_opening(person, iterations=1)
    person = ndimage.binary_closing(person, iterations=3)
    person = ndimage.binary_fill_holes(person)
    lbl, n = ndimage.label(person)
    if n > 1:
        person = lbl == (1 + int(np.argmax(
            ndimage.sum(np.ones_like(lbl), lbl, range(1, n + 1)))))
    return person


_FACE_DET = None


def detect_face(src, np):
    """(face_h_px, cx_px, cy_px) via OpenCV Haar (ships with cv2, no download).
    Robust to hair volume — unlike shoulder width, which big afros/slight builds
    throw off. Returns None if no face is found."""
    global _FACE_DET
    import cv2
    if _FACE_DET is None:
        _FACE_DET = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    g = cv2.cvtColor(np.asarray(src.convert("RGB")), cv2.COLOR_RGB2GRAY)
    faces = _FACE_DET.detectMultiScale(g, 1.1, 5, minSize=(120, 120))
    if not len(faces):
        return None
    x, y, w, h = sorted(faces, key=lambda r: -r[2] * r[3])[0]
    return float(h), x + w / 2.0, y + h / 2.0


def reframe(src, np, ndimage):
    """Return an RGBA BOXxBOX cutout placed at Durham's FACE spec: face height
    FACE_H_FRAC of the frame, face-center at (FACE_CX_FRAC, FACE_CY_FRAC). Falls
    back to a person-bbox estimate if no face is detected."""
    from PIL import Image
    person = segment_person(src, np, ndimage)
    face = detect_face(src, np)
    if face is None:
        ys, xs = np.where(person)                       # fallback: head-box guess
        fh = 0.42 * (xs.max() - xs.min())
        cxp, cyp = (xs.min() + xs.max()) / 2.0, ys.min() + 0.55 * fh
    else:
        fh, cxp, cyp = face

    s = (FACE_H_FRAC * BOX) / max(1.0, fh)               # scale face -> target size
    rgb = np.asarray(src.convert("RGB"))
    a8 = (person * 255).astype("uint8")
    im = Image.fromarray(np.dstack([rgb, a8]), "RGBA")
    nw, nh = max(1, round(im.width * s)), max(1, round(im.height * s))
    im = im.resize((nw, nh), Image.LANCZOS)

    off_x = int(round(FACE_CX_FRAC * BOX - cxp * s))
    off_y = int(round(FACE_CY_FRAC * BOX - cyp * s))
    canvas = Image.new("RGBA", (BOX, BOX), (0, 0, 0, 0))
    canvas.alpha_composite(im, (off_x, off_y))
    return canvas


def ch_tank(a, person, np, ndimage):
    """Tank mask for the BESPOKE CH busts. Their fabric is often a warm cream,
    which the pipeline's warmth-based skin filter wrongly rejects. Saturation
    separates fabric from skin far better: cream tank S~0.2 vs skin S~0.45+.
    So: bright, LOW-SATURATION, below the neck, largest region, eroded off skin."""
    H = a.shape[0]
    maxc, minc = a.max(2), a.min(2)
    V = maxc / 255.0
    S = (maxc - minc) / (maxc + 1e-6)
    # bright & low-sat catches cream fabric; skin (even pale chest) runs S>0.42
    tank = (V > 0.58) & (S < 0.42) & person
    tank[:int(0.45 * H)] = False
    tank = ndimage.binary_opening(tank, iterations=1)     # gentle: keep thin tanks
    tank = ndimage.binary_closing(tank, iterations=6)     # bridge fold/neck shadows
    lbl, n = ndimage.label(tank)
    if n >= 1:
        tank = lbl == (1 + int(np.argmax(
            ndimage.sum(np.ones_like(lbl), lbl, range(1, n + 1)))))
    tank = ndimage.binary_closing(tank, iterations=8)     # solidify the triangle
    tank = ndimage.binary_fill_holes(tank)
    return ndimage.binary_erosion(tank, iterations=2)


def apply_sky(reframed, np, ndimage, primary, secondary, wordmark):
    """Recolor the white tank to Sky + stamp SKY at 50%-visible. Identical to the
    Durham uniform stage, but fed the reframe's own alpha (u2net not needed) and
    a saturation-based tank mask tuned for the bespoke cream tanks."""
    from PIL import Image, ImageDraw, ImageFont
    arr = np.asarray(reframed)
    a = arr[..., :3].astype(np.float32)
    alpha = arr[..., 3]
    person = alpha > 128
    H, W, _ = a.shape
    tank = ch_tank(a, person, np, ndimage)
    ys, xs = np.where(tank)
    if len(ys) == 0:
        raise ValueError("no tank found")
    top, bot = ys.min(), ys.max()
    cx = int((xs.min() + xs.max()) / 2)
    tone = np.clip(_lum(a) / 238.0, 0.55, 1.12)[..., None]
    P = np.array(primary, np.float32)
    S = np.array(secondary, np.float32)

    out = a.copy()
    soft = ndimage.gaussian_filter(tank.astype(np.float32), 1.2)[..., None]
    out = out * (1 - soft) + (P[None, None, :] * tone) * soft

    rim = tank & ~ndimage.binary_erosion(tank, iterations=8)
    rim[int(bot - 6):] = False
    rimS = ndimage.gaussian_filter(rim.astype(np.float32), 0.6)[..., None]
    out = out * (1 - rimS) + (S[None, None, :] * tone) * rimS

    txt = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(txt)
    tank_w = xs.max() - xs.min()
    font, b = fit_font(d, wordmark, ImageFont, int(tank_w * WM_WIDTH_FRAC))
    wm_h = b[3] - b[1]
    tx = cx - (b[2] - b[0]) // 2 - b[0]
    ty = int(CROP_KEEP_FRAC * H - WM_VISIBLE_FRAC * wm_h) - b[1]
    d.text((tx, ty), wordmark, fill=255, font=font)
    tmask = np.asarray(txt).astype(np.float32) / 255.0

    amp = max(2, int(0.018 * (bot - top)))
    half = max(1.0, 0.5 * tank_w)
    shift = np.clip((amp * ((np.arange(W) - cx) / half) ** 2), 0, amp).astype(int)
    arced = np.zeros_like(tmask)
    for x in range(W):
        sh = int(shift[x])
        arced[sh:, x] = tmask[:H - sh, x] if sh else tmask[:, x]
    arced = ndimage.gaussian_filter(arced, 0.7)
    tm = (arced * ndimage.binary_erosion(tank, iterations=1))[..., None]
    ink = S[None, None, :] * np.clip(tone * 1.15, 0.42, 1.18)
    out = out * (1 - 0.92 * tm) + ink * (0.92 * tm)

    return np.dstack([np.clip(out, 0, 255), alpha]).astype("uint8")


def finish(rgba, np, ndimage):
    from PIL import Image
    a = ndimage.binary_erosion(rgba[..., 3] > 20, iterations=2).astype(np.float32)
    a = ndimage.gaussian_filter(a, 1.5)
    src = Image.fromarray(np.dstack([rgba[..., :3],
                                     np.clip(a * 255, 0, 255).astype("uint8")]), "RGBA")
    scale = CANVAS_W / src.width
    src = src.resize((CANVAS_W, round(src.height * scale)), Image.LANCZOS)
    canvas = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    canvas.alpha_composite(src, (0, 0))
    return canvas


def main():
    import numpy as np
    from scipy import ndimage
    from PIL import Image, ImageDraw, ImageFont

    ap = argparse.ArgumentParser()
    ap.add_argument("--reframe-only", action="store_true",
                    help="stop after reframing (crop/zoom proof, no uniform)")
    args = ap.parse_args()

    _, _, prim, sec = team_info("Chapel Hill")
    primary, secondary = hex2rgb(prim), hex2rgb(sec)
    for dd in (NORM_DIR, FINAL_DIR, QC):
        os.makedirs(dd, exist_ok=True)

    files = sorted(f for f in glob.glob(os.path.join(SRC_DIR, "*"))
                   if f.lower().endswith((".png", ".jpg", ".jpeg")))
    results = []
    for f in files:
        name = os.path.splitext(os.path.basename(f))[0]
        src = Image.open(f)
        try:
            rf = reframe(src, np, ndimage)
            rf.save(os.path.join(NORM_DIR, name + ".png"))
            if args.reframe_only:
                results.append((name, finish(np.asarray(rf), np, ndimage)))
                print(f"[reframe] {name}")
                continue
            uni = apply_sky(rf, np, ndimage, primary, secondary, "SKY")
            fin = finish(uni, np, ndimage)
            fin.save(os.path.join(FINAL_DIR, name + ".png"))
            results.append((name, fin))
            print(f"[ok] {name}")
        except Exception as e:
            print(f"[fail] {name}: {type(e).__name__}: {str(e)[:120]}")

    # comparison sheet: CH masters on top rows, a Durham reference row at the end
    C, cols = 340, 4
    rows = (len(results) + cols - 1) // cols + 1
    hdr = 24
    sheet = Image.new("RGB", (C * cols, (C + hdr) * rows), (238, 238, 240))
    dr = ImageDraw.Draw(sheet)
    try:
        fnt = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
    except Exception:
        fnt = ImageFont.load_default()

    def cell(img, x, y, label):
        thumb = img.copy(); thumb.thumbnail((C, C))
        bg = Image.new("RGBA", (C, C), (238, 238, 240, 255))
        bg.alpha_composite(thumb, ((C - thumb.width) // 2, 0))
        dr.rectangle([x, y, x + C, y + hdr], fill=(28, 42, 68))
        dr.text((x + 6, y + 4), label, fill=(135, 181, 230), font=fnt)
        sheet.paste(bg.convert("RGB"), (x, y + hdr))

    for i, (name, img) in enumerate(results):
        cell(img, (i % cols) * C, (i // cols) * (C + hdr), name[:24])
    # Durham reference row
    dref = sorted(glob.glob("tmp/portrait-pilot/finished/*.png"))
    dref = [p for p in dref if " " in os.path.basename(p)
            and not os.path.basename(p).startswith(("durham", "wm"))][:cols]
    ry = (len(results) // cols + (1 if len(results) % cols else 0)) * (C + hdr)
    for i, p in enumerate(dref):
        img = Image.open(p).convert("RGBA")
        cell(img, i * C, ry, "DURHAM: " + os.path.basename(p)[:-4][:16])
    out = os.path.join(QC, "ch_reframe.png" if args.reframe_only else "ch_normalized.png")
    sheet.save(out)
    print(f"\n[sheet] -> {out}")


if __name__ == "__main__":
    main()
