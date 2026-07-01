

##Main Buckets of Animation Issues

**Unusually Long Pauses in HCO steps**
- This seems to be exclusive to Motion offense
- This does not happen all steps, but in many
- All ten players remain frozen or stationary for unusually long beats

- Desired behavior
    - We eliminate unnecessary pauses between steps when they're not dictated by a bh hold
    - If a bh hold is in palce that should not preclude the other 9 players form moving. I don't know if htis is the case, but we should find out.
    - While we should not have steps where all ten players are programmed to be stationary, but if we should consider an idle organic movment animation for palyer sprite on steps where they are stationary

**Pause Between Some Turn Transitions**
- We may have some pauses programemd for soem reason and others may be due to buggy animation. We need to research.
- Transitions where I'm consistently seeing pauses
    - DREB to HCO
    - DREB to FB
    - HCT (steal) to FB

- For comparison, turn transistion that are no pause perfect every time
    - HCO to SIP (after a foul or db turnover)
    - HCO shot (make or miss) to DREB or OREB
    - HCO make to BIP
    - HCO (steal) to HCO (new team offense)
    - SIP to HCO
    - FCP (steal) to HCO
    - HCT (foul) to SIP
    - HCT (foul) to Free Throw
    - HCT to HCO


**Pause Between Some Step Transitions**
- We may have some pauses programemd for soem reason and others may be due to buggy animation. We need to research.
- Transitions where I'm consistently seeing pauses
    - RR & Triangl FB -- the Outlet REceiver passing to the RR down court

**Defense Movment Relative to Pass Animation in HCO turns**
- bug: in some, but not all steps with a pass, the defenders are moving to their position, then the ball detaches from teh passr to the receiver
- desired animation: the ball detaches from teh passer at the same time tha tthe defenders begin moving ot their step destinations, so these movements should be in unison.

- Situtaions where I"m definitley seeing this consistentlh
    - Set Play vs Zone Defense (many if not all instances)
    - Motion offense vs Zone Defense (some if not many instances)
    - Motion Offense vs Man Defense (some if not many instances)
    - Set Play vs Man Defense (some if not many instances)
