# Crash Model A — where crashers land, by shot distance

Static sampling of the model, 40,000 draws per cell — no game measurement. Each panel is a
half-court density map: x 60-96 left to right at 2 units per character, y 4-46 bottom to top at
2 units per row, attacking the rim on the right (`R`). `o` is the shooter. Density runs
` .:-=+*#%@` from empty to the busiest cell **within that panel** (each panel is scaled to its
own maximum, so compare SHAPE and SPREAD, not absolute darkness between panels).

Three columns per band:
- **TODAY** — the flat box, `randint(85,92)` by x and `randint(20,30)` by y. Identical in every band.
- **MODEL A t=1.0** — crashers drawn from exactly the ball's own spread for that shot.
- **MODEL A t=0.7** — crashers hedge toward the rim, drawn from a narrowed version of it.
- **BALL** — where the ball actually bounces, for comparison. Model A never reads this.

Nothing is landed: `GOB_CRASH_SHOT_AWARE` is default OFF and flag-off is byte-identical.
Read with `reports/crash-model-a-2026-09-19.md`.

---

### Shot distance 0-10 (rim) — shooter 6 units from the rim

Ball's own band for this shot: x-offset 2-6, y-variance +/-6

```
TODAY (flat box)     MODEL A  t=1.0       MODEL A  t=0.7       BALL (for comparison)
-------------------- -------------------- -------------------- --------------------
|                    |                    |                    |
|                    |                    |                    |
|                    |                    |                    |
|                    |                    |                    |
|                    |                    |                    |
|                    |                    |                    |
|                    |                    |                    |
|                    |                    |                    |
|            ..*:-   |            ::%     |              :     |            -:%
|            . : .   |              :     |             .-     |            . -
|            o:%:R   |            o:% R   |            o:% R   |            o-@ R
|            . :..   |              :     |              :     |             .-
|            :-@:+   |            ::@     |             -@     |            -:%
|              :..   |              :     |                    |              :
|                    |            . :     |                    |              :
|                    |                    |                    |
|                    |                    |                    |
|                    |                    |                    |
|                    |                    |                    |
|                    |                    |                    |
|                    |                    |                    |
|                    |                    |                    |
-------------------- -------------------- -------------------- --------------------
```

| | mean x | mean distance from rim | y spread (sd) |
|---|---|---|---|
| TODAY | 88.5 | 2.8 | 3.2 |
| Model A t=1.0 | 87.0 | 4.0 | 3.7 |
| Model A t=0.7 | 87.5 | 3.5 | 2.6 |
| BALL | 87.0 | 4.0 | 3.7 |

### Shot distance 10-18 (short) — shooter 14 units from the rim

Ball's own band for this shot: x-offset 2-6, y-variance +/-6

```
TODAY (flat box)     MODEL A  t=1.0       MODEL A  t=0.7       BALL (for comparison)
-------------------- -------------------- -------------------- --------------------
|                    |                    |                    |
|                    |                    |                    |
|                    |                    |                    |
|                    |                    |                    |
|                    |                    |                    |
|                    |                    |                    |
|                    |                    |                    |
|                    |                    |                    |
|            ::*:=   |            :-@     |              :     |            ::@
|            . -.:   |              :     |              :     |             .:
|        o   :-@-R   |        o   ::% R   |        o    :% R   |        o   ::% R
|              -..   |            . :     |              :     |              :
|            --%-*   |            :-%     |             :@     |            -:%
|            ..- .   |              :     |                    |            . :
|                    |            . :     |                    |              :
|                    |                    |                    |
|                    |                    |                    |
|                    |                    |                    |
|                    |                    |                    |
|                    |                    |                    |
|                    |                    |                    |
|                    |                    |                    |
-------------------- -------------------- -------------------- --------------------
```

| | mean x | mean distance from rim | y spread (sd) |
|---|---|---|---|
| TODAY | 88.5 | 2.7 | 3.2 |
| Model A t=1.0 | 87.0 | 4.0 | 3.8 |
| Model A t=0.7 | 87.5 | 3.5 | 2.6 |
| BALL | 87.0 | 4.0 | 3.7 |

### Shot distance 18-26 (mid) — shooter 22 units from the rim

Ball's own band for this shot: x-offset 3-14, y-variance +/-10

```
TODAY (flat box)     MODEL A  t=1.0       MODEL A  t=0.7       BALL (for comparison)
-------------------- -------------------- -------------------- --------------------
|                    |                    |                    |
|                    |                    |                    |
|                    |                    |                    |
|                    |                    |                    |
|                    |                    |                    |
|                    |                    |                    |
|                    |        ::%:#:+     |                    |        -:%:%:+
|                    |          : : .     |          : : :     |         .: : .
|            ::+:-   |        :-%-%:+     |          +-@-+     |        -:%-%:+
|            . -..   |        . : : .     |          :.-..     |         .-.: :
|    o       ::%-R   |    o   ::%:%:+ R   |    o     *-%:+ R   |    o   -:%-%:+ R
|            ..:.:   |          : : .     |          : -..     |          - :..
|            :-@:+   |        :-%-%:+     |          +:%-+     |        ::%:%:+
|             .: :   |          : :..     |          . -..     |         .: - .
|                    |        ::%:@:+     |          -:+.=     |        ::%:@:+
|                    |          : : .     |                    |          : - .
|                    |         .: : .     |                    |          :.: :
|                    |                    |                    |
|                    |                    |                    |
|                    |                    |                    |
|                    |                    |                    |
|                    |                    |                    |
-------------------- -------------------- -------------------- --------------------
```

| | mean x | mean distance from rim | y spread (sd) |
|---|---|---|---|
| TODAY | 88.5 | 2.7 | 3.2 |
| Model A t=1.0 | 82.5 | 8.5 | 6.0 |
| Model A t=0.7 | 84.0 | 7.0 | 4.3 |
| BALL | 82.5 | 8.5 | 6.1 |

### Shot distance 26-40 (long) — shooter 33 units from the rim

Ball's own band for this shot: x-offset 5-22, y-variance +/-12

```
TODAY (flat box)     MODEL A  t=1.0       MODEL A  t=0.7       BALL (for comparison)
-------------------- -------------------- -------------------- --------------------
|                    |                    |                    |
|                    |                    |                    |
|                    |                    |                    |
|                    |                    |                    |
|                    |      : : : :       |                    |      - : : :
|                    |      : : - :.      |                    |      :.: : :
|                    |    :-%:@:%:#:      |        : - :.      |    ::#:#:%:#:
|                    |    . : : : :       |        : :.:       |      : : : :.
|            :.*.-   |    ::%:#:%:%:      |       -%:%-%:      |    ::#:%:@:%:
|              - .   |     .: : : :       |        : - :       |      : : : :
|            ::@-R   |    -:%:#:%:%:  R   |       :%:%:%:  R   |    ::#:%:%:%:  R
|            ..-..   |     .:.:.- :       |       .- : :       |      : : : :
|            ::%-*   |    :-%:%:%:%:      |       :%:@:%:      |    ::%:%:%:%:
|            . - :   |      :.: : :       |        - : :.      |      :.: : :
|                    |    ::%-%:%:#:      |       :%:%:%:      |    ::%:#:%:#:
|                    |     .: : : :       |                    |    . : : : :
|                    |    ::%:%-%:%:      |                    |    ::%:%:%:%:
|                    |                    |                    |
|                    |                    |                    |
|                    |                    |                    |
|                    |                    |                    |
|                    |                    |                    |
-------------------- -------------------- -------------------- --------------------
```

| | mean x | mean distance from rim | y spread (sd) |
|---|---|---|---|
| TODAY | 88.5 | 2.7 | 3.2 |
| Model A t=1.0 | 77.5 | 13.5 | 7.2 |
| Model A t=0.7 | 80.0 | 11.0 | 4.9 |
| BALL | 77.5 | 13.5 | 7.2 |

### Shot distance 40+ (deep) — shooter 48 units from the rim

Ball's own band for this shot: x-offset 8-26, y-variance +/-14

```
TODAY (flat box)     MODEL A  t=1.0       MODEL A  t=0.7       BALL (for comparison)
-------------------- -------------------- -------------------- --------------------
|                    |                    |                    |
|                    |                    |                    |
|                    |                    |                    |
|                    |                    |                    |
|                    |  -:%:%:%:%::       |                    |  ::%:%:%:%::
|                    |    : :.: : .       |                    |  . :.-.: : .
|                    |  -:%:%:%:%::       |     :%:%:%::       |  ::#-%:%-%::
|                    |    : - : :.        |      :.:.:         |   .- - : :
|            ..*:=   |  ::%:#:%-%::       |     :%:%:%:-       |  ::%:%:%-%::
|            ..- :   |    -.:.: : .       |      :.: :         |  ..: :.: :.
|            --%-R   |  -:@:%:%:%::   R   |     :%-%-%-:   R   |  ::%:%:%:%-:   R
|             .- :   |    : : - :..       |      : -.: .       |    :.: :.:
|            ::@-+   |  ::%-%:%:%-:       |     -%:%:%:-       |  ::%:#:%:@::
|              - :   |    : : : :         |      : - -         |    : : : - .
|                    |  ::%:%:@-#::       |     :%:@:%::       |  ::%:%:%:%::
|                    |    :.- : :.        |      : :.: .       |    : : : : .
|                    |  ::%:%:%:%-:       |     .:.: - .       |  -:%:%:%:%::
|                    |    : : : -         |                    |    - -.- -
|                    |   .: : :.: .       |                    |    : : :.:.
|                    |                    |                    |
|                    |                    |                    |
|                    |                    |                    |
-------------------- -------------------- -------------------- --------------------
```

| | mean x | mean distance from rim | y spread (sd) |
|---|---|---|---|
| TODAY | 88.5 | 2.7 | 3.2 |
| Model A t=1.0 | 74.0 | 17.0 | 8.4 |
| Model A t=0.7 | 76.5 | 14.5 | 6.0 |
| BALL | 74.1 | 16.9 | 8.4 |

