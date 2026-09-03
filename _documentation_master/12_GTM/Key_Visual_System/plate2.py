#!/usr/bin/env python3
"""Round 2 plates. Three changes from A1, all of them Jamie's calls.

  BALL      Rozier holds a basketball at chest height. It hides the jersey graphics by
            occlusion instead of by argument, and it echoes the app icon, where the same
            player holds a ball over his face.

  BLANK     Both jerseys go into the plate with their chest graphics dissolved away. Round
            1 proved the generator cannot preserve a crest, a wordmark or a jersey numeral
            -- it invented a cat, wiped JOHNNIES to an empty white box and re-set both
            numbers in a generic font. So it is never shown one again. It generates plain
            fabric; the real marks are composited afterwards, pixel-accurate.

  BUILD     Measured on the round-1 output, shoulder width came to about 2.3 head widths.
            A typical adult male is nearer 2.6 and an athletic one 2.8-3.0, which is why
            the heads read too big. Scaling the cutouts down leaves the generator the room
            to build the wider frame the prompt now asks for.

The staging stays symmetrical on purpose. Three variables are already in flight; adding an
asymmetric rivalry composition on the same run would make a bad result unattributable.
"""
import pathlib
from PIL import Image, ImageFilter
import numpy as np

ROOT = pathlib.Path(__file__).parent
OUT = ROOT / "plates"; OUT.mkdir(exist_ok=True)
W, H = 3840, 2160

BLUE_SRC   = ROOT / "source" / "rozier_portrait_trimmed.png"
ORANGE_SRC = ROOT / "source" / "buckles_portrait_trimmed.png"
BALL_SRC   = ROOT / "assets" / "basketball.png"

INK  = np.array([10, 12, 18], dtype=np.float32)
COOL = np.array([28, 46, 88], dtype=np.float32)
WARM = np.array([116, 46, 6], dtype=np.float32)


def ground(split=0.5, strength=0.55, floor=0.30):
    x = np.linspace(0, 1, W)[None, :, None]
    t = np.clip((x - split) * 3.2, -1, 1)
    side = np.where(t < 0, COOL[None, None, :], WARM[None, None, :])
    field = INK[None, None, :] + side * (np.abs(t) ** 1.5) * strength
    y = np.linspace(0, 1, H)[:, None, None]
    vign = floor + (1 - floor) * np.exp(-((y - 0.42) ** 2) / 0.10)
    return Image.fromarray(np.clip(field * vign, 0, 255).astype(np.uint8))


def figure(src, height, fade=0.36):
    """Scale a cutout and dissolve its bottom `fade` fraction, which is where the crest,
    wordmark and numeral live. What survives is a head, shoulders and blank fabric."""
    im = Image.open(src).convert("RGBA")
    im = im.resize((max(1, int(im.width * height / im.height)), height), Image.LANCZOS)
    a = np.array(im, dtype=np.float32)
    n = int(height * fade)
    a[-n:, :, 3] *= (np.linspace(1, 0, n) ** 2.2)[:, None]   # steep: a gentle ramp left
                                                            # JOHNNIES readable at 33% alpha
    return Image.fromarray(a.astype(np.uint8))


def plate(name, note=""):
    base = ground().convert("RGBA")
    subj = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    roz = figure(BLUE_SRC, 1460)
    buc = figure(ORANGE_SRC, 1530)          # bigger: he is the power forward and nearer
    ROZ_X, BUC_X = 1140, 2710
    subj.alpha_composite(roz, (ROZ_X - roz.width // 2, 190))
    subj.alpha_composite(buc, (BUC_X - buc.width // 2, 150))

    # A real ball in the plate, not a described one. The generator then wraps hands around
    # fixed geometry instead of inventing a sphere and two hands at once -- hands being the
    # one thing round 1 never had to attempt, and the likeliest way this round fails.
    # Diameter is set to head height: a basketball is ~24cm, an adult head ~23cm.
    ball_d = int(1460 * 0.54)          # a basketball is ~24cm, a head ~23cm: near parity
    ball = Image.open(BALL_SRC).convert("RGBA").resize((ball_d, ball_d), Image.LANCZOS)
    subj.alpha_composite(ball, (ROZ_X - ball_d // 2, 190 + 1460 - int(ball_d * 0.72)))   # raised ~200px: it must cover the upper chest,
                                                          # where a wordmark and the top of a numeral sit

    base.alpha_composite(subj)
    out = base.convert("RGB")
    out.save(OUT / f"{name}.png")
    out.resize((210, 118), Image.LANCZOS).save(OUT / f"{name}_210.png")
    a = np.array(subj)[:, :, 3]
    print(f"{name}: subject {100*(a>10).mean():.1f}% of frame, ball {ball_d}px   {note}")


if __name__ == "__main__":
    plate("C3", "ball raised to cover the upper chest; ball given matte leather material")
