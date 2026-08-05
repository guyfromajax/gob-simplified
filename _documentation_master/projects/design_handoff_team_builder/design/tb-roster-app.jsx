/* GOB Team Builder — Chapter III · The Floor
   Board + inspector. Budget totals are aggregated client-side (allowed);
   position grades are requested on release and rendered from the response. */
const { useState, useMemo, useRef, useCallback, useEffect } = React;
const R = window.GOBRoster;

const rosterStyles = {
  toneOf: (t) => R.TONES[Math.max(0, Math.min(5, t - 1))]
};
const initials = (name) => (name || '').trim().split(/\s+/).map(w => w[0] || '').join('').slice(0, 3) || '—';
const firstOf = (name) => (name || '').trim().split(/\s+/)[0] || '';
const lastOf = (name) => (name || '').trim().split(/\s+/).slice(1).join(' ');

/* ---------- small parts ---------- */

function Portrait({ p, size }) {
  const bg = rosterStyles.toneOf(p.tone);
  return (
    <div className={size === 'lg' ? 'pt-lg' : 'pt'} style={{ background: bg }}>
      <i></i><b>{initials(p.name)}</b>
    </div>
  );
}

function Signature({ attrs }) {
  return (
    <div className="sig">
      {R.ATTRS.map(t => {
        const v = attrs[t.code];
        return <i key={t.code} title={t.code + ' ' + v}
          style={{ height: Math.max(2, Math.round(v / 99 * 20)) + 'px', background: R.scaleColor(v) }} />;
      })}
    </div>
  );
}

function Meter({ k, rule, used, cap, unit, exact, info }) {
  const diff = used - cap;
  const pct = Math.min(100, used / cap * 100);
  if (info) return (
    <div className="meter">
      <div className="mt-top"><div className="mt-k">{k}</div><div className="mt-rule">reference</div></div>
      <div className="mt-v">{used}<span>/ {cap} inherited</span></div>
      <div className="mt-track"><div className="mt-fill" style={{ width: pct + '%', background: 'rgba(255,255,255,.4)' }} /></div>
      <div className="mt-note mute">{diff === 0 ? 'unchanged' : (diff > 0 ? '+' + diff : diff) + (unit || '') + ' vs inherited'} — no cap</div>
    </div>
  );
  const over = exact ? used !== cap : used > cap;
  const color = over ? '#ff6d6d' : (diff === 0 ? '#34EC27' : 'rgba(255,255,255,.42)');
  let note;
  if (exact) note = diff === 0
    ? <span className="ok">Exact match — spent</span>
    : <span className="bad">{diff > 0 ? '+' + diff : diff} — must land on {cap}</span>;
  else note = diff === 0
    ? <span className="ok">At the cap</span>
    : (diff < 0 ? <span className="mute">{Math.abs(diff)}{unit} under — nothing to do</span>
                : <span className="bad">{diff}{unit} over the cap</span>);
  return (
    <div className={'meter' + (over ? ' bad' : (diff === 0 && exact ? ' exact' : ''))}>
      <div className="mt-top"><div className="mt-k">{k}</div><div className="mt-rule">{rule}</div></div>
      <div className="mt-v">{used}<span>/ {cap}</span></div>
      <div className="mt-track"><div className="mt-fill" style={{ width: pct + '%', background: color }} /></div>
      <div className="mt-note">{note}</div>
    </div>
  );
}

/* ---------- board ---------- */

function Board({ players, sel, onSelect, grades, pools, view, setView, mode }) {
  const rows = (list, offset) => list.map((p, i) => {
    const idx = offset + i;
    const g = grades[p.id];
    const pool = pools[p.id];
    const bad = mode === 'capped' && pool !== 0;
    const edited = R.ATTRS.some(t => p.attrs[t.code] !== p.base[t.code]) || p.ht !== p.baseHt || p.cls !== p.baseCls;
    return (
      <div key={p.id} className={'bd-row' + (idx === sel ? ' sel' : '') + (bad ? ' bad' : '')}
        onClick={() => onSelect(idx)}>
        <div className="bd-num">{p.n}</div>
        <Portrait p={p} />
        <div className="bd-name">{p.name}{p.wo && <em>WO</em>}
          <span className={'cls' + (p.cls !== p.baseCls ? ' chg' : '')}>{p.cls}</span></div>
        <div className={'bd-ht' + (p.ht !== p.baseHt ? ' chg' : '')}>{R.feetInches(p.ht)}</div>
        <div><span className="pos" style={{ background: R.POS_COLOR[p.pos] }}>{p.pos}</span></div>
        <div className={'bd-grade' + (g.pending ? ' pending' : '')}>{g.pending ? '·  ·  ·' : g.v[p.pos]}</div>
        <Signature attrs={p.attrs} />
        <div>{bad ? <span className="mk bad" title="Attribute points unspent" />
          : edited ? <span className="mk edit" title="Changed from inherited" /> : null}</div>
      </div>
    );
  });

  const head = (
    <div className="pane-hd">
      <h2>Roster</h2>
      <div className="sp" />
      <div className="seg">
        <button className={view === 'sig' ? 'on' : ''} onClick={() => setView('sig')}>Signature</button>
        <button className={view === 'grid' ? 'on' : ''} onClick={() => setView('grid')}>Full grid</button>
      </div>
    </div>
  );

  if (view === 'grid') {
    return (
      <div className="pane">
        {head}
        <div style={{ overflowX: 'auto' }}>
          <table className="gr">
            <thead><tr>
              <th className="l">Player</th><th>Cl</th><th>Ht</th><th>Pos</th><th title="Position rating at the listed slot">RT</th>
              {R.ATTRS.map(t => <th key={t.code}>{t.code}</th>)}<th>Tot</th>
            </tr></thead>
            <tbody>
              {players.map((p, i) => (
                <tr key={p.id} className={i === sel ? 'sel' : ''}
                  onClick={() => { onSelect(i); setView('sig'); }} title="Edit this player">
                  <td className="l nm">{p.n} · {p.name}</td>
                  <td>{p.cls}</td><td>{R.feetInches(p.ht)}</td>
                  <td><span className="pos" style={{ background: R.POS_COLOR[p.pos] }}>{p.pos}</span></td>
                  <td style={{ fontFamily: 'var(--disp)', fontSize: 15, color: '#fff' }}>
                    {grades[p.id].pending ? '···' : grades[p.id].v[p.pos]}</td>
                  {R.ATTRS.map(t => (
                    <td key={t.code}><span className="av" style={{ background: R.scaleColor(p.attrs[t.code]) }}>
                      {p.attrs[t.code]}</span></td>
                  ))}
                  <td style={{ fontFamily: 'var(--disp)', fontSize: 15, color: pools[p.id] === 0 ? '#fff' : '#ff6d6d' }}>
                    {R.total(p.attrs)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  return (
    <div className="pane">
      {head}
      <div className="bd-head">
        <div style={{ textAlign: 'right' }}>#</div><div></div><div>Player</div><div>Ht</div>
        <div>Pos</div><div style={{ textAlign: 'center' }} title="Position rating at the listed slot">RT</div><div>Signature · SC→FT</div><div></div>
      </div>
      {rows(players.slice(0, 12), 0)}
      <div className="bd-split">Walk-ons — 3</div>
      {rows(players.slice(12), 12)}
      <div className="bd-foot">
        <span><i style={{ background: '#F79420' }} />Changed from inherited</span>
      </div>
    </div>
  );
}

/* ---------- inspector ---------- */

function Attr({ t, value, base, onInput, onCommit }) {
  const moved = value !== base;
  const d = value - base;
  return (
    <div className={'attr' + (moved ? ' moved' : '')}>
      <div className="code" title={t.name}>{t.code}</div>
      <div className="trk">
        <div className="rail"><div className="fill" style={{ width: (value / 99 * 100) + '%', background: R.scaleColor(value) }} /></div>
        <div className="tick" style={{ left: (base / 99 * 100) + '%' }} title={'Inherited ' + base} />
        <input type="range" min="5" max="99" value={value}
          onChange={e => onInput(t.code, +e.target.value)}
          onPointerUp={onCommit} onKeyUp={onCommit} />
      </div>
      <div className="num">{value}</div>
      <div className="dlt" style={{ color: moved ? 'var(--org)' : 'var(--tx3)' }}>{moved ? (d > 0 ? '+' + d : d) : '—'}</div>
    </div>
  );
}

function Inspector({ p, mode, pool, heightUsed, heightBudget, classUsed, classBudget, legal, reason, jump,
  grades, setAttr, commit, setClass, setHeight, setFirst, setLast, setNumber, openPicker, randomize, resetPlayer }) {
  const g = grades[p.id];
  const htDiff = heightUsed - heightBudget;
  const clDiff = classUsed - classBudget;
  const capped = mode === 'capped';
  const cats = [];
  R.ATTRS.forEach(t => {
    if (!cats.length || cats[cats.length - 1].cat !== t.cat) cats.push({ cat: t.cat, items: [t] });
    else cats[cats.length - 1].items.push(t);
  });

  return (
    <div className="pane insp">
      <div className="insp-hd">
        <div>
          <div className="pt-lg" style={{ background: rosterStyles.toneOf(p.tone) }} onClick={openPicker}>
            <i></i><b>{initials(p.name)}</b>
            <div className="pt-ov">
              <button onClick={e => { e.stopPropagation(); openPicker(); }}>Choose</button>
              <button onClick={e => { e.stopPropagation(); randomize(); }}>Randomize</button>
            </div>
          </div>
          <div className="pt-cap">auto-assigned · click to override</div>
        </div>
        <div className="ih">
          <div className="ih-top">
            <div className="fld num"><label>Jersey #</label>
              <input value={p.n} inputMode="numeric" maxLength="2" onChange={e => setNumber(e.target.value)} /></div>
            <div className="fld nm"><label>First name</label>
              <input value={firstOf(p.name)} maxLength="16"
                onChange={e => setFirst(e.target.value)} /></div>
            <div className="fld nm"><label>Last name</label>
              <input value={lastOf(p.name)} maxLength="18"
                onChange={e => setLast(e.target.value)} /></div>
          </div>
          <div className="grades">
            {R.POS.map(pos => (
              <div key={pos} className={'gcard' + (g.pending ? ' pending' : '')}>
                <span className="gp" style={{ background: R.POS_COLOR[pos] }}>{pos}</span>
                <span className="gv">{g.pending ? '··' : g.v[pos]}</span>
              </div>
            ))}
          </div>
          {g.pending && <div className="srv">recomputing…</div>}
        </div>
      </div>

      <div className="insp-body">
        <div className="col-l">
          <div>
            <div className="blk-k"><span>Year</span></div>
            <div className="cseg">
              {R.CLASSES.map(c => (
                <button key={c} className={(p.cls === c ? 'on' : '') + (c === p.baseCls ? ' base' : '')}
                  onClick={() => setClass(c)} title={c === p.baseCls ? 'Inherited' : ''}>{c}</button>
              ))}
            </div>
            <div className={'tally' + (capped ? (clDiff === 0 ? ' ok' : ' bad') : '')}>
              <span>Team</span><b>{classUsed} / {classBudget}</b>
              <em>{capped
                ? (clDiff === 0 ? 'exact' : (clDiff > 0 ? '+' + clDiff + ' over' : clDiff + ' short'))
                : 'inherited'}</em>
            </div>
          </div>

          <div>
            <div className="blk-k"><span>Height</span><em>{R.feetInches(66)} – {R.feetInches(84)}</em></div>
            <div className="step">
              <button onClick={() => setHeight(p.ht - 1)} disabled={p.ht <= 66}>–</button>
              <div className="val">{R.feetInches(p.ht)}<em>{p.ht !== p.baseHt
                ? R.feetInches(p.baseHt) + ' inherited'
                : 'inherited'}</em></div>
              <button onClick={() => setHeight(p.ht + 1)} disabled={p.ht >= 84}>+</button>
            </div>
            {capped ? (
              <>
                <div className="htbar"><div style={{
                  height: '100%', borderRadius: 2,
                  width: Math.min(100, heightUsed / heightBudget * 100) + '%',
                  background: htDiff > 0 ? '#ff6d6d' : (htDiff === 0 ? '#34EC27' : 'rgba(255,255,255,.42)')
                }} /></div>
                <div className={'tally' + (htDiff > 0 ? ' bad' : (htDiff === 0 ? ' ok' : ''))}>
                  <span>Team</span><b>{heightUsed} / {heightBudget}″</b>
                  <em>{htDiff > 0 ? '+' + htDiff + '″ over' : (htDiff === 0 ? 'at the cap' : Math.abs(htDiff) + '″ under')}</em>
                </div>
              </>
            ) : (
              <div className="tally">
                <span>Team</span><b>{heightUsed} / {heightBudget}″</b><em>inherited</em>
              </div>
            )}
            <div className="wt">Weight will be re-calibrated at franchise initialization based on the player's height and attributes.</div>
          </div>

          <div style={{ marginTop: 'auto' }}>
            <button className="btn ghost sm" style={{ width: '100%' }} onClick={resetPlayer}>Revert to inherited</button>
          </div>
        </div>

        <div className="col-r">
          {capped ? (
            <div className={'pool' + (pool === 0 ? ' ok' : ' bad')}>
              <div className="pool-l">
                <div className="k">Attribute points — this player</div>
                <div className="v">{R.total(p.attrs)}<span> / {p.budget}</span></div>
              </div>
              <div className="pool-r">
                <div className="n" style={{ color: pool === 0 ? 'var(--grn)' : 'var(--red)' }}>
                  {pool === 0 ? '0' : (pool > 0 ? '+' + pool : pool)}</div>
                <div className="c">{pool === 0 ? 'all placed' : (pool > 0 ? 'left to place' : 'over budget')}</div>
              </div>
            </div>
          ) : (
            <div className="pool"><div className="pool-l">
              <div className="k">Attribute points — this player</div>
              <div className="v">{R.total(p.attrs)}<span> / {p.budget} inherited</span></div>
            </div><div className="pool-r">
              <div className="n" style={{ color: R.total(p.attrs) === p.budget ? 'var(--tx2)' : 'var(--org)' }}>
                {R.total(p.attrs) === p.budget ? '—' : (R.total(p.attrs) > p.budget ? '+' + (R.total(p.attrs) - p.budget) : R.total(p.attrs) - p.budget)}</div>
              <div className="c">vs inherited</div>
            </div></div>
          )}

          <div className="attrcols">
            {[cats.slice(0, 3), cats.slice(3)].map((col, ci) => (
              <div key={ci}>
                {col.map(group => (
                  <div key={group.cat}>
                    <div className="catrow">
                      <span style={{ color: R.CATS[group.cat].color }}>{R.CATS[group.cat].label}</span><i />
                    </div>
                    {group.items.map(t => (
                      <Attr key={t.code} t={t} value={p.attrs[t.code]} base={p.base[t.code]}
                        onInput={setAttr} onCommit={commit} />
                    ))}
                  </div>
                ))}
              </div>
            ))}
          </div>

          <div className="attr-foot">
            <div className="hint">Ticks mark inherited values.{capped ? ' Points never move between players.' : ''}</div>
          </div>
        </div>
      </div>

      <div className="alegend">
        {R.ATTRS.map(t => (
          <span key={t.code}>
            <b style={{ color: R.CATS[t.cat].color }}>{t.code}</b><i>{t.name}</i>
          </span>
        ))}
      </div>
    </div>
  );
}

/* ---------- portrait picker ---------- */

function Picker({ p, onPick, onClose }) {
  const [tone, setTone] = useState(p.tone);
  const [build, setBuild] = useState(p.build);
  const scored = useMemo(() => R.POOL.map(i => ({
    ...i, exact: i.tone === tone && i.build === build,
    score: Math.abs(i.tone - tone) * 2 + (i.build === build ? 0 : 3)
  })).sort((a, b) => a.score - b.score), [tone, build]);
  const exact = scored.filter(s => s.exact).length;
  return (
    <div className="ov" onClick={onClose}>
      <div className="mdl wide" onClick={e => e.stopPropagation()}>
        <div className="mdl-acc" />
        <div className="pk-hd">
          <h3>Portrait</h3>
          <div>
            <div className="mt-k" style={{ marginBottom: 5 }}>Tone</div>
            <div className="tones">
              {R.TONES.map((c, i) => (
                <button key={i} className={tone === i + 1 ? 'on' : ''} style={{ background: c }}
                  onClick={() => setTone(i + 1)} aria-label={'Tone ' + (i + 1)} />
              ))}
            </div>
          </div>
          <div>
            <div className="mt-k" style={{ marginBottom: 5 }}>Build</div>
            <div className="builds">
              {R.BUILDS.map(b => (
                <button key={b} className={build === b ? 'on' : ''} onClick={() => setBuild(b)}>{b}</button>
              ))}
            </div>
          </div>
        </div>
        <div className="pk-note">
          <b>{exact} exact match{exact === 1 ? '' : 'es'}</b> in a pool of 450 — best matches first, the rest dimmed but still selectable.
          Nothing is removed, so the grid never empties.
        </div>
        <div className="pk-grid">
          {scored.map(i => (
            <div key={i.id} className={'pk-i' + (i.exact ? '' : ' off') + (i.id === p.portraitId ? ' on' : '')}
              style={{ background: rosterStyles.toneOf(i.tone) }}
              onClick={() => onPick(i)}>
              <i></i><em>{i.build.toLowerCase()}</em>
            </div>
          ))}
        </div>
        <div className="pk-ft">
          <div className="hint">Best matches first. Every player already has a portrait — this is an override.</div>
          <button className="btn ghost sm" onClick={onClose}>Done</button>
        </div>
      </div>
    </div>
  );
}

/* ---------- app ---------- */

function App() {
  const [players, setPlayers] = useState(() => R.PLAYERS.map(p => ({ ...p, portraitId: p.id })));
  const [sel, setSel] = useState(0);
  const [mode, setMode] = useState('capped');
  const [view, setView] = useState('sig');
  const [picker, setPicker] = useState(false);
  const [modeModal, setModeModal] = useState(false);
  const [toast, setToast] = useState(null);
  const [grades, setGrades] = useState(() => {
    const g = {};
    R.PLAYERS.forEach(p => { g[p.id] = { pending: false, v: R.gradesFor(p.attrs, p.ht) }; });
    return g;
  });
  const timers = useRef({});
  const [zMode, setZMode] = useState(() => localStorage.getItem('tbRosterZoom') || 'fit');
  const [fitZ, setFitZ] = useState(1);
  useEffect(() => {
    const fit = () => setFitZ(Math.min(1, window.innerWidth / 1440));
    fit(); window.addEventListener('resize', fit);
    return () => window.removeEventListener('resize', fit);
  }, []);
  useEffect(() => { localStorage.setItem('tbRosterZoom', zMode); }, [zMode]);
  const z = zMode === 'fit' ? fitZ : Number(zMode);

  const p = players[sel];
  const capped = mode === 'capped';

  const pools = useMemo(() => {
    const o = {};
    players.forEach(pl => { o[pl.id] = pl.budget - R.total(pl.attrs); });
    return o;
  }, [players]);
  const heightUsed = useMemo(() => players.reduce((s, pl) => s + pl.ht, 0), [players]);
  const classUsed = useMemo(() => players.reduce((s, pl) => s + R.CLASS_RANK[pl.cls], 0), [players]);
  const changed = useMemo(() => players.filter(pl =>
    pl.ht !== pl.baseHt || pl.cls !== pl.baseCls || R.ATTRS.some(t => pl.attrs[t.code] !== pl.base[t.code])
  ).length, [players]);

  /* server round trip for position ratings — fired on control release */
  const request = useCallback((id) => {
    setGrades(g => ({ ...g, [id]: { ...g[id], pending: true } }));
    clearTimeout(timers.current[id]);
    timers.current[id] = setTimeout(() => {
      setPlayers(cur => {
        const pl = cur.find(x => x.id === id);
        setGrades(g => ({ ...g, [id]: { pending: false, v: R.gradesFor(pl.attrs, pl.ht) } }));
        return cur;
      });
    }, 520);
  }, []);
  useEffect(() => () => Object.values(timers.current).forEach(clearTimeout), []);

  const patch = (fn) => setPlayers(cur => cur.map((pl, i) => (i === sel ? fn(pl) : pl)));
  const setAttr = (code, v) => patch(pl => ({ ...pl, attrs: { ...pl.attrs, [code]: v } }));
  const commit = () => request(p.id);
  const setClass = (c) => { patch(pl => ({ ...pl, cls: c })); request(p.id); };
  const setHeight = (h) => { if (h < 66 || h > 84) return; patch(pl => ({ ...pl, ht: h })); request(p.id); };
  const setFirst = (v) => patch(pl => ({ ...pl, name: (v + ' ' + lastOf(pl.name)).trim() }));
  const setLast = (v) => patch(pl => ({ ...pl, name: (firstOf(pl.name) + ' ' + v).trim() }));
  const setNumber = (v) => {
    const d = String(v).replace(/[^0-9]/g, '').slice(0, 2);
    patch(pl => ({ ...pl, n: d === '' ? '' : String(Number(d)) }));
  };
  const randomize = () => {
    const pick = R.POOL[Math.floor(Math.random() * R.POOL.length)];
    patch(pl => ({ ...pl, tone: pick.tone, build: pick.build, portraitId: pick.id }));
  };
  const resetPlayer = () => { patch(pl => ({ ...pl, attrs: { ...pl.base }, ht: pl.baseHt, cls: pl.baseCls })); request(p.id); };

  const offenders = capped ? players.filter(pl => pools[pl.id] !== 0) : [];
  const classOff = capped && classUsed !== R.CLASS_BUDGET;
  const heightOff = capped && heightUsed > R.HEIGHT_BUDGET;
  const legal = !offenders.length && !classOff && !heightOff;

  let reason = null, jump = null;
  if (offenders.length) {
    reason = <><b>{offenders.length} player{offenders.length > 1 ? 's' : ''}</b> {offenders.length > 1 ? 'have' : 'has'} attribute points unplaced.</>;
    jump = () => { setView('sig'); setSel(players.indexOf(offenders[0])); };
  } else if (classOff) {
    reason = <>Class budget is <b>{classUsed > R.CLASS_BUDGET ? '+' + (classUsed - R.CLASS_BUDGET) : classUsed - R.CLASS_BUDGET}</b> against {R.CLASS_BUDGET}. It has to match exactly.</>;
  } else if (heightOff) {
    reason = <>Height budget is <b>{heightUsed - R.HEIGHT_BUDGET}″ over</b> the inherited cap.</>;
  }

  return (
    <>
    <div className="vbar">
      <span>Prototype view — not part of the design</span>
      <div className="seg">
        {[['fit', 'Fit'], ['1', '100%'], ['1.25', '125%'], ['1.5', '150%'], ['2', '200%']].map(([v, l]) => (
          <button key={v} className={zMode === v ? 'on' : ''} onClick={() => setZMode(v)}>{l}</button>
        ))}
      </div>
    </div>
    <div className="shell" style={{ zoom: z }} data-screen-label="Chapter III — The Floor (roster)">
      {/* program state strip */}
      <div className="statebar">
        <div className="sb-cell chap"><div className="sb-k">Chapter</div><div className="sb-v">Ⅲ · The Floor<small>Claim · Found · <b style={{ color: '#fff' }}>The Floor</b></small></div></div>
        <div className="sb-cell link"><div className="sb-k">Replacing</div><div className="sb-v">Rainier Central<small>Conference 14 · Region G</small></div></div>
        <div className="sb-cell link"><div className="sb-k">Program</div><div className="sb-v">Cascade Valley<small>CVU · Founded on Apply</small></div></div>
        <div className="sb-cell link" onClick={() => setModeModal(true)}>
          <div className="sb-k">Build mode</div>
          <div className="sb-v"><span className={'dot ' + (capped ? 'd-warn' : 'd-bad')} />{capped ? 'Capped' : 'Uncapped'}
            <small>{capped ? 'eligible for online play' : 'not eligible for online play'}</small></div>
        </div>
        <div className="sb-cell">
          <div className="sb-k">Roster</div>
          <div className="sb-v"><span className={'dot ' + (legal ? 'd-ok' : 'd-bad')} />{legal ? 'Ready' : 'Not legal'}
            <small>{changed === 0 ? 'inherited, unchanged' : changed + ' player' + (changed > 1 ? 's' : '') + ' changed'}</small></div>
        </div>
        <div className="sb-cell act">
          <span className="sb-rev">Editable until you establish the program</span>
          <div className="act-stack">
            <button className="btn" disabled={!legal}
              onClick={() => setToast({ t: 'Program established', s: 'Cascade Valley takes Rainier Central\u2019s place in Conference 14.' })}>
              Establish Cascade Valley
            </button>
          </div>
        </div>
      </div>

      {/* team budgets — the two team-scope budgets live here; the per-player one lives in the inspector */}
      <div className="budgetbar">
        <div className="bb-lede">
          <h1>Edit Your Roster</h1>
        </div>
        {capped ? <>
          <Meter k="Height — team" rule="under ok" used={heightUsed} cap={R.HEIGHT_BUDGET} unit="″" />
          <Meter k="Class — team" rule="exact" used={classUsed} cap={R.CLASS_BUDGET} exact />
        </> : <>
          <Meter k="Height — team" used={heightUsed} cap={R.HEIGHT_BUDGET} unit="″" info />
          <Meter k="Class — team" used={classUsed} cap={R.CLASS_BUDGET} info />
        </>}
        {capped && (
          <div className={'verdict' + (legal ? ' ok' : ' bad')}>
            <div className="vd-k">{legal ? 'Legal' : 'Not legal'}</div>
            <div className="vd-t">{legal ? 'All three budgets satisfied.' : reason}</div>
            {!legal && jump && <button className="jump" onClick={jump}>Take me there</button>}
          </div>
        )}
        {!capped && (
          <div className="alert warn">
            <span className="al-k">Uncapped</span>
            <div className="al-t">No online play, ranked or otherwise. <b>Written permanently when the program is established.</b></div>
          </div>
        )}
      </div>

      <div className={'work' + (view === 'grid' ? ' wide' : '')}>
        <Board players={players} sel={sel} onSelect={setSel} grades={grades} pools={pools}
          view={view} setView={setView} mode={mode} />
        {view === 'sig' && (
          <Inspector p={p} mode={mode} pool={pools[p.id]}
            heightUsed={heightUsed} heightBudget={R.HEIGHT_BUDGET}
            classUsed={classUsed} classBudget={R.CLASS_BUDGET}
            legal={legal} reason={reason} jump={jump}
            grades={grades} setAttr={setAttr} commit={commit} setClass={setClass} setHeight={setHeight}
            setFirst={setFirst} setLast={setLast} setNumber={setNumber}
            openPicker={() => setPicker(true)} randomize={randomize} resetPlayer={resetPlayer} />
        )}
      </div>

      {picker && <Picker p={p} onClose={() => setPicker(false)}
        onPick={i => patch(pl => ({ ...pl, tone: i.tone, build: i.build, portraitId: i.id }))} />}

      {modeModal && (
        <div className="ov" onClick={() => setModeModal(false)}>
          <div className="mdl" onClick={e => e.stopPropagation()}>
            <div className={'mdl-acc' + (capped ? ' red' : '')} />
            <div className="mdl-b">
              <h3 className="mdl-t">Change build mode?</h3>
              <p className="mdl-s">{capped
                ? <>Switching to <b>Uncapped</b> removes all three budgets and makes this program <b>ineligible for online play</b>. You can switch back while you are still building — once the program is founded, this is permanent.</>
                : <>Switching to <b>Capped</b> re-imposes the attribute, height and class budgets. Any edit that breaks one will have to be resolved before you can found the program.</>}</p>
              <div className="mdl-a">
                <button className="btn org" onClick={() => { setMode(capped ? 'uncapped' : 'capped'); setModeModal(false); }}>
                  Switch to {capped ? 'Uncapped' : 'Capped'}
                </button>
                <button className="btn ghost" onClick={() => setModeModal(false)}>Cancel</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {toast && (
        <div className="toast" onClick={() => setToast(null)}>
          <div className="t">{toast.t}</div><div className="s">{toast.s}</div>
        </div>
      )}
    </div>
    </>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
