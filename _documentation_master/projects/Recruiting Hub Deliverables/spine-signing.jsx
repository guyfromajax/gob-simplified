/* Signing Board (D3) — single working pool table + budget/committed rail.
   window.SpineSigning = { SigningApp } */
(function () {
  const { useState, useMemo, useRef } = React;
  const { TEAM_NAME, pool, REGIONS, REGION_NAMES } = window.SpineData;
  const { analyzeLean } = window.SpineLean;
  const { PhaseStrip } = window.SpinePhase;

  const byId = {};
  pool.forEach(r => (byId[r.id] = r));
  const TOTAL = 50, CAP = 20, MAX_PER = 20, CUR_WEEK = 35, PROMISE_W = 18;

  const Dot = () => <svg viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="12" r="6"/></svg>;
  const Warn = () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2"><path d="M12 9v4M12 17v.5"/><path d="M10.3 3.9L2.4 18a2 2 0 0 0 1.7 3h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/></svg>;
  const Check = () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><path d="M20 6L9 17l-5-5"/></svg>;

  function standBadge(r) {
    const a = analyzeLean(r);
    if (a.standing === 'you1') return <span className="brow-stand you1"><Dot />#1</span>;
    if (a.standing === 'list') return <span className="brow-stand list">#{a.rank}</span>;
    return null;
  }
  function signOdds(r, points, promise) {
    const a = analyzeLean(r);
    const base = a.standing === 'you1' ? 48 : a.standing === 'list' ? (a.rank === 2 ? 34 : 26)
      : a.standing === 'locked' ? 8 : a.standing === 'open' ? 20 : a.standing === 'quiet' ? 16 : 14;
    let s = Math.max(4, Math.min(99, Math.round(base + points * 2.2 + (promise ? PROMISE_W : 0))));
    const band = s >= 72 ? { cls: 'o-lock', lab: 'Strong' } : s >= 48 ? { cls: 'o-even', lab: 'In the Mix' }
      : s >= 26 ? { cls: 'o-slim', lab: 'Slim' } : { cls: 'o-long', lab: 'Long shot' };
    return { pct: s, ...band };
  }

  /* ---------------- pool row ---------------- */
  function PRow({ r, a, remaining, flash, onStep, onPromise }) {
    const committed = a.points > 0 || a.promise;
    const o = signOdds(r, a.points, a.promise);
    const claimed = (r.leans || []).filter(s => s.team).length;
    const canPlus = remaining > 0 && a.points < MAX_PER;
    return (
      <div className={`prow ${committed ? 'funded' : ''} ${flash ? 'flash' : ''}`} data-id={r.id}>
        <div className="prow-name">
          <div className="nm"><span className="txt">{r.name}</span>{standBadge(r)}</div>
          <div className="prow-arch">{r.archetype}</div>
        </div>
        <span className="prow-pos">{r.pos}</span>
        <span className="prow-region">{r.region}</span>
        <span className="prow-rt"><span className={`v rt-${r.rtTier}`}>{r.rt}</span></span>
        <span className="prow-leans" title={`${claimed} of 3 leans`}>{[0, 1, 2].map(i => <i key={i} className={i < claimed ? 'on' : ''}></i>)}</span>
        <div>
          <div className="stepper">
            <button disabled={a.points === 0} onClick={() => onStep(r.id, -1)}>−</button>
            <span className={`val ${a.points === 0 ? 'zero' : ''}`}>{a.points}</span>
            <button disabled={!canPlus} onClick={() => onStep(r.id, 1)}>+</button>
            <span className="stepper-pts">pts</span>
          </div>
        </div>
        <div className={`promise-cell ${a.promise ? 'set' : ''}`}>
          <button className="promise-toggle" title="Promise playing time" onClick={() => onPromise(r.id)}><span className="box"><Check /></span>{a.promise ? 'Binding' : 'Promise'}</button>
        </div>
        <div className={`odds ${o.cls}`}>
          <div className="odds-top"><span className="odds-lab">{o.lab}</span><span className="odds-pct">{o.pct}%</span></div>
          <div className="odds-bar"><div className="odds-fill" style={{ width: o.pct + '%' }}></div></div>
        </div>
      </div>
    );
  }

  function Toast({ show }) {
    return (
      <div className={`hub-toast ${show ? 'show' : ''}`}>
        <span className="ti"><Check /></span>
        <div><div className="tt1">Orders Submitted</div><div className="tt2">Points spent and promises are now binding.</div></div>
      </div>
    );
  }

  /* ---------------- app ---------------- */
  function seedAlloc() {
    const mine = pool.filter(r => r.leansToUser && !r.lost).sort((a, b) => b.rt - a.rt);
    const out = {};
    if (mine[0]) out[mine[0].id] = { points: 12, promise: true };
    if (mine[1]) out[mine[1].id] = { points: 9, promise: true };
    if (mine[2]) out[mine[2].id] = { points: 6, promise: false };
    return out;
  }
  const EMPTY = { points: 0, promise: false };

  function SigningApp() {
    const [alloc, setAlloc] = useState(seedAlloc);
    const [tab, setTab] = useState('mine');
    const [q, setQ] = useState('');
    const [region, setRegion] = useState('all');
    const [phaseOpen, setPhaseOpen] = useState(false);
    const [toast, setToast] = useState(false);
    const [flash, setFlash] = useState(null);
    const rowsRef = useRef(null);

    const committedIds = useMemo(() => Object.keys(alloc).filter(id => alloc[id].points > 0 || alloc[id].promise), [alloc]);
    const spent = committedIds.reduce((s, id) => s + alloc[id].points, 0);
    const remaining = TOTAL - spent;
    const promises = committedIds.filter(id => alloc[id].promise).length;

    const step = (id, d) => setAlloc(prev => {
      const cur = prev[id] || EMPTY;
      const nv = cur.points + d;
      if (nv < 0 || nv > MAX_PER) return prev;
      if (d > 0 && remaining <= 0) return prev;
      const next = { ...prev, [id]: { ...cur, points: nv } };
      if (next[id].points === 0 && !next[id].promise) delete next[id];
      return next;
    });
    const togglePromise = id => setAlloc(prev => {
      const cur = prev[id] || EMPTY;
      const next = { ...prev, [id]: { ...cur, promise: !cur.promise } };
      if (next[id].points === 0 && !next[id].promise) delete next[id];
      return next;
    });
    const removeCommit = id => setAlloc(prev => { const n = { ...prev }; delete n[id]; return n; });
    const submit = () => { setToast(true); setTimeout(() => setToast(false), 3200); };

    const jump = id => {
      setTab(byId[id].leansToUser ? tab : 'all');
      requestAnimationFrame(() => {
        const cont = rowsRef.current;
        const row = cont && cont.querySelector(`[data-id="${id}"]`);
        if (row) cont.scrollTop = row.offsetTop - 8;
        setFlash(id); setTimeout(() => setFlash(null), 1100);
      });
    };

    const list = pool.filter(r => {
      if (r.lost) return false;
      if (tab === 'mine' && !r.leansToUser) return false;
      if (region !== 'all' && r.region !== region) return false;
      if (q && !r.name.toLowerCase().includes(q.toLowerCase())) return false;
      return true;
    }).sort((a, b) => b.rt - a.rt);

    const committed = committedIds.map(id => ({ r: byId[id], a: alloc[id], o: signOdds(byId[id], alloc[id].points, alloc[id].promise) }))
      .sort((x, y) => y.a.points - x.a.points || y.o.pct - x.o.pct);

    return (
      <div className="hub">
        <div className="hub-head">
          <div className="hub-eyebrow">Recruiting Hub · Deliverable 3 — Signing Board (Phase 3)</div>
          <h1 className="hub-title">Signing Day — spend it all.</h1>
          <p className="hub-lede">Week 35, the payoff. Work the pool directly: spend a <strong>50-point budget</strong> and make <strong>binding Playing Time promises</strong> right on the row. Recruits <strong>leaning to you</strong> are pre-loaded and top targets pre-funded — adjust from there. The rail keeps a running tally of everyone you've committed points to. One surface, back on the spine's pool-left / dock-right frame.</p>
        </div>
        <div className="hub-shell">
          <div className="hub-topbar">
            <span className="hub-hname">Recruiting <b>Hub</b></span>
            <span className="hub-team">{TEAM_NAME}</span>
            <button className="hub-anchor" onClick={() => { const el = document.querySelector('.spool'); if (el) window.scrollTo({ top: el.getBoundingClientRect().top + window.scrollY - 60, behavior: 'smooth' }); }}><span className="ic">◗</span> Recruit Pool</button>
          </div>
          <div className="hub-phase">
            <PhaseStrip phase="day" week={CUR_WEEK} points={remaining} open={phaseOpen} onToggle={() => setPhaseOpen(o => !o)} />
          </div>
          <div className="hub-body-sign">
            <div className="spool">
              <div className="spool-head">
                <div className="spool-title">Recruit Pool</div>
                <div className="spool-tools">
                  <div className="spool-tabs">
                    <button className={`spool-tab ${tab === 'mine' ? 'on' : ''}`} onClick={() => setTab('mine')}>Leaning to you</button>
                    <button className={`spool-tab ${tab === 'all' ? 'on' : ''}`} onClick={() => setTab('all')}>All</button>
                  </div>
                  <select className="spool-region" value={region} onChange={e => setRegion(e.target.value)}>
                    <option value="all">All regions</option>
                    {REGIONS.map(rg => <option key={rg} value={rg}>{rg} · {REGION_NAMES[rg]}</option>)}
                  </select>
                  <input className="spool-search" placeholder="Search name…" value={q} onChange={e => setQ(e.target.value)} />
                </div>
              </div>
              <div className="spool-colhdr">
                <span>Recruit</span><span className="c-num">Pos</span><span className="c-num">Region</span><span className="c-num">RT</span>
                <span>Leans</span><span>Points</span><span>Playing Time</span><span>Sign odds</span>
              </div>
              <div className="spool-rows" ref={rowsRef}>
                {list.map(r => <PRow key={r.id} r={r} a={alloc[r.id] || EMPTY} remaining={remaining} flash={flash === r.id} onStep={step} onPromise={togglePromise} />)}
              </div>
            </div>

            <aside className="rail">
              <div className="rail-head">
                <div className="rail-title">Your Orders</div>
                <div className="budget-nums"><span className={`rem ${remaining < 0 ? 'over' : ''}`}>{remaining}</span><span className="of">/ {TOTAL}</span></div>
                <div className="budget-caprow">
                  <span className="budget-cap">Points to spend</span>
                  <span className="budget-promises"><b>{promises}</b> {promises === 1 ? 'promise' : 'promises'}</span>
                </div>
                <div className="budget-bar"><div className={`budget-fill ${remaining < 0 ? 'over' : ''}`} style={{ width: Math.min(100, (spent / TOTAL) * 100) + '%' }}></div></div>
              </div>
              {committed.length === 0
                ? <div className="rail-list"><div className="rail-empty"><div className="t1">Nothing committed</div><div className="t2">Add points to a recruit in the pool and they'll appear here.</div></div></div>
                : <div className="rail-list">
                    {committed.map(({ r, a, o }) => (
                      <div key={r.id} className="citem" onClick={() => jump(r.id)} title="Jump to recruit">
                        <div className="citem-body">
                          <div className="citem-name"><span className="nm">{r.name}</span>{a.promise && <span className="pmk">· PT</span>}</div>
                          <div className="citem-meta"><span className="citem-pts">{a.points} pts</span><span>{r.pos} · {r.rt} RT</span><span className={`citem-odds ${o.cls.replace('o-', 'rt-')}`} style={{ color: 'var(--muted)' }}>{o.pct}%</span></div>
                        </div>
                        <button className="citem-x" title="Remove" onClick={e => { e.stopPropagation(); removeCommit(r.id); }}>×</button>
                      </div>
                    ))}
                  </div>}
              <div className="rail-foot">
                <div className="rail-note">{promises > 0
                  ? <><Warn /><span><b>{promises} binding {promises === 1 ? 'promise' : 'promises'}</b> — honor the playing time or your program's standing suffers.</span></>
                  : <span>Promises are <b>binding</b> — set one only if you'll honor the minutes.</span>}</div>
                <button className="rail-submit" onClick={submit}>Submit Orders</button>
              </div>
            </aside>
          </div>
        </div>
        <Toast show={toast} />
      </div>
    );
  }

  window.SpineSigning = { SigningApp };
})();
