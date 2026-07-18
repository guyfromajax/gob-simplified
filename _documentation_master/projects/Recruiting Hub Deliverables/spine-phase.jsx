/* Phase strip — compact indicator + expandable season timeline.
   window.SpinePhase = { PhaseStrip, PHASES } */
(function () {
  const PHASES = {
    passive: { dot: 'passive', name: 'Passive', nmeta: 'passive',
      sub: 'Leans come to you — win games', next: 'Invite Season opens Week 20' },
    invite: { dot: 'live', name: 'Invite Season', nmeta: 'live',
      sub: 'Invite 1 recruit per week', next: 'Signing Day is Week 35' },
    day: { dot: 'payoff', name: 'Signing Day', nmeta: 'payoff',
      sub: '50 points · binding playing-time promises', next: 'Signings post Week 36' },
    results: { dot: 'done', name: 'Results', nmeta: 'done',
      sub: 'Signings are final', next: 'Season complete' }
  };

  const SEGS = [
    { key: 'passive', cls: 'passive', lo: 1, hi: 19, nm: 'Passive' },
    { key: 'invite', cls: 'invite', lo: 20, hi: 26, nm: 'Invite Season' },
    { key: 'passive', cls: 'passive', lo: 27, hi: 34, nm: 'Tournament' },
    { key: 'day', cls: 'day', lo: 35, hi: 35, nm: 'Signing' },
    { key: 'results', cls: 'results', lo: 36, hi: 36, nm: 'Results' }
  ];

  const Chevron = () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M6 9l6 6 6-6"></path></svg>
  );
  const Info = () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2"><circle cx="12" cy="12" r="9"></circle><path d="M12 11v5M12 7.5v.5"></path></svg>
  );

  function PhaseStrip({ phase, week, inviteSent = 0, points = 50, open, onToggle }) {
    const p = PHASES[phase];
    const counter =
      phase === 'invite' ? <div className="pstrip-counter"><div className="n"><b>{inviteSent}</b><i> / 7</i></div><div className="cap">Invites sent</div></div>
      : phase === 'day' ? <div className="pstrip-counter"><div className="n"><b>{points}</b></div><div className="cap">Points left</div></div>
      : null;
    return (
      <React.Fragment>
        <div className={`pstrip ${open ? 'is-open' : ''}`}>
          <div className="pstrip-status">
            <span className={`pstrip-phase-dot ${p.dot}`}></span>
            <span className="pstrip-wk">Week {week}</span>
            <span className="pstrip-meta">
              <span className={`pstrip-name ${p.nmeta}`}>{p.name}</span>
              <span className="pstrip-sub">{p.sub}</span>
            </span>
          </div>
          <div className="pstrip-action">
            {counter}
            <button className="pstrip-expand" onClick={onToggle}>
              {open ? 'Hide season' : 'Season'} <Chevron />
            </button>
          </div>
        </div>
        <div className="ptl">
          <div className="ptl-inner">
            <div className="ptl-track">
              {SEGS.map((s, i) => {
                const cur = week >= s.lo && week <= s.hi;
                return (
                  <div key={i} className={`ptl-seg ${s.cls} ${cur ? 'is-current' : ''}`}>
                    {cur && <span className="ptl-now">Now</span>}
                    <span className="wk">{s.lo === s.hi ? `WK ${s.lo}` : `WK ${s.lo}–${s.hi}`}</span>
                    <span className="nm">{s.nm}</span>
                  </div>
                );
              })}
            </div>
            <div className="ptl-key">
              <span><i style={{ background: 'rgba(74,144,217,.6)' }}></i>Passive · leans build from results</span>
              <span><i style={{ background: 'rgba(52,236,39,.6)' }}></i>Invite Season · 7 invites</span>
              <span><i style={{ background: 'rgba(247,148,32,.7)' }}></i>Signing Day · 50 points</span>
              <span><i style={{ background: 'rgba(255,255,255,.5)' }}></i>Results · signed</span>
            </div>
            <div className="ptl-orient">
              <Info />
              <span>{phase === 'passive'
                ? <React.Fragment><strong>Why can't I invite yet?</strong> It's Week {week}. Invites begin Week 20 — {p.next.toLowerCase()}.</React.Fragment>
                : <React.Fragment><strong>You're in {p.name}.</strong> {p.next}.</React.Fragment>}</span>
            </div>
          </div>
        </div>
      </React.Fragment>
    );
  }

  window.SpinePhase = { PhaseStrip, PHASES };
})();
