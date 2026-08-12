/* GOB Team Builder — Chapter I · Claim.

   Merges the shipped franchise-select-team screen with the overhauled UX:
   - identity comes back to the cards (every program has a face)
   - conference sections carry the real Conference N · Region X · geography
   - filters dim and never remove (§4.2 / shipped §5.3)
   - selection resolves in a sticky bar, never a modal (§4.3)
   - the Team Builder entry says what it does, not what it is called */
const { useState, useMemo, useEffect, useRef } = React;
const L = window.GOBLeague;

const FILTERS = [
  { k: 'talent', label: 'Talent' },
  { k: 'prestige', label: 'Prestige' },
  { k: 'size', label: 'Size' },
  { k: 'experience', label: 'Experience' }
];

function Tier({ label, tier, labels, top }) {
  return (
    <div className={'tr' + (tier === 1 && top ? ' ' + top : '')}>
      <b>{label}</b><span>{labels[tier - 1]}</span>
    </div>
  );
}

function Card({ p, out, selected, onSelect }) {
  return (
    <button className={'pg' + (out ? ' out' : '') + (selected ? ' sel' : '')}
      onClick={() => !out && onSelect(p)} aria-disabled={out}>
      <div className="pg-art">
        <img src={p.art} alt={p.name} loading="lazy" decoding="async"
          onError={e => { if (e.currentTarget.src.indexOf('general_') === -1) e.currentTarget.src = p.artFallback; }} />
      </div>
      <div className="pg-b">
        <div className="pg-nm">{p.name}</div>
        <div className="pg-t">
          <Tier label="Tlnt" tier={p.talent} labels={L.TIERS.talent} top="top1t" />
          <Tier label="Prstg" tier={p.prestige} labels={L.TIERS.prestige} top="top1" />
          <Tier label="Size" tier={p.size} labels={L.TIERS.size} />
          <Tier label="Exp" tier={p.experience} labels={L.TIERS.experience} />
        </div>
      </div>
      {selected && <div className="pg-check">✓</div>}
      <div className="pg-more">
        <div className="r"><b>Talent</b><span>{p.talentRaw.toLocaleString()} pts</span></div>
        <div className="r"><b>Prestige</b><span>{p.prestigeRaw}</span></div>
        <div className="r"><b>Conference</b><span>{p.conf} · Region {p.region}</span></div>
        <div className="rec">last season {p.lastConf} conf · {p.lastOv} overall</div>
      </div>
    </button>
  );
}

function App() {
  const [builder, setBuilder] = useState(false);
  const [q, setQ] = useState('');
  const [f, setF] = useState({ talent: 0, prestige: 0, size: 0, experience: 0, geo: '' });
  const [sel, setSel] = useState(null);
  const [toast, setToast] = useState(null);
  const [zMode, setZMode] = useState(() => localStorage.getItem('tbClaimZoom') || 'fit');
  const [fitZ, setFitZ] = useState(1);
  const barRef = useRef(null);
  const pageRef = useRef(null);

  useEffect(() => {
    const fit = () => setFitZ(Math.min(1, window.innerWidth / 1440));
    fit(); window.addEventListener('resize', fit);
    return () => window.removeEventListener('resize', fit);
  }, []);
  useEffect(() => { localStorage.setItem('tbClaimZoom', zMode); }, [zMode]);
  const z = zMode === 'fit' ? fitZ : Number(zMode);

  /* offsets that cross the scaled/unscaled boundary are derived, never authored */
  useEffect(() => {
    const el = barRef.current, page = pageRef.current;
    if (!el || !page) return;
    const sync = () => {
      const vb = document.querySelector('.vbar');
      const mb = document.querySelector('.mbar');
      const vbh = vb ? vb.getBoundingClientRect().height : 0;
      /* the banner is outside .cl, so its offset lives on :root — and it is
         measured, not authored, because the prototype bar only exists here */
      document.documentElement.style.setProperty('--mbar-top', vbh + 'px');
      const vh = vbh + (mb ? mb.getBoundingClientRect().height : 0);
      page.style.setProperty('--fbar-top', ((vh + 7) / z) + 'px');
      const h = sel ? el.getBoundingClientRect().height : 0;
      document.body.style.paddingBottom = (h ? h + 26 : 26) + 'px';
    };
    sync();
    const ro = new ResizeObserver(sync);
    ro.observe(el);
    window.addEventListener('resize', sync);
    return () => { ro.disconnect(); window.removeEventListener('resize', sync); };
  }, [sel, z, builder]);

  const matches = useMemo(() => {
    const needle = q.trim().toLowerCase();
    const set = {};
    L.PROGRAMS.forEach(p => {
      set[p.id] = FILTERS.every(x => !f[x.k] || p[x.k] === f[x.k])
        && (!f.geo || p.geo.indexOf(f.geo) > -1)
        && (!needle || p.name.toLowerCase().includes(needle)
          || ('conference ' + p.conf).includes(needle)
          || p.geo.join(' ').toLowerCase().includes(needle));
    });
    return set;
  }, [q, f]);

  const count = Object.values(matches).filter(Boolean).length;
  const active = FILTERS.filter(x => f[x.k]).length + (f.geo ? 1 : 0) + (q.trim() ? 1 : 0);
  useEffect(() => { if (sel && !matches[sel.id]) setSel(null); }, [matches, sel]);
  const clear = () => { setF({ talent: 0, prestige: 0, size: 0, experience: 0, geo: '' }); setQ(''); };

  const confs = [];
  for (let c = 1; c <= 16; c++) confs.push(c);

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

      {/* mode banner — the page visibly joins a flow, and says how to leave it */}
      {builder && (
        <div className="mbar">
          <div className="mbar-in">
            <span className="mb-k">Team Builder</span>
            <span className="mb-s">Step 1 of 3</span>
            <div className="mb-t">Choose whose place your program takes. <b>Nothing is committed yet.</b></div>
            <button className="mb-x" onClick={() => { setBuilder(false); setSel(null); }}>Cancel</button>
          </div>
        </div>
      )}

      <div className={'cl' + (builder ? ' building' : '')} ref={pageRef} style={{ zoom: z }}
        data-screen-label={builder ? 'Chapter I — Claim (taking a place)' : 'Program select (128 programs)'}>
        <div className="hd">
          <div className="hd-t">
            <h1>{builder ? 'Whose place are you taking?' : 'Who are you coaching?'}</h1>
            <p>{builder
              ? <>Your program replaces one of these. You inherit <b>its conference, its region and its schedule</b>.</>
              : <>Take over one of the 128 programs below.</>}</p>
          </div>
        </div>

        {/* the entry says what it does — the feature name is the label, not the button */}
        {!builder && (
          <div className="tbe">
            <div className="tbe-t">
              <div className="tbe-h">Or put your own program in the league</div>
              <p>Your school <b>takes an existing program's place</b> — its conference, its region, its schedule.</p>
            </div>
            <div className="tbe-a">
              <button className="btn" onClick={() => setBuilder(true)}>Open Team Builder</button>
            </div>
          </div>
        )}

        <div className="fbar">
          <div className="srch">
            <i></i>
            <input value={q} onChange={e => setQ(e.target.value)} placeholder="Search program, conference or state" />
          </div>
          {FILTERS.map(x => (
            <div className={'fsel' + (f[x.k] ? ' on' : '')} key={x.k}>
              <label>{x.label}</label>
              <select value={f[x.k]} onChange={e => setF({ ...f, [x.k]: +e.target.value })}>
                <option value={0}>Any tier</option>
                {L.TIERS[x.k].map((t, i) => <option key={t} value={i + 1}>{t}</option>)}
              </select>
            </div>
          ))}
          <div className={'fsel' + (f.geo ? ' on' : '')}>
            <label>Geography</label>
            <select value={f.geo} onChange={e => setF({ ...f, geo: e.target.value })}>
              <option value="">Anywhere</option>
              {L.GEOS.map(g => <option key={g} value={g}>{g}</option>)}
            </select>
          </div>
          <div className="fspace" />
          <div className="fcount"><b>{count}</b> of 128 match</div>
          {active > 0 && <button className="fclear" onClick={clear}>Clear {active}</button>}
        </div>

        {confs.map(c => {
          const list = L.PROGRAMS.filter(p => p.conf === c)
            .sort((a, b) => b.talentRaw - a.talentRaw || a.name.localeCompare(b.name));
          const hit = list.filter(p => matches[p.id]).length;
          return (
            <div className="conf" key={c}>
              <div className="conf-k">
                <h2>Conference {c}</h2>
                <span className="cid">Region {list[0].region}</span>
                <span className="cgeo">{L.CONFERENCE_GEOGRAPHY[c].join(' · ')}</span>
                <i />
                <span className="cn">{hit} of 8</span>
              </div>
              <div className="row">
                {list.map(p => (
                  <Card key={p.id} p={p} out={!matches[p.id]}
                    selected={sel && sel.id === p.id} onSelect={setSel} />
                ))}
              </div>
            </div>
          );
        })}
      </div>

      <div className={'abar' + (sel ? ' up' : '')} ref={barRef}>
        {sel && (
          <div className="ab-in">
            <div className="ab-art">
              <img src={sel.art} alt={sel.name} onError={e => { e.currentTarget.src = sel.artFallback; }} />
            </div>
            <div className="ab-t">
              <div className="ab-h">{builder
                ? <>You are taking <em>{sel.name}</em>’s place</>
                : <>{sel.name} <em>{sel.mascot}</em></>}</div>
              <div className="ab-s"><b>Conference {sel.conf} · Region {sel.region}</b> · {L.TIERS.prestige[sel.prestige - 1]} · {L.TIERS.talent[sel.talent - 1]} · last season {sel.lastConf} conf, {sel.lastOv} overall</div>
            </div>
            <div className="ab-f">
              <div><div className="k">Prestige</div><div className="v">{L.TIERS.prestige[sel.prestige - 1]}</div></div>
              <div><div className="k">Talent</div><div className="v">{L.TIERS.talent[sel.talent - 1]}</div></div>
              <div><div className="k">Size</div><div className="v">{L.TIERS.size[sel.size - 1]}</div></div>
              <div><div className="k">Experience</div><div className="v">{L.TIERS.experience[sel.experience - 1]}</div></div>
            </div>
            <button className="btn ghost" onClick={() => setSel(null)}>Clear</button>
            <button className={'btn lg' + (builder ? '' : ' grn')} onClick={() => setToast(builder
              ? { t: 'Next — Identity', s: 'Name your program, color it and design its court. ' + sel.name + '’s place is held until you establish it.' }
              : { t: 'Entering ' + sel.name, s: 'Take the program over exactly as it stands — roster, schedule and standing intact.' })}>
              {builder ? 'Take This Slot' : 'Enter Franchise'}
            </button>
          </div>
        )}
      </div>

      {toast && (
        <div className="toast" onClick={() => setToast(null)}>
          <div className="t">{toast.t}</div><div className="s">{toast.s}</div>
        </div>
      )}
    </>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
