#!/usr/bin/env python3
"""Dynamic Defense (Dynamic_MM_Brief §7 P1) — defender-placement VISUAL proof.

Generates a standalone HTML/SVG court showing the PROPOSED tight / normal / loose defender
placement for a representative HCO offensive alignment, side by side, so we can eyeball the
geometry (the one thing the rate prototype can't judge). No DB / server.

  Run:    python3 scripts/defense_posture_proof.py
  Output: tmp/defense_posture_proof.html   (open in a browser)

This is a DESIGN PROOF, not live code. It uses a clean self-computed man baseline (not the real
calculate_defender_coords, whose orientation branches would obscure the posture deltas). The live
P1 will layer POSTURE_SPACING / POSTURE_HELP_SHADE onto the real reconstruction. Tune the knobs at
the top and re-run to iterate on the look.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from BackEnd.constants import HCO_STRING_SPOTS, HOME_RIM_COORDS
from BackEnd.engine.motion_read_map import is_inside_location

# ── Representative offense (home half, attacking HOME_RIM at (91,25)) ────────
# BH at key; two wings; a corner; a post — a normal HCO look with an inside man.
OFFENSE = {
    "PG": "key",            # ball handler
    "SG": "upper wing",
    "SF": "lower corner",
    "PF": "upper lowPost",  # inside
    "C":  "lower lowPost",  # inside
}
BALL_POS_KEY = "PG"

# ── PROPOSED POSTURE KNOBS (tune here) ──────────────────────────────────────
# On-ball defender cushion (grid units from the BH toward the basket). loose = sag.
ONBALL_CUSHION = {"tight": 2.0, "normal": 3.0, "loose": 5.0}
# Off-ball baseline cushion off the man toward the basket (grid).
OFFBALL_CUSHION = 2.0
# tight off-ball = DENY: stand this many grid off the man, ON THE BALL SIDE (in the direct passing
# lane to HIS man). Small = hug the man; he denies his guy without drifting into other lanes.
DENY_DISTANCE = 2.0
# Help lives in the middle of the floor. Anchor = point on the ball→basket line the defender
# sags toward; HELP_ANCHOR_FRAC=0.5 → the midpoint (center of the floor).
HELP_ANCHOR_FRAC = 0.5
# off-ball shade fraction from the man baseline toward the help anchor, by posture.
HELP_SHADE = {"tight": 0.0, "normal": 0.28, "loose": 0.55}
# ─────────────────────────────────────────────────────────────────────────────

BASKET = (float(HOME_RIM_COORDS["x"]), float(HOME_RIM_COORDS["y"]))


def _coords(spot):
    c = HCO_STRING_SPOTS[spot]
    return (float(c["x"]), float(c["y"]))


def _unit(ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    d = math.hypot(dx, dy) or 1.0
    return dx / d, dy / d


def _toward(p, target, amt):
    ux, uy = _unit(p[0], p[1], target[0], target[1])
    return (p[0] + ux * amt, p[1] + uy * amt)


def _lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def onball_defender(bh, posture):
    """Between the BH and the basket at the posture's cushion."""
    return _toward(bh, BASKET, ONBALL_CUSHION[posture])


def defender_positions(ball_holder, posture):
    """All five defender coords given who holds the ball, under `posture`. Inside men locked normal.
    Shared with dynamic_defense_prototype.py (the two-gate intercept geometry)."""
    ball = _coords(OFFENSE[ball_holder])
    out = {}
    for pos, spot in OFFENSE.items():
        man = _coords(spot)
        eff = "normal" if is_inside_location(spot) else posture
        out[pos] = onball_defender(man, eff) if pos == ball_holder else offball_defender(man, ball, eff)
    return out


def offball_defender(man, ball, posture):
    """Man baseline (toward basket), then posture shade: tight→deny (ballward), loose→help (middle)."""
    if posture == "tight":
        # deny: hug the man on the ball side — sit DENY_DISTANCE off him, in his own passing lane
        return _toward(man, ball, DENY_DISTANCE)
    base = _toward(man, BASKET, OFFBALL_CUSHION)
    # help: sag toward the middle of the floor (a point on the ball→basket line)
    help_anchor = _lerp(ball, BASKET, HELP_ANCHOR_FRAC)
    return _lerp(base, help_anchor, HELP_SHADE[posture])


# ── SVG rendering (home half: court x∈[50,100], y∈[0,50]) ────────────────────
W, H, PAD = 320, 320, 24
X0, X1 = 50.0, 100.0
Y0, Y1 = 0.0, 50.0


def _sx(x):
    return PAD + (x - X0) / (X1 - X0) * W


def _sy(y):
    return PAD + (y - Y0) / (Y1 - Y0) * H


def _circle(cx, cy, r, fill, label=None, stroke="none", sw=0):
    s = (f'<circle cx="{_sx(cx):.1f}" cy="{_sy(cy):.1f}" r="{r}" fill="{fill}" '
         f'stroke="{stroke}" stroke-width="{sw}"/>')
    if label:
        s += (f'<text x="{_sx(cx):.1f}" y="{_sy(cy) + 3.5:.1f}" text-anchor="middle" '
              f'font-size="9" font-weight="700" fill="#fff">{label}</text>')
    return s


def _line(a, b, color, dash=""):
    d = f'stroke-dasharray="{dash}"' if dash else ""
    return (f'<line x1="{_sx(a[0]):.1f}" y1="{_sy(a[1]):.1f}" x2="{_sx(b[0]):.1f}" '
            f'y2="{_sy(b[1]):.1f}" stroke="{color}" stroke-width="1.4" {d}/>')


def _panel(posture):
    ball = _coords(OFFENSE[BALL_POS_KEY])
    parts = [f'<svg width="{W + 2 * PAD}" height="{H + 2 * PAD}" '
             f'viewBox="0 0 {W + 2 * PAD} {H + 2 * PAD}">']
    # court backdrop
    parts.append(f'<rect x="{PAD}" y="{PAD}" width="{W}" height="{H}" fill="#12321c" '
                 f'stroke="#2f6b42" stroke-width="2" rx="4"/>')
    # basket
    parts.append(_circle(BASKET[0], BASKET[1], 6, "none", stroke="#ff8c42", sw=2.5))
    # players
    for pos, spot in OFFENSE.items():
        man = _coords(spot)
        is_bh = pos == BALL_POS_KEY
        # Rule: posture only applies to defenders guarding a PERIMETER man. A defender on an
        # inside man (lowPost / midPost / midLane / basketSpot) always plays standard post D.
        inside = is_inside_location(spot)
        eff = "normal" if inside else posture
        d = onball_defender(man, eff) if is_bh else offball_defender(man, ball, eff)
        # tether line man→defender
        parts.append(_line(man, d, "#5a5a5a", dash="3,3"))
        # offense (blue), defender (red), BH highlighted
        parts.append(_circle(man[0], man[1], 11, "#2f80ed" if not is_bh else "#f2c94c", label=pos))
        # inside-man defenders are locked to normal post D → white ring marker
        parts.append(_circle(d[0], d[1], 9, "#eb5757", label="x",
                             stroke=("#ffffff" if inside else "none"), sw=(2 if inside else 0)))
    parts.append('</svg>')
    return "".join(parts)


def build_html():
    panels = "".join(
        f'<div class="panel"><h2>{p.upper()}</h2>{_panel(p)}</div>'
        for p in ("tight", "normal", "loose")
    )
    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>Defense Posture Proof</title>
<style>
  body {{ background:#0d0d0f; color:#e6e6e6; font-family:-apple-system,system-ui,sans-serif;
         margin:0; padding:24px; }}
  h1 {{ font-size:18px; margin:0 0 4px; }}
  p.sub {{ color:#9a9a9a; margin:0 0 20px; font-size:13px; }}
  .row {{ display:flex; gap:20px; flex-wrap:wrap; }}
  .panel {{ background:#161619; border:1px solid #26262b; border-radius:10px; padding:12px; }}
  .panel h2 {{ font-size:13px; letter-spacing:.08em; margin:0 0 8px; color:#c9c9c9; }}
  .legend {{ margin-top:18px; font-size:12px; color:#b8b8b8; display:flex; gap:18px; flex-wrap:wrap; }}
  .legend b {{ color:#fff; }}
  .dot {{ display:inline-block; width:10px; height:10px; border-radius:50%; vertical-align:middle; margin-right:5px; }}
  code {{ background:#1e1e22; padding:1px 5px; border-radius:4px; color:#d8b46a; }}
</style></head><body>
<h1>Dynamic Defense — posture placement proof</h1>
<p class="sub">Representative HCO look, ball at PG (key), attacking basket (orange ring). Proposed geometry — tune knobs in <code>scripts/defense_posture_proof.py</code> and re-run.</p>
<div class="row">{panels}</div>
<div class="legend">
  <span><span class="dot" style="background:#f2c94c"></span><b>BH</b> (ball handler)</span>
  <span><span class="dot" style="background:#2f80ed"></span>off-ball offense</span>
  <span><span class="dot" style="background:#eb5757"></span>defender (x)</span>
  <span><span class="dot" style="background:none;border:2px solid #ff8c42"></span>basket</span>
  <span>dashed = man↔defender tether</span>
  <span><span class="dot" style="background:#eb5757;border:2px solid #fff"></span>inside-man defender = locked to normal post D</span>
</div>
<div class="legend" style="margin-top:10px">
  <span><b>tight</b>: on-ball cushion {ONBALL_CUSHION['tight']}, off-ball denies {DENY_DISTANCE} grid off man (ball-side)</span>
  <span><b>normal</b>: cushion {ONBALL_CUSHION['normal']}, help-shade {int(HELP_SHADE['normal']*100)}%</span>
  <span><b>loose</b>: cushion {ONBALL_CUSHION['loose']} (sag), help-shade {int(HELP_SHADE['loose']*100)}%</span>
</div>
</body></html>"""


def main():
    out_dir = os.path.join(os.getcwd(), "tmp")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "defense_posture_proof.html")
    with open(out, "w") as f:
        f.write(build_html())
    print(f"wrote {out}")
    print("open it in a browser to review tight / normal / loose placement.")


if __name__ == "__main__":
    main()
