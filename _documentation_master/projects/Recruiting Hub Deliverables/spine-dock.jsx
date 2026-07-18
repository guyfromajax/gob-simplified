/* Invite Dock (D2) — HubPool (condensed pool + add column) + InviteDock + HubApp.
   window.SpineDock = { HubApp } */
(function () {
  const { useState, useMemo, useRef } = React;
  const { ATTR_KEYS, REGIONS, REGION_NAMES, TEAM_NAME, pool, abbr } = window.SpineData;
  const { LeanObject, analyzeLean } = window.SpineLean;
  const { PhaseStrip } = window.SpinePhase;

  const byId = {};
  pool.forEach(r => (byId[r.id] = r));
  const INVITE_WEEKS = [20, 21, 22, 23, 24, 25, 26];
  const CUR_WEEK = 22;
  const POS_ORDER = ['PG', 'SG', 'SF', 'PF', 'C'];

  const Check = () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><path d="M20 6L9 17l-5-5"/></svg>;
  const Dot = () => <svg viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="12" r="6"/></svg>;
  const Info = () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2"><circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 7.5v.5"/></svg>;
  const Chevron = () => <svg className="region-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M6 9l6 6 6-6"/></svg>;

  /* ---------------- HubPool ---------------- */
  function HubPool({ board, onAdd }) {
    const [search, setSearch] = useState('');
    const [region, setRegion] = useState('all');
    const [mineOnly, setMineOnly] = useState(false);
    const [collapsed, setCollapsed] = useState({});
    const onBoard = useMemo(() => new Set(board), [board]);

    const filtered = pool.filter(r => {
      if (region !== 'all' && r.region !== region) return false;
      if (mineOnly && !r.leansToUser) return false;
      if (search && !r.name.toLowerCase().includes(search.toLowerCase())) return false;
      return true;
    });
    const groups = REGIONS.map(rg => ({ region: rg, recs: filtered.filter(r => r.region === rg).sort((a, b) => b.rt - a.rt) })).filter(g => g.recs.length);

    return (
      <div className="pool-wrap">
        <div className="pool-toolbar">
          <div className="ptb-group"><span className="ptb-label">Find</span>
            <input className="ptb-search" placeholder="Name…" value={search} onChange={e => setSearch(e.target.value)} /></div>
          <div className="ptb-group"><span className="ptb-label">Region</span>
            <button className={`chip ${region === 'all' ? 'is-active' : ''}`} onClick={() => setRegion('all')}>All</button>
            {REGIONS.map(r => <button key={r} className={`chip ${region === r ? 'is-active' : ''}`} onClick={() => setRegion(r)}>{r}</button>)}</div>
          <button className={`chip mine ${mineOnly ? 'is-active' : ''}`} onClick={() => setMineOnly(m => !m)}>◗ Leaning to me</button>
          <span className="ptb-count">Showing <strong>{filtered.length}</strong> of {pool.length}</span>
        </div>
        <div className="pool-scroll" style={{ maxHeight: 560 }}>
          <table className="pool condensed">
            <thead><tr>
              <th className="act"></th>
              <th className="name-col">Name</th>
              <th className="num">Pos</th>
              <th className="num">Yr</th>
              <th className="num">RT</th>
              <th className="lean-col">Leans / Your Standing</th>
            </tr></thead>
            <tbody>
              {groups.map(g => {
                const isCol = collapsed[g.region];
                const mineCount = g.recs.filter(r => r.leansToUser).length;
                return (
                  <React.Fragment key={g.region}>
                    <tr className="region-row"><td colSpan={6}>
                      <button className={`region-bar ${isCol ? 'region-collapsed' : ''}`} onClick={() => setCollapsed(c => ({ ...c, [g.region]: !c[g.region] }))}>
                        <Chevron /><span className="region-letter">{g.region}</span><span className="region-name">{REGION_NAMES[g.region]}</span>
                        <span className="region-stat"><b>{g.recs.length}</b> recruits</span>
                        {mineCount > 0 && <span className="region-mine"><span className="d"></span>{mineCount} leaning to you</span>}
                      </button></td></tr>
                    {!isCol && g.recs.map(r => {
                      const picked = onBoard.has(r.id);
                      const rank = picked ? board.indexOf(r.id) + 1 : null;
                      const rowCls = r.yourRank === 1 ? 'mine' : r.yourRank > 1 ? 'list-mine' : '';
                      return (
                        <tr key={r.id} className={`rec ${rowCls} ${picked ? 'on-board' : ''}`}>
                          <td className="act">
                            {picked
                              ? <button className="pool-rankbadge" title="Remove from board" onClick={() => onAdd(r.id)}>{rank}</button>
                              : <button className="pool-add" title="Add to invite board" onClick={() => onAdd(r.id)}>+</button>}
                          </td>
                          <td className="name-col"><div className="pc-name"><span className="nm">{r.name}</span>
                            {r.newLean && <span className="flag new">New</span>}</div><div className="pc-arch">{r.archetype}</div></td>
                          <td className="pos">{r.pos}</td>
                          <td className="year">{r.year}</td>
                          <td className="rt"><span className={`v rt-${r.rtTier}`}>{r.rt}</span></td>
                          <td className="lean-col"><LeanObject rec={r} variant="B" /></td>
                        </tr>
                      );
                    })}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  /* ---------------- Slot ---------------- */
  function Slot({ id, index, onRemove, dnd }) {
    const r = byId[id];
    const a = analyzeLean(r);
    const stand = a.standing === 'you1'
      ? <span className="islot-stand you1"><Dot />#1</span>
      : a.standing === 'list' ? <span className="islot-stand list">#{a.rank}</span> : null;
    const claimed = (r.leans || []).filter(s => s.team).length; // teams already on his list (0–3)
    return (
      <div
        className={`islot queued ${dnd.dragIndex === index ? 'dragging' : ''} ${dnd.overIndex === index ? 'dragover' : ''}`}
        draggable
        onDragStart={e => dnd.start(e, index)}
        onDragOver={e => dnd.over(e, index)}
        onDrop={e => dnd.drop(e, index)}
        onDragEnd={dnd.end}>
        <span className="islot-rank">{index + 1}</span>
        <span className="islot-grip"><span></span><span></span><span></span><span></span><span></span><span></span></span>
        <div className="islot-body">
          <div className="islot-name"><span className="nm">{r.name}</span>{stand}</div>
          <div className="islot-meta"><span className="islot-pos">{r.pos}</span><span>Rgn {r.region}</span><span className={`islot-rt rt-${r.rtTier}`}>{r.rt} RT</span></div>
        </div>
        <div className="islot-right">
          <span className={`islot-lists c${claimed}`} title={`${claimed} of 3 lean slots claimed`}>
            <span className="dots">{[0, 1, 2].map(i => <i key={i} className={i < claimed ? 'on' : ''}></i>)}</span>
            <span className="cap">{claimed === 0 ? 'Open list' : `${claimed}/3 leans`}</span>
          </span>
        </div>
        <button className="islot-remove" title="Remove" onClick={() => onRemove(id)}>×</button>
      </div>
    );
  }

  /* ---------------- InviteDock ---------------- */
  function InviteDock({ board, onRemove, onReorder, onSave, onClear }) {
    const [dragIndex, setDragIndex] = useState(null);
    const [overIndex, setOverIndex] = useState(null);
    const dnd = {
      dragIndex, overIndex,
      start: (e, i) => { setDragIndex(i); e.dataTransfer.effectAllowed = 'move'; },
      over: (e, i) => { e.preventDefault(); if (i !== overIndex) setOverIndex(i); },
      drop: (e, i) => { e.preventDefault(); if (dragIndex != null && dragIndex !== i) onReorder(dragIndex, i); setDragIndex(null); setOverIndex(null); },
      end: () => { setDragIndex(null); setOverIndex(null); }
    };
    const recs = board.map(id => byId[id]);
    const leaning = recs.filter(r => r.leansToUser).length;
    const posCount = POS_ORDER.map(p => ({ p, n: recs.filter(r => r.pos === p).length }));
    const weeksElapsed = INVITE_WEEKS.filter(w => w < CUR_WEEK).length;
    const invitesLeft = INVITE_WEEKS.length - weeksElapsed;
    const needMore = Math.max(0, INVITE_WEEKS.length - board.length);

    return (
      <aside className="idock">
        <div className="idock-head">
          <div className="idock-titlerow">
            <div className="idock-title"><small>Invite Season · Wk {CUR_WEEK}</small>Invite Board</div>
            <div className="idock-count"><span className="n">{board.length}</span><span className="of">/ 20</span></div>
          </div>
          <div className="idock-weeks">
            {INVITE_WEEKS.map(w => {
              const cls = w < CUR_WEEK ? 'sent' : w === CUR_WEEK ? 'now' : 'future';
              return <div key={w} className={`iweek ${cls}`}><span className="pip"></span><span className="wl">W{w}</span></div>;
            })}
          </div>
          <div className="idock-meta">
            <span className="idock-leaning"><span className="d"></span><b>{leaning}</b> of {board.length} lean to you</span>
            <span className="idock-break">
              {posCount.map(pc => <span key={pc.p} className={`ibreak ${pc.n === 0 ? 'zero' : ''}`}><span className="bn">{pc.n}</span><span className="bl">{pc.p}</span></span>)}
            </span>
          </div>
        </div>

        {board.length === 0
          ? <div className="idock-list"><div className="idock-empty"><div className="t1">No recruits ranked</div><div className="t2">Click <strong>+</strong> on a recruit in the pool to add them. Each week the hub invites your top-ranked recruit.</div></div></div>
          : <div className="idock-list">
              <div className="idock-group-lbl">Priority order · drag to rank</div>
              {board.map((id, i) => <Slot key={id} id={id} index={i} onRemove={onRemove} dnd={dnd} />)}
            </div>}

        {needMore > 0 && <div className="idock-nudge"><Info /><span><b>{invitesLeft} invites left</b> this season — rank {needMore} more so every week has a target.</span></div>}

        <div className="idock-foot">
          <button className="idock-clear" onClick={onClear}>Clear</button>
          <button className="idock-save" onClick={onSave}>Save Board</button>
        </div>
      </aside>
    );
  }

  /* ---------------- HubApp ---------------- */
  function seedBoard() {
    // a varied starter board so standing (#1/on-list) and lean-list fill (0–3) both show range
    const wanted = ['you1', 'you2open', 'you1', 'you3', 'partial', 'allopen', 'single', 'you2', 'others', 'you1'];
    const out = [];
    const used = new Set();
    wanted.forEach(mode => {
      const cand = pool.find(r => r.leanMode === mode && !r.lost && !used.has(r.id));
      if (cand) { out.push(cand.id); used.add(cand.id); }
    });
    return out;
  }

  function Toast({ show }) {
    return (
      <div className={`hub-toast ${show ? 'show' : ''}`}>
        <span className="ti"><Check /></span>
        <div><div className="tt1">Invite Board Saved</div><div className="tt2">The hub runs your invites each week.</div></div>
      </div>
    );
  }

  function HubApp() {
    const [board, setBoard] = useState(seedBoard);
    const [phaseOpen, setPhaseOpen] = useState(false);
    const [toast, setToast] = useState(false);

    const toggle = id => setBoard(b => b.includes(id) ? b.filter(x => x !== id) : b.length >= 20 ? b : [...b, id]);
    const remove = id => setBoard(b => b.filter(x => x !== id));
    const reorder = (from, to) => setBoard(b => {
      const next = [...b]; const [m] = next.splice(from, 1); next.splice(to, 0, m); return next;
    });
    const save = () => { setToast(true); setTimeout(() => setToast(false), 3000); };
    const clear = () => setBoard([]);

    return (
      <div className="hub">
        <div className="hub-head">
          <div className="hub-eyebrow">Recruiting Hub · Deliverable 2 — Invite Dock (Phase 2)</div>
          <h1 className="hub-title">Invite Season, one surface.</h1>
          <p className="hub-lede">The two forked "Recruiting Orders" pages merge into one docked board. Rank up to <strong>20</strong> recruits; the hub sends <strong>one invite per week</strong> (Wks 20–26) to your top available recruit. Find in the pool → click <strong>+</strong> → drag to rank. The pool stays put on the left and condenses to make room — the D1 split, now carrying the action layer.</p>
        </div>
        <div className="hub-shell">
          <div className="hub-topbar">
            <span className="hub-hname">Recruiting <b>Hub</b></span>
            <span className="hub-team">{TEAM_NAME}</span>
            <button className="hub-anchor" onClick={() => { const el = document.querySelector('.hub-poolcol'); if (el) window.scrollTo({ top: el.getBoundingClientRect().top + window.scrollY - 60, behavior: 'smooth' }); }}><span className="ic">◗</span> Recruit Pool</button>
          </div>
          <div className="hub-phase">
            <PhaseStrip phase="invite" week={CUR_WEEK} inviteSent={2} open={phaseOpen} onToggle={() => setPhaseOpen(o => !o)} />
          </div>
          <div className="hub-body">
            <div className="hub-poolcol"><HubPool board={board} onAdd={toggle} /></div>
            <InviteDock board={board} onRemove={remove} onReorder={reorder} onSave={save} onClear={clear} />
          </div>
        </div>
        <Toast show={toast} />
      </div>
    );
  }

  window.SpineDock = { HubApp };
})();
