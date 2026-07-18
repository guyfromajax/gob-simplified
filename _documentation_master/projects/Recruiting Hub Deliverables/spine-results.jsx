/* Results / Signed (D4) — weekly-visit panel + Week-36 final signings.
   window.SpineResults = { ResultsApp } */
(function () {
  const { useState, useMemo, useRef } = React;
  const { TEAM_NAME, abbr, pool, REGIONS, REGION_NAMES } = window.SpineData;
  const { analyzeLean } = window.SpineLean;
  const { PhaseStrip } = window.SpinePhase;
  const { Pool } = window.SpinePool;

  const Dot = () => <svg viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="12" r="6"/></svg>;
  const ArrowUp = () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6"><path d="M7 17L17 7M9 7h8v8"/></svg>;
  const Flag = () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2"><path d="M4 22V4M4 4h13l-2 4 2 4H4"/></svg>;

  const hash = s => { let h = 0; for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) % 997; return h; };

  // deterministic signing outcomes from the pool
  const signings = pool.filter(r => !r.lost).map(r => {
    const a = analyzeLean(r);
    const h = (hash(r.id) + r.rt) % 100;
    let withYou = false;
    if (a.standing === 'you1') withYou = h < 68;
    else if (a.standing === 'list') withYou = h < (a.rank === 2 ? 30 : 18);
    const rival = (r.leans.find(s => s.team && s.team !== TEAM_NAME) || {}).team
      || window.SpineData.RIVAL_NAMES[h % window.SpineData.RIVAL_NAMES.length];
    return { ...r, stand: a, withYou, signedTeam: withYou ? TEAM_NAME : rival };
  }).sort((a, b) => (b.withYou - a.withYou) || (b.rt - a.rt));

  function standChip(stand, cls = 'sstand') {
    if (stand.standing === 'you1') return <span className={`${cls} you1`}><Dot />#1</span>;
    if (stand.standing === 'list') return <span className={`${cls} list`}>#{stand.rank}</span>;
    return <span className={`${cls} none`}>—</span>;
  }

  /* ---------- weekly-visit results panel ---------- */
  function WeeklyPanel({ onDismiss }) {
    const mine = pool.filter(r => r.leansToUser && !r.lost).sort((a, b) => b.rt - a.rt);
    const visited = mine[0];
    // rival threats: recruits leaning to you that a rival visited this week, by region
    const threats = mine.slice(1, 9);
    const byRegion = {};
    threats.forEach(r => { (byRegion[r.region] = byRegion[r.region] || []).push(r); });
    const regionsShown = REGIONS.filter(rg => byRegion[rg]).slice(0, 4);
    return (
      <div className="wpanel">
        <div className="wpanel-head">
          <span className="wpanel-badge"><Flag /></span>
          <div className="wpanel-title"><small>Week 22 · Visits processed</small>This Week's Results</div>
          <button className="wpanel-dismiss" onClick={onDismiss}>Back to hub</button>
        </div>
        <div className="wpanel-hero">
          <div className="whero">
            <div className="whero-lbl">Your visit</div>
            <div className="wvisit">
              <span className="wvisit-mark gain"><ArrowUp /></span>
              <div className="wvisit-body">
                <div className="nm">{visited.name}<span className="wmeta"><span className="pos">{visited.pos}</span>Region {visited.region} · {visited.rt} RT</span></div>
                <div className="sub">Visit landed — <b>now leaning you at #{visited.yourRank || 1}</b>. Odds up sharply.</div>
              </div>
            </div>
          </div>
          <div className="whero">
            <div className="whero-lbl">What it changed</div>
            <div className="wvisit">
              <span className="wvisit-mark gain"><Dot /></span>
              <div className="wvisit-body">
                <div className="nm">+1 new lean this week</div>
                <div className="sub"><b>{mine.length}</b> recruits now have your team on their list. 4 invites left this season.</div>
              </div>
            </div>
          </div>
        </div>
        <div className="wregion">
          {regionsShown.map(rg => (
            <div className="wregion-row" key={rg}>
              <span className="wregion-tag">{rg} · {REGION_NAMES[rg]}</span>
              <div className="wregion-visits">
                {byRegion[rg].map(r => {
                  const rival = (r.leans.find(s => s.team && s.team !== TEAM_NAME) || {}).team;
                  return (
                    <div className="wvrow" key={r.id}>
                      <span className="team you">{abbr(TEAM_NAME)}</span>
                      <span className="who">{r.name}</span>
                      <span className="arrow">·</span>
                      {rival
                        ? <><span className="team">{abbr(rival)}</span><span className="note threat">also visited — contested</span></>
                        : <span className="note">no rival visits — clear lane</span>}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  /* ---------- final signings (Wk 36) ---------- */
  function FinalSignings() {
    const [filter, setFilter] = useState('all');
    const targets = signings.filter(r => r.leansToUser);
    const won = signings.filter(r => r.withYou);
    const lostTargets = targets.filter(r => !r.withYou);
    const rows = useMemo(() => filter === 'mine' ? signings.filter(r => r.withYou)
      : filter === 'targets' ? targets : signings, [filter]);
    return (
      <React.Fragment>
        <div className="signsum">
          <div>
            <div className="signsum-big"><span className="n">{won.length}</span><span className="of">signings</span></div>
            <div className="signsum-cap">To {TEAM_NAME}</div>
          </div>
          <div className="signsum-breakdown">
            <div className="ssb"><span className="v win">{targets.filter(r => r.withYou).length}</span><span className="l">Targets won</span></div>
            <div className="ssb"><span className="v loss">{lostTargets.length}</span><span className="l">Targets lost</span></div>
            <div className="ssb"><span className="v">{targets.length}</span><span className="l">Leaned to you</span></div>
          </div>
        </div>
        <div className="sign-filter">
          <button className={`chip ${filter === 'all' ? 'on' : ''}`} onClick={() => setFilter('all')}>All signings</button>
          <button className={`chip ${filter === 'mine' ? 'on' : ''}`} onClick={() => setFilter('mine')}>Signed with you</button>
          <button className={`chip ${filter === 'targets' ? 'on' : ''}`} onClick={() => setFilter('targets')}>Your targets</button>
        </div>
        <div className="signtable">
          <div className="shdr"><span>Recruit</span><span className="c">Pos</span><span className="c">Region</span><span className="c">RT</span><span className="c">Your standing</span><span>Signed with</span><span></span></div>
          {rows.map(r => (
            <div className={`srow ${r.withYou ? 'win' : ''}`} key={r.id}>
              <div className="sname"><span className="nm">{r.name}</span></div>
              <span className="scol spos">{r.pos}</span>
              <span className="scol sregion">{r.region}</span>
              <span className="scol srt"><span className={`v rt-${r.rtTier}`}>{r.rt}</span></span>
              <span className="scol">{standChip(r.stand)}</span>
              <div className="ssigned">
                <span className={`logo ${r.withYou ? 'you' : 'rival'}`}>{abbr(r.signedTeam)}</span>
                <span className={`team ${r.withYou ? 'you' : 'rival'}`}>{r.signedTeam}</span>
              </div>
              <span className={`soutcome ${r.withYou ? 'win' : 'loss'}`}>{r.withYou ? 'Signed' : 'Lost'}</span>
            </div>
          ))}
        </div>
      </React.Fragment>
    );
  }

  /* ---------- app ---------- */
  function ResultsApp() {
    const [view, setView] = useState('weekly');
    const [phaseOpen, setPhaseOpen] = useState(false);
    const [dismissed, setDismissed] = useState(false);
    const poolRef = useRef(null);
    const isWeekly = view === 'weekly';
    const toPool = () => {
      setDismissed(true);
      requestAnimationFrame(() => { const el = poolRef.current; if (el) window.scrollTo({ top: el.getBoundingClientRect().top + window.scrollY - 70, behavior: 'smooth' }); });
    };
    return (
      <div className="hub">
        <div className="hub-head">
          <div className="hub-eyebrow">Recruiting Hub · Deliverable 4 — Results & Signed</div>
          <h1 className="hub-title">Reached without leaving.</h1>
          <p className="hub-lede">Results aren't a separate page — they're states of the hub. During Invite Season, each processed week surfaces a <strong>visit-results panel above the pool</strong>. At Week 36 the pool becomes the <strong>final signings</strong> board. The <strong>Recruit Pool</strong> anchor in the header is always there to drop you back on the full list.</p>
        </div>
        <div className="hub-shell">
          <div className="hub-topbar">
            <span className="hub-hname">Recruiting <b>Hub</b></span>
            <span className="hub-team">{TEAM_NAME}</span>
            <button className="hub-anchor" onClick={toPool}><span className="ic">◗</span> Recruit Pool</button>
          </div>
          <div className="hub-phase">
            <PhaseStrip phase={isWeekly ? 'invite' : 'results'} week={isWeekly ? 22 : 36} inviteSent={2} open={phaseOpen} onToggle={() => setPhaseOpen(o => !o)} />
          </div>
          <div className="res-switch">
            <button className={isWeekly ? 'on' : ''} onClick={() => { setView('weekly'); setDismissed(false); }}>Weekly results · Wk 22</button>
            <button className={!isWeekly ? 'on' : ''} onClick={() => setView('final')}>Final signings · Wk 36</button>
          </div>
          <div style={{ height: 16 }}></div>
          {isWeekly
            ? <React.Fragment>
                {!dismissed && <WeeklyPanel onDismiss={toPool} />}
                <div ref={poolRef} style={{ margin: '0 22px 22px' }}><Pool recruits={pool} variant="B" /></div>
              </React.Fragment>
            : <div ref={poolRef} style={{ margin: '0 22px 22px', border: '1px solid var(--border)', borderRadius: 16, overflow: 'hidden', background: 'var(--panel-2)' }}><FinalSignings /></div>}
        </div>
      </div>
    );
  }

  window.SpineResults = { ResultsApp };
})();
