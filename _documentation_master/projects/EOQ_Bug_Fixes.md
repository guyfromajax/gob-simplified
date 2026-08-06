# End-of-Quarter Bug Fixes

## Objective

Make end-of-quarter gameplay and animation independent of the turn type that first enters the final 30 seconds. No live-ball result or clock-running animation may execute beyond 0:00, and every terminal turn must expose one consistent backend/frontend contract.

## Agreed behavior

- HCT, FCP, and Fast Break retain as much of their normal movement as fits, but reserve enough time to transition to and release an FLSS. If the full turn cannot fit, it is shortened at a valid animation boundary and hands off to FLSS from the live ballhandler and player positions.
- In Q4/OT, Run Out the Clock overrides Fast Break whenever `should_run_out_clock()` applies.
- In Q4/OT, Force Foul takes precedence when the defense remains in the existing Force Foul score band. The foul occurs immediately after BIP/SIP receipt, before an FCP or HCT turn begins.
- When Force Foul does not apply and `should_run_out_clock()` does, Run Out also overrides FCP and HCT.
- When BIP, OREB, or DREB consumes the remaining clock, the terminal payload has `quarter_ends_after=true`, no next play, no pending FLSS, and no action after 0:00.
- With insufficient time for a normal OREB putback, a tied or trailing offense uses a shortened buzzer-beating putback/FLSS animation. A leading offense follows Run Out policy when eligible.
- Free throws and SIP remain clock-stopped, but their exits must use the same EOQ routing and terminal invariants.

## Work plan

### 1. Universal quarter-end invariant

- Centralize terminal cleanup after every game-clock mutation.
- Clamp backend and animation clock contracts to nonnegative values.
- Clear impossible continuation routes and pending EOQ state at 0:00.
- Preserve the sole exception for free throws that must still be completed.

### 2. Universal runway calculation

- Calculate the FLSS movement-and-release reserve from the prospective shooter and live coordinates.
- Derive the time budget available to the originating turn.
- Replace the fixed low-clock cutoff with the calculated runway decision.

The existing FLSS contract permits a shot from every court location and reserves one game-second for release. Accordingly, movement toward the basket is optional: the originating turn receives `max(0, time_remaining - 1)` seconds, then Task 3 hands the live ballhandler and coordinates to FLSS. Ball flight is post-release animation and does not consume game clock.

### 3. Shortened non-HCO paths

- Add valid truncation/handoff points for HCT, FCP, and every migrated Fast Break type.
- Preserve normal animation and execution only through the selected cutoff.
- Start FLSS from the actual ballhandler, coordinates, score state, and remaining clock.

Implementation uses a deep-cloned, RNG-neutral preview of the selected resolver. A fitting turn is rerun unchanged on the live game. An overrun contributes only complete non-terminal schema steps within the runway budget; their end coordinates and ball owner become the live FLSS start. Speculative score, stat, foul, turnover, rebound, and possession mutations remain isolated on the clone.

### 4. Q4/OT situational priority

Apply the following decision before Fast Break, HCT, or FCP begins:

1. Force Foul after inbound, when eligible.
2. Run Out the Clock, when eligible.
3. Quick Shot, when eligible.
4. Otherwise, normal/final-shot execution with runway protection.

The priority is evaluated once, before HCO/HCT/FCP/Fast Break routing. Force Foul uses the live/prior-seam ballhandler and quick-foul schema; Run Out is terminal from every live state. This prevents a defensive pressure choice or transition state from bypassing the score-and-clock decision.

### 5. Inbound Force Foul

- Use BIP/SIP to establish the inbound receiver and pressure alignment.
- Execute the foul on the receiver before starting HCT/FCP.
- Remove reliance on an HCO-labelled force-foul conversion for an active pressure turn.

BIP retains the selected FCP/HCT route while using the quick-foul receiver/fouler formation. At the next possession boundary the universal state-neutral hook executes the foul before the pressure resolver begins. The obsolete HCO-labelled Final Turn force-foul resolver is removed.

### 6. Synthesized-turn normalization

- Route BIP, OREB, and DREB clock mutations through the universal terminal finalizer.
- Stop batched OREB processing immediately at 0:00.
- Prevent terminal rebound/inbound payloads from advertising another possession.

All synthesized clock mutations now use one `GameManager` finalization seam. OREB checks it immediately, before possession flips or nested DREB creation; BIP clears the local pressure route when runoff reaches 0:00; DREB uses the same terminal contract.

### 7. Short-clock OREB

- Preserve rebound capture.
- Use a normal putback only when its complete animation fits.
- Otherwise, transition a tied/trailing offense into a shortened buzzer putback/FLSS.
- Use Run Out for an eligible leading offense.

Normal putbacks retain their complete schema when it fits. When only the
post-release resolution overruns, the normal capture/release timing is kept and
the flight is clocked only through 0:00. When capture plus release cannot fit,
those two beats are proportionally shortened so release occurs at 0:00. In both
cases the remaining rim/bounce resolution stays visible with the game clock
pinned at zero. An offense eligible for Run Out secures the rebound and drains
the clock without resolving a speculative shot.

### 8. SIP and free-throw exits

- Keep SIP and FT clock-neutral.
- Validate every make, miss, and rebound exit against the corrected EOQ decision layer.

SIP and every FT attempt remain game-clock neutral. A shared clock-stopped
inbound gate now rejects BIP/SIP synthesis once the source turn is terminal or
the clock is 0:00, closing the post-buzzer SIP path. Final-FT makes route to BIP
only with positive time; final misses route to OREB/DREB only with positive
time; unfinished FT trips remain the sole 0:00 continuation exception.

### 9. Documentation

Update `EOQ_System.md`, `Situational_Logic_System.md`, animation routing documentation, and any affected turn-system documents as each behavior lands.

Synchronized the canonical EOQ lifecycle, universal terminal payload,
possession-entry priority, measured HCT/FCP/Fast Break preview, short-clock OREB,
clock-neutral FT/SIP exits, and frontend Run Out/putback routing. Removed the
fixed-cutoff and HCO-only wording where it no longer describes the live path;
the fixed `<=8s` non-HCO gate is documented only as the preview-failure fallback.

### 10. Regression coverage

Cover HCO, HCT, FCP, Fast Break, BIP, SIP, FT, OREB, and DREB at 30, 9, 8, 3, 1, and 0 seconds. Include Q1-Q3 tied situations and Q4/OT score margins of offense +1, +8, +9, -3, -4, and -19. Assert release timing, ownership, terminal routing, absence of negative clocks, and the free-throw exception.

`tests/test_eoq_regression_matrix.py` supplies the required cross-product: all
nine turn families, six clock boundaries, Q1-Q3 tied entries, and all six Q4/OT
score margins. It asserts situational priority, FLSS reserve/release timing,
rebounder ownership, terminal continuation cleanup, nonnegative schema clocks,
clock-neutral inbounds/FTs, and the unfinished-FT exception. The broader focused
suite covers the real HCO pacing, pressure, Fast Break, OREB/DREB, quick-foul,
and FT resolver contracts. The matrix also exposed and fixed a randomized
"worst-case" Final Turn reserve calculation; it now evaluates every eligible
outside target deterministically without consuming simulation RNG.

## Implementation status

- [x] Task 1 — Universal quarter-end invariant
- [x] Task 2 — Universal runway calculation
- [x] Task 3 — Shortened non-HCO paths
- [x] Task 4 — Q4/OT situational priority
- [x] Task 5 — Inbound Force Foul
- [x] Task 6 — Synthesized-turn normalization
- [x] Task 7 — Short-clock OREB
- [x] Task 8 — SIP and free-throw exits
- [x] Task 9 — Documentation synchronization
- [x] Task 10 — Regression coverage
