"""
Dynamic HCO Motion — per-step decision engine (brief Step 2).

Pure decision logic: given the current skeleton step, the ball handler + his
defender, the read map (Phase 1), and team/aggression context, decide what the
ball handler does this step. Returns a Decision dict describing the action —
it does NOT emit any UESS/skeleton steps (that is Phase 3+). See
_documentation_master/projects/Z-Completed/Dynamic_HCO_Motion_Brief.md (Step 2).

Scores use brief "form B": (raw_helper + team_modifier) * random.randint(1,6) —
a single roll, with the raw (roll-free) helper variants from BackEnd.utils.shared
so there is no double random.
"""
import logging
from BackEnd.utils.sim_random import sim_rng as _random
from BackEnd.utils.team_attr_scale import core8_gameplay
from BackEnd.constants import HCO_STRING_SPOTS
from BackEnd.utils.shared import (
    player_read_raw, defender_pressure_raw, inside_defender_raw, ball_handling_raw,
)
from BackEnd.engine.motion_read_map import is_inside_location

# --- action vocabulary (Decision["action"]) ---
ADVANCE = "ADVANCE"                  # do nothing this step → next skeleton step
SHOOT = "SHOOT"                      # ball handler shoots (desperation / no-kickout fallback)
KICKOUT_SHOOT = "KICKOUT_SHOOT"      # desperation kick-out → receiver catch-and-shoot
HOT_READ_SHOOT = "HOT_READ_SHOOT"    # hot read executed → shooter shoots (self or via pass)
SUBTLE_MOVEMENT = "SUBTLE_MOVEMENT"
FREELANCE_FORCED = "FREELANCE_FORCED"
PASS_IMMEDIATE = "PASS_IMMEDIATE"
BACKDOOR = "BACKDOOR"                 # S3c (Goal 2): off-ball man cuts behind a denying defender → BH feeds him at the rim

# --- tunables (brief) ---
# Single shared read threshold (brief: "one constant"): a `(read_raw + team_eff) * d6` read
# clears it when > MOTION_READ_THRESHOLD. Used by the desperation ceiling, the per-teammate
# offense subtle read (motion_subtle), and the per-defender subtle read.
MOTION_READ_THRESHOLD = 110
DESPERATION_OFFENSE_CEILING = MOTION_READ_THRESHOLD  # offense_score below this triggers the shot-clock pre-check
KICKOUT_MAX_DIST = 10                # euclidean grid spots for the 25% desperation kick-out
TEMPO_MOD = {"slow": -25, "normal": 0, "fast": 25}
# Subtle-movement step elapsed (game seconds) by offense tempo — a FLOOR the emitter honors
# (brief: Updated Subtle Movement Logic). The slowest mover's natural travel can exceed it.
SUBTLE_STEP_ELAPSED_BY_TEMPO = {"slow": (2, 4), "normal": (2, 3), "fast": (1, 3)}
# Hard penalty applied to shot_score when the BH is forced to shoot because a subtle step
# ran the shot clock to expiry (brief: force a shot with 1s left, -50 to shot score).
SUBTLE_FORCED_SHOT_PENALTY = 50

# Subtle-beat idle motion (COSMETIC; render-space only, never touches gameplay coords). A
# subtle beat gives the BH + some teammates a small gameplay nudge, then its 2-4s clock budget
# leaves everyone stationary. To avoid a frozen court, all non-BH players get a render-space
# "idle_wander" flourish (organic within-radius drift spanning the beat); the BH gets one on a
# coin flip (else he stands with the always-on NG heartbeat pulse). Seeded (SS&S-reproducible).
SUBTLE_IDLE_WANDER_RADIUS_GRID = 1.0   # legacy fallback radius (grid units) when no style amp
BH_IDLE_WANDER_PROBABILITY = 0.5       # (legacy) kept for compatibility

# Role-based idle-motion styles (v1). Assigned by geography (inside spot vs perimeter) + role;
# the FE renders each in-place, returning to anchor. Amplitudes in grid units (render-space).
#   jockey      — inside offense/defense: grounded basket-ward lean/jostle (continuous)
#   jab         — perimeter off-ball offense: hold → ball-ward jab-step → recover (intermittent)
#   shuffle     — perimeter defense: lateral in-stance slide (continuous)
#   survey_rock — perimeter ball handler: gentle lateral survey sway (continuous)
SUBTLE_IDLE_STYLE_AMPLITUDE_GRID = {
    "jockey": 0.6,
    "jab": 1.2,
    "shuffle": 1.0,
    "survey_rock": 0.5,
}
BH_SURVEY_PROBABILITY = 0.5   # perimeter BH: survey-rock vs still (heartbeat only)


# --------------------------------------------------------------------------- #
# small helpers
# --------------------------------------------------------------------------- #
def _coords(location):
    c = HCO_STRING_SPOTS.get(location) or {"x": 50.0, "y": 25.0}
    return float(c.get("x", 50.0)), float(c.get("y", 25.0))


def _dist(loc_a, loc_b):
    ax, ay = _coords(loc_a)
    bx, by = _coords(loc_b)
    return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5


def _aggr_delta(call, aggressive_delta, passive_delta):
    """Return the aggressive/passive adjustment for an aggression_call (0.0 for normal)."""
    if call == "aggressive":
        return aggressive_delta
    if call == "passive":
        return passive_delta
    return 0.0


def _team_attr(team, key, default):
    return (getattr(team, "team_attributes", {}) or {}).get(key, default)


def _aggr_call(team):
    return (getattr(team, "strategy_calls", {}) or {}).get("aggression_call", "normal")


def _step_locations(step):
    out = {}
    for pos, info in (step.get("pos_actions") or {}).items():
        loc = (info or {}).get("location")
        if loc:
            out[pos] = loc
    return out


def _choose_attack_or_outside(player, rng):
    """Brief: attack_score=(AG+SC)/2, outside_score=SH; roll in [1,sum] picks attack vs outside."""
    a = getattr(player, "attributes", {}) or {}
    attack_score = (a.get("AG", 0) + a.get("SC", 0)) / 2
    outside_score = a.get("SH", 0)
    total = attack_score + outside_score
    # Guard the sub-1 case, not just <=0: int(round(total)) collapses 0<total<1 to
    # 0, which makes rng.randint(1, 0) raise "empty range for randrange()". A player
    # with near-zero AG/SC/SH (e.g. practice-squad marginals) trips it.
    if int(round(total)) < 1:
        return "outside"
    shot_roll = rng.randint(1, int(round(total)))
    return "attack" if shot_roll <= attack_score else "outside"


def _shot_type_for_location(player, location, rng):
    if is_inside_location(location):
        return "inside"
    return _choose_attack_or_outside(player, rng)


# --------------------------------------------------------------------------- #
# branches
# --------------------------------------------------------------------------- #
def _forced_action(bh, bh_pos, bh_location, bh_at_inside, off_lineup, locations, rng):
    """Shot-clock desperation: 75% bh shot / 25% kick-out catch-and-shoot."""
    if rng.random() < 0.75:
        shot_type = "inside" if bh_at_inside else _choose_attack_or_outside(bh, rng)
        return {"action": SHOOT, "shooter_pos": bh_pos, "shot_type": shot_type}

    candidates = [
        pos for pos, loc in locations.items()
        if pos != bh_pos and off_lineup.get(pos) is not None
        and _dist(bh_location, loc) <= KICKOUT_MAX_DIST
    ]
    if candidates:
        rpos = rng.choice(candidates)
        receiver = off_lineup.get(rpos)
        rloc = locations.get(rpos, "key")
        return {"action": KICKOUT_SHOOT, "shooter_pos": rpos,
                "shot_type": _shot_type_for_location(receiver, rloc, rng)}
    # no teammate within range → bh shoots himself
    shot_type = "inside" if bh_at_inside else _choose_attack_or_outside(bh, rng)
    return {"action": SHOOT, "shooter_pos": bh_pos, "shot_type": shot_type}


def _disruption_branch(def_aggr, rng):
    """Defense won the read: 50% subtle / 20% Freelance Forced / 30% none (def-aggr adjusts FF/none)."""
    ff = 0.20 + _aggr_delta(def_aggr, 0.10, -0.10)
    none = 0.30 + _aggr_delta(def_aggr, -0.10, 0.10)
    r = rng.random()
    subtle = 1.0 - ff - none  # stays 0.50
    if r < subtle:
        return {"action": SUBTLE_MOVEMENT}
    if r < subtle + ff:
        return {"action": FREELANCE_FORCED}
    return {"action": ADVANCE}  # no effect


def _neutral_branch(off_aggr, def_aggr, rng):
    """Neither side decisively won: 50/50 subtle vs pass, adjusted by both teams' aggression."""
    pass_pct = 0.50 + _aggr_delta(off_aggr, 0.20, -0.20) + _aggr_delta(def_aggr, -0.20, 0.20)
    pass_pct = max(0.10, min(0.90, pass_pct))  # brief: can build to 90/10
    if rng.random() < pass_pct:
        return {"action": PASS_IMMEDIATE}
    return {"action": SUBTLE_MOVEMENT}


# --------------------------------------------------------------------------- #
# Universal Shoot Decision (brief: Proposed: Universal Shoot Decision)
#
# One shared decision evaluated at every BH step, after every subtle beat, and at every
# reception. Two steps: (1) is the look optimal? (shot-type mismatch + openness vs a clock/
# tempo-scaled bar) then (2) does the shooter make the right call? (read tier). Shares the
# read map's raw mismatch scores with the (now label-only) hot read — one computation.
# --------------------------------------------------------------------------- #
SHOT_CLOCK_START = 30              # clamp ceiling for shot-clock-scaled bars
# Read tiers (HCO only — used only by should_shoot in the motion + set-play dynamic walks).
# Widened the "safe" band (300/100 vs old 200/125) so far more steps resolve as "safe" (always
# progress / work the ball, never shoot) — cuts FGA by deferring shots, and notably shrinks the
# bar-immune "random" tier that was chucking in the Mid shot-clock tier. See Dynamic_HCO_System.md.
SHOOT_READ_RIGHT = 200             # read tier: optimal decision (shoot/dish if optimal, else progress)
SHOOT_READ_SAFE = 125              # read tier: safe decision (conservative — cascades by shot clock)
SAFE_HOLD_CLOCK = 20.0             # safe tier: clock > this → hold (work the ball)
SAFE_PASS_CLOCK = 10.0             # safe tier: clock in (PASS, HOLD] → hold-or-pass; ≤ PASS → 3-way


# Shot-clock tiers — shared by the random-tier % grid and the SM-precedence grid.
# Boundaries (high→low): Early ≥23, Mid ≥15, Late ≥6, Very late ≥1, Forced <1.
# See Dynamic_HCO_System.md §Tunable Constants.
def _shot_clock_tier(shot_clock):
    c = float(shot_clock or 0)
    if c >= 23:
        return "early"
    if c >= 15:
        return "mid"
    if c >= 6:
        return "late"
    if c >= 1:
        return "very_late"
    return "forced"  # <1s — forced-shot region (handled upstream)


# Optimal-look bar (continuous): bar = clock × steepness × tempo_mult. A look's
# 0–100 mismatch quality must clear the bar to be "optimal" — higher = fewer /
# later shots. Self-shot and hot-read dish share the same steepness; tempo scales
# the bar (slow demands a better look — work the ball; fast shoots sooner).
# Raised 1.6→2.0 to push more HCO shots from the Mid (15-22s) tier into Late
# (6-14s) and cut total FGA. See Dynamic_HCO_System.md §Tunable Constants.
OPTIMAL_BAR_STEEPNESS = 2.0
OPTIMAL_BAR_TEMPO_MULT = {"slow": 1.2, "normal": 1.0, "fast": 0.8}

# Non-strategic ("random") read-tier shoot probability (1–100) by shot-clock tier
# and tempo — a clock+tempo progression (low early, high late) so undisciplined
# possessions stop dumping early shots. Very-late is a flat 95% (clock pressure
# dominates); <1s is the forced-shot backstop upstream.
RANDOM_TIER_SHOOT_PCT = {
    "early":     {"slow": 10, "normal": 20, "fast": 30},
    "mid":       {"slow": 20, "normal": 35, "fast": 50},
    "late":      {"slow": 95, "normal": 95, "fast": 95},
    "very_late": {"slow": 95, "normal": 95, "fast": 95},
}

# Minimum nearest-defender separation for an HCO OUTSIDE candidate to be eligible.
# Inside/attack candidates are unaffected. The gate relaxes with clock pressure and
# is shared by optimal self shots, optimal dishes, and random-tier self shots.
OUTSIDE_SHOT_MIN_GAP_BY_TIER = {
    "early": 11.0,
    "mid": 7.0,
    "late": 3.0,
    "very_late": 0.0,
    "forced": 0.0,
}

# Outside-shot selection is discounted at the attack-vs-outside choice itself,
# rather than rejecting an already-selected shot later in the walk. This keeps
# shot volume/timing intact while steering eligible outside players toward drives.
OUTSIDE_SHOT_SELECTION_MULTIPLIER = 0.55

# Focus-emphasis: how far one point of the inside/attack/outside strategy slider moves a
# candidate's shot quality. Slider 0–4 with 2 == neutral, so the multiplier spans
# 0.5x (slider 0) .. 1.5x (slider 4). Sized against the optimal bar (clock x 2.0 x tempo:
# ~60 early, ~20 late) and read scores in the +/-50 range, so it is a real lever late in
# the clock without swamping the mismatch read itself.
#
# WHY THIS EXISTS: `attack` and `outside` already steered motion via
# `_weighted_attack_or_outside`, but `inside` reached nothing — a post player's read could
# never be promoted by team emphasis. The orphaned `_build_shot_type_weighted_list`
# (phase_resolution) was the original implementation of that intent and had no callers
# after the 2026-07-11 motion/set-play unification. This restores the surface at the point
# the current architecture actually decides between candidates.
FOCUS_EMPHASIS_STEP = 0.25
FOCUS_EMPHASIS_NEUTRAL = 2

# Retained as an explicit all-tier acceptance dial. At 100, selected outside
# shots are never discarded after the weighted attack-vs-outside choice.
OUTSIDE_SHOT_ACCEPTANCE_PCT_BY_TIER = {
    "early": 100,
    "mid": 100,
    "late": 100,
    "very_late": 100,
    "forced": 100,
}

# Subtle-movement precedence: per shot-clock tier, the tempos for which subtle
# movement takes precedence over the shoot decision (the offense works the ball
# instead of shooting). Gated upstream by the turn's offense_reads / alterations
# roll — NOT a second alterations roll. Precedence retreats as the clock drains
# and as tempo speeds up. See Dynamic_HCO_System.md §Tunable Constants.
SM_PRECEDENCE_TEMPOS = {
    "early":     ("slow", "normal", "fast"),
    "mid":       ("slow", "normal"),
    "late":      ("slow",),
    "very_late": (),
}


def _weighted_attack_or_outside(player, off_team, rng):
    """Attack-vs-outside pick from the PLAYER alone: attack_score=(AG+SC)/2 vs
    outside_score=SH x OUTSIDE_SHOT_SELECTION_MULTIPLIER. A stronger skill is chosen MORE
    often, not always.

    Team emphasis is deliberately NOT here. The `attack`/`outside` sliders used to add
    +10/point to these scores, which meant the sliders steered shot type in TWO places —
    this roll and (since the focus-emphasis wiring) the quality multiplier in
    `_evaluate_shot`. Two mechanisms for one job is how the orphaned
    `_build_shot_type_weighted_list` came about in the first place: they drift, and the
    docs end up describing whichever the author remembered. Emphasis now lives in exactly
    one place, `_focus_emphasis`.

    The resulting model is also the more honest one: shot TYPE reflects who the player is,
    and the coach's emphasis decides WHO SHOOTS. The team mix still moves with the sliders
    — emphasising outside raises the quality of outside-classified candidates so more of
    them win the `should_shoot` comparison — it shifts through SELECTION rather than
    through RECLASSIFICATION.

    ``off_team`` is retained in the signature: callers pass it positionally, and it keeps
    the seam open for a future player-level (rather than team-level) bias.
    """
    a = getattr(player, "attributes", {}) or {}
    attack_score = (a.get("AG", 0) + a.get("SC", 0)) / 2
    outside_score = a.get("SH", 0) * OUTSIDE_SHOT_SELECTION_MULTIPLIER
    total = attack_score + outside_score
    # Same sub-1 rounding guard as _choose_attack_or_outside: int(round(total)) can
    # collapse 0<total<1 to 0 and make rng.randint(1, 0) raise. MORE reachable now that
    # the emphasis floor (~+20 from the sliders) is gone — a player with near-zero
    # AG/SC/SH now genuinely lands here.
    if int(round(total)) < 1:
        return "outside"
    return "attack" if rng.randint(1, int(round(total))) <= attack_score else "outside"


def _shoot_threshold(shot_clock, tempo_call):
    """Optimal-look bar = clock × steepness × tempo_mult (continuous). Drops as the
    clock drains; slow tempo raises it (work the ball), fast lowers it (shoot sooner)."""
    clock = max(0.0, min(float(shot_clock or 0), SHOT_CLOCK_START))
    return clock * OPTIMAL_BAR_STEEPNESS * OPTIMAL_BAR_TEMPO_MULT.get(tempo_call, 1.0)


def _shoot_read_tier(shooter, off_team, rng):
    """Decision-quality tier: right (> SHOOT_READ_RIGHT=200) / safe (> SHOOT_READ_SAFE=125) / random (else)."""
    read = (player_read_raw(shooter) + core8_gameplay(_team_attr(off_team, "discipline", 0))) * rng.randint(1, 6)
    if read > SHOOT_READ_RIGHT:
        return "right"
    if read > SHOOT_READ_SAFE:
        return "safe"
    return "random"


def _random_tier_shoot_pct(shot_clock, tempo_call):
    """Shoot probability (1–100) for the non-strategic read tier — clock+tempo
    progression (low early, high late). See RANDOM_TIER_SHOOT_PCT."""
    tier = _shot_clock_tier(shot_clock)
    if tier == "forced":
        tier = "very_late"  # <1s forced-shot region — fall to the very-late floor
    tempo = tempo_call if tempo_call in ("slow", "normal", "fast") else "normal"
    return RANDOM_TIER_SHOOT_PCT[tier][tempo]


def sm_takes_precedence(shot_clock, tempo_call):
    """True when subtle movement should take precedence over the shoot decision at
    this shot-clock tier + tempo. The caller gates this on the turn's offense_reads
    (alterations) roll — this is NOT a second alterations roll. See SM_PRECEDENCE_TEMPOS."""
    tier = _shot_clock_tier(shot_clock)
    tempo = tempo_call if tempo_call in ("slow", "normal", "fast") else "normal"
    return tempo in SM_PRECEDENCE_TEMPOS.get(tier, ())


def _outside_shot_is_eligible(pos, shot_type, shot_clock, separation_map):
    """Clock-tier separation gate for outside candidates.

    ``None`` preserves legacy behavior for non-HCO/specialized callers that have
    not supplied an authoritative per-step geometry frame. An explicit map with a
    missing player is treated as unknown/ineligible while a positive gap is required.
    """
    if shot_type != "outside":
        return True
    tier = _shot_clock_tier(shot_clock)
    required = OUTSIDE_SHOT_MIN_GAP_BY_TIER[tier]
    if required <= 0:
        return True
    if separation_map is None:
        return True
    gap = separation_map.get(pos)
    return gap is not None and float(gap) >= required


def _apply_outside_shot_acceptance(decision, shot_clock, rng):
    """Apply the clock-tier preference discount to a selected outside shot."""
    if not decision or decision.get("shot_type") != "outside":
        return decision
    pct = OUTSIDE_SHOT_ACCEPTANCE_PCT_BY_TIER[_shot_clock_tier(shot_clock)]
    if pct >= 100 or rng.randint(1, 100) <= pct:
        return decision
    return None


def _focus_emphasis(off_team, shot_type):
    """Multiplier for the team's inside/attack/outside emphasis on this shot type.

    Slider keys are literally 'inside' / 'attack' / 'outside', so the shot type indexes
    the slider directly. Neutral (2) returns 1.0. Pure arithmetic — draws no RNG, so
    wiring this adds nothing to the sim stream.
    """
    s = getattr(off_team, "strategy_settings", {}) or {}
    try:
        val = int(s.get(shot_type, FOCUS_EMPHASIS_NEUTRAL))
    except (TypeError, ValueError):
        val = FOCUS_EMPHASIS_NEUTRAL
    return 1.0 + FOCUS_EMPHASIS_STEP * (val - FOCUS_EMPHASIS_NEUTRAL)


def _apply_focus_emphasis(quality, mult):
    """Apply the emphasis multiplier sign-safely.

    Read scores are DIFFERENTIALS and are frequently negative, so a naive `quality * mult`
    inverts the intent — emphasising inside would make a bad inside read even worse and
    push it further from selection. Scaling a positive quality up and shrinking a negative
    quality toward zero keeps 'more emphasis => more likely to be chosen' true in both
    regimes.
    """
    if mult == 1.0 or quality == 0:
        return quality
    return quality * mult if quality > 0 else quality / mult


def _evaluate_shot(player, position, location, read_scores, off_team, shot_clock,
                   tempo_call, openness, rng, separation_map=None):
    """(shot_type, quality, optimal, is_mismatch, eligible) for one candidate."""
    from BackEnd.engine.motion_read_map import READ_THRESHOLD
    scores = read_scores.get(getattr(player, "player_id", None), {}) or {}
    if is_inside_location(location):
        shot_type = "inside"
    else:
        shot_type = _weighted_attack_or_outside(player, off_team, rng)
    raw = float(scores.get(shot_type, 0.0))
    # Team focus emphasis. Applied to the candidate's quality (not to the type roll), because
    # this architecture picks a type per candidate and then competes candidates — so emphasis
    # belongs where candidates are compared. `is_mismatch` below stays on the RAW score: a hot
    # read is a genuine personnel edge, not something a slider should be able to manufacture.
    quality = _apply_focus_emphasis(raw + openness, _focus_emphasis(off_team, shot_type))
    eligible = _outside_shot_is_eligible(position, shot_type, shot_clock, separation_map)
    return (
        shot_type,
        quality,
        eligible and quality >= _shoot_threshold(shot_clock, tempo_call),
        raw > READ_THRESHOLD,
        eligible,
    )


def should_shoot(shooter_pos, off_lineup, locations, read_scores, off_team,
                 shot_clock, tempo_call, rng, openness=0.0, allow_dish=True,
                 blocked_dish_targets=None, openness_map=None, separation_map=None):
    """Universal shoot decision. Returns a SHOOT Decision
    ``{action, shooter_pos, shot_type, via_pass, hot_read}`` or ``None`` (progress).

    Step 1 evaluates the shooter's look (and, when ``allow_dish``, teammates — the "best shot
    available" = the collapsed hot read as a *dish*); Step 2 applies the shooter's read tier:
    right → take it if optimal (self or dish) else progress; safe → progress; random → 50/50.
    ``openness`` (>=0) lifts the shooter's quality (e.g. a frozen defender post-subtle). The
    ``hot_read`` flag tags a shot that came off a genuine mismatch (label only). Receptions pass
    ``allow_dish=False`` (no re-dish).

    ``openness_map`` (S3b / Goal 2, ``{pos: openness}``) supplies a PER-PLAYER openness so both the
    shooter AND every dish candidate are judged by his own space (from the S1 cushion). When given it
    overrides the scalar ``openness`` per position (missing pos → the scalar for the shooter, 0.0 for a
    teammate — i.e. legacy). This is what lets an open off-ball man become the best look (step-in / the
    open-man dish); without it teammate openness was hardcoded 0.0, so a beaten defender never surfaced.

    ``blocked_dish_targets`` (a set of positions) are teammates whose passing lane is covered —
    the hot-read "truly open" gate (see Dynamic_HCO_System.md §4). They're excluded as
    dish candidates: the offense won't dish into a covered lane."""
    shooter = off_lineup.get(shooter_pos)
    if shooter is None:
        return None
    blocked_dish_targets = blocked_dish_targets or set()

    def _openness_for(pos, default):
        return openness_map.get(pos, default) if openness_map else default

    s_type, s_quality, s_optimal, s_mismatch, s_eligible = _evaluate_shot(
        shooter, shooter_pos, locations.get(shooter_pos, "key"), read_scores, off_team,
        shot_clock, tempo_call, _openness_for(shooter_pos, openness), rng, separation_map)
    best = {"pos": shooter_pos, "type": s_type, "quality": s_quality,
            "optimal": s_optimal, "mismatch": s_mismatch, "via_pass": False}
    if allow_dish:
        for pos, p in off_lineup.items():
            if pos == shooter_pos or not p or locations.get(pos) is None:
                continue
            if pos in blocked_dish_targets:
                continue  # covered passing lane → not "truly open" → not a dish candidate
            t, q, opt, mm, _eligible = _evaluate_shot(
                p, pos, locations[pos], read_scores, off_team, shot_clock,
                tempo_call, _openness_for(pos, 0.0), rng, separation_map)
            if opt and q > best["quality"]:
                best = {"pos": pos, "type": t, "quality": q, "optimal": opt, "mismatch": mm, "via_pass": True}

    # 🔎 Optimal-bar diagnostic: confirms the new clock×steepness×tempo bar is live.
    logging.debug(
        "🪟 [SHOT-SELECT] clock=%.1f tempo=%s bar=%.1f best_q=%.1f optimal=%s via_pass=%s",
        float(shot_clock or 0), tempo_call, float(_shoot_threshold(shot_clock, tempo_call)),
        float(best["quality"]), best["optimal"], best["via_pass"],
    )

    tier = _shoot_read_tier(shooter, off_team, rng)

    def _dish_to_best():
        return _apply_outside_shot_acceptance(
            {"action": SHOOT, "shooter_pos": best["pos"], "shot_type": best["type"],
             "via_pass": True, "hot_read": best["mismatch"]},
            shot_clock,
            rng,
        )

    def _nonstrategic():
        # SHOOT / HOLD / PASS coin flip: pass → dish to the best open man (finds a cutter when the BH
        # isn't reading); shoot → clock+tempo-gated BH look (so early possessions don't dump shots);
        # else hold → progress.
        c = rng.choice(("shoot", "hold", "pass"))
        if c == "pass" and best["via_pass"]:
            return _dish_to_best()
        if (c == "shoot" and s_eligible
                and rng.randint(1, 100) <= _random_tier_shoot_pct(shot_clock, tempo_call)):
            return _apply_outside_shot_acceptance(
                {"action": SHOOT, "shooter_pos": shooter_pos, "shot_type": s_type,
                 "via_pass": False, "hot_read": False},
                shot_clock,
                rng,
            )
        return None

    if tier == "right":
        if best["optimal"]:
            return _apply_outside_shot_acceptance(
                {"action": SHOOT, "shooter_pos": best["pos"], "shot_type": best["type"],
                 "via_pass": best["via_pass"], "hot_read": best["mismatch"]},
                shot_clock,
                rng,
            )
        return None  # nothing optimal → progress
    if tier == "safe":
        # Conservative read CASCADES by shot clock: lots of time → work the ball; mid → work it or take
        # the easy pass; late → open up to a full shoot/hold/pass. Never forces the BH's own shot early.
        sc = float(shot_clock or 0)
        if sc > SAFE_HOLD_CLOCK:                        # > 20 → hold (work the ball)
            return None
        if sc > SAFE_PASS_CLOCK:                        # 10–20 → hold, or the easy pass to an open man
            if rng.choice(("hold", "pass")) == "pass" and best["via_pass"]:
                return _dish_to_best()
            return None
        return _nonstrategic()                          # ≤ 10 → shoot / hold / pass
    return _nonstrategic()                              # random tier


# --------------------------------------------------------------------------- #
# entry point
# --------------------------------------------------------------------------- #
def decide_step_action(game, step, bh_pos, bh_defender, off_lineup, read_map, rng=_random,
                       offense_reads=True, defense_pressure=True):
    """
    Decide the ball handler's action for one motion skeleton step (brief Step 2 + Turn-Level
    Read Gating). The two booleans are rolled once per turn by the resolver and select which of
    the four condition-matrix branches applies:

      offense_reads=T, defense_pressure=T  → read battle (offense read vs defense): offense wins
          → hot read or (fallback) subtle; defense wins → disruption; neutral → subtle/pass.
      offense_reads=T, defense_pressure=F  → offense unopposed/"successful" → hot read or subtle.
      offense_reads=F, defense_pressure=T  → ball-handling battle (ball_handling vs defense):
          defense wins → disruption; otherwise (offense wins / neutral) → advance.
      (offense_reads=F, defense_pressure=F → the resolver defers to the static skeleton; this
          function isn't called.)

    Args:
        game: GameManager (offense_team/defense_team team_attributes + aggression_call; game_state).
        step: the skeleton step dict (pos_actions give each player's location this step).
        bh_pos: ball-handler position key (e.g. "PG").
        bh_defender: the ball handler's defender Player (man matchup, or nearest zone defender).
            May be None (treated as no defensive pressure).
        off_lineup: {pos: Player} for the offense.
        read_map: Phase-1 {player_id: {inside,attack,outside}} flags.
        rng: random source (injectable for tests).
        offense_reads: turn-level — offense is executing reads this turn.
        defense_pressure: turn-level — defense is executing pressure this turn.

    Returns:
        Decision dict: {"action": <one of the action constants>, ...payload}.
        Shot actions carry shooter_pos + shot_type (and via_pass for hot reads).
    """
    game_state = getattr(game, "game_state", {}) or {}
    off_team = game.offense_team
    def_team = game.defense_team

    bh = off_lineup.get(bh_pos)
    locations = _step_locations(step)
    bh_location = locations.get(bh_pos, "key")
    bh_at_inside = is_inside_location(bh_location)

    discipline = core8_gameplay(_team_attr(off_team, "discipline", 0))
    fight = core8_gameplay(_team_attr(def_team, "fight", 0))
    off_eff = core8_gameplay(_team_attr(off_team, "offensive_efficiency", 0))
    def_eff = core8_gameplay(_team_attr(def_team, "defensive_efficiency", 0))
    off_chem = _team_attr(off_team, "team_chemistry", 7)
    def_chem = _team_attr(def_team, "team_chemistry", 7)
    off_aggr = _aggr_call(off_team)
    def_aggr = _aggr_call(def_team)
    shot_clock = game_state.get("shot_clock_remaining", 30)
    defense_playcall = game_state.get("defense_playcall")
    tempo = (getattr(off_team, "strategy_calls", {}) or {}).get("tempo_call", "normal")

    # offense_score (form B) — read-based
    offense_score = (player_read_raw(bh) + discipline) * rng.randint(1, 6)

    # shot-clock desperation pre-check (universal shot-clock safety; only bites when the offense
    # isn't reading well and the clock is low).
    if offense_score < DESPERATION_OFFENSE_CEILING:
        roll = rng.randint(1, 100) + TEMPO_MOD.get(tempo, 0)
        if roll > 4 * shot_clock:
            return _forced_action(bh, bh_pos, bh_location, bh_at_inside, off_lineup, locations, rng)
        # else fall through to the condition matrix

    # NOTE: shots (incl. the old hot read, now a label) are handled BEFORE this by
    # ``should_shoot`` in the resolver. This function is the MOVEMENT decision for when the BH
    # progresses (doesn't shoot): subtle / advance / disruption / pass.

    # Condition 2 — offense reading, defense not pressuring: the offense is unopposed → it keeps
    # probing off-pattern (subtle), since it didn't take a shot.
    if offense_reads and not defense_pressure:
        return {"action": SUBTLE_MOVEMENT}

    # Defense IS pressuring (Condition 1 or 3) → defense_score (form B).
    if bh_defender is None:
        raw_def = 0.0
    elif bh_at_inside:
        raw_def = inside_defender_raw(bh_defender)
    else:
        raw_def = defender_pressure_raw(bh_defender, defense_playcall)
    defense_score = (raw_def + fight) * rng.randint(1, 6)

    if offense_reads:
        # Condition 1 — read battle: offense read score vs defense. Offense wins → it keeps the
        # initiative with a subtle probe (the shot was already offered by should_shoot); defense
        # wins → disruption; neutral → subtle/pass.
        if offense_score > defense_score + def_eff + def_chem:
            return {"action": SUBTLE_MOVEMENT}
        if defense_score > offense_score + off_eff + off_chem:
            return _disruption_branch(def_aggr, rng)
        return _neutral_branch(off_aggr, def_aggr, rng)

    # Condition 3 — offense NOT reading, defense pressuring → ball-handling battle (symmetric to
    # defense_score). Defense wins → disruption; offense wins or neutral → advance (the d-foul
    # check on an offense win is deferred per brief).
    ball_handling_score = (ball_handling_raw(bh) + off_eff) * rng.randint(1, 6)
    if defense_score > ball_handling_score + off_eff + off_chem:
        return _disruption_branch(def_aggr, rng)
    return {"action": ADVANCE}
