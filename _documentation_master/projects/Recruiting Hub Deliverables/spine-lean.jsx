/* Lean object — three treatment directions (A/B/C).
   window.SpineLean = { LeanObject, analyzeLean, ODDS } */
(function () {
  const { abbr, TEAM_NAME } = window.SpineData;
  const ODDS = { 1: '≈8×', 2: '≈4×', 3: '≈2×' };

  // Reduce a recruit's lean model to a single "standing" the row communicates.
  function analyzeLean(rec) {
    const leans = rec.leans || [];
    if (rec.locked) {
      const top = leans[0] && leans[0].team ? abbr(leans[0].team) : '—';
      return { standing: 'locked', topRival: top };
    }
    if (rec.yourRank === 1) return { standing: 'you1' };
    if (rec.yourRank > 1) return { standing: 'list', rank: rec.yourRank };
    if (leans.length === 0) return { standing: 'quiet' };
    if (leans.every(s => s.open)) return { standing: 'open' };
    return { standing: 'others' };
  }

  function Tok({ slot }) {
    if (slot.open) return <span className="tok is-open">open</span>;
    const you = slot.team === TEAM_NAME;
    return <span className={`tok ${you ? 'is-you' : ''}`}>{abbr(slot.team)}</span>;
  }

  const LockIcon = () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4">
      <rect x="5" y="11" width="14" height="10" rx="2"></rect><path d="M8 11V7a4 4 0 0 1 8 0v4"></path>
    </svg>
  );

  /* ---------- Direction A · Standing chip ---------- */
  function LeanA({ rec }) {
    const a = analyzeLean(rec);
    const leans = rec.leans || [];
    const run = leans.length > 0 && (
      <span className="la-list-run">
        {leans.map((s, i) => (
          <span key={i} className="la-list-run" style={{ gap: '3px' }}>
            <span className="seq">{i + 1}</span><Tok slot={s} />
          </span>
        ))}
      </span>
    );
    let chip;
    if (a.standing === 'you1') chip = <span className="la-chip la-you1"><i className="dotpin"></i>Top Choice</span>;
    else if (a.standing === 'list') chip = <span className="la-chip la-list"><i className="dotpin"></i>#{a.rank} On List</span>;
    else if (a.standing === 'locked') chip = <span className="la-chip la-locked"><i className="dotpin"></i>Loyal → {a.topRival}</span>;
    else if (a.standing === 'open') chip = <span className="la-chip la-open"><i className="dotpin"></i>Open Board</span>;
    else if (a.standing === 'quiet') return <span className="lean-a"><span className="la-quiet">No leans yet</span></span>;
    else chip = <span className="la-chip la-none"><i className="dotpin"></i>Not Listed</span>;
    return <span className="lean-a">{chip}{run}</span>;
  }

  /* ---------- Direction B · Ranked ladder ---------- */
  function LeanB({ rec }) {
    const leans = rec.leans || [];
    if (leans.length === 0) return <span className="lean-b"><span className="lb-empty">No leans yet</span></span>;
    return (
      <span className="lean-b">
        {leans.map((s, i) => {
          const you = !s.open && s.team === TEAM_NAME;
          const cls = you ? (i === 0 ? 'is-you' : 'is-you-list') : s.open ? 'is-open' : '';
          return (
            <span key={i} className={`lb-slot ${cls}`}>
              {rec.locked && i === 0 && <span className="lb-lock"><LockIcon /></span>}
              <span className="rk">{i + 1}</span>
              <span className="lb-tok">{s.open ? 'open' : abbr(s.team)}</span>
            </span>
          );
        })}
      </span>
    );
  }

  /* ---------- Direction C · Edge accent + dots ---------- */
  function LeanC({ rec }) {
    const a = analyzeLean(rec);
    const leans = rec.leans || [];
    const edge = a.standing === 'you1' ? 'you' : a.standing === 'list' ? 'list' : null;
    let cap;
    if (a.standing === 'you1') cap = <span className="lc-cap you">Top choice<small>{ODDS[1]} odds</small></span>;
    else if (a.standing === 'list') cap = <span className="lc-cap list">#{a.rank} on list<small>{ODDS[a.rank]} odds</small></span>;
    else if (a.standing === 'locked') cap = <span className="lc-cap locked">Loyal → {a.topRival}<small>hard target</small></span>;
    else if (a.standing === 'open') cap = <span className="lc-cap open">Open board<small>up for grabs</small></span>;
    else if (a.standing === 'quiet') cap = <span className="lc-cap none">No leans yet<small>win games</small></span>;
    else cap = <span className="lc-cap none">Not listed<small>1× odds</small></span>;
    return (
      <span className="lean-c">
        {edge && <span className={`lc-edge ${edge}`}></span>}
        <span className="lc-dots">
          {leans.length === 0 && <span className="lc-dot open"></span>}
          {leans.map((s, i) => {
            const you = !s.open && s.team === TEAM_NAME;
            let dc = 'filled';
            if (s.open) dc = 'open';
            else if (you) dc = i === 0 ? 'you' : 'you-list';
            else if (rec.locked && i === 0) dc = 'filled locked';
            return <span key={i} className={`lc-dot ${dc}`}></span>;
          })}
        </span>
        {cap}
      </span>
    );
  }

  function LeanObject({ rec, variant }) {
    if (variant === 'A') return <LeanA rec={rec} />;
    if (variant === 'B') return <LeanB rec={rec} />;
    return <LeanC rec={rec} />;
  }

  window.SpineLean = { LeanObject, analyzeLean, ODDS };
})();
